# =============================================================================
# 모듈 설명: AppStore 앱 생성/수정/삭제 서비스 로직을 제공합니다.
# - 주요 함수: create_app, update_app, delete_app
# - 불변 조건: 스크린샷 입력은 URL 또는 data URL 형식입니다.
# =============================================================================
from __future__ import annotations

from typing import Any, Dict

from ..selectors import get_app_by_id
from ..models import AppStoreApp
from .screenshots import (
    normalize_screenshot_gallery,
    normalize_screenshot_input,
    split_cover_and_gallery,
)


def create_app(
    *,
    owner: Any,
    name: str,
    category: str,
    description: str,
    url: str,
    manual_url: str | None = None,
    screenshot_urls: list[str] | None = None,
    screenshot_url: str,
    contact_name: str,
    contact_knoxid: str,
) -> AppStoreApp:
    """AppStore 앱을 생성합니다.

    인자:
        owner: 앱 소유자(Django user).
        name: 앱 이름.
        category: 앱 카테고리.
        description: 앱 설명.
        url: 앱 URL.
        manual_url: 메뉴얼 URL(없으면 None).
        screenshot_urls: 스크린샷 목록(대표가 첫 번째). URL 또는 data URL.
        screenshot_url: 스크린샷 URL 또는 data URL.
        contact_name: 담당자 이름.
        contact_knoxid: 담당자 knox id.

    반환:
        생성된 AppStoreApp 인스턴스(댓글 수 포함 재조회 시도).

    부작용:
        AppStoreApp 레코드를 생성합니다.

    오류:
        ORM 저장 과정에서 예외가 발생할 수 있습니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 스크린샷 입력 분리/정규화
    # -----------------------------------------------------------------------------
    cover_input, gallery_inputs = split_cover_and_gallery(screenshot_urls or [])
    if not cover_input:
        cover_input = (screenshot_url or "").strip()

    normalized_url, screenshot_base64, screenshot_mime_type = normalize_screenshot_input(cover_input)
    screenshot_gallery = normalize_screenshot_gallery(gallery_inputs)

    # -----------------------------------------------------------------------------
    # 2) 앱 레코드 생성
    # -----------------------------------------------------------------------------
    app = AppStoreApp.objects.create(
        name=name,
        category=category,
        description=description,
        url=url,
        screenshot_url=normalized_url,
        screenshot_base64=screenshot_base64,
        screenshot_mime_type=screenshot_mime_type,
        screenshot_gallery=screenshot_gallery,
        contact_name=contact_name,
        contact_knoxid=contact_knoxid,
        owner=owner,
        manual_url=manual_url,
    )

    # -----------------------------------------------------------------------------
    # 3) 댓글 수 포함 재조회(없으면 생성된 객체 반환)
    # -----------------------------------------------------------------------------
    return get_app_by_id(app_id=app.pk) or app


def update_app(*, app: AppStoreApp, updates: Dict[str, Any]) -> AppStoreApp:
    """AppStore 앱 정보를 업데이트합니다.

    인자:
        app: 대상 AppStoreApp 인스턴스.
        updates: 업데이트할 필드 dict.

    반환:
        업데이트된 AppStoreApp 인스턴스(댓글 수 포함 재조회 시도).

    부작용:
        AppStoreApp 레코드를 업데이트합니다.

    오류:
        ORM 저장 과정에서 예외가 발생할 수 있습니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 스크린샷 입력 분리
    # -----------------------------------------------------------------------------
    screenshot_input: str | None = None
    screenshot_urls_input: list[str] | None = None
    if "screenshot_url" in updates:
        screenshot_input = str(updates.pop("screenshot_url") or "")
    if "screenshot_urls" in updates:
        raw = updates.pop("screenshot_urls")
        screenshot_urls_input = raw if isinstance(raw, list) else []

    # -----------------------------------------------------------------------------
    # 2) 일반 필드 반영
    # -----------------------------------------------------------------------------
    for field, value in updates.items():
        setattr(app, field, value)

    # -----------------------------------------------------------------------------
    # 3) 스크린샷 필드 반영
    # -----------------------------------------------------------------------------
    if screenshot_urls_input is not None:
        cover_input, gallery_inputs = split_cover_and_gallery(screenshot_urls_input)
        normalized_url, screenshot_base64, screenshot_mime_type = normalize_screenshot_input(cover_input)
        app.screenshot_url = normalized_url
        app.screenshot_base64 = screenshot_base64
        app.screenshot_mime_type = screenshot_mime_type
        app.screenshot_gallery = normalize_screenshot_gallery(gallery_inputs)
    elif screenshot_input is not None:
        normalized_url, screenshot_base64, screenshot_mime_type = normalize_screenshot_input(screenshot_input)
        app.screenshot_url = normalized_url
        app.screenshot_base64 = screenshot_base64
        app.screenshot_mime_type = screenshot_mime_type
        if not (normalized_url or screenshot_base64):
            app.screenshot_gallery = []

    # -----------------------------------------------------------------------------
    # 4) 저장 및 재조회
    # -----------------------------------------------------------------------------
    app.save()
    return get_app_by_id(app_id=app.pk) or app


def delete_app(*, app: AppStoreApp) -> None:
    """AppStore 앱을 삭제합니다.

    인자:
        app: 대상 AppStoreApp 인스턴스.

    반환:
        없음.

    부작용:
        AppStoreApp 레코드를 삭제합니다.

    오류:
        ORM 삭제 과정에서 예외가 발생할 수 있습니다.
    """

    app.delete()
