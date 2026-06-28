"""station_master 적재 앱 테스트입니다."""

from __future__ import annotations

import zlib
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from api.data_movement.common.services.postgres_copy import CopyFullReplaceResult
from api.data_movement.station_master.management.commands.load_station_master import services
from api.data_movement.station_master.models import StationMaster, StationMasterLoadJob
from api.data_movement.station_master.selectors import list_distinct_sdwt_prod_lookup_values
from api.data_movement.station_master.services import loader as loader_module
from api.data_movement.station_master.services import spec
from api.data_movement.station_master.services.loader import LoadFileOutcome, LoadRunSummary


def _write_deflate_station_csv(path: Path, rows: list[list[str]]) -> None:
    """테스트용 station_master deflate CSV 파일을 생성합니다."""

    payload = "\n".join(spec.FILE_SEPARATOR.join(row) for row in rows).encode("utf-8")
    path.write_bytes(zlib.compress(payload))


def _build_station_row(*, station: str = "E01", machine_id: str = "M01") -> list[str]:
    """spec 컬럼 순서에 맞춘 테스트용 station_master row를 생성합니다."""

    row = [""] * len(spec.COLUMNS)
    row[0] = "AREA1"
    row[1] = station
    row[2] = "101"
    row[3] = "M1"
    row[5] = machine_id
    row[6] = "TYPE1"
    row[7] = "A"
    row[8] = "Station"
    row[15] = "SDWT_PROD"
    row[17] = "1.5"
    row[18] = "2"
    row[20] = "3"
    row[21] = "4"
    row[22] = "5"
    row[24] = "20260620"
    row[30] = "6"
    row[34] = "PRC"
    row[50] = "Y"
    row[51] = "ADDR01"
    row[52] = "EFF"
    row[53] = "INCLD"
    row[54] = "MAKER"
    return row


class StationMasterStructureTests(SimpleTestCase):
    """station_master 앱 구조와 command 경계를 검증합니다."""

    def test_model_table_names_match_expected_tables(self) -> None:
        """모델의 실제 DB 테이블명이 합의한 이름과 일치하는지 확인합니다."""

        self.assertEqual(StationMaster._meta.db_table, "station_master")
        self.assertEqual(StationMasterLoadJob._meta.db_table, "station_master_load_job")

    @patch.object(services, "load_station_master_files")
    def test_command_reports_no_files(self, load_files) -> None:
        """처리 파일이 없으면 성공 메시지만 출력하는지 확인합니다."""

        load_files.return_value = LoadRunSummary(outcomes=[])
        stdout = StringIO()

        call_command("load_station_master", stdout=stdout)

        self.assertIn("처리할 파일 없음", stdout.getvalue())

    @patch.object(services, "load_station_master_files")
    def test_command_raises_when_any_file_failed(self, load_files) -> None:
        """실패 파일이 하나라도 있으면 Airflow가 실패를 감지하도록 예외를 발생시킵니다."""

        load_files.return_value = LoadRunSummary(
            outcomes=[
                LoadFileOutcome(
                    file_name="bad.csv.deflate",
                    status=StationMasterLoadJob.Status.FAILED,
                    row_count=0,
                    error_message="broken file",
                )
            ]
        )

        with self.assertRaises(CommandError):
            call_command("load_station_master", stdout=StringIO())


