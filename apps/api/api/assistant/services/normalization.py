# =============================================================================
# 모듈: 어시스턴트 입력/응답 정규화
# 주요 함수: normalize_history, resolve_permission_groups, normalize_segments
# 주요 가정: permission_groups는 접근 가능한 그룹에 한해 허용합니다.
# =============================================================================
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

from api.account import selectors as account_selectors
import api.rag.services as rag_services

from .. import selectors
from .constants import DEFAULT_HISTORY_LIMIT, DEFAULT_ROOM_ID
from .errors import AssistantRequestError
from .parsing import _normalize_string_list


def normalize_history(raw_history: object, *, limit: int = DEFAULT_HISTORY_LIMIT) -> List[Dict[str, str]]:
    """history 배열에서 role/content가 있는 메시지만 정규화합니다.

    인자:
        raw_history: 원본 history 입력(list 기대).
        limit: 최대 메시지 개수(최신 N개 유지).

    반환:
        {"role": str, "content": str} 형태의 메시지 리스트.

    부작용:
        없음. 순수 정규화입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 타입 확인
    # -----------------------------------------------------------------------------
    normalized: List[Dict[str, str]] = []
    if not isinstance(raw_history, list):
        return normalized

    # -----------------------------------------------------------------------------
    # 2) 항목 정규화 및 최신 N개 유지
    # -----------------------------------------------------------------------------
    safe_limit = max(1, limit)
    for entry in raw_history:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        content = entry.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            continue

        role_clean = role.strip()
        content_clean = content.strip()
        if role_clean and content_clean:
            normalized.append({"role": role_clean, "content": content_clean})
    if len(normalized) > safe_limit:
        normalized = normalized[-safe_limit:]

    return normalized


def validate_user_identity(user: object) -> Tuple[str, str]:
    """사용자 객체에서 knox_id를 추출합니다.

    인자:
        user: Django 사용자 객체.

    반환:
        (user_key, user_header_id) 튜플.

    부작용:
        없음. 순수 검증입니다.

    오류:
        knox_id가 없으면 AssistantRequestError를 발생시킵니다.
    """

    # -----------------------------------------------------------------------------
    # 1) knox_id 추출 및 검증
    # -----------------------------------------------------------------------------
    knox_id = getattr(user, "knox_id", None)
    if not isinstance(knox_id, str) or not knox_id.strip():
        raise AssistantRequestError("knox_id가 필요합니다.")

    # -----------------------------------------------------------------------------
    # 2) 정규화된 키 반환
    # -----------------------------------------------------------------------------
    normalized = knox_id.strip()
    return normalized, normalized


def normalize_csv_string(raw: str) -> List[str]:
    """comma-separated 문자열을 리스트로 정규화합니다.

    인자:
        raw: 콤마로 구분된 문자열.

    반환:
        공백 제거 및 중복 제거된 문자열 리스트.

    부작용:
        없음. 순수 정규화입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 빈 입력 처리
    # -----------------------------------------------------------------------------
    if not raw:
        return []
    # -----------------------------------------------------------------------------
    # 2) 분리/정리 후 중복 제거
    # -----------------------------------------------------------------------------
    normalized = [value.strip() for value in raw.split(",") if value.strip()]
    return list(dict.fromkeys(normalized))


def resolve_sender_id(user: object) -> str | None:
    """사용자에서 sender_id(knox_id)를 추출합니다.

    인자:
        user: Django 사용자 객체.

    반환:
        sender_id 문자열 또는 None.

    부작용:
        없음. 순수 조회입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) knox_id 추출 및 정규화
    # -----------------------------------------------------------------------------
    knox_id = getattr(user, "knox_id", None)
    if isinstance(knox_id, str) and knox_id.strip():
        return knox_id.strip()
    return None


def default_permission_groups(user: object) -> List[str]:
    """기본 permission_groups 값을 계산합니다.

    인자:
        user: Django 사용자 객체.

    반환:
        기본 권한 그룹 문자열 리스트.

    부작용:
        없음. 순수 계산입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 소속(user_sdwt_prod) 반영
    # -----------------------------------------------------------------------------
    groups: List[str] = []
    raw_user_sdwt = account_selectors.get_current_user_sdwt_prod(user=user)
    if isinstance(raw_user_sdwt, str) and raw_user_sdwt.strip():
        groups.append(raw_user_sdwt.strip())

    # -----------------------------------------------------------------------------
    # 2) 발신자 ID + 공개 그룹 추가
    # -----------------------------------------------------------------------------
    sender_id = resolve_sender_id(user)
    if sender_id:
        groups.append(sender_id)
    groups.append(rag_services.RAG_PUBLIC_GROUP)
    return list(dict.fromkeys(groups))


