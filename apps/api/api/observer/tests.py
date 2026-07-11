# =============================================================================
# 모듈 설명: observer 엔드포인트 테스트를 제공합니다.
# - 주요 클래스: ObserverEndpointTests
# - 불변 조건: URL 네임(observer-*)이 등록되어 있어야 합니다.
# =============================================================================

from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import selectors

OBSERVER_VIEW_SELECTORS = "api.observer.views.selectors"
OBSERVER_SELECTORS = "api.observer.selectors"


def _allow_test_scope_access(test_case: TestCase) -> None:
    """도메인 endpoint 테스트에서 공통 portal/app 권한 경계를 격리합니다."""

    for service_name in ("get_portal_access_payload", "get_access_payload"):
        patcher = patch(
            f"api.account.services.{service_name}",
            return_value={"allowed": True},
        )
        patcher.start()
        test_case.addCleanup(patcher.stop)


class ObserverEndpointTests(TestCase):
    def setUp(self) -> None:
        """보호된 Observer endpoint를 호출할 인증 사용자를 준비합니다."""

        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S-OBSERVER",
            password="test-password",
            knox_id="knox-observer",
        )
        self.client.force_login(self.user)

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

    def test_observer_lines_selector_uses_drone_tip_status_options(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}.drone_selectors.get_tip_status_line_sdwt_options_payload",
            return_value={
                "lines": [
                    {"lineId": "LINE-A", "userSdwtProds": ["SD-10"]},
                    {"lineId": "", "userSdwtProds": ["SD-EMPTY"]},
                ],
                "userSdwtProds": ["SD-10"],
            },
        ) as options:
            lines = selectors.list_lines()

        self.assertEqual(lines, [{"id": "LINE-A", "name": "LINE-A"}])
        options.assert_called_once_with()

    def test_observer_sdwt_selector_uses_drone_tip_status_options(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}.drone_selectors.get_tip_status_line_sdwt_options_payload",
            return_value={
                "lines": [
                    {"lineId": "LINE-A", "userSdwtProds": ["SD-10", ""]},
                    {"lineId": "LINE-B", "userSdwtProds": ["SD-20"]},
                ],
                "userSdwtProds": ["SD-10", "SD-20"],
            },
        ) as options:
            sdwts = selectors.list_sdwt_for_line(line_id="line-a")

        self.assertEqual(sdwts, [{"id": "SD-10", "name": "SD-10", "lineId": "LINE-A"}])
        options.assert_called_once_with()

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
        with (
            patch(
                f"{OBSERVER_SELECTORS}.drone_selectors.get_tip_status_line_sdwt_options_payload",
                return_value={
                    "lines": [{"lineId": "LINE-A", "userSdwtProds": ["SD-10"]}],
                    "userSdwtProds": ["SD-10"],
                },
            ) as options,
            patch(
                f"{OBSERVER_SELECTORS}._fetch_all",
                return_value=[{"id": "ETCH"}],
            ) as fetch_all,
        ):
            groups = selectors.list_prc_groups(line_id="LINE-A", sdwt_id="sd-10")

        query, params = fetch_all.call_args.args
        self.assertEqual(groups[0]["id"], "ETCH")
        self.assertIn("from station_master", query)
        self.assertIn("sdwt_prod_lookup = %s", query)
        self.assertEqual(params, ["SD-10"])
        options.assert_called_once_with()

    def test_observer_prc_groups_selector_rejects_unowned_sdwt(self) -> None:
        with (
            patch(
                f"{OBSERVER_SELECTORS}.drone_selectors.get_tip_status_line_sdwt_options_payload",
                return_value={
                    "lines": [{"lineId": "LINE-B", "userSdwtProds": ["SD-10"]}],
                    "userSdwtProds": ["SD-10"],
                },
            ),
            patch(f"{OBSERVER_SELECTORS}._fetch_all") as fetch_all,
        ):
            groups = selectors.list_prc_groups(line_id="LINE-A", sdwt_id="sd-10")

        self.assertEqual(groups, [])
        fetch_all.assert_not_called()

    def test_observer_equipments_selector_uses_station_master(self) -> None:
        with (
            patch(
                f"{OBSERVER_SELECTORS}.drone_selectors.get_tip_status_line_sdwt_options_payload",
                return_value={
                    "lines": [{"lineId": "LINE-A", "userSdwtProds": ["SD-10"]}],
                    "userSdwtProds": ["SD-10"],
                },
            ) as options,
            patch(
                f"{OBSERVER_SELECTORS}._fetch_all",
                return_value=[
                    {
                        "id": "EQP-ALPHA",
                        "line_id": "LINE-A",
                        "sdwt_prod": "SD-10",
                        "prc_group": "ETCH",
                    },
                    {
                        "id": "EQP-ALPHA",
                        "line_id": "LINE-A",
                        "sdwt_prod": "SD-10",
                        "prc_group": "ETCH",
                    },
                ],
            ) as fetch_all,
        ):
            equipments = selectors.list_equipments(
                line_id="LINE-A",
                sdwt_id="sd-10",
                prc_group="etch",
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(equipments[0]["id"], "EQP-ALPHA")
        self.assertEqual(equipments[0]["lineId"], "LINE-A")
        self.assertEqual(len(equipments), 1)
        self.assertIn("select distinct on (station.station)", query)
        self.assertIn("from station_master station", query)
        self.assertNotIn("mes_line_mapping_info", query)
        self.assertIn("station.prc_group_lookup = %s", query)
        self.assertIn("station.sdwt_prod_lookup = %s", query)
        self.assertEqual(params, ["LINE-A", "ETCH", "SD-10"])
        options.assert_called_once_with()

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

    def test_tkin_prevent_prc_groups_requires_user_sdwt_prod(self) -> None:
        response = self.client.get(reverse("observer-tkin-prevent-prc-groups"))
        self.assertEqual(response.status_code, 400)

    def test_tkin_prevent_prc_groups_returns_results(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_tkin_prevent_prc_groups",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-tkin-prevent-prc-groups"),
                {"userSdwtProd": "sd-10"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(user_sdwt_prod="SD-10")

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
                {"userSdwtProd": "sd-10", "prcGroup": "etch"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(
            user_sdwt_prod="SD-10",
            prc_group="ETCH",
        )

    def test_tkin_prevent_step_seqs_requires_process(self) -> None:
        with patch(
            f"{OBSERVER_VIEW_SELECTORS}.list_tkin_prevent_step_seqs",
            return_value=[],
        ) as selector:
            response = self.client.get(
                reverse("observer-tkin-prevent-step-seqs"),
                {"userSdwtProd": "SD-10", "prcGroup": "ETCH"},
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
                    "userSdwtProd": "sd-10",
                    "prcGroup": "etch",
                    "processId": "proc-1",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        selector.assert_called_once_with(
            user_sdwt_prod="SD-10",
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
                    "userSdwtProd": "SD-10",
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
                    "userSdwtProd": "sd-10",
                    "prcGroup": "etch",
                    "processId": "proc-1",
                    "stepSeq": "10",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        selector.assert_called_once_with(
            user_sdwt_prod="SD-10",
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
                user_sdwt_prod="sd-10",
                prc_group="etch",
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(processes[0]["id"], "PROC-1")
        self.assertIn("from station_master station", query)
        self.assertIn("station.ch_main as eqp_id", query)
        self.assertIn("from m_tkin_prevent prevent", query)
        self.assertIn("prevent.eqp_id = target_eqp.eqp_id", query)
        self.assertNotIn("upper(trim(prevent.eqp_id))", query)
        self.assertNotIn("upper(trim(target_eqp.eqp_id))", query)
        self.assertNotIn("mes_line_mapping_info", query)
        self.assertNotIn("gpm_line_name_lookup", query)
        self.assertIn("station.sdwt_prod_lookup = %s", query)
        self.assertIn("station.prc_group_lookup = %s", query)
        self.assertIn(
            "prevent.registration_level in (%s, %s, %s)",
            query,
        )
        self.assertEqual(params, ["SD-10", "ETCH", "LEVEL1", "LEVEL2", "LEVEL3"])

    def test_tkin_prevent_prc_groups_selector_uses_station_master(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}._fetch_all",
            return_value=[{"id": "ETCH"}],
        ) as fetch_all:
            groups = selectors.list_tkin_prevent_prc_groups(user_sdwt_prod="sd-10")

        query, params = fetch_all.call_args.args
        self.assertEqual(groups[0]["id"], "ETCH")
        self.assertIn("from station_master", query)
        self.assertIn("sdwt_prod_lookup = %s", query)
        self.assertIn("prc_group_lookup as id", query)
        self.assertNotIn("mes_line_mapping_info", query)
        self.assertEqual(params, ["SD-10"])

    def test_tkin_prevent_step_selector_filters_process(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}._fetch_all",
            return_value=[{"step_seq": "10"}],
        ) as fetch_all:
            steps = selectors.list_tkin_prevent_step_seqs(
                user_sdwt_prod="SD-10",
                prc_group="ETCH",
                process_id="proc-1",
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(steps[0]["id"], "10")
        self.assertIn("prevent.process_id = %s", query)
        self.assertNotIn("upper(trim(prevent.process_id))", query)
        self.assertIn(
            "prevent.registration_level in (%s, %s, %s)",
            query,
        )
        self.assertEqual(
            params,
            ["SD-10", "ETCH", "PROC-1", "LEVEL1", "LEVEL2", "LEVEL3"],
        )

    def test_tkin_prevent_matrix_formats_cells(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}._fetch_all",
            return_value=[
                {
                    "ppid": "PPID-A",
                    "line_id": "LINE-A",
                    "eqp_id": "EQP-1",
                    "tkin_prevent_chamber_id": "CH-1",
                    "tkin_prevent_type": "DOING",
                    "tkin_prevent_comment": "DOING COMMENT",
                    "registration_level": None,
                    "tkin_restrc_lot_count": None,
                    "tkin_lot_count": None,
                    "level2_restrc_lot_count": None,
                },
                {
                    "ppid": "PPID-A",
                    "line_id": "LINE-A",
                    "eqp_id": "EQP-1",
                    "tkin_prevent_chamber_id": "CH-2",
                    "tkin_prevent_type": "PREVENT",
                    "tkin_prevent_comment": "PREVENT COMMENT",
                    "registration_level": "LEVEL2",
                    "tkin_restrc_lot_count": 4.0,
                    "tkin_lot_count": 10.0,
                    "level2_restrc_lot_count": 2.0,
                },
            ],
        ) as fetch_all:
            matrix = selectors.get_tkin_prevent_matrix(
                user_sdwt_prod="SD-10",
                prc_group="ETCH",
                process_id="proc-1",
                step_seq="10",
            )

        query, params = fetch_all.call_args.args
        self.assertEqual(matrix["totalRows"], 1)
        self.assertEqual(matrix["totalColumns"], 2)
        self.assertIn(
            "prevent.registration_level in (%s, %s, %s)",
            query,
        )
        self.assertEqual(
            params,
            ["SD-10", "ETCH", "PROC-1", "10", "LEVEL1", "LEVEL2", "LEVEL3"],
        )
        first_column_id = "LINE-A::EQP-1::CH-1"
        second_column_id = "LINE-A::EQP-1::CH-2"
        self.assertEqual(matrix["columns"][0]["id"], first_column_id)
        self.assertEqual(matrix["columns"][0]["label"], "EQP-1-CH-1")
        self.assertEqual(matrix["columns"][0]["lineId"], "LINE-A")
        self.assertEqual(matrix["rows"][0]["cells"][first_column_id][0]["status"], "DOING")
        self.assertEqual(
            matrix["rows"][0]["cells"][first_column_id][0]["comment"],
            "DOING COMMENT",
        )
        self.assertEqual(
            matrix["rows"][0]["cells"][second_column_id][0]["status"],
            "LEVEL2(2/4/10)",
        )
        self.assertEqual(
            matrix["rows"][0]["cells"][second_column_id][0]["comment"],
            "PREVENT COMMENT",
        )
        self.assertIn("prevent.tkin_prevent_comment", query)
        self.assertIn("prevent.process_id = %s", query)
        self.assertIn("prevent.step_seq = %s", query)
        self.assertIn(
            (
                "order by prevent.ppid, prevent.line_id, prevent.eqp_id, "
                "prevent.tkin_prevent_chamber_id"
            ),
            query,
        )
        self.assertNotIn("upper(trim(prevent.process_id))", query)
        self.assertNotIn("upper(trim(prevent.step_seq))", query)

    def test_tkin_prevent_matrix_separates_columns_by_line_id(self) -> None:
        with patch(
            f"{OBSERVER_SELECTORS}._fetch_all",
            return_value=[
                {
                    "ppid": "PPID-A",
                    "line_id": "LINE-A",
                    "eqp_id": "EQP-1",
                    "tkin_prevent_chamber_id": "CH-1",
                    "tkin_prevent_type": "DOING",
                    "tkin_prevent_comment": "SAME COMMENT",
                    "registration_level": None,
                    "tkin_restrc_lot_count": None,
                    "tkin_lot_count": None,
                    "level2_restrc_lot_count": None,
                },
                {
                    "ppid": "PPID-A",
                    "line_id": "LINE-B",
                    "eqp_id": "EQP-1",
                    "tkin_prevent_chamber_id": "CH-1",
                    "tkin_prevent_type": "DOING",
                    "tkin_prevent_comment": "SAME COMMENT",
                    "registration_level": None,
                    "tkin_restrc_lot_count": None,
                    "tkin_lot_count": None,
                    "level2_restrc_lot_count": None,
                },
            ],
        ):
            matrix = selectors.get_tkin_prevent_matrix(
                user_sdwt_prod="SD-10",
                prc_group="ETCH",
                process_id="proc-1",
                step_seq="10",
            )

        first_column_id = "LINE-A::EQP-1::CH-1"
        second_column_id = "LINE-B::EQP-1::CH-1"
        self.assertEqual(matrix["totalRows"], 1)
        self.assertEqual(matrix["totalColumns"], 2)
        self.assertEqual(
            [column["id"] for column in matrix["columns"]],
            [first_column_id, second_column_id],
        )
        self.assertEqual(
            [column["lineId"] for column in matrix["columns"]],
            ["LINE-A", "LINE-B"],
        )
        self.assertEqual(
            matrix["rows"][0]["cells"][first_column_id][0]["status"],
            "DOING",
        )
        self.assertEqual(
            matrix["rows"][0]["cells"][second_column_id][0]["status"],
            "DOING",
        )

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
        ) as selector:
            response = self.client.get(
                reverse("observer-equipment-info", kwargs={"eqp_id": "EQP-ALPHA"})
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "EQP-ALPHA")
        selector.assert_called_once_with(eqp_id="EQP-ALPHA", line_id="")

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
        ) as selector:
            response = self.client.get(
                reverse(
                    "observer-equipment-info-line",
                    kwargs={"line_id": "LINE-A", "eqp_id": "EQP-ALPHA"},
                )
            )

        self.assertEqual(response.status_code, 200)
        selector.assert_called_once_with(eqp_id="EQP-ALPHA", line_id="LINE-A")

    def test_observer_equipment_info_selector_uses_drone_target_line(self) -> None:
        with (
            patch(
                f"{OBSERVER_SELECTORS}.drone_selectors.get_tip_status_line_sdwt_options_payload",
                return_value={
                    "lines": [{"lineId": "LINE-A", "userSdwtProds": ["SD-10"]}],
                    "userSdwtProds": ["SD-10"],
                },
            ) as options,
            patch(
                f"{OBSERVER_SELECTORS}._fetch_one",
                return_value={
                    "id": "EQP-ALPHA",
                    "sdwt_prod": "Sd-10",
                    "sdwt_prod_lookup": "SD-10",
                    "prc_group": "ETCH",
                },
            ) as fetch_one,
        ):
            info = selectors.get_equipment_info(eqp_id="eqp-alpha")

        query, params = fetch_one.call_args.args
        self.assertEqual(info["id"], "EQP-ALPHA")
        self.assertEqual(info["lineId"], "LINE-A")
        self.assertEqual(info["sdwtId"], "SD-10")
        self.assertIn("from station_master station", query)
        self.assertNotIn("mes_line_mapping_info", query)
        self.assertIn("station.station_lookup = %s", query)
        self.assertEqual(params, ["EQP-ALPHA"])
        options.assert_called_once_with()

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
                    "core_summary": "Core summary",
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
        self.assertEqual(logs[0]["coreSummary"], "Core summary")
        self.assertEqual(logs[0]["summary"], "LLM summary")
        self.assertIn("from ctttm_workorder_list workorder", query)
        self.assertIn("left join ct_process_comment comment", query)
        self.assertIn("comment.llm_core_summary as core_summary", query)
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
