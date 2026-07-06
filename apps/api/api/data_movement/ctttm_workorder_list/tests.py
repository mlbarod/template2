"""ctttm_workorder_list 적재 앱 테스트입니다."""

from __future__ import annotations

import zlib
from datetime import datetime
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from api.data_movement.ctttm_workorder_list.management.commands.load_ctttm_workorder_list import services
from api.data_movement.ctttm_workorder_list.models import CtttmWorkorderList, CtttmWorkorderListLoadJob
from api.data_movement.ctttm_workorder_list.services.fast_csv import (
    build_fast_csv_plan,
    write_fast_selected_deflate_csv,
)
from api.data_movement.ctttm_workorder_list.services import loader as loader_module
from api.data_movement.ctttm_workorder_list import selectors
from api.data_movement.ctttm_workorder_list.services import spec
from api.data_movement.ctttm_workorder_list.services.loader import LoadFileOutcome, LoadRunSummary


def _write_deflate_csv(path: Path, rows: list[list[str]]) -> None:
    """테스트용 deflate CSV 파일을 생성합니다."""

    payload = "\n".join(spec.FILE_SEPARATOR.join(row) for row in rows).encode("utf-8")
    path.write_bytes(zlib.compress(payload))


def _write_fast_selected_csv(*, source: Path, selected: Path, source_type: str) -> int:
    """테스트용 source_type 기준 fast selected CSV를 생성합니다."""

    plan = build_fast_csv_plan(
        file_columns=spec.get_file_columns(source_type=source_type),
        db_columns=spec.DB_COLUMNS,
        column_sources=spec.COLUMN_SOURCES,
        row_filters=spec.ROW_FILTERS,
        min_datetime_filters={
            spec.CREATE_DATE_FILTER_COLUMN: datetime(2025, 11, 29, 0, 0, 0),
        },
    )
    return write_fast_selected_deflate_csv(
        source_path=source,
        output_path=selected,
        plan=plan,
        separator=spec.FILE_SEPARATOR,
    )


def _build_mst_workorder_row(
    *,
    workorder_id: str = "WO1",
    line_id: str = "L1",
    asset: str = "EQP1",
    area_name: str = "ETCH",
    create_date: str = "2999-01-01 00:00:00",
) -> list[str]:
    """MST DDL 순서에 맞춘 테스트용 workorder row를 생성합니다."""

    row = [""] * len(spec.MST_FILE_COLUMNS)
    row[0] = workorder_id
    row[1] = line_id
    row[5] = "desc"
    row[6] = asset
    row[8] = "PM"
    row[11] = area_name
    row[12] = "2026-05-29 14:00:00"
    row[13] = "2026-05-29 15:00:00"
    row[31] = create_date
    return row


def _build_mnu_workorder_row(
    *,
    workorder_id: str = "WO1",
    line_id: str = "L1",
    asset: str = "EQP1",
    area_name: str = "ETCH",
    create_date: str = "2999-01-01 00:00:00",
) -> list[str]:
    """MNU DDL 순서에 맞춘 테스트용 workorder row를 생성합니다."""

    row = [""] * len(spec.MNU_FILE_COLUMNS)
    row[0] = workorder_id
    row[1] = line_id
    row[2] = "desc"
    row[3] = asset
    row[4] = "PM"
    row[7] = area_name
    row[10] = "2026-05-29 14:00:00"
    row[12] = "2026-05-29 15:00:00"
    row[27] = create_date
    row[31] = "Y"
    return row


