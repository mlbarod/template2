# common/services/request_helpers.py
"""Django 웹 요청/응답 관련 헬퍼 함수 모음."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme


def parse_json_body(request: HttpRequest) -> Optional[Dict[str, Any]]:
    """요청 바디(JSON)를 파싱해 딕셔너리로 반환합니다."""
    try:
        body = request.body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_json_body_or_error_when_present(
    request: HttpRequest,
) -> tuple[Dict[str, Any], JsonResponse | None]:
    """요청 바디가 있을 때만 JSON 파싱을 시도하고 실패 시 에러를 반환합니다.

    인자:
        request: Django HttpRequest 객체.

    반환:
        (payload, error_response) 형태의 튜플.
        - 바디 없음: ({}, None)
        - 성공: (payload, None)
        - 실패: ({}, JsonResponse)

    부작용:
        없음. 순수 파싱입니다.
    """

    if not request.body:
        return {}, None
    payload = parse_json_body(request)
    if payload is None:
        return {}, JsonResponse({"error": "Invalid JSON body"}, status=400)
    return payload, None


def extract_first_error_message(detail: Any, default: str = "Invalid request") -> str:
    """중첩된 DRF/Django 오류 구조에서 첫 번째 사용자 메시지를 추출합니다.

    인자:
        detail: serializer.errors 같은 dict/list/문자열 기반 오류 구조.
        default: 추출 가능한 메시지가 없을 때 사용할 기본 문자열.

    반환:
        사용자에게 바로 보여줄 수 있는 첫 번째 오류 메시지 문자열.

    부작용:
        없음. 순수 변환 함수입니다.
    """

    if isinstance(detail, dict):
        for value in detail.values():
            message = extract_first_error_message(value, default="")
            if message:
                return message
        return default

    if isinstance(detail, (list, tuple)):
        for item in detail:
            message = extract_first_error_message(item, default="")
            if message:
                return message
        return default

    if detail is None:
        return default

    message = str(detail).strip()
    return message or default


def extract_bearer_token(request: HttpRequest) -> str:
    """Authorization 헤더에서 토큰 문자열을 추출합니다."""
    auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION") or ""
    if not isinstance(auth_header, str):
        return ""
    normalized = auth_header.strip()
    if normalized.lower().startswith("bearer "):
        return normalized[7:].strip()
    return normalized


def ensure_airflow_token(request: HttpRequest, *, require_bearer: bool = False) -> JsonResponse | None:
    """AIRFLOW_TRIGGER_TOKEN을 검증하고 실패 시 JsonResponse를 반환합니다."""
    expected = (
        getattr(settings, "AIRFLOW_TRIGGER_TOKEN", "") or os.getenv("AIRFLOW_TRIGGER_TOKEN") or ""
    ).strip()
    if not expected:
        return JsonResponse({"error": "AIRFLOW_TRIGGER_TOKEN not configured"}, status=500)

    if require_bearer:
        auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION") or ""
        if isinstance(auth_header, str) and auth_header.strip().lower().startswith("bearer "):
            provided = auth_header.strip()[7:].strip()
        else:
            provided = ""
    else:
        provided = extract_bearer_token(request)

    if provided != expected:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    return None


def resolve_frontend_target(
    next_value: Optional[str], *, request: Optional[HttpRequest] = None
) -> str:
    """프론트엔드 베이스 URL과 next 값을 조합해 안전한 리다이렉트를 생성합니다."""
    base = str(getattr(settings, "FRONTEND_BASE_URL", "") or "").strip()
    if not base and request is not None:
        base = request.build_absolute_uri("/").rstrip("/")
    if not base:
        base = "http://localhost"

    base = base.rstrip("/")
    parsed_base = urlparse(base if "://" in base else f"http://{base.lstrip('/')}")
    allowed_hosts = {parsed_base.netloc} if parsed_base.netloc else set()

    if next_value:
        candidate = str(next_value).strip()
        if candidate:
            if url_has_allowed_host_and_scheme(
                candidate, allowed_hosts=allowed_hosts, require_https=False
            ):
                return candidate
            if candidate.startswith("/"):
                trimmed = candidate.lstrip("/")
                return f"{base}/{trimmed}" if trimmed else base
            if "://" not in candidate:
                trimmed = candidate.lstrip("/")
                return f"{base}/{trimmed}" if trimmed else base
    return base

__all__ = [
    "extract_first_error_message",
    "parse_json_body",
    "parse_json_body_or_error_when_present",
    "extract_bearer_token",
    "ensure_airflow_token",
    "resolve_frontend_target",
]
