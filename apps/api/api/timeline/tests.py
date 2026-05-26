# =============================================================================
# 모듈 설명: timeline 엔드포인트 테스트를 제공합니다.
# - 주요 클래스: TimelineEndpointTests
# - 불변 조건: URL 네임(timeline-*)이 등록되어 있어야 합니다.
# =============================================================================

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from . import selectors

TIMELINE_VIEW_SELECTORS = "api.timeline.views.selectors"
TIMELINE_SELECTORS = "api.timeline.selectors"


class TimelineEndpointTests(TestCase):
    def assert_log_selector_called(
        self,
        selector,
        *,
        log_key: str,
        start_at: str | None = None,
        end_at: str | None = None,
        limit: int | None = None,
    ) -> None:
        selector.assert_called_once_with(
            eqp_id="EQP-ALPHA",
            log_key=log_key,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        )

    def test_timeline_lines_returns_list(self) -> None:
        with patch(f"{TIMELINE_VIEW_SELECTORS}.list_lines", return_value=[]) as selector:
            response = self.client.get(reverse("timeline-lines"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with()

    def test_timeline_sdwts_requires_line(self) -> None:
        response = self.client.get(reverse("timeline-sdwts"))
        self.assertEqual(response.status_code, 400)

    def test_timeline_sdwts_returns_results(self) -> None:
        with patch(
            f"{TIMELINE_VIEW_SELECTORS}.list_sdwt_for_line",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("timeline-sdwts"),
                {"lineId": "LINE-A"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(line_id="LINE-A")

    def test_timeline_sdwt_selector_uses_case_insensitive_line_filter(self) -> None:
        with patch(f"{TIMELINE_SELECTORS}._fetch_all", return_value=[]) as fetch_all:
            sdwts = selectors.list_sdwt_for_line(line_id="line-a")

        query, params = fetch_all.call_args.args
        self.assertEqual(sdwts, [])
        self.assertIn("upper(line_id) = %s", query)
        self.assertEqual(params, ["LINE-A"])

    def test_timeline_prc_groups_returns_results(self) -> None:
        with patch(
            f"{TIMELINE_VIEW_SELECTORS}.list_prc_groups",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("timeline-prc-groups"),
                {"lineId": "LINE-A", "sdwtId": "SD-10"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(line_id="LINE-A", sdwt_id="SD-10")

    def test_timeline_prc_groups_is_case_insensitive(self) -> None:
        with patch(
            f"{TIMELINE_VIEW_SELECTORS}.list_prc_groups",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("timeline-prc-groups"),
                {"lineId": "line-a", "sdwtId": "sd-10"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(line_id="LINE-A", sdwt_id="SD-10")

    def test_timeline_equipments_returns_results(self) -> None:
        with patch(
            f"{TIMELINE_VIEW_SELECTORS}.list_equipments",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("timeline-equipments"),
                {"lineId": "LINE-A", "sdwtId": "SD-10", "prcGroup": "ETCH"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(
            line_id="LINE-A",
            sdwt_id="SD-10",
            prc_group="ETCH",
        )

    def test_timeline_equipments_is_case_insensitive(self) -> None:
        with patch(
            f"{TIMELINE_VIEW_SELECTORS}.list_equipments",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("timeline-equipments"),
                {"lineId": "line-a", "sdwtId": "sd-10", "prcGroup": "etch"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(
            line_id="LINE-A",
            sdwt_id="SD-10",
            prc_group="ETCH",
        )

    def test_timeline_equipment_info_returns_result(self) -> None:
        payload = {
            "id": "EQP-ALPHA",
            "lineId": "LINE-A",
            "sdwtId": "SD-10",
            "prcGroup": "ETCH",
        }
        with patch(
            f"{TIMELINE_VIEW_SELECTORS}.get_equipment_info",
            return_value=payload,
        ):
            response = self.client.get(
                reverse("timeline-equipment-info", kwargs={"eqp_id": "EQP-ALPHA"})
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "EQP-ALPHA")

    def test_timeline_equipment_info_with_line_scope(self) -> None:
        payload = {
            "id": "EQP-ALPHA",
            "lineId": "LINE-A",
            "sdwtId": "SD-10",
            "prcGroup": "ETCH",
        }
        with patch(
            f"{TIMELINE_VIEW_SELECTORS}.get_equipment_info",
            return_value=payload,
        ):
            response = self.client.get(
                reverse(
                    "timeline-equipment-info-line",
                    kwargs={"line_id": "LINE-A", "eqp_id": "EQP-ALPHA"},
                )
            )

        self.assertEqual(response.status_code, 200)

    def test_timeline_equipment_info_selector_uses_case_insensitive_eqp_filter(self) -> None:
        with patch(
            f"{TIMELINE_SELECTORS}._fetch_one",
            return_value={
                "id": "EQP-ALPHA",
                "line_id": "LINE-A",
                "sdwt_prod": "SD-10",
                "prc_group": "ETCH",
            },
        ) as fetch_one:
            info = selectors.get_equipment_info(eqp_id="eqp-alpha")

        query, params = fetch_one.call_args.args
        self.assertEqual(info["id"], "EQP-ALPHA")
        self.assertIn("upper(eqp_cb) = %s", query)
        self.assertEqual(params, ["EQP-ALPHA"])

    def test_timeline_logs_requires_eqp_id(self) -> None:
        response = self.client.get(reverse("timeline-logs"))
        self.assertEqual(response.status_code, 400)

    def test_timeline_eqp_logs_returns_results(self) -> None:
        with patch(
            f"{TIMELINE_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("timeline-logs-eqp"),
                {"eqpId": "EQP-ALPHA"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        self.assert_log_selector_called(selector, log_key="eqp")

    def test_timeline_logs_passes_range_and_clamped_limit(self) -> None:
        with patch(
            f"{TIMELINE_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("timeline-logs-eqp"),
                {
                    "eqpId": "EQP-ALPHA",
                    "from": "2026-01-01",
                    "to": "2026-01-02",
                    "limit": str(selectors.MAX_LOG_LIMIT + 1),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assert_log_selector_called(
            selector,
            log_key="eqp",
            start_at="2026-01-01T00:00:00",
            end_at="2026-01-02T23:59:59.999999",
            limit=selectors.MAX_LOG_LIMIT,
        )

    def test_timeline_logs_default_uses_no_row_limit(self) -> None:
        with patch(
            f"{TIMELINE_SELECTORS}._period_date",
            return_value="2026-01-01",
        ) as period_date:
            with patch(f"{TIMELINE_SELECTORS}._fetch_all", return_value=[]) as fetch_all:
                logs = selectors.get_logs_by_type(
                    eqp_id="EQP-ALPHA",
                    log_key="eqp",
                )

        query, params = fetch_all.call_args.args
        self.assertEqual(logs, [])
        self.assertEqual(selectors.DEFAULT_LOG_QUERY_DAYS, 60)
        period_date.assert_called_once_with()
        self.assertNotIn("limit %s", query.lower())
        self.assertEqual(params, ["2026-01-01", "EQP-ALPHA"])

    def test_timeline_eqp_selector_uses_stable_id_expression(self) -> None:
        with patch(
            f"{TIMELINE_SELECTORS}._fetch_all",
            return_value=[
                {
                    "id": "EQP-EQP-ALPHA-20260101000000000000-STATE-USER-abc",
                    "eqp_cb": "EQP-ALPHA",
                    "log_type": "EQP",
                    "event_type": "STATE",
                    "event_time": "2026-01-01T00:00:00",
                    "operator": "USER",
                    "comment": "EQP comment",
                }
            ],
        ) as fetch_all:
            logs = selectors.get_logs_by_type(
                eqp_id="EQP-ALPHA",
                log_key="eqp",
                start_at="2026-01-01T00:00:00",
                limit=20,
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(logs[0]["id"], "EQP-EQP-ALPHA-20260101000000000000-STATE-USER-abc")
        self.assertIn("concat_ws", query)
        self.assertIn("upper(eqp_cb) = %s", query)
        self.assertNotIn("row_number()", query)
        self.assertEqual(params, ["2026-01-01T00:00:00", "EQP-ALPHA", 20])

    def test_timeline_tip_selector_uses_stable_id_expression(self) -> None:
        with patch(
            f"{TIMELINE_SELECTORS}._fetch_all",
            return_value=[
                {
                    "id": "TIP-EQP-ALPHA-20260101000000000000-CREATE-P-S-PPID-abc",
                    "eqp_cb": "EQP-ALPHA",
                    "log_type": "TIP",
                    "event_type": "CREATE",
                    "event_time": "2026-01-01T00:00:00",
                    "operator": "USER",
                    "comment": "TIP comment",
                    "line_id": "LINE-A",
                    "process": "P",
                    "step": "S",
                    "ppid": "PPID",
                }
            ],
        ) as fetch_all:
            logs = selectors.get_logs_by_type(
                eqp_id="EQP-ALPHA",
                log_key="tip",
                start_at="2026-01-01T00:00:00",
                limit=20,
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(logs[0]["id"], "TIP-EQP-ALPHA-20260101000000000000-CREATE-P-S-PPID-abc")
        self.assertIn("concat_ws", query)
        self.assertIn("upper(eqp_cb) = %s", query)
        self.assertNotIn("row_number()", query)
        self.assertEqual(params, ["2026-01-01T00:00:00", "EQP-ALPHA", 20])

    def test_timeline_logs_rejects_invalid_limit(self) -> None:
        with patch(
            f"{TIMELINE_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("timeline-logs-eqp"),
                {"eqpId": "EQP-ALPHA", "limit": "bad"},
            )

        self.assertEqual(response.status_code, 400)
        selector.assert_not_called()

    def test_timeline_logs_rejects_reversed_range(self) -> None:
        with patch(
            f"{TIMELINE_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("timeline-logs-eqp"),
                {
                    "eqpId": "EQP-ALPHA",
                    "from": "2026-01-03",
                    "to": "2026-01-02",
                },
            )

        self.assertEqual(response.status_code, 400)
        selector.assert_not_called()

    def test_timeline_tip_logs_returns_results(self) -> None:
        with patch(
            f"{TIMELINE_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("timeline-logs-tip"),
                {"eqpId": "EQP-ALPHA"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        self.assert_log_selector_called(selector, log_key="tip")

    def test_timeline_ctttm_logs_returns_results(self) -> None:
        with patch(
            f"{TIMELINE_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("timeline-logs-ctttm"),
                {"eqpId": "EQP-ALPHA"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        self.assert_log_selector_called(selector, log_key="ctttm")

    def test_timeline_racb_logs_returns_results(self) -> None:
        with patch(
            f"{TIMELINE_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("timeline-logs-racb"),
                {"eqpId": "EQP-ALPHA"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        self.assert_log_selector_called(selector, log_key="racb")

    def test_timeline_racb_selector_maps_eqp_id(self) -> None:
        with patch(
            f"{TIMELINE_SELECTORS}._fetch_all",
            return_value=[
                {
                    "id": "LINE-A-EQP-ALPHA-2026-01-01-ALARM",
                    "event_type": "ALARM",
                    "event_time": "2026-01-01T00:00:00",
                    "operator": "USER",
                    "comment": "RACB title",
                    "line_id": "LINE-A",
                    "eqp_id": "EQP-ALPHA",
                }
            ],
        ) as fetch_all:
            logs = selectors.get_logs_by_type(
                eqp_id="EQP-ALPHA",
                log_key="racb",
                start_at="2026-01-01T00:00:00",
                end_at="2026-01-02T23:59:59.999999",
                limit=20,
            )

        self.assertEqual(logs[0]["eqpId"], "EQP-ALPHA")
        self.assertEqual(logs[0]["logType"], "RACB")
        self.assertEqual(
            fetch_all.call_args.args[1],
            [
                "EQP-ALPHA",
                "2026-01-01T00:00:00",
                "2026-01-02T23:59:59.999999",
                20,
            ],
        )
        self.assertIn("upper(eqp_cb) = %s", fetch_all.call_args.args[0])

    def test_timeline_drone_logs_returns_results(self) -> None:
        with patch(
            f"{TIMELINE_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("timeline-logs-drone"),
                {"eqpId": "EQP-ALPHA"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        self.assert_log_selector_called(selector, log_key="drone")

    def test_timeline_drone_selector_uses_case_insensitive_eqp_filter(self) -> None:
        with patch(
            f"{TIMELINE_SELECTORS}._fetch_all_on_default",
            return_value=[],
        ) as fetch_all:
            logs = selectors.get_logs_by_type(
                eqp_id="eqpalpha",
                log_key="drone",
                start_at="2026-01-01T00:00:00",
                limit=20,
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(logs, [])
        self.assertIn("upper(sop.eqp_id) = %s", query)
        self.assertEqual(params, ["2026-01-01T00:00:00", "EQPALPHA", 20])
