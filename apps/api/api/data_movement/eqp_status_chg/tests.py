"""eqp_status_chg 적재 앱 테스트입니다."""

from __future__ import annotations

import zlib
import warnings
from datetime import datetime, timezone as datetime_timezone
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from api.data_movement.eqp_status_chg import selectors
from api.data_movement.eqp_status_chg.management.commands.load_eqp_status_chg import services
from api.data_movement.eqp_status_chg.models import EqpStatusChg, EqpStatusChgLoadJob
from api.data_movement.eqp_status_chg.services import loader as loader_module
from api.data_movement.eqp_status_chg.services import spec
from api.data_movement.eqp_status_chg.services.loader import LoadFileOutcome, LoadRunSummary


def _write_deflate_csv(path: Path, rows: list[list[str]]) -> None:
    """테스트용 eqp_status_chg deflate CSV 파일을 생성합니다."""

    payload = "\n".join(spec.FILE_SEPARATOR.join(row) for row in rows).encode("utf-8")
    path.write_bytes(zlib.compress(payload))


def _build_status_row(
    *,
    eqp_id: str = "EAAA301",
    chamber_id: str = "1",
    chg_time: str = "2026-06-20 10:00:00",
    eqp_status_type: str = "RUN",
    eqp_event_key: str = "100",
    chg_comment: str = "status changed",
) -> list[str]:
    """spec 컬럼 순서에 맞춘 테스트용 상태 변경 row를 생성합니다."""

    return [
        eqp_id,
        "L1",
        chamber_id,
        chg_time,
        "CODE",
        "AUTO",
        eqp_status_type,
        chg_comment,
        "OP01",
        eqp_event_key,
        chg_time,
    ]


class EqpStatusChgStructureTests(SimpleTestCase):
    """eqp_status_chg 앱 구조와 command 경계를 검증합니다."""

    def test_model_table_names_match_expected_tables(self) -> None:
        """모델의 실제 DB 테이블명이 합의한 이름과 일치하는지 확인합니다."""

        self.assertEqual(EqpStatusChg._meta.db_table, "eqp_status_chg")
        self.assertEqual(EqpStatusChgLoadJob._meta.db_table, "eqp_status_chg_load_job")

    def test_model_indexes_support_timeline_query(self) -> None:
        """EQP-CB별 시간 범위 조회용 복합 인덱스가 있는지 확인합니다."""

        index_names = {index.name for index in EqpStatusChg._meta.indexes}
        constraint_names = {constraint.name for constraint in EqpStatusChg._meta.constraints}

        self.assertIn("idx_eqp_sts_lkp_tm", index_names)
        self.assertIn("idx_eqp_sts_chg_cb_tm", index_names)
        self.assertIn("idx_eqp_sts_chg_tm", index_names)
        self.assertIn("uniq_eqp_sts_chg_evt", constraint_names)

    @patch.object(services, "load_eqp_status_chg_files")
    def test_command_reports_no_files(self, load_files) -> None:
        """처리 파일이 없으면 성공 메시지만 출력하는지 확인합니다."""

        load_files.return_value = LoadRunSummary(outcomes=[])
        stdout = StringIO()

        call_command("load_eqp_status_chg", stdout=stdout)

        self.assertIn("처리할 파일 없음", stdout.getvalue())

    @patch.object(services, "load_eqp_status_chg_files")
    def test_command_raises_when_any_file_failed(self, load_files) -> None:
        """실패 파일이 하나라도 있으면 Airflow가 실패를 감지하도록 예외를 발생시킵니다."""

        load_files.return_value = LoadRunSummary(
            outcomes=[
                LoadFileOutcome(
                    file_name="bad.csv.deflate",
                    status=EqpStatusChgLoadJob.Status.FAILED,
                    row_count=0,
                    error_message="invalid",
                )
            ]
        )

        with self.assertRaises(CommandError):
            call_command("load_eqp_status_chg", stdout=StringIO())


