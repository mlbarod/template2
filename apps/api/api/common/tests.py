# =============================================================================
# 모듈 설명: common 서비스 유틸 테스트를 제공합니다.
# - 주요 대상: sanitize_identifier
# - 불변 조건: DB 접근 없이 순수 함수 동작만 검증합니다.
# =============================================================================

from __future__ import annotations

from django.test import SimpleTestCase

from api.common.services import build_line_filters, LINE_SDWT_TABLE_NAME, sanitize_identifier


class CommonNormalizationTests(SimpleTestCase):
    """공용 정규화 유틸 동작을 검증합니다."""

    def test_sanitize_identifier_returns_value_when_valid(self) -> None:
        """유효한 식별자는 그대로 반환되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 정상 입력 검증
        # -----------------------------------------------------------------------------
        result = sanitize_identifier(" table_1 ")

        self.assertEqual(result, "table_1")

    def test_sanitize_identifier_uses_fallback_when_value_invalid(self) -> None:
        """유효하지 않은 값은 fallback으로 대체되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) 기본값 fallback 적용
        # -----------------------------------------------------------------------------
        result = sanitize_identifier("table-name", "fallback_table")

        self.assertEqual(result, "fallback_table")

    def test_sanitize_identifier_rejects_invalid_fallback(self) -> None:
        """fallback도 유효하지 않으면 None을 반환하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) fallback 검증 실패 처리
        # -----------------------------------------------------------------------------
        result = sanitize_identifier(None, "bad-name")

        self.assertIsNone(result)

    def test_sanitize_identifier_trims_fallback(self) -> None:
        """fallback 공백이 제거되어 반환되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) fallback 공백 제거 확인
        # -----------------------------------------------------------------------------
        result = sanitize_identifier(123, "  ok_table ")

        self.assertEqual(result, "ok_table")


class CommonDbUtilsTests(SimpleTestCase):
    """공용 DB 유틸 필터 규칙을 검증합니다."""

    def test_build_line_filters_returns_empty_when_line_missing(self) -> None:
        """lineId가 없으면 필터가 비어있는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) lineId 미지정 시 필터 없음
        # -----------------------------------------------------------------------------
        result = build_line_filters(["sdwt_prod", "line_id"], None)

        self.assertEqual(result["filters"], [])
        self.assertEqual(result["params"], [])

    def test_build_line_filters_prefers_sdwt_prod(self) -> None:
        """sdwt_prod가 있으면 sdwt_prod 기준 필터를 사용하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) sdwt_prod 우선 규칙 확인
        # -----------------------------------------------------------------------------
        result = build_line_filters(["user_sdwt_prod", "sdwt_prod", "line_id"], "L1")

        expected = (
            "sdwt_prod IN ("
            f"SELECT user_sdwt_prod FROM {LINE_SDWT_TABLE_NAME} "
            "WHERE line = %s "
            "AND user_sdwt_prod IS NOT NULL "
            "AND user_sdwt_prod <> ''"
            ")"
        )
        self.assertEqual(result["filters"], [expected])
        self.assertEqual(result["params"], ["L1"])

    def test_build_line_filters_uses_user_sdwt_prod_when_sdwt_missing(self) -> None:
        """sdwt_prod가 없으면 user_sdwt_prod 기준 필터를 사용하는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) user_sdwt_prod fallback 확인
        # -----------------------------------------------------------------------------
        result = build_line_filters(["user_sdwt_prod", "line_id"], "L1")

        expected = (
            "user_sdwt_prod IN ("
            f"SELECT user_sdwt_prod FROM {LINE_SDWT_TABLE_NAME} "
            "WHERE line = %s "
            "AND user_sdwt_prod IS NOT NULL "
            "AND user_sdwt_prod <> ''"
            ")"
        )
        self.assertEqual(result["filters"], [expected])
        self.assertEqual(result["params"], ["L1"])

    def test_build_line_filters_falls_back_to_line_id(self) -> None:
        """sdwt_prod가 없으면 line_id 직접 비교로 fallback 되는지 확인합니다."""
        # -----------------------------------------------------------------------------
        # 1) line_id fallback 확인
        # -----------------------------------------------------------------------------
        result = build_line_filters(["line_id", "created_at"], "L1")

        self.assertEqual(result["filters"], ["line_id = %s"])
        self.assertEqual(result["params"], ["L1"])
