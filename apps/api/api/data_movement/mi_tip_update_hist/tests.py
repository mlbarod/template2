"""mi_tip_update_hist 적재 앱 테스트입니다."""

from __future__ import annotations

import zlib
from datetime import datetime, timezone as datetime_timezone
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from api.data_movement.mi_tip_update_hist.management.commands.load_mi_tip_update_hist import services
from api.data_movement.mi_tip_update_hist.models import MiTipUpdateHist, MiTipUpdateHistLoadJob
from api.data_movement.mi_tip_update_hist import selectors
from api.data_movement.mi_tip_update_hist.services import loader as loader_module
from api.data_movement.mi_tip_update_hist.services import spec
from api.data_movement.mi_tip_update_hist.services.loader import LoadFileOutcome, LoadRunSummary


def _write_deflate_csv(path: Path, rows: list[list[str]]) -> None:
    """테스트용 mi_tip_update_hist deflate CSV 파일을 생성합니다."""

    payload = "\n".join(spec.FILE_SEPARATOR.join(row) for row in rows).encode("utf-8")
    path.write_bytes(zlib.compress(payload))


def _build_tip_row(
    *,
    line_id: str = "L1",
    eqp_id: str = "EAAA301",
    step_seq: str = "100",
    process_id: str = "ETCH",
    ppid: str = "PPID-A",
    tip_chamber_id: str = "A",
    gpm_update_date: str = "2026-06-20 10:00:00",
    register_name: str = "USER01-NAME",
    tip_type: str = "PREVENT",
    tip_chg_type: str = "TIP_OCCUR",
    tip_level: str = "LEVEL1",
    tip_comment: str = "TIP comment",
    rule_pkg_update_date: str = "2026-06-20 09:00:00",
    last_update_date: str = "2026-06-20 10:05:00",
) -> list[str]:
    """spec 컬럼 순서에 맞춘 테스트용 TIP row를 생성합니다."""

    return [
        line_id,
        eqp_id,
        step_seq,
        process_id,
        ppid,
        tip_chamber_id,
        "RETICLE",
        "PRODUCT",
        "10",
        rule_pkg_update_date,
        gpm_update_date,
        register_name,
        tip_type,
        tip_chg_type,
        tip_level,
        tip_comment,
        "3",
        "2",
        "202606201000000000",
        last_update_date,
    ]


def _build_tip_event_key(
    *,
    eqp_cb: str = "EAAA301-A",
    gpm_update_date: str = "2026-06-20 10:00:00",
    event_type: str = "L1_TIP",
    process_id: str = "ETCH",
    step_seq: str = "100",
    ppid: str = "PPID-A",
    tip_comment: str = "TIP comment",
) -> str:
    """loader와 같은 규칙으로 테스트용 upsert key를 생성합니다."""

    return loader_module._build_tip_event_key(
        eqp_cb=eqp_cb,
        gpm_update_date=gpm_update_date,
        event_type=event_type,
        process_id=process_id,
        step_seq=step_seq,
        ppid=ppid,
        tip_comment=tip_comment,
    )


