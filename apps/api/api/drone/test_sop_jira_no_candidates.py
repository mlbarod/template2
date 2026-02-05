# =============================================================================
# 모듈: Drone SOP Jira 생성(후보 없음) 테스트
# 주요 대상: run_drone_sop_jira_create_from_env 빠른 종료
# 주요 가정: 후보가 없으면 skipped=True로 반환됩니다.
# =============================================================================
from __future__ import annotations

from django.test import TestCase
from django.test.utils import override_settings

from api.drone import services


class DroneSopJiraNoCandidateTests(TestCase):
    """Jira 생성 대상이 없을 때의 동작을 검증합니다."""

    @override_settings(
        DRONE_JIRA_BASE_URL="http://example.local/jira",
        DRONE_JIRA_USE_BULK_API=True,
    )
    def test_run_returns_skipped_when_no_candidates(self) -> None:
        """후보가 없으면 skipped=True와 skip_reason이 반환되는지 확인합니다."""
        result = services.run_drone_sop_jira_create_from_env()

        self.assertEqual(result.candidates, 0)
        self.assertEqual(result.created, 0)
        self.assertEqual(result.updated_rows, 0)
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "no_candidates")
