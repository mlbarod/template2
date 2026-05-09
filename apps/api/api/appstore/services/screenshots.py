# =============================================================================
# 모듈 설명: AppStore 스크린샷 정규화/커버 이미지 해석 유틸을 제공합니다.
# - 주요 함수: normalize_screenshot_input, split_cover_and_gallery, resolve_cover_image
# - 불변 조건: data URL 형식은 data:<mime>;base64,<data> 입니다.
# =============================================================================
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class CoverImageResult:
    """커버 이미지 조회 결과를 HTTP 응답과 분리해 표현합니다."""

    redirect_url: str = ""
    binary: bytes | None = None
    content_type: str = "image/png"
    status_code: int = 404

    @property
    def is_redirect(self) -> bool:
        """외부 URL redirect 응답인지 확인합니다."""

        return bool(self.redirect_url)

    @property
    def has_binary(self) -> bool:
        """바이너리 이미지 응답이 가능한지 확인합니다."""

        return self.binary is not None


def normalize_screenshot_input(value: str) -> tuple[str, str, str]:
    """스크린샷 입력을 (url, base64, mime_type)로 정규화합니다.

    인자:
        value: 스크린샷 입력 문자열.

    반환:
        (url, base64, mime_type) 튜플.

    부작용:
        없음. 읽기 전용 정규화입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 기본 정리
    # -----------------------------------------------------------------------------
    raw = (value or "").strip()
    if not raw:
        return "", "", ""

    # -----------------------------------------------------------------------------
    # 2) data URL 여부 판별
    # -----------------------------------------------------------------------------
    if not raw.startswith("data:"):
        return raw, "", ""

    if "," not in raw:
        return raw, "", ""

    # -----------------------------------------------------------------------------
    # 3) data URL 파싱
    # -----------------------------------------------------------------------------
    meta, data = raw.split(",", 1)
    meta = meta[5:]  # "data:" 접두어 제거
    parts = [part.strip() for part in meta.split(";")]
    if not any(part.lower() == "base64" for part in parts):
        return raw, "", ""

    mime_type = parts[0] if parts else ""
    return "", data, mime_type


def sanitize_screenshot_urls(values: Iterable[Any] | None) -> list[str]:
    """스크린샷 입력을 문자열 배열로 정규화합니다.

    인자:
        values: 스크린샷 입력 리스트.

    반환:
        공백 제거된 문자열 리스트.

    부작용:
        없음. 읽기 전용 정규화입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 유효성 확인
    # -----------------------------------------------------------------------------
    if not isinstance(values, list):
        return []

    # -----------------------------------------------------------------------------
    # 2) 문자열만 정리
    # -----------------------------------------------------------------------------
    cleaned: list[str] = []
    for raw in values:
        if not isinstance(raw, str):
            continue
        value = raw.strip()
        if not value:
            continue
        cleaned.append(value)
    return cleaned


def normalize_screenshot_gallery(values: list[str]) -> list[dict[str, str]]:
    """갤러리(추가 스크린샷) 입력을 저장 형태로 정규화합니다.

    인자:
        values: 스크린샷 입력 리스트.

    반환:
        DB 저장용 갤러리 dict 리스트.

    부작용:
        없음. 읽기 전용 정규화입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력별 URL/base64 분리
    # -----------------------------------------------------------------------------
    normalized: list[dict[str, str]] = []
    for value in values:
        url, base64_value, mime_type = normalize_screenshot_input(value)
        if not url and not base64_value:
            continue
        normalized.append(
            {
                "url": url,
                "base64": base64_value,
                "mime_type": mime_type,
            }
        )
    return normalized


def split_cover_and_gallery(screenshot_urls: list[str]) -> tuple[str, list[str]]:
    """대표 이미지(첫번째)와 갤러리(나머지)로 분리합니다.

    인자:
        screenshot_urls: 스크린샷 URL 목록.

    반환:
        (대표 이미지, 갤러리 목록) 튜플.

    부작용:
        없음. 읽기 전용 정규화입니다.

    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 문자열 목록 정리
    # -----------------------------------------------------------------------------
    cleaned = sanitize_screenshot_urls(screenshot_urls)
    if not cleaned:
        return "", []
    # -----------------------------------------------------------------------------
    # 2) 대표/갤러리 분리
    # -----------------------------------------------------------------------------
    return cleaned[0], cleaned[1:]


def apply_cover_index(screenshot_urls: list[str], cover_index: Any) -> list[str]:
    """cover_index를 반영해 대표 이미지를 0번으로 이동합니다.

    인자:
        screenshot_urls: 스크린샷 URL 목록(대표 포함).
        cover_index: 대표 이미지 인덱스 입력값.

    반환:
        대표 이미지가 0번에 위치하도록 정렬된 목록.

    부작용:
        없음. 읽기 전용 정렬입니다.

    오류:
        없음.
    """

    if not screenshot_urls:
        return []

    try:
        index = int(cover_index)
    except (TypeError, ValueError):
        return screenshot_urls

    if index < 0 or index >= len(screenshot_urls):
        return screenshot_urls

    if index == 0:
        return screenshot_urls

    cover = screenshot_urls[index]
    remaining = [item for i, item in enumerate(screenshot_urls) if i != index]
    return [cover, *remaining]


def resolve_cover_image(app: Any) -> CoverImageResult:
    """앱 대표 이미지를 redirect 또는 바이너리 결과로 해석합니다.

    인자:
        app: AppStoreApp 인스턴스.

    반환:
        CoverImageResult 값 객체.

    부작용:
        없음. base64 문자열 디코딩만 수행합니다.

    오류:
        없음. 잘못된 base64는 status_code=400으로 표현합니다.
    """

    redirect_url = getattr(app, "screenshot_url", "") or ""
    if redirect_url:
        return CoverImageResult(redirect_url=redirect_url, status_code=302)

    base64_value = getattr(app, "screenshot_base64", "") or ""
    if not base64_value:
        return CoverImageResult(status_code=404)

    try:
        binary = base64.b64decode(base64_value, validate=True)
    except (binascii.Error, ValueError):
        return CoverImageResult(status_code=400)

    content_type = getattr(app, "screenshot_mime_type", "") or "image/png"
    return CoverImageResult(binary=binary, content_type=content_type, status_code=200)


__all__ = [
    "CoverImageResult",
    "apply_cover_index",
    "normalize_screenshot_gallery",
    "normalize_screenshot_input",
    "resolve_cover_image",
    "sanitize_screenshot_urls",
    "split_cover_and_gallery",
]
