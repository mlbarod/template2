# =============================================================================
# 모듈: L3 Spider 서비스 테스트
# 주요 대상: meta, summary, data 응답 형태
# 주요 가정: 테스트 데이터는 임시 Parquet 파일로 생성합니다.
# =============================================================================
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

import pandas as pd

from . import services
from .models import L3SpiderExclusionFilter


class L3SpiderServiceTests(SimpleTestCase):
    """L3 Spider 파일 기반 서비스 동작을 검증합니다."""

    def _columnar_rows(self, data: dict[str, object]) -> list[dict[str, object]]:
        """columnar 응답을 테스트 검증용 row 목록으로 변환합니다."""

        cols = data.get("cols", [])
        col_data = data.get("colData", [])
        if not cols or not col_data:
            return []
        return [
            {column: col_data[column_index][row_index] for column_index, column in enumerate(cols)}
            for row_index in range(len(col_data[0]))
        ]

    def _write_sample(self, root: Path) -> None:
        """테스트용 Parquet 파일을 생성합니다."""

        target = root / "2025-01-15" / "L1" / "P1" / "EDS_M"
        target.mkdir(parents=True)
        frame = pd.DataFrame(
            [
                {
                    "tkin_time": pd.Timestamp("2025-01-15 00:00:00"),
                    "step_seq": "S1",
                    "ppid": "PPID_A",
                    "root_lot_id": "ROOT",
                    "lot_id": "LOT",
                    "wafer_id": "W01",
                    "eqc": "EQC_A",
                    "bin_name": "BIN_A",
                    "bin_value": 1.2,
                    "prop_over_50": 0.7,
                    "lsl": 0.0,
                    "usl": 2.0,
                    "display_status": "High Risk Chamber",
                    "comment": "위험",
                },
                {
                    "tkin_time": pd.Timestamp("2025-01-15 01:00:00"),
                    "step_seq": "S1",
                    "ppid": "PPID_A",
                    "root_lot_id": "ROOT",
                    "lot_id": "LOT",
                    "wafer_id": "W02",
                    "eqc": "EQC_B",
                    "bin_name": "BIN_A",
                    "bin_value": 0.8,
                    "prop_over_50": 0.1,
                    "lsl": 0.0,
                    "usl": 2.0,
                    "display_status": "Normal (Ref)",
                    "comment": None,
                },
            ]
        )
        frame.to_parquet(target / "sample", engine="pyarrow")

    def _write_filename_key_sample(self, root: Path) -> None:
        """확장자 없는 파일명에서 step_seq와 ppid를 보강하는 샘플을 생성합니다."""

        target = root / "2025-01-15" / "L1" / "P1" / "EDS_M"
        target.mkdir(parents=True)
        frame = pd.DataFrame(
            [
                {
                    "tkin_time": pd.Timestamp("2025-01-15 00:00:00"),
                    "root_lot_id": "ROOT",
                    "lot_id": "LOT",
                    "wafer_id": "W01",
                    "eqc": "EQC_A",
                    "bin_name": "BIN_A",
                    "bin_value": 1.2,
                    "prop_over_50": 0.7,
                    "lsl": 0.0,
                    "usl": 2.0,
                    "display_status": "High Risk Chamber",
                    "comment": "위험",
                }
            ]
        )
        frame.to_parquet(target / "S1#PPID_A#0", engine="pyarrow")

    def test_meta_summary_and_data_use_camel_case_contract(self) -> None:
        """메타/요약/데이터 응답이 camelCase 계약을 따르는지 확인합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_sample(root)
            selection = {
                "dates": ["2025-01-15"],
                "lineIds": ["L1"],
                "processIds": ["P1"],
                "edsSteps": ["EDS_M"],
                "selectedEqcs": ["EQC_A"],
                "selectedStepBins": [],
                "selectedPpidBins": [],
                "selectedSteps": [],
                "checkedPpids": ["PPID_A"],
                "checkedBins": ["BIN_A"],
            }

            with override_settings(L3_SPIDER_DATA_ROOT=str(root)), patch.object(
                services,
                "_get_exclusion_rules",
                return_value=[],
            ):
                meta = services.get_meta()
                summary = services.get_summary(selection)
                data = services.get_data(selection)
                rows = self._columnar_rows(data)

        self.assertEqual(meta["lineIds"], ["L1"])
        self.assertEqual(meta["processIds"], ["P1"])
        self.assertEqual(meta["edsSteps"], ["EDS_M"])
        self.assertEqual(summary["stats"]["highRiskEqpchs"], 1)
        self.assertEqual(summary["stepPpids"], {"S1": ["PPID_A"]})
        self.assertEqual(summary["ppidEqcs"], {"PPID_A": ["EQC_A", "EQC_B"]})
        self.assertEqual(summary["ppidHighRiskEqcs"], {"PPID_A": ["EQC_A"]})
        self.assertEqual(summary["eqcHighRiskBins"], {"EQC_A": ["BIN_A"]})
        self.assertEqual(summary["anomalies"][0]["binName"], "BIN_A")
        self.assertEqual(rows[0]["stepSeq"], "S1")
        self.assertIn("displayStatus", rows[0])

    def test_extensionless_filename_key_supplies_step_and_ppid(self) -> None:
        """확장자 없는 STEP#PPID#N 파일명이 summary/data 필터에 반영되는지 확인합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_filename_key_sample(root)
            selection = {
                "dates": ["2025-01-15"],
                "lineIds": ["L1"],
                "processIds": ["P1"],
                "edsSteps": ["EDS_M"],
                "selectedEqcs": ["EQC_A"],
                "selectedStepBins": [],
                "selectedPpidBins": [],
                "selectedSteps": ["S1"],
                "checkedPpids": ["PPID_A"],
                "checkedBins": ["BIN_A"],
            }

            with override_settings(L3_SPIDER_DATA_ROOT=str(root)), patch.object(
                services,
                "_get_exclusion_rules",
                return_value=[],
            ):
                summary = services.get_summary(selection)
                data = services.get_data(selection)
                rows = self._columnar_rows(data)

        self.assertEqual(summary["stepPpids"], {"S1": ["PPID_A"]})
        self.assertEqual(summary["edsStepPpids"], {"EDS_M|||S1": ["PPID_A"]})
        self.assertEqual(rows[0]["stepSeq"], "S1")
        self.assertEqual(rows[0]["ppid"], "PPID_A")


