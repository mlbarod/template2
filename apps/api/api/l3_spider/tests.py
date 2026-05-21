# =============================================================================
# 모듈: L3 Spider 서비스 테스트
# 주요 대상: meta, summary, data 응답 형태
# 주요 가정: 테스트 데이터는 임시 Parquet 파일로 생성합니다.
# =============================================================================
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, override_settings

import pandas as pd

from . import services


class L3SpiderServiceTests(SimpleTestCase):
    """L3 Spider 파일 기반 서비스 동작을 검증합니다."""

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

            with override_settings(L3_SPIDER_DATA_ROOT=str(root)):
                meta = services.get_meta()
                summary = services.get_summary(selection)
                data = services.get_data(selection)

        self.assertEqual(meta["lineIds"], ["L1"])
        self.assertEqual(meta["processIds"], ["P1"])
        self.assertEqual(meta["edsSteps"], ["EDS_M"])
        self.assertEqual(summary["stats"]["highRiskEqpchs"], 1)
        self.assertEqual(summary["stepPpids"], {"S1": ["PPID_A"]})
        self.assertEqual(summary["anomalies"][0]["binName"], "BIN_A")
        self.assertEqual(data["rows"][0]["stepSeq"], "S1")
        self.assertIn("displayStatus", data["rows"][0])
