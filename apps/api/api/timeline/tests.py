# =============================================================================
# 모듈 설명: timeline 더미 엔드포인트 테스트를 제공합니다.
# - 주요 클래스: TimelineEndpointTests
# - 불변 조건: URL 네임(timeline-*)이 등록되어 있어야 합니다.
# =============================================================================

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse


class TimelineEndpointTests(TestCase):
    def test_timeline_lines_returns_list(self) -> None:
        response = self.client.get(reverse("timeline-lines"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))

    def test_timeline_sdwts_requires_line(self) -> None:
        response = self.client.get(reverse("timeline-sdwts"))
        self.assertEqual(response.status_code, 400)

    def test_timeline_sdwts_returns_results(self) -> None:
        response = self.client.get(reverse("timeline-sdwts"), {"lineId": "LINE-A"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))

    def test_timeline_prc_groups_returns_results(self) -> None:
        response = self.client.get(
            reverse("timeline-prc-groups"),
            {"lineId": "LINE-A", "sdwtId": "SD-10"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))

    def test_timeline_prc_groups_is_case_insensitive(self) -> None:
        response = self.client.get(
            reverse("timeline-prc-groups"),
            {"lineId": "line-a", "sdwtId": "sd-10"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))

    def test_timeline_equipments_returns_results(self) -> None:
        response = self.client.get(
            reverse("timeline-equipments"),
            {"lineId": "LINE-A", "sdwtId": "SD-10", "prcGroup": "ETCH"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))

    def test_timeline_equipments_is_case_insensitive(self) -> None:
        response = self.client.get(
            reverse("timeline-equipments"),
            {"lineId": "line-a", "sdwtId": "sd-10", "prcGroup": "etch"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))

    def test_timeline_equipment_info_returns_result(self) -> None:
        response = self.client.get(reverse("timeline-equipment-info", kwargs={"eqp_id": "EQP-ALPHA"}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "EQP-ALPHA")

    def test_timeline_equipment_info_with_line_scope(self) -> None:
        response = self.client.get(
            reverse("timeline-equipment-info-line", kwargs={"line_id": "LINE-A", "eqp_id": "EQP-ALPHA"})
        )
        self.assertEqual(response.status_code, 200)

    def test_timeline_logs_requires_eqp_id(self) -> None:
        response = self.client.get(reverse("timeline-logs"))
        self.assertEqual(response.status_code, 400)

    def test_timeline_eqp_logs_returns_results(self) -> None:
        response = self.client.get(reverse("timeline-logs-eqp"), {"eqpId": "EQP-ALPHA"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))

    def test_timeline_tip_logs_returns_results(self) -> None:
        response = self.client.get(reverse("timeline-logs-tip"), {"eqpId": "EQP-ALPHA"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))

    def test_timeline_ctttm_logs_returns_results(self) -> None:
        response = self.client.get(reverse("timeline-logs-ctttm"), {"eqpId": "EQP-ALPHA"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))

    def test_timeline_racb_logs_returns_results(self) -> None:
        response = self.client.get(reverse("timeline-logs-racb"), {"eqpId": "EQP-ALPHA"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))

    def test_timeline_jira_logs_returns_results(self) -> None:
        response = self.client.get(reverse("timeline-logs-jira"), {"eqpId": "EQP-ALPHA"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
