# =============================================================================
# 모듈 설명: 외부 예측 소속 스냅샷 동기화 서비스를 제공합니다.
# - 주요 대상: sync_external_affiliations
# - 불변 조건: knox_id는 외부 예측 소속의 고유 키로 사용합니다.
# =============================================================================

"""외부 예측 소속 스냅샷 동기화 서비스 모음.

- 주요 대상: sync_external_affiliations
- 주요 엔드포인트/클래스: 없음(서비스 함수 제공)
- 가정/불변 조건: knox_id는 외부 예측 소속의 고유 키로 사용됨
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from ..models import ExternalAffiliationSnapshot, UserCurrentAffiliation
from .. import selectors
from .utils import _same_user_sdwt_prod


def sync_external_affiliations(
    *,
    records: Iterable[dict[str, object]],
) -> dict[str, int]:
    """외부 예측 소속 스냅샷을 업서트하고 변경 시 재확인 플래그를 세웁니다.

    입력:
    - records: knox_id/department/user_sdwt_prod/source_updated_at을 포함한 레코드 목록

    반환:
    - dict[str, int]: created/updated/unchanged/flagged 카운트

    부작용:
    - ExternalAffiliationSnapshot 업서트
    - 현재 앱 소속의 requires_reconfirm 갱신

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 카운터 및 입력 정규화
    # -----------------------------------------------------------------------------
    now = timezone.now()
    created = 0
    updated = 0
    unchanged = 0
    flagged = 0

    record_list = [record for record in records if isinstance(record, dict)]
    predicted_by_knox: dict[str, str] = {}
    to_create: list[ExternalAffiliationSnapshot] = []
    to_update: list[ExternalAffiliationSnapshot] = []
    changed_knox_ids: list[str] = []
    processed_existing_ids: list[str] = []
    bulk_batch_size = 5000
    # 동일 knox_id 중복 입력으로 인한 고유 제약 충돌을 피하려고 마지막 레코드로 정규화합니다.
    normalized_records: dict[str, dict[str, object]] = {}
    for record in record_list:
        knox_id = record.get("knox_id")
        if isinstance(knox_id, str) and knox_id.strip():
            normalized_records[knox_id.strip()] = record

    # -----------------------------------------------------------------------------
    # 2) 기존 스냅샷 조회
    # -----------------------------------------------------------------------------
    knox_ids = list(normalized_records.keys())
    existing = selectors.get_external_affiliation_snapshots_by_knox_ids(knox_ids=knox_ids)

    # -----------------------------------------------------------------------------
    # 3) 레코드별 변경/생성 목록 준비
    # -----------------------------------------------------------------------------
    for record in normalized_records.values():
        knox_id = (record.get("knox_id") or "").strip()
        department = (record.get("department") or "").strip()
        predicted = (record.get("user_sdwt_prod") or record.get("predicted_user_sdwt_prod") or "").strip()
        source_updated_at = record.get("source_updated_at") or record.get("sourceUpdatedAt") or now
        if not knox_id or not predicted or not department:
            continue
        if isinstance(source_updated_at, datetime) and timezone.is_naive(source_updated_at):
            source_updated_at = timezone.make_aware(source_updated_at, timezone.utc)
        if not isinstance(source_updated_at, datetime):
            source_updated_at = now

        predicted_by_knox[knox_id] = predicted

        snapshot = existing.get(knox_id)
        if snapshot is None:
            snapshot = ExternalAffiliationSnapshot(
                knox_id=knox_id,
                department=department,
                predicted_user_sdwt_prod=predicted,
                source_updated_at=source_updated_at,
                last_seen_at=now,
            )
            to_create.append(snapshot)
            created += 1
            continue

        processed_existing_ids.append(knox_id)

        # -----------------------------------------------------------------------------
        # 4) 변경 여부 판단
        # -----------------------------------------------------------------------------
        changed = not _same_user_sdwt_prod(snapshot.predicted_user_sdwt_prod, predicted)
        changed_department = (snapshot.department or "").strip() != department
        changed_source = snapshot.source_updated_at != source_updated_at
        if changed or changed_department or changed_source:
            snapshot.department = department
            snapshot.predicted_user_sdwt_prod = predicted
            snapshot.source_updated_at = source_updated_at
            to_update.append(snapshot)
            updated += 1
            if changed:
                changed_knox_ids.append(knox_id)
        else:
            unchanged += 1

    # -----------------------------------------------------------------------------
    # 5) 스냅샷 생성/갱신(벌크)
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        if to_create:
            ExternalAffiliationSnapshot.objects.bulk_create(to_create, batch_size=bulk_batch_size)
        if to_update:
            ExternalAffiliationSnapshot.objects.bulk_update(
                to_update,
                ["department", "predicted_user_sdwt_prod", "source_updated_at"],
                batch_size=bulk_batch_size,
            )
        if processed_existing_ids:
            ExternalAffiliationSnapshot.objects.filter(knox_id__in=processed_existing_ids).update(last_seen_at=now)

    # -----------------------------------------------------------------------------
    # 6) 사용자 재확인 플래그 갱신
    # -----------------------------------------------------------------------------
    if changed_knox_ids:
        users_by_knox = selectors.get_users_by_knox_ids(knox_ids=changed_knox_ids)
        user_ids = [user.id for user in users_by_knox.values() if user]
        pending_user_ids = selectors.get_pending_user_sdwt_prod_changes_by_user_ids(user_ids=user_ids)
        flagged_affiliations = []

        for knox_id in changed_knox_ids:
            user = users_by_knox.get(knox_id)
            if user is None:
                continue

            if user.id in pending_user_ids:
                continue

            current_affiliation = selectors.get_current_affiliation_record(user=user)
            if current_affiliation is None:
                continue

            current_user_sdwt = (
                current_affiliation.affiliation.user_sdwt_prod
                if current_affiliation.affiliation_id
                else ""
            ).strip()
            if not current_user_sdwt:
                continue

            predicted = (predicted_by_knox.get(knox_id) or "").strip()
            if not predicted or _same_user_sdwt_prod(current_user_sdwt, predicted):
                continue

            current_affiliation.requires_reconfirm = True
            flagged_affiliations.append(current_affiliation)

        if flagged_affiliations:
            UserCurrentAffiliation.objects.bulk_update(
                flagged_affiliations,
                ["requires_reconfirm"],
                batch_size=bulk_batch_size,
            )
            flagged = len(flagged_affiliations)

    # -----------------------------------------------------------------------------
    # 7) 결과 반환
    # -----------------------------------------------------------------------------
    return {"created": created, "updated": updated, "unchanged": unchanged, "flagged": flagged}
