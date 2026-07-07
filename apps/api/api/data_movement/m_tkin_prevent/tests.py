"""m_tkin_prevent 적재 앱 테스트입니다."""

from __future__ import annotations

import zlib
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from api.data_movement.common.services.file_loader import list_data_files
from api.data_movement.common.services.postgres_copy import CopyReplaceResult
from api.data_movement.m_tkin_prevent.management.commands.load_m_tkin_prevent import services
from api.data_movement.m_tkin_prevent.models import MTkinPrevent, MTkinPreventLoadJob
from api.data_movement.m_tkin_prevent.services import loader as loader_module
from api.data_movement.m_tkin_prevent.services import spec
from api.data_movement.m_tkin_prevent.services.loader import LoadFileOutcome, LoadRunSummary


def _write_deflate_tkin_csv(path: Path, rows: list[list[str]]) -> None:
    """테스트용 m_tkin_prevent deflate CSV 파일을 생성합니다."""

    payload = "\n".join("\x03".join(row) for row in rows).encode("utf-8")
    path.write_bytes(zlib.compress(payload))


def _build_tkin_row(*, line_id: str = "L1", operator_name: str = "operator") -> list[str]:
    """spec 컬럼 순서에 맞춘 테스트용 m_tkin_prevent row를 생성합니다."""

    row = [""] * len(spec.COLUMNS)
    row[0] = operator_name
    row[6] = line_id
    row[8] = "0"
    row[10] = "process"
    row[25] = "0"
    row[26] = "0"
    row[29] = "0"
    row[30] = "0"
    row[32] = "0"
    row[40] = "0"
    row[43] = "0"
    return row


class MTkinPreventStructureTests(SimpleTestCase):
    """m_tkin_prevent 앱 구조와 command 경계를 검증합니다."""

    def test_model_table_names_match_expected_tables(self) -> None:
        """모델의 실제 DB 테이블명이 합의한 이름과 일치하는지 확인합니다."""

        self.assertEqual(MTkinPrevent._meta.db_table, "m_tkin_prevent")
        self.assertEqual(MTkinPreventLoadJob._meta.db_table, "m_tkin_prevent_load_job")

    def test_model_indexes_support_observer_matrix_query(self) -> None:
        """Observer matrix 조회 조건을 지원하는 index가 있는지 확인합니다."""

        index_names = {index.name for index in MTkinPrevent._meta.indexes}

        self.assertIn("idx_mtk_prc_stp_lvl_eqp", index_names)

    def test_list_data_files_returns_sorted_limited_deflate_files(self) -> None:
        """파일 목록 helper가 이름순 및 limit을 적용하는지 확인합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "b.csv.deflate").touch()
            (root / "a.csv.deflate").touch()
            (root / "ignore.txt").touch()

            files = list_data_files(data_dir=root, pattern="*.csv.deflate", limit=1)

        self.assertEqual([path.name for path in files], ["a.csv.deflate"])

    @patch.object(services, "load_m_tkin_prevent_files")
    def test_command_reports_no_files(self, load_files) -> None:
        """처리 파일이 없으면 성공 메시지만 출력하는지 확인합니다."""

        load_files.return_value = LoadRunSummary(outcomes=[])
        stdout = StringIO()

        call_command("load_m_tkin_prevent", stdout=stdout)

        self.assertIn("처리할 파일 없음", stdout.getvalue())

    @patch.object(services, "load_m_tkin_prevent_files")
    def test_command_raises_when_any_file_failed(self, load_files) -> None:
        """실패 파일이 하나라도 있으면 Airflow가 실패를 감지하도록 예외를 발생시킵니다."""

        load_files.return_value = LoadRunSummary(
            outcomes=[
                LoadFileOutcome(
                    file_name="bad.csv.deflate",
                    status=MTkinPreventLoadJob.Status.FAILED,
                    row_count=0,
                    replace_values=[],
                    error_message="line_id 없음",
                )
            ]
        )

        with self.assertRaises(CommandError):
            call_command("load_m_tkin_prevent", stdout=StringIO())


@override_settings(DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS=0, DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS=0)
class MTkinPreventLifecycleTests(TestCase):
    """FTP 수신 파일과 loader 처리 파일의 lifecycle을 검증합니다."""

    def test_loader_replaces_line_rows_in_database(self) -> None:
        """실제 COPY 경로로 line_id 단위 기존 row를 교체합니다."""

        MTkinPrevent.objects.create(line_id="L1", operator_name="old")
        MTkinPrevent.objects.create(line_id="L2", operator_name="keep")

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "a.csv.deflate"
            _write_deflate_tkin_csv(
                source,
                [_build_tkin_row(line_id="L1", operator_name="new")],
            )

            summary = loader_module.load_m_tkin_prevent_files(data_dir=root)

        self.assertEqual(summary.success_count, 1)
        self.assertFalse(MTkinPrevent.objects.filter(line_id="L1", operator_name="old").exists())
        self.assertTrue(MTkinPrevent.objects.filter(line_id="L2", operator_name="keep").exists())
        loaded_row = MTkinPrevent.objects.get(line_id="L1")
        self.assertEqual(loaded_row.operator_name, "new")
        self.assertIsNotNone(loaded_row.id)

    @patch.object(loader_module, "copy_replace_rows")
    @patch.object(loader_module, "extract_replace_values")
    @patch.object(loader_module, "read_deflate_csv_file")
    def test_loader_claims_incoming_file_and_deletes_on_success(
        self,
        read_file,
        extract_values,
        copy_rows,
    ) -> None:
        """성공 시 incoming 파일을 processing 경유 삭제합니다."""

        read_file.return_value = type("Frame", (), {"shape": (1, 50)})()
        extract_values.return_value = ["L1"]
        copy_rows.return_value = CopyReplaceResult(row_count=1, column_count=50, replace_values=["L1"])

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "a.csv.deflate"
            source.write_text("payload", encoding="utf-8")

            summary = loader_module.load_m_tkin_prevent_files(data_dir=root)

            self.assertEqual(summary.success_count, 1)
            self.assertFalse(source.exists())
            self.assertFalse((root / "archive").exists())
            self.assertFalse((root / "error").exists())
            self.assertEqual(list((root / "processing").iterdir()), [])

        self.assertEqual(MTkinPreventLoadJob.objects.filter(status=MTkinPreventLoadJob.Status.SUCCESS).count(), 1)

    @patch.object(loader_module, "read_deflate_csv_file")
    def test_loader_deletes_failed_file(self, read_file) -> None:
        """처리 실패 시 선점 파일도 삭제합니다."""

        read_file.side_effect = ValueError("broken file")

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "bad.csv.deflate"
            source.write_text("payload", encoding="utf-8")

            summary = loader_module.load_m_tkin_prevent_files(data_dir=root)

            self.assertEqual(summary.failure_count, 1)
            self.assertFalse(source.exists())
            self.assertFalse((root / "archive").exists())
            self.assertFalse((root / "error").exists())
            self.assertEqual(list((root / "processing").iterdir()), [])

        self.assertEqual(MTkinPreventLoadJob.objects.filter(status=MTkinPreventLoadJob.Status.FAILED).count(), 1)
