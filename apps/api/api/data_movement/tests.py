"""data_movement Airflow trigger API 테스트입니다."""

from __future__ import annotations

import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from api.data_movement.common.services.file_loader import list_data_files, list_incoming_files
from api.data_movement.ct_process_comment.services import SummaryRowOutcome, SummaryRunSummary
from api.data_movement.m_tkin_prevent.models import MTkinPreventLoadJob
from api.data_movement.m_tkin_prevent.services.loader import LoadFileOutcome, LoadRunSummary


class DataMovementFileLoaderTests(SimpleTestCase):
    """data movement 공통 파일 탐색 동작을 검증합니다."""

    def test_list_data_files_matches_file_name_case_insensitively(self) -> None:
        """파일명 대소문자가 달라도 spec pattern에 맞는 파일을 찾습니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            matched = root / "65635_ct_process_comment_20260529_1300.CSV.DEFLATE"
            ignored = root / "other.txt"
            matched.write_text("ok", encoding="utf-8")
            ignored.write_text("skip", encoding="utf-8")

            files = list_data_files(
                data_dir=root,
                pattern="*_CT_PROCESS_COMMENT_*.csv.deflate",
            )

        self.assertEqual([path.name for path in files], [matched.name])

    @override_settings(
        DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS=60,
        DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS=0,
    )
    def test_list_incoming_files_skips_recent_files(self) -> None:
        """최근 수정된 incoming 파일은 아직 전송 중일 수 있어 제외합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            recent = incoming / "recent.csv.deflate"
            recent.write_text("ok", encoding="utf-8")

            files = list_incoming_files(table_dir=root, pattern="*.csv.deflate")

        self.assertEqual(files, [])

    @override_settings(
        DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS=60,
        DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS=0,
    )
    def test_list_incoming_files_includes_old_files(self) -> None:
        """최소 안정화 시간을 지난 incoming 파일은 적재 후보로 반환합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            matched = incoming / "old.csv.deflate"
            matched.write_text("ok", encoding="utf-8")
            old_timestamp = time.time() - 120
            os.utime(matched, (old_timestamp, old_timestamp))

            files = list_incoming_files(table_dir=root, pattern="*.csv.deflate")

        self.assertEqual([path.name for path in files], [matched.name])

    @override_settings(
        DATA_MOVEMENT_FILE_READY_MIN_AGE_SECONDS=0,
        DATA_MOVEMENT_FILE_READY_STABILITY_SECONDS=1,
    )
    def test_list_incoming_files_skips_files_changed_during_stability_check(self) -> None:
        """재확인 중 stat 값이 바뀐 incoming 파일은 이번 적재에서 제외합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            incoming = root / "incoming"
            incoming.mkdir()
            changing = incoming / "changing.csv.deflate"
            changing.write_text("ok", encoding="utf-8")

            with patch(
                "api.data_movement.common.services.file_loader.time.sleep",
                side_effect=lambda _seconds: changing.write_text("changed", encoding="utf-8"),
            ):
                files = list_incoming_files(table_dir=root, pattern="*.csv.deflate")

        self.assertEqual(files, [])


@override_settings(AIRFLOW_TRIGGER_TOKEN="test-token")
class DataMovementLoadTriggerApiTests(TestCase):
    """data_movement loader trigger API 동작을 검증합니다."""

    def test_load_trigger_requires_airflow_bearer_token(self) -> None:
        """Bearer token이 없으면 적재를 실행하지 않습니다."""

        response = self.client.post("/api/v1/data-movement/m_tkin_prevent/load/")

        self.assertEqual(response.status_code, 401)

    def test_load_trigger_runs_table_loader(self) -> None:
        """지원 테이블 요청이면 loader를 실행하고 summary를 반환합니다."""

        summary = LoadRunSummary(
            outcomes=[
                LoadFileOutcome(
                    file_name="a.csv.deflate",
                    status=MTkinPreventLoadJob.Status.SUCCESS,
                    row_count=1,
                    replace_values=["L1"],
                )
            ]
        )
        load_files = Mock(return_value=summary)
        with patch.dict("api.data_movement.views.DATA_MOVEMENT_LOADERS", {"m_tkin_prevent": load_files}):
            response = self.client.post(
                "/api/v1/data-movement/m_tkin_prevent/load/",
                data={"limit": 1, "dry_run": True},
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test-token",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success_count"], 1)
        load_files.assert_called_once_with(dry_run=True, limit=1)

    def test_load_trigger_rejects_unknown_table(self) -> None:
        """지원하지 않는 테이블명은 404로 거절합니다."""

        response = self.client.post(
            "/api/v1/data-movement/unknown_table/load/",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(response.status_code, 404)

    def test_summary_trigger_runs_ct_process_comment_summary(self) -> None:
        """ct_process_comment 요약 trigger가 service를 실행하고 summary를 반환합니다."""

        summary = SummaryRunSummary(
            outcomes=[
                SummaryRowOutcome(
                    workorder_id="WO1",
                    status="success",
                    summary="시간순 요약: 점검",
                )
            ]
        )
        with patch(
            "api.data_movement.views.summarize_pending_ct_process_comments",
            return_value=summary,
        ) as summarize_comments:
            response = self.client.post(
                "/api/v1/data-movement/ct_process_comment/summarize/",
                data={"limit": 3, "dry_run": True},
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test-token",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success_count"], 1)
        self.assertEqual(response.json()["skipped_count"], 0)
        self.assertEqual(response.json()["dry_run_count"], 0)
        summarize_comments.assert_called_once_with(dry_run=True, limit=3)

    def test_summary_trigger_returns_500_when_any_summary_failed(self) -> None:
        """요약 실패 row가 있으면 Airflow가 실패를 감지할 수 있게 500을 반환합니다."""

        summary = SummaryRunSummary(
            outcomes=[
                SummaryRowOutcome(
                    workorder_id="WO1",
                    status="failed",
                    error_message="OpenWebUI 오류",
                )
            ]
        )
        with patch(
            "api.data_movement.views.summarize_pending_ct_process_comments",
            return_value=summary,
        ):
            response = self.client.post(
                "/api/v1/data-movement/ct_process_comment/summarize/",
                data={},
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test-token",
            )

        self.assertEqual(response.status_code, 500)