def resolve_permission_groups(payload: Dict[str, object], user: object) -> List[str]:
    """요청/사용자 정보로 permission_groups를 결정합니다.

    인자:
        payload: 요청 payload(dict).
        user: Django 사용자 객체.

    반환:
        접근 허용된 permission_groups 문자열 리스트.

    부작용:
        없음. 읽기 전용 검증입니다.

    오류:
        잘못된 타입이면 ValueError, 권한 없으면 AssistantRequestError를 발생시킵니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 파싱(카멜/스네이크 케이스 지원)
    # -----------------------------------------------------------------------------
    raw_groups = payload.get("permission_groups") or payload.get("permissionGroups")
    if raw_groups is not None and not isinstance(raw_groups, list):
        raise ValueError("permission_groups must be an array")

    # -----------------------------------------------------------------------------
    # 2) 기본 그룹 계산
    # -----------------------------------------------------------------------------
    normalized = _normalize_string_list(raw_groups)
    if not normalized:
        normalized = default_permission_groups(user)

    # -----------------------------------------------------------------------------
    # 3) 접근 가능 그룹 검증
    # -----------------------------------------------------------------------------
    accessible = selectors.get_accessible_user_sdwt_prods_for_user(user=user)
    allowed = set(accessible)
    sender_id = resolve_sender_id(user)
    if sender_id:
        allowed.add(sender_id)
    allowed.add(rag_services.RAG_PUBLIC_GROUP)
    invalid = [group for group in normalized if group not in allowed]
    if invalid:
        raise AssistantRequestError("해당 permission_groups에 대한 접근 권한이 없습니다.")

    return normalized


def resolve_rag_index_names(payload: Dict[str, object]) -> List[str]:
    """요청 페이로드로 RAG 인덱스 목록을 결정합니다.

    인자:
        payload: 요청 payload(dict).

    반환:
        유효한 RAG 인덱스 이름 리스트.

    부작용:
        없음. 읽기 전용 검증입니다.

    오류:
        입력 형식이 잘못되면 ValueError를 발생시킵니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 타입 파싱(카멜/스네이크 케이스 지원)
    # -----------------------------------------------------------------------------
    raw_indexes = payload.get("rag_index_name") or payload.get("ragIndexName")
    if raw_indexes is None:
        normalized: List[str] = []
    elif isinstance(raw_indexes, str):
        normalized = normalize_csv_string(raw_indexes)
    elif isinstance(raw_indexes, list):
        normalized = _normalize_string_list(raw_indexes)
    else:
        raise ValueError("rag_index_name must be a comma-separated string or array")

    # -----------------------------------------------------------------------------
    # 2) 기본값 fallback
    # -----------------------------------------------------------------------------
    if not normalized:
        return rag_services.resolve_rag_index_names(None)

    # -----------------------------------------------------------------------------
    # 3) 후보군 검증
    # -----------------------------------------------------------------------------
    candidates = rag_services.get_rag_index_candidates()
    if candidates:
        invalid = [value for value in normalized if value not in candidates]
        if invalid:
            raise ValueError("rag_index_name contains invalid index")

    return normalized


def normalize_room_id(room_id: object) -> str:
    """방 ID를 문자열로 정규화하고 기본값을 적용합니다.

    인자:
        room_id: 원본 room_id 입력.

    반환:
        정규화된 room_id 문자열.

    부작용:
        없음. 순수 정규화입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 문자열 입력 처리 및 허용 문자만 유지
    # -----------------------------------------------------------------------------
    if isinstance(room_id, str):
        cleaned = room_id.strip()
        if cleaned:
            safe = re.sub(r"[^a-zA-Z0-9_-]", "-", cleaned)
            return safe[:64]
    return DEFAULT_ROOM_ID


def append_user_prompt(
    history: List[Dict[str, str]],
    prompt: str,
    *,
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> List[Dict[str, str]]:
    """정규화된 이력에 현재 사용자 메시지를 중복 없이 추가합니다.

    인자:
        history: 기존 이력 목록.
        prompt: 사용자 입력 문자열.
        limit: 최대 보관 메시지 수.

    반환:
        최신 prompt가 반영된 이력 리스트.

    부작용:
        없음. 순수 정규화입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    prompt_clean = prompt.strip()
    normalized_history = normalize_history(history, limit=limit)
    prompt_message = {"role": "user", "content": prompt_clean}

    # -----------------------------------------------------------------------------
    # 2) 마지막 메시지 중복 제거
    # -----------------------------------------------------------------------------
    if normalized_history and normalized_history[-1] == prompt_message:
        return normalized_history[-limit:]

    # -----------------------------------------------------------------------------
    # 3) 신규 메시지 추가 및 길이 제한
    # -----------------------------------------------------------------------------
    normalized_history.append(prompt_message)
    if len(normalized_history) > limit:
        normalized_history = normalized_history[-limit:]

    return normalized_history