class MiTipUpdateHistStructureTests(SimpleTestCase):
    """mi_tip_update_hist 앱 구조와 command 경계를 검증합니다."""

    def test_model_table_names_match_expected_tables(self) -> None:
        """모델의 실제 DB 테이블명이 합의한 이름과 일치하는지 확인합니다."""

        self.assertEqual(MiTipUpdateHist._meta.db_table, "mi_tip_update_hist")
        self.assertEqual(MiTipUpdateHistLoadJob._meta.db_table, "mi_tip_update_hist_load_job")

    def test_model_indexes_support_timeline_query(self) -> None:
        """EQP-CB별 시간 범위 조회용 복합 인덱스가 있는지 확인합니다."""

        index_names = {index.name for index in MiTipUpdateHist._meta.indexes}
        constraint_names = {constraint.name for constraint in MiTipUpdateHist._meta.constraints}

        self.assertIn("idx_mi_tip_lkp_dt", index_names)
        self.assertIn("idx_mi_tip_upd_hist_cb_dt", index_names)
        self.assertIn("idx_mi_tip_upd_hist_dt", index_names)
        self.assertIn("uniq_mi_tip_upd_hist_evt", constraint_names)

    @patch.object(services, "load_mi_tip_update_hist_files")
    def test_command_reports_no_files(self, load_files) -> None:
        """처리 파일이 없으면 성공 메시지만 출력하는지 확인합니다."""

        load_files.return_value = LoadRunSummary(outcomes=[])
        stdout = StringIO()

        call_command("load_mi_tip_update_hist", stdout=stdout)

        self.assertIn("처리할 파일 없음", stdout.getvalue())

    @patch.object(services, "load_mi_tip_update_hist_files")
    def test_command_raises_when_any_file_failed(self, load_files) -> None:
        """실패 파일이 하나라도 있으면 Airflow가 실패를 감지하도록 예외를 발생시킵니다."""

        load_files.return_value = LoadRunSummary(
            outcomes=[
                LoadFileOutcome(
                    file_name="bad.csv.deflate",
                    status=MiTipUpdateHistLoadJob.Status.FAILED,
                    row_count=0,
                    error_message="invalid",
                )
            ]
        )

        with self.assertRaises(CommandError):
            call_command("load_mi_tip_update_hist", stdout=StringIO())


