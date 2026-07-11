from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

import pandas as pd

from api.l0_spider import services


class L0SpiderHardSpecServiceTests(SimpleTestCase):
    def test_meta_uses_hardspec_directory_shape(self) -> None:
        """line/model/step/ppid/recipe 디렉터리 구조에서 선택 옵션을 생성합니다."""

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "PFBP" / "MODEL_A" / "C1380250" / "PPID_1" / "RCP_1").mkdir(parents=True)

            with override_settings(FDC_HARD_SPEC_DATA_ROOT=root):
                with patch("api.l0_spider.selectors.fetch_fdc_models", return_value=["FDC_A"]):
                    payload = services.get_hard_spec_meta({"lineId": "PFBP"})

            self.assertEqual(payload["lineId"], "PFBP")
            self.assertEqual(payload["stepSeqs"], ["C%380250"])
            self.assertEqual(payload["recipeIds"], ["RCP_1"])
            self.assertEqual(payload["fdcModels"], ["FDC_A"])

    def test_recommendations_calculates_spec_gap_from_real_paths(self) -> None:
        """통계/priority/unit_model/HARD_LIMIT parquet을 읽어 Spec격차를 계산합니다."""

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            stat_root = root / "stats"
            data_dir = stat_root / "PFBP" / "MODEL_A" / "C1380250" / "PPID_1" / "RCP_1" / "20260610"
            data_dir.mkdir(parents=True)
            pd.DataFrame(
                [
                    {"sensor": "SENSOR_A@1200@001", "upper_bound": 12.0, "lower_bound": 2.0},
                    {"sensor": "SENSOR_A@1200@001", "upper_bound": 14.0, "lower_bound": 1.0},
                ]
            ).to_parquet(data_dir / "part.parquet", engine="pyarrow")

            priority_path = root / "priority.parquet"
            unit_model_path = root / "unit_model.parquet"
            hard_limit_path = root / "HARD_LIMIT.parquet"
            pd.DataFrame([{"eqp_id": "FDC_A", "priority": "A", "param_name": "SENSOR_A"}]).to_parquet(priority_path, engine="pyarrow")
            pd.DataFrame([{"fdc_model": "FDC_A", "unit_model_id": "UNIT_A"}]).to_parquet(unit_model_path, engine="pyarrow")
            pd.DataFrame(
                [
                    {
                        "UNIT_MODEL_ID": "UNIT_A",
                        "PARAMETER_NAME": "SENSOR_A",
                        "RECIPE": "RCP_1",
                        "BEGIN_STEP": "1000",
                        "END_STEP": "1300",
                        "UPDATE_DATE": "2026-06-10",
                        "UPPER_VALUE": 20.0,
                        "LOWER_VALUE": 0.0,
                    }
                ]
            ).to_parquet(hard_limit_path, engine="pyarrow")

            with override_settings(
                FDC_HARD_SPEC_DATA_ROOT=stat_root,
                FDC_HARD_SPEC_PRIORITY_PATH=priority_path,
                FDC_HARD_SPEC_UNIT_MODEL_PATH=unit_model_path,
                FDC_HARD_SPEC_HARD_LIMIT_PATH=hard_limit_path,
            ):
                with patch("api.l0_spider.selectors.fetch_fdc_models", return_value=["FDC_A"]):
                    payload = services.get_hard_spec_recommendations(
                        {"lineId": "PFBP", "stepSeq": "C%380250", "recipeId": "RCP_1", "fdcModel": "FDC_A"}
                    )

            self.assertEqual(len(payload["rows"]), 1)
            self.assertEqual(payload["rows"][0]["sensor_name"], "SENSOR_A")
            self.assertEqual(payload["rows"][0]["Spec격차"], "1.4배")