@override_settings(DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS=0, DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS=0)
class StationMasterLifecycleTests(TestCase):
    """station_master 수신 파일과 loader 처리 파일의 생명주기를 검증합니다."""

    def test_list_distinct_sdwt_prod_lookup_values_returns_normalized_values(self) -> None:
        """빈 lookup을 제외하고 station_master 소속 lookup 값 집합을 반환합니다."""

        StationMaster.objects.create(station="E01", sdwt_prod="sd-10")
        StationMaster.objects.create(station="E02", sdwt_prod=" SD-20 ")
        StationMaster.objects.create(station="E03", sdwt_prod="")
        StationMaster.objects.create(station="E04", sdwt_prod=None)

        values = list_distinct_sdwt_prod_lookup_values()

        self.assertEqual(values, {"SD-10", "SD-20"})

    def test_loader_replaces_all_rows_in_database(self) -> None:
        """실제 COPY 경로로 기존 전체 row를 새 파일 내용으로 교체합니다."""

        StationMaster.objects.create(station="OLD", machine_id="OLD_MACHINE")

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "86114_STATION_MASTER_20260620.csv.deflate"
            _write_deflate_station_csv(
                source,
                [
                    _build_station_row(station="E01", machine_id="M01"),
                    _build_station_row(station="e02", machine_id="M02"),
                    _build_station_row(station="ST03", machine_id="M03"),
                ],
            )

            summary = loader_module.load_station_master_files(data_dir=root)

        self.assertEqual(summary.success_count, 1)
        self.assertFalse(StationMaster.objects.filter(station="OLD").exists())
        self.assertEqual(StationMaster.objects.count(), 2)
        self.assertFalse(StationMaster.objects.filter(station="ST03").exists())
        loaded_row = StationMaster.objects.get(station="E01")
        self.assertEqual(loaded_row.station_lookup, "E01")
        self.assertEqual(loaded_row.sdwt_prod_lookup, "SDWT_PROD")
        self.assertEqual(loaded_row.prc_group_lookup, "PRC")
        self.assertEqual(loaded_row.machine_id, "M01")
        self.assertEqual(loaded_row.machine_time, 1.5)
        self.assertEqual(loaded_row.da_date, "20260620")
        self.assertEqual(loaded_row.purge_target_yn, "Y")
        self.assertEqual(loaded_row.addr_book_id, "ADDR01")
        self.assertEqual(loaded_row.maker_name, "MAKER")

    def test_read_station_frame_keeps_e_station_rows_only(self) -> None:
        """파일 읽기 단계에서 station이 E로 시작하는 row만 남깁니다."""

        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "86114_STATION_MASTER_20260620.csv.deflate"
            _write_deflate_station_csv(
                source,
                [
                    _build_station_row(station=" E01", machine_id="M01"),
                    _build_station_row(station="e02", machine_id="M02"),
                    _build_station_row(station="ST03", machine_id="M03"),
                ],
            )

            frame = loader_module._read_station_frame(file_path=source)

        self.assertEqual(frame.select("station").to_series().to_list(), [" E01", "e02"])

    @patch.object(loader_module, "copy_full_replace_rows")
    @patch.object(loader_module, "_read_station_frame")
    def test_loader_claims_incoming_file_and_deletes_on_success(
        self,
        read_file,
        copy_rows,
    ) -> None:
        """성공 시 incoming 파일을 processing 경유 삭제합니다."""

        read_file.return_value = type("Frame", (), {"shape": (1, len(spec.COLUMNS))})()
        copy_rows.return_value = CopyFullReplaceResult(row_count=1, column_count=len(spec.DB_COLUMNS))

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "86114_STATION_MASTER_20260620.csv.deflate"
            source.write_text("payload", encoding="utf-8")

            summary = loader_module.load_station_master_files(data_dir=root)

            self.assertEqual(summary.success_count, 1)
            self.assertFalse(source.exists())
            self.assertFalse((root / "archive").exists())
            self.assertFalse((root / "error").exists())
            self.assertEqual(list((root / "processing").iterdir()), [])

        self.assertEqual(StationMasterLoadJob.objects.filter(status=StationMasterLoadJob.Status.SUCCESS).count(), 1)

    @patch.object(loader_module, "_read_station_frame")
    def test_loader_deletes_failed_file(self, read_file) -> None:
        """처리 실패 시 선점 파일도 삭제합니다."""

        read_file.side_effect = ValueError("broken file")

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "86114_STATION_MASTER_20260620.csv.deflate"
            source.write_text("payload", encoding="utf-8")

            summary = loader_module.load_station_master_files(data_dir=root)

            self.assertEqual(summary.failure_count, 1)
            self.assertFalse(source.exists())
            self.assertFalse((root / "archive").exists())
            self.assertFalse((root / "error").exists())
            self.assertEqual(list((root / "processing").iterdir()), [])

        self.assertEqual(StationMasterLoadJob.objects.filter(status=StationMasterLoadJob.Status.FAILED).count(), 1)