def normalize_sources(raw_sources: object) -> List[Dict[str, str]]:
    """RAG 검색 결과에서 프론트에 전달할 출처 리스트를 정규화합니다.

    인자:
        raw_sources: 원본 출처 목록(list 기대).

    반환:
        {"docId","title","snippet"} 형태의 출처 리스트.

    부작용:
        없음. 순수 정규화입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 타입 확인
    # -----------------------------------------------------------------------------
    normalized: List[Dict[str, str]] = []
    seen_doc_ids: set[str] = set()
    if not isinstance(raw_sources, list):
        return normalized

    # -----------------------------------------------------------------------------
    # 2) 출처 항목 정규화(중복 doc_id 제거)
    # -----------------------------------------------------------------------------
    for entry in raw_sources:
        if not isinstance(entry, dict):
            continue
        doc_id = entry.get("doc_id") or entry.get("docId")
        if not isinstance(doc_id, str) or not doc_id.strip():
            continue
        doc_id_clean = doc_id.strip()
        if doc_id_clean in seen_doc_ids:
            continue
        seen_doc_ids.add(doc_id_clean)
        title_raw = entry.get("title")
        title = title_raw.strip() if isinstance(title_raw, str) else ""
        snippet_raw = entry.get("snippet")
        snippet = snippet_raw.strip() if isinstance(snippet_raw, str) else ""
        normalized.append(
            {
                "docId": doc_id_clean,
                "title": title,
                "snippet": snippet,
            }
        )
    return normalized


def normalize_segments(raw_segments: object) -> List[Dict[str, object]]:
    """LLM 응답 segment 목록을 프론트 전달용으로 정규화합니다.

    인자:
        raw_segments: 원본 segments 목록(list 기대).

    반환:
        {"reply": str, "sources": list} 형태의 segments 리스트.

    부작용:
        없음. 순수 정규화입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 타입 확인
    # -----------------------------------------------------------------------------
    normalized: List[Dict[str, object]] = []
    if not isinstance(raw_segments, list):
        return normalized

    # -----------------------------------------------------------------------------
    # 2) segments 정규화
    # -----------------------------------------------------------------------------
    for entry in raw_segments:
        if not isinstance(entry, dict):
            continue

        reply_raw = entry.get("reply") or entry.get("answer") or entry.get("content")
        reply = reply_raw.strip() if isinstance(reply_raw, str) else ""
        if not reply:
            continue

        sources = normalize_sources(entry.get("sources"))
        if not sources:
            continue

        normalized.append({"reply": reply, "sources": sources})

    return normalized


def build_rag_index_list_payload(*, user: object) -> dict[str, object]:
    """현재 사용자 기준 RAG 인덱스/권한 그룹 정보를 반환합니다.

    인자:
        user: Django 사용자 객체.

    반환:
        RAG 인덱스/권한 그룹/현재 사용자 정보를 포함한 dict.

    부작용:
        없음. 읽기 전용 조회입니다.

    오류:
        sender_id가 없으면 AssistantRequestError를 발생시킵니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 접근 가능한 그룹 조회
    # -----------------------------------------------------------------------------
    accessible = selectors.get_accessible_user_sdwt_prods_for_user(user=user)
    current_user_sdwt_prod = account_selectors.get_current_user_sdwt_prod(user=user)
    permission_groups = set(accessible)

    # -----------------------------------------------------------------------------
    # 2) sender_id 검증 및 그룹 확장
    # -----------------------------------------------------------------------------
    sender_id = resolve_sender_id(user)
    if not sender_id:
        raise AssistantRequestError("forbidden")
    permission_groups.add(sender_id)
    permission_groups.add(rag_services.RAG_PUBLIC_GROUP)

    # -----------------------------------------------------------------------------
    # 3) 응답 payload 구성
    # -----------------------------------------------------------------------------
    return {
        "ragIndexes": rag_services.get_rag_index_candidates(),
        "defaultRagIndex": rag_services.resolve_rag_index_name(None),
        "emailRagIndex": rag_services.resolve_rag_index_name(rag_services.RAG_INDEX_EMAILS),
        "permissionGroups": sorted(permission_groups),
        "currentUserSdwtProd": current_user_sdwt_prod,
        "ragPublicGroup": rag_services.RAG_PUBLIC_GROUP,
    }