class CtttmWorkorderListStructureTests(SimpleTestCase):
    """ctttm_workorder_list 앱 구조와 파일 spec을 검증합니다."""

    def test_model_table_names_match_expected_tables(self) -> None:
        """모델의 실제 DB 테이블명이 합의한 이름과 일치하는지 확인합니다."""

        self.assertEqual(CtttmWorkorderList._meta.db_table, "ctttm_workorder_list")
        self.assertEqual(CtttmWorkorderListLoadJob._meta.db_table, "ctttm_workorder_list_load_job")

    def test_parse_source_file_name_extracts_source_type(self) -> None:
        """파일명에서 source_type과 timestamp를 추출하는지 확인합니다."""

        info = loader_module.parse_source_file_name(file_name="CT_MNU_WORKORDER_20260529_1400.csv.deflate")

        self.assertEqual(info.source_type, "MNU")
        self.assertEqual(info.file_timestamp, "20260529_1400")

    def test_parse_source_file_name_accepts_numeric_prefix(self) -> None:
        """숫자 prefix가 붙은 파일명에서도 source_type과 timestamp를 추출합니다."""

        info = loader_module.parse_source_file_name(
            file_name="69623_CT_MNU_WORKORDER_20260530_1600.csv.deflate",
        )

        self.assertEqual(info.source_type, "MNU")
        self.assertEqual(info.file_timestamp, "20260530_1600")

    def test_parse_source_file_name_ignores_file_name_case(self) -> None:
        """파일명 대소문자가 달라도 source_type과 timestamp를 추출합니다."""

        info = loader_module.parse_source_file_name(
            file_name="69623_ct_mst_workorder_20260530_1600.CSV.DEFLATE",
        )

        self.assertEqual(info.source_type, "MST")
        self.assertEqual(info.file_timestamp, "20260530_1600")

    def test_file_columns_match_source_ddl_widths(self) -> None:
        """source별 DDL 컬럼 수가 파일 spec에 반영되어 있는지 확인합니다."""

        self.assertEqual(len(spec.MST_FILE_COLUMNS), 55)
        self.assertEqual(len(spec.MNU_FILE_COLUMNS), 49)
        self.assertEqual(
            build_fast_csv_plan(
                file_columns=spec.get_file_columns(source_type="MST"),
                db_columns=spec.DB_COLUMNS,
                column_sources=spec.COLUMN_SOURCES,
                row_filters=spec.ROW_FILTERS,
                min_datetime_filters={
                    spec.CREATE_DATE_FILTER_COLUMN: datetime(2025, 11, 29, 0, 0, 0),
                },
            ).max_required_index,
            31,
        )
        self.assertEqual(
            build_fast_csv_plan(
                file_columns=spec.get_file_columns(source_type="MNU"),
                db_columns=spec.DB_COLUMNS,
                column_sources=spec.COLUMN_SOURCES,
                row_filters=spec.ROW_FILTERS,
                min_datetime_filters={
                    spec.CREATE_DATE_FILTER_COLUMN: datetime(2025, 11, 29, 0, 0, 0),
                },
            ).max_required_index,
            27,
        )

    def test_write_fast_selected_deflate_csv_maps_mst_asset_to_eqp_id(self) -> None:
        """MST 파일에서 ETCH와 CREATE_DATE 기준을 통과한 행만 추출합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.csv.deflate"
            selected = root / "selected.csv"
            _write_deflate_csv(
                source,
                [
                    _build_mst_workorder_row(
                        workorder_id="WO1",
                        area_name="ETCH",
                        create_date="20260530 160000",
                    ),
                    _build_mst_workorder_row(workorder_id="WO2", area_name="PHOTO"),
                    _build_mst_workorder_row(
                        workorder_id="WO3",
                        area_name="ETCH",
                        create_date="2000-01-01 00:00:00",
                    ),
                ],
            )

            row_count = _write_fast_selected_csv(source=source, selected=selected, source_type="MST")

            self.assertEqual(row_count, 1)
            self.assertEqual(
                selected.read_text(encoding="utf-8").strip(),
                "WO1,L1,EQP1,PM,desc,2026-05-29 14:00:00,2026-05-29 15:00:00",
            )

    def test_write_fast_selected_deflate_csv_maps_mnu_asset_to_eqp_id(self) -> None:
        """MNU 파일에서 source별 다른 컬럼 순서를 사용해 행을 추출합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.csv.deflate"
            selected = root / "selected.csv"
            _write_deflate_csv(
                source,
                [
                    _build_mnu_workorder_row(
                        workorder_id="MNU1",
                        line_id="L2",
                        asset="EQP2",
                        area_name="ETCH",
                        create_date="20260530 160000",
                    ),
                    _build_mnu_workorder_row(workorder_id="MNU2", area_name="PHOTO"),
                ],
            )

            row_count = _write_fast_selected_csv(source=source, selected=selected, source_type="MNU")

            self.assertEqual(row_count, 1)
            self.assertEqual(
                selected.read_text(encoding="utf-8").strip(),
                "MNU1,L2,EQP2,PM,desc,2026-05-29 14:00:00,2026-05-29 15:00:00",
            )

    def test_write_fast_selected_deflate_csv_accepts_timezone_aware_create_date(self) -> None:
        """timezone 포함 CREATE_DATE도 cutoff와 비교할 수 있는지 확인합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.csv.deflate"
            selected = root / "selected.csv"
            _write_deflate_csv(
                source,
                [
                    _build_mnu_workorder_row(
                        workorder_id="MNU_TZ",
                        create_date="2999-01-01T00:00:00.000Z",
                    ),
                ],
            )

            row_count = _write_fast_selected_csv(source=source, selected=selected, source_type="MNU")

            self.assertEqual(row_count, 1)

    @patch.object(services, "load_ctttm_workorder_list_files")
    def test_command_reports_no_files(self, load_files) -> None:
        """처리 파일이 없으면 성공 메시지만 출력하는지 확인합니다."""

        load_files.return_value = LoadRunSummary(outcomes=[])
        stdout = StringIO()

        call_command("load_ctttm_workorder_list", stdout=stdout)

        self.assertIn("처리할 파일 없음", stdout.getvalue())

    @patch.object(services, "load_ctttm_workorder_list_files")
    def test_command_raises_when_any_file_failed(self, load_files) -> None:
        """실패 파일이 하나라도 있으면 Airflow가 실패를 감지하도록 예외를 발생시킵니다."""

        load_files.return_value = LoadRunSummary(
            outcomes=[
                LoadFileOutcome(
                    file_name="bad.csv.deflate",
                    status=CtttmWorkorderListLoadJob.Status.FAILED,
                    row_count=0,
                    error_message="invalid",
                )
            ]
        )

        with self.assertRaises(CommandError):
            call_command("load_ctttm_workorder_list", stdout=StringIO())


@override_settings(DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS=0, DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS=0)
class CtttmWorkorderListLifecycleTests(TestCase):
    """CTTTM workorder 파일 처리 lifecycle을 검증합니다."""

    def test_load_workorder_descriptions_by_ids_returns_latest_description(self) -> None:
        """workorder_id별 최신 작업 설명을 반환합니다."""

        CtttmWorkorderList.objects.create(
            source_type="MST",
            workorder_id="WO1",
            description="old title",
            inprg_date="2026-01-01T10:00:00Z",
        )
        CtttmWorkorderList.objects.create(
            source_type="MST",
            workorder_id="WO1",
            description="new title",
            inprg_date="2026-01-01T11:00:00Z",
        )
        CtttmWorkorderList.objects.create(
            source_type="MST",
            workorder_id="WO2",
            description="",
        )

        descriptions = selectors.load_workorder_descriptions_by_ids(workorder_ids=["WO1", "WO2", "WO1"])

        self.assertEqual(descriptions, {"WO1": "new title"})

    def test_loader_replaces_source_rows_in_database(self) -> None:
        """실제 COPY 경로로 source_type 단위 기존 row를 교체합니다."""

        CtttmWorkorderList.objects.create(
            source_type="MST",
            workorder_id="OLD",
            line_id="OLD_LINE",
            eqp_id="OLD_EQP",
        )
        CtttmWorkorderList.objects.create(
            source_type="MNU",
            workorder_id="KEEP",
            line_id="KEEP_LINE",
            eqp_id="KEEP_EQP",
        )

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "69623_CT_MST_WORKORDER_20260529_1400.csv.deflate"
            _write_deflate_csv(source, [_build_mst_workorder_row(workorder_id="NEW", line_id="L2", asset="EQP2")])

            summary = loader_module.load_ctttm_workorder_list_files(data_dir=root)

        self.assertEqual(summary.success_count, 1)
        self.assertFalse(CtttmWorkorderList.objects.filter(source_type="MST", workorder_id="OLD").exists())
        self.assertTrue(CtttmWorkorderList.objects.filter(source_type="MNU", workorder_id="KEEP").exists())
        loaded_row = CtttmWorkorderList.objects.get(source_type="MST", workorder_id="NEW")
        self.assertEqual(loaded_row.line_id, "L2")
        self.assertEqual(loaded_row.eqp_id, "EQP2")
        self.assertEqual(loaded_row.eqp_id_lookup, "EQP2")

    @patch.object(loader_module, "_replace_source_rows")
    def test_loader_replaces_source_and_deletes_processing_file(self, replace_rows) -> None:
        """성공 시 source 단위 교체를 호출하고 파일을 삭제합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "CT_MST_WORKORDER_20260529_1400.csv.deflate"
            _write_deflate_csv(source, [_build_mst_workorder_row(workorder_id="WO2", asset="EQP2")])

            summary = loader_module.load_ctttm_workorder_list_files(data_dir=root)

            self.assertEqual(summary.success_count, 1)
            self.assertFalse(source.exists())
            self.assertEqual(list((root / "processing").iterdir()), [])

        replace_rows.assert_called_once()
        self.assertEqual(CtttmWorkorderListLoadJob.objects.filter(status="success").count(), 1)

    @patch.object(loader_module, "_replace_source_rows", side_effect=ValueError("copy failed"))
    def test_loader_deletes_file_even_when_replace_fails(self, replace_rows) -> None:
        """DB 반영 실패 시에도 처리 파일을 삭제하고 실패 이력을 남깁니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "CT_MNU_WORKORDER_20260529_1400.csv.deflate"
            _write_deflate_csv(source, [_build_mnu_workorder_row()])

            summary = loader_module.load_ctttm_workorder_list_files(data_dir=root)

            self.assertEqual(summary.failure_count, 1)
            self.assertFalse(source.exists())
            self.assertEqual(list((root / "processing").iterdir()), [])

        replace_rows.assert_called_once()
        self.assertEqual(CtttmWorkorderListLoadJob.objects.filter(status="failed").count(), 1)