@override_settings(DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS=0, DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS=0)
class EqpStatusChgLifecycleTests(TestCase):
    """EQP 상태 변경 파일 처리 lifecycle을 검증합니다."""

    @patch.object(
        loader_module.timezone,
        "now",
        return_value=datetime(2026, 6, 20, 0, 0, tzinfo=datetime_timezone.utc),
    )
    def test_loader_filters_rows_and_builds_eqp_cb(self, _now) -> None:
        """E prefix와 180일 기준을 통과한 row만 eqp_cb 형태로 저장합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "m_eqp_status_chg_20260620.csv.deflate"
            _write_deflate_csv(
                source,
                [
                    _build_status_row(eqp_id="EAAA301", chamber_id="A", eqp_event_key="100"),
                    _build_status_row(eqp_id="eBBB302", chamber_id="B", eqp_event_key="101"),
                    _build_status_row(eqp_id="ECCC303", chamber_id="-", eqp_event_key="104"),
                    _build_status_row(eqp_id="EDDD304", chamber_id="", eqp_event_key="105"),
                    _build_status_row(eqp_id="AAAA301", chamber_id="A", eqp_event_key="102"),
                    _build_status_row(
                        eqp_id="EOLD301",
                        chamber_id="A",
                        chg_time="2025-01-01 00:00:00",
                        eqp_event_key="103",
                    ),
                ],
            )

            summary = loader_module.load_eqp_status_chg_files(data_dir=root)

        self.assertEqual(summary.success_count, 1, summary.outcomes)
        self.assertEqual(EqpStatusChg.objects.count(), 4)
        self.assertTrue(EqpStatusChg.objects.filter(eqp_cb="EAAA301-A").exists())
        self.assertTrue(EqpStatusChg.objects.filter(eqp_cb="eBBB302-B").exists())
        self.assertTrue(EqpStatusChg.objects.filter(eqp_cb_lookup="EBBB302-B").exists())
        self.assertTrue(EqpStatusChg.objects.filter(eqp_cb="ECCC303").exists())
        self.assertTrue(EqpStatusChg.objects.filter(eqp_cb="EDDD304").exists())
        self.assertFalse(EqpStatusChg.objects.filter(eqp_cb__in=["ECCC303--", "EDDD304-"]).exists())
        self.assertFalse(hasattr(EqpStatusChg.objects.first(), "eqp_id"))

    @patch.object(
        loader_module.timezone,
        "now",
        return_value=datetime(2026, 6, 20, 0, 0, tzinfo=datetime_timezone.utc),
    )
    def test_loader_upserts_by_event_key_and_purges_old_rows(self, _now) -> None:
        """eqp_event_key 기준 기존 row를 갱신하고 180일 초과 row를 삭제합니다."""

        EqpStatusChg.objects.create(
            eqp_cb="EAAA301-A",
            line_id="L1",
            chg_time=datetime(2026, 6, 19, 10, 0, tzinfo=datetime_timezone.utc),
            eqp_status_type="OLD",
            chg_comment="old",
            operator_emp_id="OLD",
            eqp_event_key="100",
        )
        EqpStatusChg.objects.create(
            eqp_cb="EOLD301-A",
            line_id="L1",
            chg_time=datetime(2025, 1, 1, 0, 0, tzinfo=datetime_timezone.utc),
            eqp_status_type="OLD",
            eqp_event_key="999",
        )

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "m_eqp_status_chg_20260620.csv.deflate"
            _write_deflate_csv(
                source,
                [
                    _build_status_row(
                        eqp_id="EAAA301",
                        chamber_id="A",
                        chg_time="2026-06-20 10:00:00",
                        eqp_status_type="RUN",
                        eqp_event_key="100",
                        chg_comment="new",
                    ),
                ],
            )

            summary = loader_module.load_eqp_status_chg_files(data_dir=root)

        self.assertEqual(summary.success_count, 1, summary.outcomes)
        updated_row = EqpStatusChg.objects.get(eqp_event_key="100")
        self.assertEqual(updated_row.eqp_status_type, "RUN")
        self.assertEqual(updated_row.chg_comment, "new")
        self.assertFalse(EqpStatusChg.objects.filter(eqp_event_key="999").exists())

    def test_selector_normalizes_date_filters_without_naive_datetime_warning(self) -> None:
        """문자열 날짜 경계를 timezone-aware 필터 값으로 변환합니다."""

        EqpStatusChg.objects.create(
            eqp_cb="EAAA301-A",
            eqp_cb_lookup="EAAA301-A",
            line_id="L1",
            chg_time=datetime(2026, 7, 1, 10, 0, tzinfo=datetime_timezone.utc),
            eqp_status_type="RUN",
            eqp_event_key="200",
        )

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always", RuntimeWarning)
            logs = selectors.fetch_eqp_timeline_logs(
                eqp_id="EAAA301-A",
                start_at="2026-07-01",
                end_at=datetime(2026, 7, 1, 23, 59, 59),
            )

        naive_datetime_warnings = [
            warning
            for warning in captured
            if "received a naive datetime" in str(warning.message)
        ]
        self.assertEqual(naive_datetime_warnings, [])
        self.assertEqual([log["id"] for log in logs], ["EQP-200"])
