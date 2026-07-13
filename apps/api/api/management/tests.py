# =============================================================================
# 모듈 설명: management 공통 command 테스트를 제공합니다.
# - 주요 대상: ensure_dev_database, seed_dev_data, seed_dummy_emails
# - 불변 조건: dev DB bootstrap과 명시적 더미 command guard를 검증합니다.
# =============================================================================

from __future__ import annotations

from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class EnsureDevDatabaseCommandTests(SimpleTestCase):
    """dev DB bootstrap command의 가드와 생성 흐름을 검증합니다."""

    def test_command_requires_development_environment(self) -> None:
        """개발 환경이 아니면 DB 생성을 시도하지 않습니다."""

        with patch.dict("os.environ", {"ENVIRONMENT": "production"}, clear=True):
            with self.assertRaises(CommandError):
                call_command("ensure_dev_database", stdout=StringIO())

    @patch("api.management.commands.ensure_dev_database._ensure_required_extensions")
    @patch("api.management.commands.ensure_dev_database.psycopg.connect")
    def test_command_ensures_extensions_when_target_matches_maintenance_database(
        self,
        connect: Mock,
        ensure_extensions: Mock,
    ) -> None:
        """대상 DB와 maintenance DB가 같아도 extension 보장은 수행합니다."""

        stdout = StringIO()

        with patch.dict("os.environ", {"ENVIRONMENT": "development"}, clear=True):
            call_command(
                "ensure_dev_database",
                database="airflow",
                maintenance_database="airflow",
                stdout=stdout,
            )

        connect.assert_not_called()
        ensure_extensions.assert_called_once_with(database_name="airflow")
        self.assertIn("target database already matches maintenance database: airflow", stdout.getvalue())

    @patch("api.management.commands.ensure_dev_database._database_exists", return_value=False)
    @patch("api.management.commands.ensure_dev_database._create_database")
    @patch("api.management.commands.ensure_dev_database._ensure_required_extensions")
    @patch("api.management.commands.ensure_dev_database.psycopg.connect")
    def test_command_creates_missing_database(
        self,
        connect: Mock,
        ensure_extensions: Mock,
        create_database: Mock,
        database_exists: Mock,
    ) -> None:
        """대상 DB가 없으면 maintenance DB에 접속해 생성합니다."""

        connection = connect.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        stdout = StringIO()

        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "development",
                "DJANGO_DB_USER": "airflow",
                "DJANGO_DB_PASSWORD": "airflow",
                "DJANGO_DB_HOST": "airflow-postgres",
                "DJANGO_DB_PORT": "8010",
            },
            clear=True,
        ):
            call_command(
                "ensure_dev_database",
                database="dashboard",
                maintenance_database="airflow",
                stdout=stdout,
            )

        connect.assert_called_once_with(
            dbname="airflow",
            user="airflow",
            password="airflow",
            host="airflow-postgres",
            port="8010",
            autocommit=True,
        )
        database_exists.assert_called_once_with(cursor, database_name="dashboard")
        create_database.assert_called_once_with(cursor, database_name="dashboard", owner="airflow")
        ensure_extensions.assert_called_once_with(database_name="dashboard")
        self.assertIn("database created: dashboard", stdout.getvalue())


class SeedDummyEmailsCommandTests(SimpleTestCase):
    """이메일 더미 seed command의 dev 전용 가드를 검증합니다."""

    def test_command_rejects_non_development_environment(self) -> None:
        """development 환경이 아니면 실행을 거부합니다."""

        with patch.dict("os.environ", {"ENVIRONMENT": "production"}, clear=True):
            with self.assertRaises(CommandError):
                call_command("seed_dummy_emails", skip_rag=True, stdout=StringIO())

    @patch("api.emails.management.commands.seed_dummy_emails.Email.objects")
    def test_command_allows_explicit_dev_seed_flag(self, email_objects: Mock) -> None:
        """development 환경이면 이메일 seed를 실행합니다."""

        email_objects.update_or_create.side_effect = [
            (Mock(), True),
            (Mock(), True),
        ]

        with patch.dict("os.environ", {"ENVIRONMENT": "development"}, clear=True):
            call_command("seed_dummy_emails", skip_rag=True, stdout=StringIO())

        self.assertEqual(email_objects.update_or_create.call_count, 2)


class SeedDevDataCommandTests(SimpleTestCase):
    """통합 dev seed command의 dev 전용 가드와 호출 흐름을 검증합니다."""

    def test_command_rejects_non_development_environment(self) -> None:
        """development 환경이 아니면 실행을 거부합니다."""

        with patch.dict("os.environ", {"ENVIRONMENT": "production"}, clear=True):
            with self.assertRaises(CommandError):
                call_command("seed_dev_data", stdout=StringIO())

    @patch("api.management.commands.seed_dev_data.call_command")
    @patch("api.management.commands.seed_dev_data.ensure_dev_dummy_superuser")
    def test_command_refreshes_dummy_data_when_dev_seed_is_enabled(
        self,
        ensure_dummy: Mock,
        nested_call_command: Mock,
    ) -> None:
        """development 환경이면 dummy 사용자 보정 후 하위 seed를 실행합니다."""

        ensure_dummy.return_value = Mock(sabun="S000001")

        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "development",
                "DRONE_SEED_ALLOWED": "1",
            },
            clear=True,
        ):
            call_command("seed_dev_data", reset=True, skip_rag=True, prefix="dev", stdout=StringIO())

        ensure_dummy.assert_called_once_with()
        self.assertEqual(nested_call_command.call_count, 2)
        email_call = nested_call_command.call_args_list[0]
        drone_call = nested_call_command.call_args_list[1]
        self.assertEqual(email_call.args[0], "seed_dummy_emails")
        self.assertEqual(email_call.kwargs["prefix"], "DEV")
        self.assertTrue(email_call.kwargs["reset"])
        self.assertTrue(email_call.kwargs["skip_rag"])
        self.assertEqual(drone_call.args[0], "seed_drone_dummy_data")
        self.assertEqual(drone_call.kwargs["prefix"], "DEV")
        self.assertTrue(drone_call.kwargs["reset"])

    @patch("api.management.commands.seed_dev_data.ensure_dev_dummy_superuser", return_value=None)
    def test_command_requires_dummy_user_to_be_ensured(self, ensure_dummy: Mock) -> None:
        """dummy 사용자 보장이 실패하면 더미 데이터 refresh를 중단합니다."""

        with patch.dict("os.environ", {"ENVIRONMENT": "development"}, clear=True):
            with self.assertRaises(CommandError):
                call_command("seed_dev_data", stdout=StringIO())

        ensure_dummy.assert_called_once_with()