class L3SpiderExclusionFilterOwnershipTests(TestCase):
    """L3 Spider 제외 필터 소유자 분리 규칙을 검증합니다."""

    def setUp(self) -> None:
        """테스트용 사용자를 생성합니다."""

        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="owner",
            sabun="100001",
            password="pw",
        )
        self.other = user_model.objects.create_user(
            username="other",
            sabun="100002",
            password="pw",
        )

    def _create_filter(
        self,
        *,
        user,
        line_id: str = "L1",
        memo: str = "",
        is_active: bool = True,
    ) -> L3SpiderExclusionFilter:
        """테스트용 제외 필터를 생성합니다."""

        return L3SpiderExclusionFilter.objects.create(
            line_id=line_id,
            process_id="*",
            eds_step="*",
            step_seq="*",
            ppid="*",
            eqpch="*",
            bin_name="*",
            memo=memo,
            is_active=is_active,
            created_by=user,
        )

    def test_list_exclusion_filters_returns_only_user_owned_rows(self) -> None:
        """목록 조회는 요청 사용자 소유 필터만 반환해야 합니다."""

        owner_filter = self._create_filter(user=self.owner, line_id="L1")
        self._create_filter(user=self.other, line_id="L2")

        rows = services.list_exclusion_filters(user=self.owner)

        self.assertEqual([row["id"] for row in rows], [owner_filter.id])
        self.assertEqual(rows[0]["lineId"], "L1")

    def test_exclusion_rules_use_only_user_owned_active_rows(self) -> None:
        """실제 제외 규칙도 사용자 소유 활성 필터만 사용해야 합니다."""

        self._create_filter(user=self.owner, line_id="L1")
        self._create_filter(user=self.owner, line_id="L2", is_active=False)
        self._create_filter(user=self.other, line_id="L3")

        rules = services._get_exclusion_rules(user=self.owner)

        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["line_id"], "L1")

    def test_update_exclusion_filter_rejects_other_user_row(self) -> None:
        """다른 사용자의 제외 필터는 수정할 수 없어야 합니다."""

        other_filter = self._create_filter(user=self.other, memo="원본")

        with self.assertRaises(services.L3SpiderServiceError) as context:
            services.update_exclusion_filter(
                other_filter.id,
                {"memo": "변경"},
                user=self.owner,
            )

        self.assertEqual(context.exception.status_code, 404)
        other_filter.refresh_from_db()
        self.assertEqual(other_filter.memo, "원본")

    def test_delete_exclusion_filter_rejects_other_user_row(self) -> None:
        """다른 사용자의 제외 필터는 삭제할 수 없어야 합니다."""

        other_filter = self._create_filter(user=self.other)

        with self.assertRaises(services.L3SpiderServiceError) as context:
            services.delete_exclusion_filter(other_filter.id, user=self.owner)

        self.assertEqual(context.exception.status_code, 404)
        self.assertTrue(L3SpiderExclusionFilter.objects.filter(pk=other_filter.id).exists())
