# =============================================================================
# 모듈: PM SPIDER 서비스 테스트
# 주요 대상: result rank와 data 상세 row 계산
# 주요 가정: 테스트 데이터는 임시 Parquet 파일로 생성합니다.
# =============================================================================
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, override_settings
from django.urls import Resolver404, resolve, reverse

import pandas as pd

from . import selectors, services
from .serializers import PmComparisonRequestSerializer
from .views import PmComparisonCompareView, PmComparisonMetaView


class PmComparisonServiceTests(SimpleTestCase):
    """PM SPIDER 파일 기반 서비스 동작을 검증합니다."""

    def test_pm_spider_api_contract_urls_resolve(self) -> None:
        """PM SPIDER 공개 API prefix와 URL name 계약을 검증합니다."""

        self.assertEqual(reverse("pm-spider-meta"), "/api/v1/pm_spider/meta")
        self.assertEqual(reverse("pm-spider-compare"), "/api/v1/pm_spider/compare")
        self.assertIs(resolve("/api/v1/pm_spider/meta").func.view_class, PmComparisonMetaView)
        self.assertIs(resolve("/api/v1/pm_spider/compare").func.view_class, PmComparisonCompareView)

    def test_legacy_pm_comparison_api_prefix_is_not_registered(self) -> None:
        """이전 PM comparison API prefix가 남아 있지 않은지 검증합니다."""

        with self.assertRaises(Resolver404):
            resolve("/api/v1/pm-comparison/meta")

    def _raw_base(
        self,
        root: Path,
        *,
        data_source: str,
        trace_param_name: str,
        raw_dir: str = selectors.RAW_DIR_NAME,
    ) -> Path:
        """테스트용 raw partition 경로를 반환합니다."""

        return (
            root
            / raw_dir
            / "line_id=L1"
            / "eqp_id=EQP1"
            / "fdc_bin=BIN1"
            / "dt=2026-06-01"
            / "type=ag"
            / "ppid=PPID1"
            / "recipe_id=RCP1"
            / f"data_source={data_source}"
            / f"trace_param_name={trace_param_name}"
            / "batch=001"
        )

    def _score_base(self, root: Path, *, data_type: str, score_dir: str = selectors.SCORE_DIR_NAME) -> Path:
        """테스트용 score partition 경로를 반환합니다."""

        return (
            root
            / score_dir
            / "line_id=L1"
            / "eqp_id=EQP1"
            / "type=ag"
            / f"data_type={data_type}"
        )

    def _plain_raw_base(
        self,
        root: Path,
        *,
        data_source: str,
        trace_param_name: str,
        raw_dir: str = selectors.RAW_DIR_NAME,
    ) -> Path:
        """plain raw layout 테스트 경로를 반환합니다."""

        return (
            root
            / raw_dir
            / "L1"
            / "EQP1"
            / "BIN1"
            / "2026-06-01"
            / data_source
            / "type=ag"
            / "ppid=PPID1"
            / "recipe_id=RCP1"
            / "priority=1"
            / f"trace_param_name={trace_param_name}"
        )

    def _write_trace_sample(
        self,
        root: Path,
        *,
        raw_dir: str = selectors.RAW_DIR_NAME,
        score_dir: str = selectors.SCORE_DIR_NAME,
    ) -> None:
        """테스트용 trace raw와 score 데이터를 생성합니다."""

        raw_target = self._raw_base(
            root,
            data_source="trace",
            trace_param_name="PRESSURE",
            raw_dir=raw_dir,
        )
        raw_target.mkdir(parents=True)
        pd.DataFrame(
            [
                {"날짜": "2026-04-01", "time": "2026-04-01T01:00:00Z", "value": 10.0},
                {"날짜": "2026-05-01", "time": "2026-05-01T01:00:00Z", "value": 12.0},
                {"날짜": "2026-06-01", "time": "2026-06-01T01:00:00Z", "value": 30.0},
            ]
        ).to_parquet(raw_target / "part-000.parquet", engine="pyarrow")

        score_target = self._score_base(root, data_type="trace", score_dir=score_dir)
        score_target.mkdir(parents=True)
        pd.DataFrame(
            [
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "날짜": "2026-04-01",
                    "type": "ag",
                    "data_type": "trace",
                    "item_name": "PRESSURE",
                    "step": None,
                    "wavelength": None,
                    "score": 0.52,
                },
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "날짜": "2026-05-01",
                    "type": "ag",
                    "data_type": "trace",
                    "item_name": "PRESSURE",
                    "step": None,
                    "wavelength": None,
                    "score": 0.42,
                },
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "날짜": "2026-06-01",
                    "type": "ag",
                    "data_type": "trace",
                    "item_name": "PRESSURE",
                    "step": None,
                    "wavelength": None,
                    "score": 0.12,
                },
            ]
        ).to_parquet(score_target / "part-000.parquet", engine="pyarrow")

    def _write_plain_trace_sample(self, root: Path) -> None:
        """plain raw layout trace와 기존 score 데이터를 생성합니다."""

        raw_target = self._plain_raw_base(
            root,
            data_source="trace",
            trace_param_name="PRESSURE",
        )
        raw_target.mkdir(parents=True)
        pd.DataFrame(
            [
                {"날짜": "2026-04-01", "time": "2026-04-01T01:00:00Z", "value": 10.0},
                {"날짜": "2026-06-01", "time": "2026-06-01T01:00:00Z", "value": 30.0},
            ]
        ).to_parquet(raw_target / "part-000.parquet", engine="pyarrow")

        score_target = self._score_base(root, data_type="trace")
        score_target.mkdir(parents=True)
        pd.DataFrame(
            [
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "날짜": "2026-06-01",
                    "type": "ag",
                    "data_type": "trace",
                    "item_name": "PRESSURE",
                    "score": 0.12,
                },
            ]
        ).to_parquet(score_target / "part-000.parquet", engine="pyarrow")

    def _write_oes_sample(
        self,
        root: Path,
        *,
        raw_dir: str = selectors.RAW_DIR_NAME,
        score_dir: str = selectors.SCORE_DIR_NAME,
    ) -> None:
        """테스트용 OES raw와 score 데이터를 생성합니다."""

        raw_target = self._raw_base(
            root,
            data_source="oes",
            trace_param_name="spectrum",
            raw_dir=raw_dir,
        )
        raw_target.mkdir(parents=True)
        pd.DataFrame(
            [
                {"날짜": "2026-05-01", "rcp_step": "STEP_A", "wavelength": 200.0, "value": 100.0},
                {"날짜": "2026-05-01", "rcp_step": "STEP_A", "wavelength": 201.0, "value": 120.0},
                {"날짜": "2026-06-01", "rcp_step": "STEP_A", "wavelength": 200.0, "value": 160.0},
                {"날짜": "2026-06-01", "rcp_step": "STEP_A", "wavelength": 201.0, "value": 170.0},
            ]
        ).to_parquet(raw_target / "part-000.parquet", engine="pyarrow")

        score_target = self._score_base(root, data_type="oes", score_dir=score_dir)
        score_target.mkdir(parents=True)
        pd.DataFrame(
            [
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "날짜": "2026-06-01",
                    "type": "ag",
                    "data_type": "oes",
                    "item_name": "STEP_A/200.0",
                    "step": "STEP_A",
                    "wavelength": 200.0,
                    "score": 0.08,
                }
            ]
        ).to_parquet(score_target / "part-000.parquet", engine="pyarrow")

    def _write_plain_oes_wide_sample(self, root: Path) -> None:
        """DASHBOARD_SPEC plain OES wide raw와 score 데이터를 생성합니다."""

        raw_target = (
            root
            / selectors.RAW_DIR_NAME
            / "L1"
            / "EQP1"
            / "BIN1"
            / "2026-06-01 00:00:00"
            / "oes"
            / "ag"
            / "SEQ1"
            / "PPID1"
            / "RCP1"
            / "LOT9"
            / "7"
        )
        raw_target.mkdir(parents=True)
        file_name = "L1#PROC1#SEQ1#4d#PPID1#RCP1#EQP1#BIN1#LOT9#7#2026-06-01T01:02:03.parquet"
        pd.DataFrame(
            [
                {"Time": 0.0, "200.0": 100.0, "200.5": 110.0},
                {"Time": 1.0, "200.0": 120.0, "200.5": 130.0},
            ]
        ).to_parquet(raw_target / file_name, engine="pyarrow")

        score_target = self._score_base(root, data_type="oes")
        score_target.mkdir(parents=True)
        pd.DataFrame(
            [
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "날짜": "2026-06-01",
                    "type": "ag",
                    "data_type": "oes",
                    "item_name": "4d/200.0",
                    "step": "4d",
                    "wavelength": 200.0,
                    "score": 0.0797,
                },
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "날짜": "2026-06-01",
                    "type": "ag",
                    "data_type": "oes",
                    "item_name": "4d/200.5",
                    "step": "4d",
                    "wavelength": 200.5,
                    "score": 1.0,
                },
            ]
        ).to_parquet(score_target / "part-000.parquet", engine="pyarrow")

    def _write_plain_oes_ref_dates_sample(self, root: Path) -> None:
        """score ref_dates가 가리키는 plain OES REF raw를 생성합니다."""

        for dt_value, base in [("2026-04-21 00:00:00", 100.0), ("2026-06-01 00:00:00", 200.0)]:
            raw_target = (
                root
                / selectors.RAW_DIR_NAME
                / "L1"
                / "EQP1"
                / "BIN1"
                / dt_value
                / "oes"
                / "ag"
                / "SEQ1"
                / "PPID1"
                / "RCP1"
                / "LOT9"
                / "7"
            )
            raw_target.mkdir(parents=True)
            file_name = f"L1#PROC1#SEQ1#4d#PPID1#RCP1#EQP1#BIN1#LOT9#7#{dt_value}.parquet"
            pd.DataFrame(
                [
                    {"Time": 0.0, "200.0": base, "200.5": base + 10.0},
                    {"Time": 1.0, "200.0": base + 20.0, "200.5": base + 30.0},
                ]
            ).to_parquet(raw_target / file_name, engine="pyarrow")

        score_target = self._score_base(root, data_type="oes")
        score_target.mkdir(parents=True)
        pd.DataFrame(
            [
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "날짜": "2026-06-01",
                    "type": "ag",
                    "data_type": "oes",
                    "item_name": "4d/200.0",
                    "step": "4d",
                    "wavelength": 200.0,
                    "score": 0.0797,
                    "ref_dates": "['2026-04-21 00:00:00']",
                },
            ]
        ).to_parquet(score_target / "part-000.parquet", engine="pyarrow")

    def _write_wide_oes_step_filter_sample(self, root: Path) -> None:
        """여러 step이 섞인 wide OES raw와 score 데이터를 생성합니다."""

        raw_target = self._raw_base(
            root,
            data_source="oes",
            trace_param_name="spectrum",
        )
        raw_target.mkdir(parents=True)
        rows = []
        for date, date_shift in [("2026-05-01", 0), ("2026-06-01", 100)]:
            for step, step_shift in [("1D", 10), ("3D", 1000)]:
                for time_index in [0, 1]:
                    base = date_shift + step_shift + time_index
                    rows.append(
                        {
                            "날짜": date,
                            "Time": float(time_index),
                            "rcp_step": step,
                            "lot_id": "LOT1",
                            "slot_no": 1,
                            "slot_id": "SLOT01",
                            "group": f"{step}_{date}",
                            "200.0": float(base),
                            "200.5": float(base + 1),
                            "201.0": float(base + 2),
                        }
                    )
        pd.DataFrame(rows).to_parquet(raw_target / "part-000.parquet", engine="pyarrow")

        score_target = self._score_base(root, data_type="oes")
        score_target.mkdir(parents=True)
        pd.DataFrame(
            [
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "날짜": "2026-05-01",
                    "type": "ag",
                    "data_type": "oes",
                    "item_name": "1D/200.0",
                    "step": "1D",
                    "wavelength": 200.0,
                    "score": 0.2,
                },
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "날짜": "2026-06-01",
                    "type": "ag",
                    "data_type": "oes",
                    "item_name": "1D/200.0",
                    "step": "1D",
                    "wavelength": 200.0,
                    "score": 0.03,
                },
                {
                    "line_id": "L1",
                    "eqp_id": "EQP1",
                    "날짜": "2026-06-01",
                    "type": "ag",
                    "data_type": "oes",
                    "item_name": "3D/200.0",
                    "step": "3D",
                    "wavelength": 200.0,
                    "score": 0.6,
                },
            ]
        ).to_parquet(score_target / "part-000.parquet", engine="pyarrow")

    def test_compare_pm_window_returns_score_rank_and_raw_detail(self) -> None:
        """score rank와 raw ref/comp 상세 row가 함께 반환되는지 확인합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_trace_sample(root)
            self._write_oes_sample(root)
            selection = {
                "lineId": "L1",
                "eqpId": "EQP1",
                "fdcBin": "BIN1",
                "type": "ag",
                "ppid": "PPID1",
                "recipeId": "RCP1",
                "pmTimestamp": "2026-06-01",
                "beforeHours": 2,
                "afterHours": 2,
                "traceParamNames": ["PRESSURE"],
                "dtValues": ["2026-06-01"],
                "traceDataSource": "trace",
                "oesDataSource": "oes",
                "limit": 200,
            }

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                result = services.compare_pm_window(selection)
                selected_result = services.compare_pm_window(
                    {
                        **selection,
                        "refPmDates": ["2026-04-01"],
                    }
                )
                meta = services.get_meta()
                selected_meta = services.get_meta({"lineId": "L1", "eqpId": "EQP1"})
                wavelength_result = services.compare_pm_window(
                    {
                        **selection,
                        "selectedStep": "STEP_A",
                        "selectedWavelength": "200",
                        "maxPoints": 200,
                    }
                )
                trace_only_result = services.compare_pm_window(
                    {
                        **selection,
                        "includeOesDetails": False,
                    }
                )
                oes_only_result = services.compare_pm_window(
                    {
                        **selection,
                        "selectedStep": "STEP_A",
                        "includeTraceDetails": False,
                    }
                )

        self.assertEqual(meta["lineIds"], ["L1"])
        self.assertEqual(meta["eqpIds"], [])
        self.assertIn("2026-06-01", selected_meta["pmDates"])
        self.assertEqual(result["trace"]["worstSensor"]["traceSensor"], "PRESSURE")
        self.assertEqual(result["trace"]["worstSensor"]["score"], 0.12)
        self.assertEqual(result["trace"]["trendRows"][0]["cycleIndex"], -2)
        self.assertEqual(result["trace"]["trendRows"][1]["cycleIndex"], -1)
        self.assertEqual(result["trace"]["trendRows"][2]["cycleIndex"], 0)
        self.assertGreaterEqual(result["trace"]["lineChart"]["sourcePointCount"], 3)
        self.assertGreaterEqual(len(result["trace"]["lineChart"]["series"]), 1)
        self.assertEqual(
            [row["cycleIndex"] for row in selected_result["trace"]["trendRows"]],
            [-2, 0],
        )
        self.assertEqual(
            [row["selected"] for row in selected_result["trace"]["refCycles"]],
            [False, True],
        )
        self.assertEqual(result["oes"]["worstStep"], "STEP_A")
        self.assertEqual(result["oes"]["worstWavelength"]["score"], 0.08)
        self.assertGreaterEqual(len(result["oes"]["detailRows"]), 2)
        self.assertGreaterEqual(result["oes"]["heatmap"]["width"], 1)
        self.assertGreaterEqual(result["oes"]["heatmap"]["height"], 1)
        self.assertEqual(result["oes"]["heatmap"]["wavelengths"], [200.0, 201.0])
        self.assertGreaterEqual(len(result["oes"]["spectrumChart"]["series"]), 1)

        self.assertGreaterEqual(len(wavelength_result["oes"]["lineChart"]["series"]), 1)
        self.assertEqual(trace_only_result["oes"]["rowCount"], 0)
        self.assertEqual(trace_only_result["oes"]["fileCount"], 0)
        self.assertEqual(oes_only_result["trace"]["rowCount"], 0)
        self.assertEqual(oes_only_result["trace"]["fileCount"], 0)
        self.assertGreaterEqual(oes_only_result["oes"]["heatmap"]["width"], 1)

    def test_single_mount_uses_data_and_result_dir_names(self) -> None:
        """단일 mount 아래 data/result 폴더명을 사용하는지 확인합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_trace_sample(root)

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                raw_root = selectors.ensure_dataset_root(selectors.RAW_DIR_NAME)
                score_root = selectors.ensure_dataset_root(selectors.SCORE_DIR_NAME)
                meta = services.get_meta()

        self.assertEqual(raw_root.name, "data")
        self.assertEqual(score_root.name, "result")
        self.assertEqual(meta["lineIds"], ["L1"])

    def test_plain_raw_layout_returns_meta_and_trace_rows(self) -> None:
        """plain raw layout에서도 메타와 trace 상세 row를 반환해야 합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_plain_trace_sample(root)
            selection = {
                "lineId": "L1",
                "eqpId": "EQP1",
                "fdcBin": "BIN1",
                "type": "ag",
                "ppid": "PPID1",
                "recipeId": "RCP1",
                "pmTimestamp": "2026-06-01",
                "traceParamNames": ["PRESSURE"],
                "traceDataSource": "trace",
                "oesDataSource": "oes",
            }

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                meta = services.get_meta()
                line_meta = services.get_meta({"lineId": "L1"})
                eqp_meta = services.get_meta({"lineId": "L1", "eqpId": "EQP1"})
                result = services.compare_pm_window(selection)

        self.assertEqual(meta["lineIds"], ["L1"])
        self.assertEqual(line_meta["eqpIds"], ["EQP1"])
        self.assertEqual(eqp_meta["fdcBins"], ["BIN1"])
        self.assertEqual(result["trace"]["summaryRows"][0]["traceSensor"], "PRESSURE")
        self.assertEqual(len(result["trace"]["trendRows"]), 1)

    def test_plain_oes_wide_layout_uses_path_and_filename_metadata(self) -> None:
        """plain OES wide raw는 경로와 파일명 metadata로 상세 plot을 생성해야 합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_plain_oes_wide_sample(root)
            selection = {
                "lineId": "L1",
                "eqpId": "EQP1",
                "fdcBin": "BIN1",
                "type": "ag",
                "ppid": "PPID1",
                "recipeId": "RCP1",
                "pmTimestamp": "2026-06-01",
                "dtValues": ["2026-06-01"],
                "traceDataSource": "trace",
                "oesDataSource": "oes",
                "selectedStep": "4d",
                "includeDetails": True,
            }

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                result = services.compare_pm_window(selection)

        self.assertEqual(result["oes"]["scoreFileCount"], 1)
        self.assertEqual(result["oes"]["fileCount"], 1)
        self.assertEqual(result["oes"]["rowCount"], 4)
        self.assertEqual(result["oes"]["stepRows"][0]["step"], "4d")
        self.assertEqual(result["oes"]["heatmap"]["width"], 2)
        self.assertGreaterEqual(result["oes"]["heatmap"]["height"], 1)
        self.assertEqual(result["oes"]["heatmap"]["wavelengths"], [200.0, 200.5])
        self.assertEqual(result["oes"]["heatmap"]["sourcePointCount"], 4)
        self.assertEqual(result["oes"]["detailRows"][0]["rcpStep"], "4d")
        self.assertEqual(result["oes"]["detailRows"][0]["lotId"], "LOT9")
        self.assertFalse(
            any("날짜/rcp_step/wavelength/value" in warning for warning in result["warnings"])
        )

    def test_oes_ref_dates_load_plain_ref_raw_timestamp_path(self) -> None:
        """OES score ref_dates timestamp 폴더의 REF raw를 함께 읽어야 합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_plain_oes_ref_dates_sample(root)
            selection = {
                "lineId": "L1",
                "eqpId": "EQP1",
                "fdcBin": "BIN1",
                "type": "ag",
                "ppid": "PPID1",
                "recipeId": "RCP1",
                "pmTimestamp": "2026-06-01",
                "dtValues": ["2026-06-01"],
                "traceDataSource": "trace",
                "oesDataSource": "oes",
                "selectedStep": "4d",
                "includeTraceDetails": False,
                "includeOesSpectrum": False,
            }

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                result = services.compare_pm_window(selection)

        ref_cycles = result["oes"]["refCycles"]
        heatmap = result["oes"]["heatmap"]
        ref_values = [value for value in heatmap["ref"] if value is not None]
        comp_values = [value for value in heatmap["comp"] if value is not None]
        self.assertEqual(ref_cycles, [{"pmDate": "2026-04-21", "cycleIndex": -1, "phase": "ref", "selected": True}])
        self.assertEqual(result["oes"]["fileCount"], 2)
        self.assertEqual(heatmap["sourcePointCount"], 8)
        self.assertGreater(len(ref_values), 0)
        self.assertGreater(len(comp_values), 0)
        self.assertLess(max(ref_values), min(comp_values))

    def test_wide_oes_detail_filters_selected_step_before_matrix_build(self) -> None:
        """wide OES 상세는 선택 step만 사용해 matrix와 trajectory를 만들어야 합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_wide_oes_step_filter_sample(root)
            selection = {
                "lineId": "L1",
                "eqpId": "EQP1",
                "fdcBin": "BIN1",
                "type": "ag",
                "ppid": "PPID1",
                "recipeId": "RCP1",
                "pmTimestamp": "2026-06-01",
                "dtValues": ["2026-06-01"],
                "traceDataSource": "trace",
                "oesDataSource": "oes",
                "selectedStep": "1D",
                "includeDetails": True,
                "limit": 10,
            }

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                result = services.compare_pm_window(selection)
                wavelength_result = services.compare_pm_window(
                    {
                        **selection,
                        "selectedWavelength": "200.5",
                    }
                )
                heatmap_only_result = services.compare_pm_window(
                    {
                        **selection,
                        "includeOesSpectrum": False,
                        "heatmapXBins": 2,
                    }
                )
                trajectory_only_result = services.compare_pm_window(
                    {
                        **selection,
                        "selectedWavelength": "200.5",
                        "includeOesHeatmap": False,
                        "includeOesSpectrum": False,
                    }
                )

        self.assertEqual(result["oes"]["rowCount"], 12)
        self.assertEqual(result["oes"]["heatmap"]["width"], 3)
        self.assertEqual(result["oes"]["heatmap"]["height"], 2)
        self.assertEqual(result["oes"]["heatmap"]["wavelengths"], [200.0, 200.5, 201.0])
        self.assertEqual(result["oes"]["heatmap"]["sourcePointCount"], 12)
        self.assertTrue(all(row["rcpStep"] == "1D" for row in result["oes"]["detailRows"]))
        self.assertLess(max(row["value"] for row in result["oes"]["detailRows"]), 500)
        self.assertEqual(wavelength_result["oes"]["rowCount"], 4)
        self.assertEqual(wavelength_result["oes"]["lineChart"]["sourcePointCount"], 4)
        self.assertEqual(heatmap_only_result["oes"]["heatmap"]["width"], 3)
        self.assertEqual(heatmap_only_result["oes"]["spectrumChart"]["series"], [])
        self.assertEqual(trajectory_only_result["oes"]["heatmap"]["width"], 0)
        self.assertEqual(trajectory_only_result["oes"]["spectrumChart"]["series"], [])
        self.assertEqual(trajectory_only_result["oes"]["lineChart"]["sourcePointCount"], 4)

    def test_read_parquet_applies_optional_filters(self) -> None:
        """Parquet filter가 가능한 파일은 필요한 step row만 읽어야 합니다."""

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.parquet"
            pd.DataFrame(
                [
                    {"rcp_step": "1D", "value": 10.0},
                    {"rcp_step": "3D", "value": 99.0},
                ]
            ).to_parquet(path, engine="pyarrow")

            frame = selectors.read_parquet(path, filters=[("rcp_step", "==", "1D")])

        self.assertEqual(frame["rcp_step"].tolist(), ["1D"])
        self.assertEqual(frame["value"].tolist(), [10.0])

    def test_meta_options_are_scoped_and_ignore_ipynb_checkpoints(self) -> None:
        """선택값 하위 옵션만 반환하고 checkpoint 폴더는 제외해야 합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for line_id, eqp_id, fdc_bin in [
                ("L1", "EQP1", "BIN1"),
                ("L2", "EQP2", "BIN2"),
            ]:
                target = (
                    root
                    / selectors.RAW_DIR_NAME
                    / line_id
                    / eqp_id
                    / fdc_bin
                    / "2026-06-01"
                    / "trace"
                    / "type=ag"
                    / "ppid=PPID1"
                    / "recipe_id=RCP1"
                    / "priority=1"
                    / "trace_param_name=PRESSURE"
                )
                target.mkdir(parents=True)
            checkpoint_target = (
                root
                / selectors.RAW_DIR_NAME
                / ".ipynb_checkpoints"
                / "BAD_LINE"
                / "BAD_EQP"
                / "BAD_BIN"
            )
            checkpoint_target.mkdir(parents=True)
            ppid_scoped_target = (
                root
                / selectors.RAW_DIR_NAME
                / "L1"
                / "EQP1"
                / "BIN1"
                / "2026-06-01"
                / "trace"
                / "type=ag"
                / "ppid=PPID2"
                / "recipe_id=RCP2"
                / "priority=1"
                / "trace_param_name=PRESSURE"
            )
            ppid_scoped_target.mkdir(parents=True)

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                all_meta = services.get_meta()
                line_meta = services.get_meta({"lineId": "L1"})
                eqp_meta = services.get_meta({"lineId": "L1", "eqpId": "EQP1"})
                fdc_meta = services.get_meta({"lineId": "L1", "eqpId": "EQP1", "fdcBin": "BIN1"})
                ppid_meta = services.get_meta(
                    {
                        "lineId": "L1",
                        "eqpId": "EQP1",
                        "fdcBin": "BIN1",
                        "pmTimestamp": "2026-06-01",
                        "ppid": "PPID1",
                    }
                )

        self.assertEqual(all_meta["lineIds"], ["L1", "L2"])
        self.assertNotIn("BAD_LINE", all_meta["lineIds"])
        self.assertEqual(line_meta["eqpIds"], ["EQP1"])
        self.assertEqual(eqp_meta["fdcBins"], ["BIN1"])
        self.assertEqual(fdc_meta["pmDates"], ["2026-06-01"])
        self.assertEqual(fdc_meta["ppids"], ["PPID1", "PPID2"])
        self.assertEqual(fdc_meta["recipeIds"], ["RCP1", "RCP2"])
        self.assertEqual(ppid_meta["recipeIds"], ["RCP1"])

    def test_initial_meta_does_not_descend_to_slow_deep_options(self) -> None:
        """선택값 없는 초기 메타는 line 목록만 수집하고 깊은 옵션은 비워둡니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            deep_target = (
                root
                / selectors.RAW_DIR_NAME
                / "L1"
                / "EQP1"
                / "BIN1"
                / "2026-06-03 14:23:23"
                / "trace"
                / "type=ag"
                / "ppid=PPID1"
                / "recipe_id=RCP1"
                / "priority=1"
                / "trace_param_name=PRESSURE"
            )
            deep_target.mkdir(parents=True)

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                meta = services.get_meta()

        self.assertEqual(meta["lineIds"], ["L1"])
        self.assertEqual(meta["eqpIds"], [])
        self.assertEqual(meta["ppids"], [])
        self.assertEqual(meta["recipeIds"], [])

    def test_ppid_recipe_meta_does_not_scan_trace_param_depth(self) -> None:
        """PPID/Recipe 메타는 trace_param 하위 크기에 영향을 받지 않습니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            recipe_root = (
                root
                / selectors.RAW_DIR_NAME
                / "L1"
                / "EQP1"
                / "BIN1"
                / "2026-06-03 14:23:23"
                / "trace"
                / "type=ag"
                / "ppid=PPID1"
                / "recipe_id=RCP1"
                / "priority=1"
            )
            for index in range(100):
                (recipe_root / f"trace_param_name=PARAM_{index:03d}").mkdir(parents=True)

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root), PM_COMPARISON_MAX_META_DIRS=12):
                meta = services.get_meta(
                    {
                        "lineId": "L1",
                        "eqpId": "EQP1",
                        "fdcBin": "BIN1",
                        "pmTimestamp": "2026-06-03",
                    }
                )

        self.assertEqual(meta["ppids"], ["PPID1"])
        self.assertEqual(meta["recipeIds"], ["RCP1"])
        self.assertEqual(meta["traceParamNames"], [])

    def test_selected_plain_meta_uses_direct_path_candidates(self) -> None:
        """선택값이 있는 plain 메타는 sibling 전체 순회에 의존하지 않습니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for index in range(50):
                (
                    root
                    / selectors.RAW_DIR_NAME
                    / f"L_UNUSED_{index:02d}"
                    / "EQP_UNUSED"
                    / "BIN_UNUSED"
                    / "2026-06-03 14:23:23"
                ).mkdir(parents=True)
            target = (
                root
                / selectors.RAW_DIR_NAME
                / "L1"
                / "EQP1"
                / "BIN1"
                / "2026-06-03 14:23:23"
                / "trace"
                / "type=ag"
                / "ppid=PPID1"
                / "recipe_id=RCP1"
                / "priority=1"
                / "trace_param_name=PRESSURE"
            )
            target.mkdir(parents=True)

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root), PM_COMPARISON_MAX_META_DIRS=8):
                meta = services.get_meta(
                    {
                        "lineId": "L1",
                        "eqpId": "EQP1",
                        "fdcBin": "BIN1",
                        "pmTimestamp": "2026-06-03",
                    }
                )

        self.assertEqual(meta["ppids"], ["PPID1"])
        self.assertEqual(meta["recipeIds"], ["RCP1"])

    def test_score_fallback_meta_options_are_scoped(self) -> None:
        """raw data가 없을 때 score fallback 메타도 선택값으로 좁혀야 합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for line_id, eqp_id, chamber_id in [
                ("L1", "EQP1", "BIN1"),
                ("L2", "EQP2", "BIN2"),
            ]:
                target = (
                    root
                    / selectors.SCORE_DIR_NAME
                    / selectors.SCORE_DATA_DIR_NAME
                    / f"line_id={line_id}"
                    / f"eqp_id={eqp_id}"
                    / f"chamber_id={chamber_id}"
                    / "type=ag"
                    / "data_type=trace"
                )
                target.mkdir(parents=True)
            checkpoint_target = (
                root
                / selectors.SCORE_DIR_NAME
                / selectors.SCORE_DATA_DIR_NAME
                / ".ipynb_checkpoints"
                / "line_id=BAD_LINE"
            )
            checkpoint_target.mkdir(parents=True)

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                all_meta = services.get_meta()
                line_meta = services.get_meta({"lineId": "L1"})
                eqp_meta = services.get_meta({"lineId": "L1", "eqpId": "EQP1"})

        self.assertEqual(all_meta["lineIds"], ["L1", "L2"])
        self.assertEqual(line_meta["eqpIds"], ["EQP1"])
        self.assertEqual(eqp_meta["fdcBins"], ["BIN1"])

    def test_meta_options_after_pm_timestamp_do_not_require_raw_dt_match(self) -> None:
        """score PM 날짜와 raw dt 폴더명이 달라도 하위 옵션을 반환해야 합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_target = (
                root
                / selectors.RAW_DIR_NAME
                / "L1"
                / "EQP1"
                / "BIN1"
                / "20260601"
                / "trace"
                / "type=ag"
                / "ppid=PPID1"
                / "recipe_id=RCP1"
                / "priority=1"
                / "trace_param_name=PRESSURE"
            )
            raw_target.mkdir(parents=True)
            score_target = (
                root
                / selectors.SCORE_DIR_NAME
                / "line_id=L1"
                / "eqp_id=EQP1"
                / "type=ag"
                / "data_type=trace"
            )
            score_target.mkdir(parents=True)
            pd.DataFrame([{"날짜": "2026-06-01"}]).to_parquet(score_target / "part-000.parquet", engine="pyarrow")

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                timestamp_meta = services.get_meta(
                    {
                        "lineId": "L1",
                        "eqpId": "EQP1",
                        "fdcBin": "BIN1",
                        "pmTimestamp": "2026-06-01",
                    }
                )

        self.assertEqual(timestamp_meta["pmDates"], ["2026-06-01"])
        self.assertEqual(timestamp_meta["ppids"], ["PPID1"])
        self.assertEqual(timestamp_meta["recipeIds"], ["RCP1"])

    def test_pm_timestamp_scopes_ppid_options_by_raw_dt(self) -> None:
        """PM 시점 선택 후 PPID 후보는 같은 raw dt 하위 값만 반환합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for dt_value, ppid in [("2026-06-01", "PPID1"), ("2026-06-02", "PPID2")]:
                raw_target = (
                    root
                    / selectors.RAW_DIR_NAME
                    / "L1"
                    / "EQP1"
                    / "BIN1"
                    / dt_value
                    / "trace"
                    / "type=ag"
                    / f"ppid={ppid}"
                    / "recipe_id=RCP1"
                    / "priority=1"
                    / "trace_param_name=PRESSURE"
                )
                raw_target.mkdir(parents=True)

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                timestamp_meta = services.get_meta(
                    {
                        "lineId": "L1",
                        "eqpId": "EQP1",
                        "fdcBin": "BIN1",
                        "pmTimestamp": "2026-06-01",
                    }
                )

        self.assertEqual(timestamp_meta["ppids"], ["PPID1"])

    def test_pm_timestamp_matches_datetime_raw_dt_folder(self) -> None:
        """날짜 선택값은 시각이 붙은 raw dt 폴더와도 매칭됩니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for dt_value, ppid in [("2026-06-03 14:23:23", "PPID1"), ("2026-06-04 09:00:00", "PPID2")]:
                raw_target = (
                    root
                    / selectors.RAW_DIR_NAME
                    / "L1"
                    / "EQP1"
                    / "BIN1"
                    / dt_value
                    / "trace"
                    / "type=ag"
                    / f"ppid={ppid}"
                    / "recipe_id=RCP1"
                    / "priority=1"
                    / "trace_param_name=PRESSURE"
                )
                raw_target.mkdir(parents=True)

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                timestamp_meta = services.get_meta(
                    {
                        "lineId": "L1",
                        "eqpId": "EQP1",
                        "fdcBin": "BIN1",
                        "pmTimestamp": "2026-06-03",
                    }
                )

        self.assertEqual(timestamp_meta["ppids"], ["PPID1"])

    def test_fdc_meta_prefers_raw_datetime_pm_dates(self) -> None:
        """raw dt가 시각 포함 폴더명이면 PM 시점 옵션도 해당 값을 반환합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_target = (
                root
                / selectors.RAW_DIR_NAME
                / "line_id"
                / "eqp_id"
                / "A"
                / "2026-06-16 09:28:00"
                / "trace"
                / "type=ag"
                / "ppid=abc"
                / "recipe_id=abc"
                / "priority=B"
                / "trace_param_name=abc"
            )
            raw_target.mkdir(parents=True)

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                meta = services.get_meta(
                    {
                        "lineId": "line_id",
                        "eqpId": "eqp_id",
                        "fdcBin": "A",
                    }
                )
                selected_meta = services.get_meta(
                    {
                        "lineId": "line_id",
                        "eqpId": "eqp_id",
                        "fdcBin": "A",
                        "pmTimestamp": "2026-06-16 09:28:00",
                    }
                )

        self.assertEqual(meta["pmDates"], ["2026-06-16 09:28:00"])
        self.assertEqual(selected_meta["ppids"], ["abc"])
        self.assertEqual(selected_meta["recipeIds"], ["abc"])

    def test_compare_without_dt_values_limits_raw_lookup_to_pm_timestamp(self) -> None:
        """dtValues가 없어도 raw 조회는 선택 PM 시점 partition으로 제한됩니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for dt_value, sensor, value in [
                ("2026-06-01", "PRESSURE", 30.0),
                ("2026-06-02", "TEMP", 99.0),
            ]:
                raw_target = (
                    root
                    / selectors.RAW_DIR_NAME
                    / "line_id=L1"
                    / "eqp_id=EQP1"
                    / "fdc_bin=BIN1"
                    / f"dt={dt_value}"
                    / "type=ag"
                    / "ppid=PPID1"
                    / "recipe_id=RCP1"
                    / "data_source=trace"
                    / f"trace_param_name={sensor}"
                    / "batch=001"
                )
                raw_target.mkdir(parents=True)
                pd.DataFrame(
                    [{"날짜": dt_value, "time": f"{dt_value}T01:00:00Z", "value": value}]
                ).to_parquet(raw_target / "part-000.parquet", engine="pyarrow")

            score_target = self._score_base(root, data_type="trace")
            score_target.mkdir(parents=True)
            pd.DataFrame(
                [
                    {
                        "line_id": "L1",
                        "eqp_id": "EQP1",
                        "날짜": "2026-06-01",
                        "type": "ag",
                        "data_type": "trace",
                        "item_name": "PRESSURE",
                        "score": 0.12,
                    }
                ]
            ).to_parquet(score_target / "part-000.parquet", engine="pyarrow")
            selection = {
                "lineId": "L1",
                "eqpId": "EQP1",
                "fdcBin": "BIN1",
                "type": "ag",
                "ppid": "PPID1",
                "recipeId": "RCP1",
                "pmTimestamp": "2026-06-01",
                "traceDataSource": "trace",
                "oesDataSource": "oes",
            }

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                result = services.compare_pm_window(selection)

        self.assertEqual(result["trace"]["fileCount"], 1)
        self.assertEqual(result["trace"]["rowCount"], 1)
        self.assertEqual(result["trace"]["trendRows"][0]["traceParamName"], "PRESSURE")

    def test_compare_can_skip_raw_detail_for_summary_request(self) -> None:
        """초기 summary 요청은 raw 상세 파일 읽기를 생략할 수 있습니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_trace_sample(root)
            selection = {
                "lineId": "L1",
                "eqpId": "EQP1",
                "fdcBin": "BIN1",
                "type": "ag",
                "ppid": "PPID1",
                "recipeId": "RCP1",
                "pmTimestamp": "2026-06-01",
                "traceParamNames": ["PRESSURE"],
                "traceDataSource": "trace",
                "oesDataSource": "oes",
                "includeDetails": False,
            }

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                result = services.compare_pm_window(selection)

        self.assertEqual(result["trace"]["summaryRows"][0]["traceSensor"], "PRESSURE")
        self.assertEqual(result["trace"]["fileCount"], 0)
        self.assertEqual(result["trace"]["rowCount"], 0)
        self.assertEqual(result["trace"]["trendRows"], [])

    def test_serializer_accepts_datetime_dt_values(self) -> None:
        """raw dt 폴더명과 같은 공백/콜론 포함 날짜 값을 허용합니다."""

        serializer = PmComparisonRequestSerializer(
            data={
                "lineId": "L1",
                "eqpId": "EQP1",
                "pmTimestamp": "2026-06-03 14:23:23",
                "dtValues": ["2026-06-03 14:23:23"],
                "maxPoints": 2000,
                "xStart": 0,
                "xEnd": 100,
                "heatmapXBins": 1200,
                "heatmapYBins": 100,
                "includeOesHeatmap": False,
                "includeOesSpectrum": False,
                "includeTraceDetails": False,
                "includeOesDetails": True,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_compare_pm_window_returns_empty_response_without_score_rows(self) -> None:
        """result 파일이 없을 때도 pm_date KeyError 없이 빈 응답을 반환합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / selectors.RAW_DIR_NAME).mkdir()
            (root / selectors.SCORE_DIR_NAME).mkdir()
            selection = {
                "lineId": "L1",
                "eqpId": "EQP1",
                "fdcBin": "BIN1",
                "type": "ag",
                "ppid": "PPID1",
                "recipeId": "RCP1",
                "pmTimestamp": "2026-06-01",
                "traceParamNames": ["PRESSURE"],
                "dtValues": ["2026-06-01"],
                "traceDataSource": "trace",
                "oesDataSource": "oes",
            }

            with override_settings(PM_COMPARISON_DATA_ROOT=str(root)):
                result = services.compare_pm_window(selection)

        self.assertEqual(result["trace"]["summaryRows"], [])
        self.assertEqual(result["oes"]["summaryRows"], [])
        self.assertEqual(result["window"]["pmDate"], "2026-06-01")
