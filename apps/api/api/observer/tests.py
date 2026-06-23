# =============================================================================
# 모듈 설명: observer 엔드포인트 테스트를 제공합니다.
# - 주요 클래스: ObserverEndpointTests
# - 불변 조건: URL 네임(observer-*)이 등록되어 있어야 합니다.
# =============================================================================

from __future__ import annotations

import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from . import selectors

OBSERVER_VIEW_SELECTORS = "api.observer.views.selectors"
OBSERVER_SELECTORS = "api.observer.selectors"


class ObserverEndpointTests(TestCase):
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

    def test_observer_lines_returns_list(self) -> None:
        with patch(f"{OBSERVER_VIEW_SELECTORS}.list_lines", return_value=[]) as selector:
            response = self.client.get(reverse("observer-lines"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with()

    def test_observer_sdwts_requires_line(self) -> None:
        response = self.client.get(reverse("observer-sdwts"))
        self.assertEqual(response.status_code, 400)

    def test_observer_sdwts_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_sdwt_for_line",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-sdwts"),
                {"lineId": "LINE-A"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(line_id="LINE-A")

    def test_observer_lines_selector_uses_mes_mapping_info_with_sdwt_station(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}._fetch_all",
            return_value=[{"id": "GPM-LINE-A", "name": "GPM-LINE-A"}],
        ) as fetch_all:
            lines = selectors.list_lines()

        query = fetch_all.call_args.args[0]
        self.assertEqual(lines[0]["id"], "GPM-LINE-A")
        self.assertIn("from mes_line_mapping_info mapping", query)
        self.assertIn("join station_master station", query)
        self.assertIn("station.floor_line_id = mapping.msg_line_id", query)
        self.assertIn("mapping.gpm_line_name as id", query)
        self.assertIn("mapping.gbm_name = 'MEMORY'", query)
        self.assertIn("mapping.use_yn = 'Y'", query)
        self.assertIn("mapping.del_yn = 'N'", query)
        self.assertIn("station.sdwt_prod_lookup is not null", query)

    def test_observer_sdwt_selector_uses_lookup_line_filter(self) -> None:
        with patch(f"{OBSERVER_SELECTORS}._fetch_all", return_value=[]) as fetch_all:
            sdwts = selectors.list_sdwt_for_line(line_id="line-a")

        query, params = fetch_all.call_args.args
        self.assertEqual(sdwts, [])
        self.assertIn("from station_master station", query)
        self.assertIn("join mes_line_mapping_info mapping", query)
        self.assertIn("mapping.gpm_line_name_lookup = %s", query)
        self.assertIn("mapping.gbm_name = 'MEMORY'", query)
        self.assertIn("mapping.use_yn = 'Y'", query)
        self.assertIn("mapping.del_yn = 'N'", query)
        self.assertEqual(params, ["LINE-A"])

    def test_observer_prc_groups_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_prc_groups",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-prc-groups"),
                {"lineId": "LINE-A", "sdwtId": "SD-10"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(line_id="LINE-A", sdwt_id="SD-10")

    def test_observer_prc_groups_normalizes_query_values(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_prc_groups",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-prc-groups"),
                {"lineId": "line-a", "sdwtId": "sd-10"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(line_id="LINE-A", sdwt_id="SD-10")

    def test_observer_equipments_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_equipments",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-equipments"),
                {"lineId": "LINE-A", "sdwtId": "SD-10", "prcGroup": "ETCH"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(
            line_id="LINE-A",
            sdwt_id="SD-10",
            prc_group="ETCH",
        )

    def test_observer_prc_groups_selector_uses_station_master(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}._fetch_all",
            return_value=[{"id": "ETCH"}],
        ) as fetch_all:
            groups = selectors.list_prc_groups(line_id="LINE-A", sdwt_id="sd-10")

        query, params = fetch_all.call_args.args
        self.assertEqual(groups[0]["id"], "ETCH")
        self.assertIn("from station_master", query)
        self.assertIn("sdwt_prod_lookup = %s", query)
        self.assertEqual(params, ["SD-10"])

    def test_observer_equipments_selector_uses_station_master(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}._fetch_all",
            return_value=[
                {
                    "id": "EQP-ALPHA",
                    "line_id": "GPM-LINE-A",
                    "sdwt_prod": "SD-10",
                    "prc_group": "ETCH",
                },
                {
                    "id": "EQP-ALPHA",
                    "line_id": "GPM-LINE-B",
                    "sdwt_prod": "SD-10",
                    "prc_group": "ETCH",
                },
            ],
        ) as fetch_all:
            equipments = selectors.list_equipments(
                line_id="LINE-A",
                sdwt_id="sd-10",
                prc_group="etch",
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(equipments[0]["id"], "EQP-ALPHA")
        self.assertEqual(equipments[0]["lineId"], "GPM-LINE-A")
        self.assertEqual(len(equipments), 1)
        self.assertIn("select distinct on (station.station)", query)
        self.assertIn("from station_master station", query)
        self.assertIn("left join mes_line_mapping_info mapping", query)
        self.assertIn("station.prc_group_lookup = %s", query)
        self.assertIn("station.sdwt_prod_lookup = %s", query)
        self.assertEqual(params, ["ETCH", "SD-10"])

    def test_observer_equipments_normalizes_query_values(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_equipments",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-equipments"),
                {"lineId": "line-a", "sdwtId": "sd-10", "prcGroup": "etch"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(
            line_id="LINE-A",
            sdwt_id="SD-10",
            prc_group="ETCH",
        )

    def test_tkin_prevent_processes_requires_scope(self) -> None:
        response = self.client.get(reverse("observer-tkin-prevent-processes"))
        self.assertEqual(response.status_code, 400)

    def test_tkin_prevent_processes_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_tkin_prevent_processes",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-tkin-prevent-processes"),
                {"sdwtId": "sd-10", "prcGroup": "etch"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(
            sdwt_id="SD-10",
            prc_group="ETCH",
        )

    def test_tkin_prevent_step_seqs_requires_process(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_tkin_prevent_step_seqs",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-tkin-prevent-step-seqs"),
                {"sdwtId": "SD-10", "prcGroup": "ETCH"},
            )

        self.assertEqual(response.status_code, 400)
        selector.assert_not_called()

    def test_tkin_prevent_step_seqs_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_tkin_prevent_step_seqs",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-tkin-prevent-step-seqs"),
                {
                    "sdwtId": "sd-10",
                    "prcGroup": "etch",
                    "processId": "proc-1",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(
            sdwt_id="SD-10",
            prc_group="ETCH",
            process_id="PROC-1",
        )

    def test_tkin_prevent_matrix_requires_process_and_step(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_tkin_prevent_matrix",
            return_value={},
        ) as selector:
            response = self.client.get(
                reverse("observer-tkin-prevent-matrix"),
                {
                    "sdwtId": "SD-10",
                    "prcGroup": "ETCH",
                    "processId": "PROC-1",
                },
            )

        self.assertEqual(response.status_code, 400)
        selector.assert_not_called()

    def test_tkin_prevent_matrix_returns_results(self) -> None:
        payload = {"columns": [], "rows": [], "totalRows": 0, "totalColumns": 0}
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_tkin_prevent_matrix",
            return_value=payload,
        ) as selector:
            response = self.client.get(
                reverse("observer-tkin-prevent-matrix"),
                {
                    "sdwtId": "sd-10",
                    "prcGroup": "etch",
                    "processId": "proc-1",
                    "stepSeq": "10",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        selector.assert_called_once_with(
            sdwt_id="SD-10",
            prc_group="ETCH",
            process_id="PROC-1",
            step_seq="10",
        )

    def test_tkin_prevent_process_selector_uses_station_ch_main_scope(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}._fetch_all",
            return_value=[{"process_id": "PROC-1"}],
        ) as fetch_all:
            processes = selectors.list_tkin_prevent_processes(
                sdwt_id="sd-10",
                prc_group="etch",
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(processes[0]["id"], "PROC-1")
        self.assertIn("from station_master station", query)
        self.assertIn("station.ch_main as eqp_id", query)
        self.assertIn("from m_tkin_prevent prevent", query)
        self.assertIn("upper(trim(prevent.eqp_id))", query)
        self.assertIn("upper(trim(target_eqp.eqp_id))", query)
        self.assertNotIn("mes_line_mapping_info", query)
        self.assertNotIn("gpm_line_name_lookup", query)
        self.assertIn("station.sdwt_prod_lookup = %s", query)
        self.assertIn("station.prc_group_lookup = %s", query)
        self.assertEqual(params, ["SD-10", "ETCH"])

    def test_tkin_prevent_step_selector_filters_process(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}._fetch_all",
            return_value=[{"step_seq": "10"}],
        ) as fetch_all:
            steps = selectors.list_tkin_prevent_step_seqs(
                sdwt_id="SD-10",
                prc_group="ETCH",
                process_id="proc-1",
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(steps[0]["id"], "10")
        self.assertIn("upper(trim(prevent.process_id)) = %s", query)
        self.assertEqual(params, ["SD-10", "ETCH", "PROC-1"])

    def test_tkin_prevent_matrix_formats_cells(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}._fetch_all",
            return_value=[
                {
                    "ppid": "PPID-A",
                    "eqp_id": "EQP-1",
                    "tkin_prevent_chamber_id": "CH-1",
                    "tkin_prevent_type": "DOING",
                    "registration_level": None,
                    "tkin_restrc_lot_count": None,
                    "tkin_lot_count": None,
                    "level2_restrc_lot_count": None,
                },
                {
                    "ppid": "PPID-A",
                    "eqp_id": "EQP-1",
                    "tkin_prevent_chamber_id": "CH-2",
                    "tkin_prevent_type": "PREVENT",
                    "registration_level": "LEVEL2",
                    "tkin_restrc_lot_count": 4.0,
                    "tkin_lot_count": 10.0,
                    "level2_restrc_lot_count": 2.0,
                },
            ],
        ) as fetch_all:
            matrix = selectors.get_tkin_prevent_matrix(
                sdwt_id="SD-10",
                prc_group="ETCH",
                process_id="proc-1",
                step_seq="10",
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(matrix["totalRows"], 1)
        self.assertEqual(matrix["totalColumns"], 2)
        self.assertEqual(matrix["columns"][0]["label"], "EQP-1-CH-1")
        self.assertEqual(matrix["rows"][0]["cells"]["EQP-1-CH-1"][0]["status"], "DOING")
        self.assertEqual(
            matrix["rows"][0]["cells"]["EQP-1-CH-2"][0]["status"],
            "LEVEL2(2/4/10)",
        )
        self.assertIn("upper(trim(prevent.process_id)) = %s", query)
        self.assertIn("upper(trim(prevent.step_seq)) = %s", query)
        self.assertEqual(params, ["SD-10", "ETCH", "PROC-1", "10"])

    def test_observer_equipment_info_returns_result(self) -> None:
        payload = {
            "id": "EQP-ALPHA",
            "lineId": "LINE-A",
            "sdwtId": "SD-10",
            "prcGroup": "ETCH",
        }
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_equipment_info",
            return_value=payload,
        ):
            response = self.client.get(
                reverse("observer-equipment-info", kwargs={"eqp_id": "EQP-ALPHA"})
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "EQP-ALPHA")

    def test_observer_equipment_info_with_line_scope(self) -> None:
        payload = {
            "id": "EQP-ALPHA",
            "lineId": "LINE-A",
            "sdwtId": "SD-10",
            "prcGroup": "ETCH",
        }
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_equipment_info",
            return_value=payload,
        ):
            response = self.client.get(
                reverse(
                    "observer-equipment-info-line",
                    kwargs={"line_id": "LINE-A", "eqp_id": "EQP-ALPHA"},
                )
            )

        self.assertEqual(response.status_code, 200)

    def test_observer_equipment_info_selector_uses_station_mapping(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}._fetch_one",
            return_value={
                "id": "EQP-ALPHA",
                "line_id": "GPM-LINE-A",
                "sdwt_prod": "SD-10",
                "prc_group": "ETCH",
            },
        ) as fetch_one:
            info = selectors.get_equipment_info(eqp_id="eqp-alpha")

        query, params = fetch_one.call_args.args
        self.assertEqual(info["id"], "EQP-ALPHA")
        self.assertEqual(info["lineId"], "GPM-LINE-A")
        self.assertIn("from station_master station", query)
        self.assertIn("join mes_line_mapping_info mapping", query)
        self.assertIn("mapping.msg_line_id = station.floor_line_id", query)
        self.assertIn("station.station_lookup = %s", query)
        self.assertIn("mapping.gbm_name = 'MEMORY'", query)
        self.assertIn("mapping.use_yn = 'Y'", query)
        self.assertIn("mapping.del_yn = 'N'", query)
        self.assertEqual(params, ["EQP-ALPHA"])

    def test_observer_logs_requires_eqp_id(self) -> None:
        response = self.client.get(reverse("observer-logs"))
        self.assertEqual(response.status_code, 400)

    def test_observer_eqp_logs_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-logs-eqp"),
                {"eqpId": "EQP-ALPHA"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        self.assert_log_selector_called(selector, log_key="eqp")

    def test_observer_logs_passes_range_and_clamped_limit(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-logs-eqp"),
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

    def test_observer_logs_default_uses_no_row_limit(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}._period_date",
            return_value="2026-01-01",
        ) as period_date:
            with patch(
                f"{OBSERVER_SELECTORS}.eqp_status_chg_selectors.fetch_eqp_timeline_logs",
                return_value=[],
            ) as fetch_logs:
                logs = selectors.get_logs_by_type(
                    eqp_id="EQP-ALPHA",
                    log_key="eqp",
                )

        self.assertEqual(logs, [])
        self.assertEqual(selectors.DEFAULT_LOG_QUERY_DAYS, 60)
        period_date.assert_called_once_with()
        fetch_logs.assert_called_once_with(
            eqp_id="EQP-ALPHA",
            start_at="2026-01-01",
            end_at=None,
            limit=None,
        )

    def test_observer_eqp_selector_uses_eqp_status_chg_selector(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}.eqp_status_chg_selectors.fetch_eqp_timeline_logs",
            return_value=[
                {
                    "id": "EQP-100",
                    "eqpId": "EQP-ALPHA",
                    "logType": "EQP",
                    "eventType": "STATE",
                    "eventTime": "2026-01-01T00:00:00",
                    "operator": "USER",
                    "comment": "EQP comment",
                }
            ],
        ) as fetch_logs:
            logs = selectors.get_logs_by_type(
                eqp_id="EQP-ALPHA",
                log_key="eqp",
                start_at="2026-01-01T00:00:00",
                limit=20,
            )

        self.assertEqual(logs[0]["id"], "EQP-100")
        fetch_logs.assert_called_once_with(
            eqp_id="EQP-ALPHA",
            start_at="2026-01-01T00:00:00",
            end_at=None,
            limit=20,
        )

    def test_observer_tip_selector_uses_mi_tip_update_hist_selector(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}.mi_tip_update_hist_selectors.fetch_tip_timeline_logs",
            return_value=[
                {
                    "id": "TIP-EQP-ALPHA-20260101000000000000-CREATE-P-S-PPID-abc",
                    "eqpId": "EQP-ALPHA",
                    "logType": "TIP",
                    "eventType": "CREATE",
                    "eventTime": "2026-01-01T00:00:00",
                    "operator": "USER",
                    "comment": "TIP comment",
                    "lineId": "LINE-A",
                    "process": "P",
                    "step": "S",
                    "ppid": "PPID",
                }
            ],
        ) as fetch_logs:
            logs = selectors.get_logs_by_type(
                eqp_id="EQP-ALPHA",
                log_key="tip",
                start_at="2026-01-01T00:00:00",
                limit=20,
            )

        self.assertEqual(logs[0]["id"], "TIP-EQP-ALPHA-20260101000000000000-CREATE-P-S-PPID-abc")
        fetch_logs.assert_called_once_with(
            eqp_id="EQP-ALPHA",
            start_at="2026-01-01T00:00:00",
            end_at=None,
            limit=20,
        )

    def test_observer_logs_rejects_invalid_limit(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-logs-eqp"),
                {"eqpId": "EQP-ALPHA", "limit": "bad"},
            )

        self.assertEqual(response.status_code, 400)
        selector.assert_not_called()

    def test_observer_logs_rejects_reversed_range(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-logs-eqp"),
                {
                    "eqpId": "EQP-ALPHA",
                    "from": "2026-01-03",
                    "to": "2026-01-02",
                },
            )

        self.assertEqual(response.status_code, 400)
        selector.assert_not_called()

    def test_observer_tip_logs_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-logs-tip"),
                {"eqpId": "EQP-ALPHA"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        self.assert_log_selector_called(selector, log_key="tip")

    def test_observer_ctttm_logs_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-logs-ctttm"),
                {"eqpId": "EQP-ALPHA"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        self.assert_log_selector_called(selector, log_key="ctttm")

    def test_observer_ctttm_selector_joins_ct_process_comment_summary(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}._fetch_all_on_default",
            return_value=[
                {
                    "id": "WO-1",
                    "eqp_id": "EQP-ALPHA",
                    "log_type": "CTTTM",
                    "event_type": "CBM",
                    "event_time": "2026-01-01T00:00:00",
                    "operator": None,
                    "comment": "CTTTM comment",
                    "url": "https://example.local?wono=WO-1&lineId=L1",
                    "summary": "LLM summary",
                }
            ],
        ) as fetch_all:
            logs = selectors.get_logs_by_type(
                eqp_id="EQP-ALPHA",
                log_key="ctttm",
                start_at="2026-01-01T00:00:00",
                limit=20,
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(logs[0]["summary"], "LLM summary")
        self.assertIn("from ctttm_workorder_list workorder", query)
        self.assertIn("left join ct_process_comment comment", query)
        self.assertIn("comment.llm_summary as summary", query)
        self.assertIn("comment.workorder_id = workorder.workorder_id", query)
        self.assertEqual(params[1:], ["EQP-ALPHA", "2026-01-01T00:00:00", 20])

    def test_observer_racb_logs_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-logs-racb"),
                {"eqpId": "EQP-ALPHA"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        self.assert_log_selector_called(selector, log_key="racb")

    def test_observer_racb_selector_uses_racb_list_selector(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}.racb_list_selectors.fetch_racb_timeline_logs",
            return_value=[
                {
                    "id": "LINE-A-EQP-ALPHA-2026-01-01-ALARM",
                    "eventType": "ALARM",
                    "eventTime": "2026-01-01T00:00:00",
                    "operator": "USER",
                    "comment": "RACB title",
                    "lineId": "LINE-A",
                    "eqpId": "EQP-ALPHA",
                    "logType": "RACB",
                }
            ],
        ) as selector:
            logs = selectors.get_logs_by_type(
                eqp_id="EQP-ALPHA",
                log_key="racb",
                start_at="2026-01-01T00:00:00",
                end_at="2026-01-02T23:59:59.999999",
                limit=20,
            )

        self.assertEqual(logs[0]["eqpId"], "EQP-ALPHA")
        self.assertEqual(logs[0]["logType"], "RACB")
        selector.assert_called_once_with(
            eqp_id="EQP-ALPHA",
            start_at="2026-01-01T00:00:00",
            end_at="2026-01-02T23:59:59.999999",
            limit=20,
        )

    def test_observer_esop_logs_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.get_logs_by_type",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-logs-esop"),
                {"eqpId": "EQP-ALPHA"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        self.assert_log_selector_called(selector, log_key="esop")

    def test_observer_esop_selector_uses_lookup_eqp_filter(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}._fetch_all_on_default",
            return_value=[],
        ) as fetch_all:
            logs = selectors.get_logs_by_type(
                eqp_id="eqpalpha",
                log_key="esop",
                start_at="2026-01-01T00:00:00",
                limit=20,
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(logs, [])
        self.assertIn("sop.eqp_id_lookup = %s", query)
        self.assertEqual(params, ["2026-01-01T00:00:00", "EQPALPHA", 20])

    def test_observer_esop_selector_maps_log_type_to_esop(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}._fetch_all_on_default",
            return_value=[
                {
                    "id": 1,
                    "event_type": "AUTO",
                    "event_time": "2026-01-01T00:00:00",
                    "operator": "KNOX01",
                    "status": "DONE",
                    "comment": "SOP done",
                    "line_id": "LINE-A",
                    "eqp_id": "EQP-ALPHA",
                    "chamber_ids": "1",
                    "lot_id": "LOT-1",
                    "defect_url": json.dumps(
                        [
                            {
                                "label": "ST001",
                                "map_url": "https://example.com/defect-map",
                                "map_file": "MAP001.png",
                                "image_rows": [0, 1, 1, -1, "bad"],
                            }
                        ]
                    ),
                }
            ],
        ):
            logs = selectors.get_logs_by_type(
                eqp_id="EQP-ALPHA",
                log_key="esop",
            )

        self.assertEqual(logs[0]["logType"], "ESOP")
        self.assertEqual(logs[0]["operator"], "KNOX01")
        self.assertEqual(logs[0]["eqpId"], "EQP-ALPHA")
        self.assertEqual(logs[0]["eqpCb"], "EQP-ALPHA-1")
        self.assertEqual(logs[0]["lotId"], "LOT-1")
        image_url_base = (
            "https://example.com/map/api/map-image/v3/defect-map"
            "?file=MAP001.png&selected_row={row}&profileid=DEFAULT&themeid=DEFAULT"
            "&width=500&height=500&site=GH&targetDB=APP&useCache=true"
            "&includeCoordinate=false"
        )
        self.assertEqual(
            logs[0]["defectMaps"],
            [
                {
                    "label": "ST001",
                    "url": "https://example.com/defect-map",
                    "imageUrls": [
                        image_url_base.format(row=0),
                        image_url_base.format(row=1),
                    ],
                }
            ],
        )
