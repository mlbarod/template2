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

from django.utils import timezone

from ..models import ExternalAffiliationSnapshot
from .. import selectors
from .access import ensure_self_access


def sync_external_affiliations(
    *,
    records: Iterable[dict[str, object]],
) -> dict[str, int]:
    """외부 예측 소속 스냅샷을 업서트하고 변경 시 재확인 플래그를 세웁니다.

    입력:
    - records: knox_id/user_sdwt_prod/source_updated_at을 포함한 레코드 목록

    반환:
    - dict[str, int]: created/updated/unchanged/flagged 카운트

    부작용:
    - ExternalAffiliationSnapshot 업서트
    - 사용자 requires_affiliation_reconfirm 갱신

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
    # 3) 레코드별 업서트 처리
    # -----------------------------------------------------------------------------
    for record in normalized_records.values():
        knox_id = (record.get("knox_id") or "").strip()
        predicted = (record.get("user_sdwt_prod") or record.get("predicted_user_sdwt_prod") or "").strip()
        source_updated_at = record.get("source_updated_at") or record.get("sourceUpdatedAt") or now
        if not knox_id or not predicted:
            continue
        if isinstance(source_updated_at, datetime) and timezone.is_naive(source_updated_at):
            source_updated_at = timezone.make_aware(source_updated_at, timezone.utc)
        if not isinstance(source_updated_at, datetime):
            source_updated_at = now

        snapshot = existing.get(knox_id)
        if snapshot is None:
            snapshot = ExternalAffiliationSnapshot.objects.create(
                knox_id=knox_id,
                predicted_user_sdwt_prod=predicted,
                source_updated_at=source_updated_at,
                last_seen_at=now,
            )
            created += 1
            existing[knox_id] = snapshot
            continue

        # -----------------------------------------------------------------------------
        # 4) 변경 여부 판단 및 갱신
        # -----------------------------------------------------------------------------
        changed = snapshot.predicted_user_sdwt_prod != predicted
        if changed or snapshot.source_updated_at != source_updated_at:
            snapshot.predicted_user_sdwt_prod = predicted
            snapshot.source_updated_at = source_updated_at
            snapshot.last_seen_at = now
            snapshot.save(update_fields=["predicted_user_sdwt_prod", "source_updated_at", "last_seen_at"])
            updated += 1
        else:
            snapshot.last_seen_at = now
            snapshot.save(update_fields=["last_seen_at"])
            unchanged += 1

        # -----------------------------------------------------------------------------
        # 5) 사용자 재확인 플래그 갱신
        # -----------------------------------------------------------------------------
        if changed:
            user = selectors.get_user_by_knox_id(knox_id=knox_id)
            if user is None:
                continue

            ensure_self_access(user, role="member")

            if selectors.get_pending_user_sdwt_prod_change(user=user) is not None:
                continue

            current_user_sdwt = (getattr(user, "user_sdwt_prod", None) or "").strip()
            if not current_user_sdwt:
                continue

            if current_user_sdwt == (predicted or "").strip():
                continue

            user.requires_affiliation_reconfirm = True
            user.save(update_fields=["requires_affiliation_reconfirm"])
            flagged += 1

    # -----------------------------------------------------------------------------
    # 6) 결과 반환
    # -----------------------------------------------------------------------------
    return {"created": created, "updated": updated, "unchanged": unchanged, "flagged": flagged}