@override_settings(DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS=0, DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS=0)
class MiTipUpdateHistLifecycleTests(TestCase):
    """TIP 이력 파일 처리 lifecycle을 검증합니다."""

    @patch.object(
        loader_module.timezone,
        "now",
        return_value=datetime(2026, 6, 20, 0, 0, tzinfo=datetime_timezone.utc),
    )
    def test_loader_filters_rows_and_builds_timeline_columns(self, _now) -> None:
        """E prefix와 180일 기준을 통과한 row만 변환된 형태로 저장합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "MI_TIP_UPDATE_HIST_20260620.csv.deflate"
            _write_deflate_csv(
                source,
                [
                    _build_tip_row(eqp_id="EAAA301", tip_chamber_id="A"),
                    _build_tip_row(eqp_id="eBBB302", tip_chamber_id="MAIN"),
                    _build_tip_row(eqp_id="ECCC303", tip_chamber_id="CHM-1"),
                    _build_tip_row(eqp_id="AAAA301", tip_chamber_id="A"),
                    _build_tip_row(
                        eqp_id="EOLD301",
                        tip_chamber_id="A",
                        gpm_update_date="2025-01-01 00:00:00",
                    ),
                    _build_tip_row(
                        eqp_id="EUNK301",
                        tip_chamber_id="A",
                        tip_type="OTHER",
                        tip_chg_type="OTHER",
                        tip_level="OTHER",
                    ),
                ],
            )

            summary = loader_module.load_mi_tip_update_hist_files(data_dir=root)

        self.assertEqual(summary.success_count, 1, summary.outcomes)
        self.assertEqual(MiTipUpdateHist.objects.count(), 4)
        self.assertTrue(MiTipUpdateHist.objects.filter(eqp_cb="EAAA301-A", event_type="L1_TIP").exists())
        self.assertTrue(MiTipUpdateHist.objects.filter(eqp_cb="eBBB302").exists())
        self.assertTrue(MiTipUpdateHist.objects.filter(eqp_cb_lookup="EBBB302").exists())
        self.assertTrue(MiTipUpdateHist.objects.filter(eqp_cb="ECCC303").exists())
        self.assertTrue(MiTipUpdateHist.objects.filter(eqp_cb="EUNK301-A", event_type="unknown").exists())
        self.assertFalse(hasattr(MiTipUpdateHist.objects.first(), "eqp_id"))
        self.assertFalse(hasattr(MiTipUpdateHist.objects.first(), "tip_chamber_id"))

    @patch.object(
        loader_module.timezone,
        "now",
        return_value=datetime(2026, 6, 20, 0, 0, tzinfo=datetime_timezone.utc),
    )
    def test_loader_treats_source_null_literal_as_database_null(self, _now) -> None:
        """원천 CSV의 null 리터럴을 nullable 컬럼의 DB NULL로 적재합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "MI_TIP_UPDATE_HIST_20260620.csv.deflate"
            _write_deflate_csv(
                source,
                [
                    _build_tip_row(
                        rule_pkg_update_date="null",
                        last_update_date="null",
                    ),
                ],
            )

            summary = loader_module.load_mi_tip_update_hist_files(data_dir=root)

        self.assertEqual(summary.success_count, 1, summary.outcomes)
        loaded_row = MiTipUpdateHist.objects.get()
        self.assertIsNone(loaded_row.rule_pkg_update_date)
        self.assertIsNone(loaded_row.last_update_date)

    @patch.object(
        loader_module.timezone,
        "now",
        return_value=datetime(2026, 6, 20, 0, 0, tzinfo=datetime_timezone.utc),
    )
    def test_loader_upserts_by_event_key_and_purges_old_rows(self, _now) -> None:
        """tip_event_key 기준 기존 row를 갱신하고 180일 초과 row를 삭제합니다."""

        MiTipUpdateHist.objects.create(
            tip_event_key=_build_tip_event_key(),
            eqp_cb="EAAA301-A",
            line_id="L1",
            gpm_update_date=datetime(2026, 6, 20, 10, 0, tzinfo=datetime_timezone.utc),
            event_type="L1_TIP",
            process_id="ETCH",
            step_seq="100",
            ppid="PPID-A",
            register_name="OLD-USER",
            tip_comment="TIP comment",
        )
        MiTipUpdateHist.objects.create(
            tip_event_key="old-row",
            eqp_cb="EOLD301-A",
            gpm_update_date=datetime(2025, 1, 1, 0, 0, tzinfo=datetime_timezone.utc),
            event_type="L1_TIP",
        )

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            source = incoming / "MI_TIP_UPDATE_HIST_20260620.csv.deflate"
            _write_deflate_csv(
                source,
                [
                    _build_tip_row(
                        eqp_id="EAAA301",
                        tip_chamber_id="A",
                        register_name="NEW-USER",
                        tip_comment="TIP comment",
                        last_update_date="2026-06-20 10:10:00",
                    ),
                ],
            )

            summary = loader_module.load_mi_tip_update_hist_files(data_dir=root)

        self.assertEqual(summary.success_count, 1, summary.outcomes)
        updated_row = MiTipUpdateHist.objects.get(tip_event_key=_build_tip_event_key())
        self.assertEqual(updated_row.register_name, "NEW-USER")
        self.assertFalse(MiTipUpdateHist.objects.filter(tip_event_key="old-row").exists())

    def test_selector_returns_observer_tip_payload(self) -> None:
        """내부 테이블 row를 observer TIP payload로 변환합니다."""

        MiTipUpdateHist.objects.create(
            tip_event_key=_build_tip_event_key(),
            eqp_cb="EAAA301-A",
            line_id="L1",
            gpm_update_date=datetime(2026, 6, 20, 10, 0, tzinfo=datetime_timezone.utc),
            event_type="L1_TIP",
            process_id="ETCH",
            step_seq="100",
            ppid="PPID-A",
            register_name="USER01-NAME",
            tip_comment="TIP comment",
        )

        logs = selectors.fetch_tip_timeline_logs(
            eqp_id="eaaa301-a",
            start_at="2026-06-01T00:00:00",
            limit=10,
        )

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["eqpId"], "EAAA301-A")
        self.assertEqual(logs[0]["logType"], "TIP")
        self.assertEqual(logs[0]["eventType"], "L1_TIP")
        self.assertEqual(logs[0]["operator"], "USER01")
        self.assertEqual(logs[0]["process"], "ETCH")
