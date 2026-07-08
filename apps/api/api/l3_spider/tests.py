# =============================================================================
# 모듈: L3 Spider 서비스 테스트
# 주요 대상: meta, summary, data 응답 형태
# 주요 가정: 테스트 데이터는 임시 Parquet 파일로 생성합니다.
# =============================================================================
from __future__ import annotations

from datetime import time as datetime_time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

import pandas as pd

from . import services
from .models import (
    L3SpiderExclusionFilter,
    L3SpiderMailDelivery,
    L3SpiderMailRule,
    L3SpiderMailRulePermission,
)
from .services import line_name_rules


class L3SpiderServiceTests(SimpleTestCase):
    """L3 Spider 파일 기반 서비스 동작을 검증합니다."""

    def setUp(self) -> None:
        """서비스 인메모리 캐시를 초기화합니다."""

        services._meta_cache.clear()
        services._structure_cache.clear()
        services._stats_cache.clear()
        services._daily_summary_cache.clear()
        services._raw_file_rows_cache.clear()
        services._line_groups_cache.clear()
        line_name_rules._cache["mtime"] = None
        line_name_rules._cache["rules"] = None

    def _columnar_rows(self, data: dict[str, object]) -> list[dict[str, object]]:
        """columnar 응답을 테스트 검증용 row 목록으로 변환합니다."""

        cols = data.get("cols", [])
        col_data = data.get("colData", [])
        if not cols or not col_data:
            return []
        return [
            {column: col_data[column_index][row_index] for column_index, column in enumerate(cols)}
            for row_index in range(len(col_data[0]))
        ]

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
                {
                    "tkin_time": pd.Timestamp("2025-01-15 02:00:00"),
                    "step_seq": "S1",
                    "ppid": "PPID_A",
                    "root_lot_id": "ROOT",
                    "lot_id": "LOT",
                    "wafer_id": "W03",
                    "eqc": "EQC_A",
                    "bin_name": "BIN_B",
                    "bin_value": 1.4,
                    "prop_over_50": 0.6,
                    "lsl": 0.0,
                    "usl": 2.0,
                    "display_status": "Warning",
                    "comment": "주의",
                },
            ]
        )
        frame.to_parquet(target / "sample", engine="pyarrow")

    def _write_filename_key_sample(self, root: Path) -> None:
        """확장자 없는 파일명에서 step_seq와 ppid를 보강하는 샘플을 생성합니다."""

        target = root / "2025-01-15" / "L1" / "P1" / "EDS_M"
        target.mkdir(parents=True)
        frame = pd.DataFrame(
            [
                {
                    "tkin_time": pd.Timestamp("2025-01-15 00:00:00"),
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
                }
            ]
        )
        frame.to_parquet(target / "S1#PPID_A#0", engine="pyarrow")

    def _write_line_name_sample(self, root: Path) -> None:
        """line_name 필터 검증용 다중 라인 샘플을 생성합니다."""

        rows = [
            (
                root / "2025-01-15" / "L1" / "P1" / "EDS_M" / "S1#PPID_A#0",
                "EQC_A",
                "High Risk Chamber",
            ),
            (
                root / "2025-01-15" / "L2" / "P2" / "EDS_M" / "S1#PPID_A#0",
                "EQC_B",
                "High Risk Chamber",
            ),
        ]
        for path, eqc, status in rows:
            path.parent.mkdir(parents=True, exist_ok=True)
            frame = pd.DataFrame(
                [
                    {
                        "tkin_time": pd.Timestamp("2025-01-15 00:00:00"),
                        "root_lot_id": "ROOT",
                        "lot_id": "LOT",
                        "wafer_id": "W01",
                        "eqc": eqc,
                        "bin_name": "BIN_A",
                        "bin_value": 1.2,
                        "prop_over_50": 0.7,
                        "lsl": 0.0,
                        "usl": 2.0,
                        "display_status": status,
                        "comment": None,
                    }
                ]
            )
            frame.to_parquet(path, engine="pyarrow")

    def _write_line_name_rules(self, root: Path, body: str) -> None:
        """line_name 규칙 CSV를 생성합니다."""

        meta_dir = root / "_meta"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "line_name_rules.csv").write_text(body, encoding="utf-8")
        line_name_rules._cache["mtime"] = None
        line_name_rules._cache["rules"] = None

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

            with override_settings(L3_SPIDER_DATA_ROOT=str(root)), patch.object(
                services,
                "_get_exclusion_rules",
                return_value=[],
            ):
                meta = services.get_meta()
                summary = services.get_summary(selection)
                data = services.get_data(selection)
                rows = self._columnar_rows(data)

        self.assertEqual(meta["lineIds"], ["L1"])
        self.assertEqual(meta["processIds"], ["P1"])
        self.assertEqual(meta["edsSteps"], ["EDS_M"])
        self.assertEqual(summary["stats"]["highRiskEqpchs"], 1)
        self.assertEqual(summary["stepPpids"], {"S1": ["PPID_A"]})
        self.assertEqual(summary["ppidEqcs"], {"PPID_A": ["EQC_A", "EQC_B"]})
        self.assertEqual(summary["ppidHighRiskEqcs"], {"PPID_A": ["EQC_A"]})
        self.assertEqual(summary["eqcHighRiskBins"], {"EQC_A": ["BIN_A"]})
        self.assertEqual(summary["anomalies"][0]["binName"], "BIN_A")
        self.assertEqual(rows[0]["stepSeq"], "S1")
        self.assertIn("displayStatus", rows[0])

    def test_daily_summary_returns_equipment_bin_item_ranking(self) -> None:
        """일별 요약이 설비별 이상 bin item ranking을 반환하는지 확인합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_sample(root)

            with override_settings(L3_SPIDER_DATA_ROOT=str(root)), patch.object(
                services,
                "_get_exclusion_rules",
                return_value=[],
            ):
                daily = services.get_daily_summary({"dates": ["2025-01-15"]})

        self.assertEqual(daily["equipmentRanking"], [
            {
                "line": "L1",
                "equipment": "EQC_A",
                "binItems": 2,
                "highRisk": 1,
                "warning": 1,
                "details": [
                    {
                        "process": "P1",
                        "edsStep": "EDS_M",
                        "binItems": 2,
                        "highRisk": 1,
                        "warning": 1,
                        "total": 2,
                    }
                ],
            }
        ])

    def test_extensionless_filename_key_supplies_step_and_ppid(self) -> None:
        """확장자 없는 STEP#PPID#N 파일명이 summary/data 필터에 반영되는지 확인합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_filename_key_sample(root)
            selection = {
                "dates": ["2025-01-15"],
                "lineIds": ["L1"],
                "processIds": ["P1"],
                "edsSteps": ["EDS_M"],
                "selectedEqcs": ["EQC_A"],
                "selectedStepBins": [],
                "selectedPpidBins": [],
                "selectedSteps": ["S1"],
                "checkedPpids": ["PPID_A"],
                "checkedBins": ["BIN_A"],
            }

            with override_settings(L3_SPIDER_DATA_ROOT=str(root)), patch.object(
                services,
                "_get_exclusion_rules",
                return_value=[],
            ):
                summary = services.get_summary(selection)
                data = services.get_data(selection)
                rows = self._columnar_rows(data)

        self.assertEqual(summary["stepPpids"], {"S1": ["PPID_A"]})
        self.assertEqual(summary["edsStepPpids"], {"EDS_M|||S1": ["PPID_A"]})
        self.assertEqual(rows[0]["stepSeq"], "S1")
        self.assertEqual(rows[0]["ppid"], "PPID_A")

    def test_line_name_rules_fall_back_to_line_id_without_csv(self) -> None:
        """line_name 규칙 CSV가 없으면 line_id로 폴백해야 합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with override_settings(L3_SPIDER_DATA_ROOT=str(root)):
                result = line_name_rules.resolve_line_name("L1", "P1", "S1")

        self.assertEqual(result, "L1")

    def test_line_name_rules_apply_exact_override_and_wildcards(self) -> None:
        """line_name 규칙의 exact/override/wildcard 우선순위를 검증합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_line_name_rules(
                root,
                "\n".join(
                    [
                        "type,line_id,process_id,step_seq,line_name",
                        "base,L1,P1,,BaseName",
                        "base,L%,P%,,WildBase",
                        "override,,P1,S2,OverrideName",
                        "override,,P%,S3,WildOverride",
                    ]
                ),
            )

            with override_settings(L3_SPIDER_DATA_ROOT=str(root)):
                base = line_name_rules.resolve_line_name("L1", "P1", "S1")
                override = line_name_rules.resolve_line_name("L1", "P1", "S2")
                wild_override = line_name_rules.resolve_line_name("L9", "P9", "S3")
                wild_base = line_name_rules.resolve_line_name("L9", "P9", "S9")

        self.assertEqual(base, "BaseName")
        self.assertEqual(override, "OverrideName")
        self.assertEqual(wild_override, "WildOverride")
        self.assertEqual(wild_base, "WildBase")

    def test_line_name_groups_and_filters_use_rules_csv(self) -> None:
        """lineGroups와 데이터 조회가 line_name 규칙 CSV를 기준으로 동작해야 합니다."""

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_line_name_sample(root)
            self._write_line_name_rules(
                root,
                "\n".join(
                    [
                        "type,line_id,process_id,step_seq,line_name",
                        "base,L1,P1,,FabA",
                        "base,L2,P2,,FabB",
                    ]
                ),
            )
            selection = {
                "dates": ["2025-01-15"],
                "lineIds": ["L1", "L2"],
                "lineNames": ["FabA"],
                "processIds": ["P1", "P2"],
                "edsSteps": ["EDS_M"],
                "selectedEqcs": ["EQC_A", "EQC_B"],
                "selectedStepBins": [],
                "selectedPpidBins": [],
                "selectedSteps": ["S1"],
                "checkedPpids": ["PPID_A"],
                "checkedBins": ["BIN_A"],
            }
            filter_selection = {
                "dates": ["2025-01-15"],
                "lineIds": ["L1", "L2"],
                "lineNames": ["FabA"],
                "processIds": ["P1", "P2"],
                "edsStep": "EDS_M",
                "stepSeq": "S1",
                "ppid": "PPID_A",
            }

            with override_settings(L3_SPIDER_DATA_ROOT=str(root)), patch.object(
                services,
                "_get_exclusion_rules",
                return_value=[],
            ):
                meta = services.get_meta()
                stats = services.get_stats(selection)
                data = services.get_data(selection)
                candidates = services.get_filter_candidates(filter_selection)
                rows = self._columnar_rows(data)

        self.assertEqual(
            meta["lineGroups"],
            [
                {"lineName": "FabA", "lineId": "L1", "processIds": ["P1"], "procEds": {"P1": ["EDS_M"]}},
                {"lineName": "FabB", "lineId": "L2", "processIds": ["P2"], "procEds": {"P2": ["EDS_M"]}},
            ],
        )
        self.assertEqual(stats["stats"]["total"], 1)
        self.assertEqual([row["eqc"] for row in rows], ["EQC_A"])
        self.assertEqual(candidates["eqcHighRiskBins"], {"EQC_A": ["BIN_A"]})


class L3SpiderExclusionFilterOwnershipTests(TestCase):
    """L3 Spider 제외 필터 소유자 분리 규칙을 검증합니다."""

    def setUp(self) -> None:
        """테스트용 사용자를 생성합니다."""

        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="owner",
            sabun="100001",
            password="pw",
        )
        self.other = user_model.objects.create_user(
            username="other",
            sabun="100002",
            password="pw",
        )

    def _create_filter(
        self,
        *,
        user,
        line_id: str = "L1",
        memo: str = "",
        is_active: bool = True,
    ) -> L3SpiderExclusionFilter:
        """테스트용 제외 필터를 생성합니다."""

        return L3SpiderExclusionFilter.objects.create(
            line_id=line_id,
            process_id="*",
            eds_step="*",
            step_seq="*",
            ppid="*",
            eqpch="*",
            bin_name="*",
            memo=memo,
            is_active=is_active,
            created_by=user,
        )

    def test_list_exclusion_filters_returns_only_user_owned_rows(self) -> None:
        """목록 조회는 요청 사용자 소유 필터만 반환해야 합니다."""

        owner_filter = self._create_filter(user=self.owner, line_id="L1")
        self._create_filter(user=self.other, line_id="L2")

        rows = services.list_exclusion_filters(user=self.owner)

        self.assertEqual([row["id"] for row in rows], [owner_filter.id])
        self.assertEqual(rows[0]["lineId"], "L1")

    def test_exclusion_rules_use_only_user_owned_active_rows(self) -> None:
        """실제 제외 규칙도 사용자 소유 활성 필터만 사용해야 합니다."""

        self._create_filter(user=self.owner, line_id="L1")
        self._create_filter(user=self.owner, line_id="L2", is_active=False)
        self._create_filter(user=self.other, line_id="L3")

        rules = services._get_exclusion_rules(user=self.owner)

        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["line_id"], "L1")

    def test_update_exclusion_filter_rejects_other_user_row(self) -> None:
        """다른 사용자의 제외 필터는 수정할 수 없어야 합니다."""

        other_filter = self._create_filter(user=self.other, memo="원본")

        with self.assertRaises(services.L3SpiderServiceError) as context:
            services.update_exclusion_filter(
                other_filter.id,
                {"memo": "변경"},
                user=self.owner,
            )

        self.assertEqual(context.exception.status_code, 404)
        other_filter.refresh_from_db()
        self.assertEqual(other_filter.memo, "원본")

    def test_delete_exclusion_filter_rejects_other_user_row(self) -> None:
        """다른 사용자의 제외 필터는 삭제할 수 없어야 합니다."""

        other_filter = self._create_filter(user=self.other)

        with self.assertRaises(services.L3SpiderServiceError) as context:
            services.delete_exclusion_filter(other_filter.id, user=self.owner)

        self.assertEqual(context.exception.status_code, 404)
        self.assertTrue(L3SpiderExclusionFilter.objects.filter(pk=other_filter.id).exists())


class L3SpiderMailRuleTests(TestCase):
    """L3 Spider 메일 rule 소유권과 발송 처리를 검증합니다."""

    def setUp(self) -> None:
        """테스트용 사용자를 생성합니다."""

        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="mail-owner",
            sabun="200001",
            email="mail-owner@example.com",
            password="pw",
        )
        self.other = user_model.objects.create_user(
            username="mail-other",
            sabun="200002",
            email="mail-other@example.com",
            password="pw",
        )
        self.reader = user_model.objects.create_user(
            username="mail-reader",
            sabun="200003",
            email="mail-reader@example.com",
            password="pw",
        )
        self.writer = user_model.objects.create_user(
            username="mail-writer",
            sabun="200004",
            email="mail-writer@example.com",
            password="pw",
        )

    def _create_rule(
        self,
        *,
        user,
        name: str = "알림",
        severity_mode: str = L3SpiderMailRule.SeverityModes.HIGH_RISK,
        eqpch: str = "*",
        is_active: bool = True,
    ) -> L3SpiderMailRule:
        """테스트용 메일 rule을 생성합니다."""

        return L3SpiderMailRule.objects.create(
            name=name,
            line_id="*",
            process_id="*",
            eds_step="*",
            step_seq="*",
            ppid="*",
            eqpch=eqpch,
            bin_name="*",
            severity_mode=severity_mode,
            receiver_emails=["owner@example.com"],
            schedule_type=L3SpiderMailRule.ScheduleTypes.DAILY,
            send_time=datetime_time(0, 0),
            timezone="Asia/Seoul",
            is_active=is_active,
            created_by=user,
        )

    def _write_mail_sample(self, root: Path, *, date: str = "2025-01-15") -> None:
        """메일 발송 후보 이벤트용 Parquet 파일을 생성합니다."""

        target = root / date / "L1" / "P1" / "EDS_M"
        target.mkdir(parents=True)
        frame = pd.DataFrame(
            [
                {
                    "tkin_time": pd.Timestamp(f"{date} 00:00:00"),
                    "step_seq": "S1",
                    "ppid": "PPID_A",
                    "eqc": "EQC_A",
                    "bin_name": "BIN_A",
                    "display_status": "High Risk Chamber",
                },
                {
                    "tkin_time": pd.Timestamp(f"{date} 01:00:00"),
                    "step_seq": "S1",
                    "ppid": "PPID_A",
                    "eqc": "EQC_B",
                    "bin_name": "BIN_A",
                    "display_status": "Warning",
                },
            ]
        )
        frame.to_parquet(target / "S1#PPID_A#0.parquet", engine="pyarrow")

    def test_list_mail_rules_returns_owned_and_shared_rows(self) -> None:
        """메일 rule 목록은 소유 row와 공유받은 row만 반환해야 합니다."""

        owner_rule = self._create_rule(user=self.owner, name="내 rule")
        shared_rule = self._create_rule(user=self.other, name="공유 rule")
        hidden_rule = self._create_rule(user=self.other, name="숨김 rule")
        L3SpiderMailRulePermission.objects.create(
            rule=shared_rule,
            user=self.owner,
            access_level=L3SpiderMailRulePermission.AccessLevels.READ,
            granted_by=self.other,
        )

        rows = services.list_mail_rules(user=self.owner)

        self.assertEqual({row["id"] for row in rows}, {owner_rule.id, shared_rule.id})
        self.assertNotIn(hidden_rule.id, {row["id"] for row in rows})
        owner_row = next(row for row in rows if row["id"] == owner_rule.id)
        shared_row = next(row for row in rows if row["id"] == shared_rule.id)
        self.assertTrue(owner_row["canManage"])
        self.assertEqual(shared_row["accessLevel"], "read")
        self.assertFalse(shared_row["canWrite"])

    def test_update_mail_rule_rejects_other_user_row(self) -> None:
        """다른 사용자의 메일 rule은 수정할 수 없어야 합니다."""

        other_rule = self._create_rule(user=self.other, name="원본")

        with self.assertRaises(services.L3SpiderServiceError) as context:
            services.update_mail_rule(
                other_rule.id,
                {"name": "변경"},
                user=self.owner,
            )

        self.assertEqual(context.exception.status_code, 404)
        other_rule.refresh_from_db()
        self.assertEqual(other_rule.name, "원본")

    def test_read_permission_cannot_update_mail_rule(self) -> None:
        """read 권한자는 메일 rule을 수정할 수 없어야 합니다."""

        rule = self._create_rule(user=self.owner, name="원본")
        L3SpiderMailRulePermission.objects.create(
            rule=rule,
            user=self.reader,
            access_level=L3SpiderMailRulePermission.AccessLevels.READ,
            granted_by=self.owner,
        )

        with self.assertRaises(services.L3SpiderServiceError) as context:
            services.update_mail_rule(rule.id, {"name": "변경"}, user=self.reader)

        self.assertEqual(context.exception.status_code, 403)
        rule.refresh_from_db()
        self.assertEqual(rule.name, "원본")

    def test_write_permission_can_update_mail_rule_body(self) -> None:
        """write 권한자는 메일 rule 본문 설정을 수정할 수 있어야 합니다."""

        rule = self._create_rule(user=self.owner, name="원본")
        L3SpiderMailRulePermission.objects.create(
            rule=rule,
            user=self.writer,
            access_level=L3SpiderMailRulePermission.AccessLevels.WRITE,
            granted_by=self.owner,
        )

        services.update_mail_rule(rule.id, {"name": "변경"}, user=self.writer)

        rule.refresh_from_db()
        self.assertEqual(rule.name, "변경")

    def test_owner_replaces_mail_rule_permissions_by_existing_users(self) -> None:
        """owner는 기존 사용자 식별자로 read/write 권한을 교체할 수 있어야 합니다."""

        rule = self._create_rule(user=self.owner)

        result = services.replace_mail_rule_permissions(
            rule.id,
            [
                {"user": "mail-reader@example.com", "access_level": "read"},
                {"user": "mail-writer", "access_level": "write"},
            ],
            user=self.owner,
        )

        self.assertEqual(len(result["permissions"]), 2)
        self.assertTrue(
            L3SpiderMailRulePermission.objects.filter(
                rule=rule,
                user=self.reader,
                access_level=L3SpiderMailRulePermission.AccessLevels.READ,
            ).exists()
        )
        self.assertTrue(
            L3SpiderMailRulePermission.objects.filter(
                rule=rule,
                user=self.writer,
                access_level=L3SpiderMailRulePermission.AccessLevels.WRITE,
            ).exists()
        )

    def test_non_owner_cannot_replace_mail_rule_permissions(self) -> None:
        """공유받은 write 권한자도 권한 목록은 변경할 수 없어야 합니다."""

        rule = self._create_rule(user=self.owner)
        L3SpiderMailRulePermission.objects.create(
            rule=rule,
            user=self.writer,
            access_level=L3SpiderMailRulePermission.AccessLevels.WRITE,
            granted_by=self.owner,
        )

        with self.assertRaises(services.L3SpiderServiceError) as context:
            services.replace_mail_rule_permissions(
                rule.id,
                [{"user": "mail-reader@example.com", "access_level": "read"}],
                user=self.writer,
            )

        self.assertEqual(context.exception.status_code, 404)

    def test_test_send_mail_rule_sends_without_delivery_history(self) -> None:
        """테스트 발송은 정기 발송 이력을 소모하지 않고 메일만 전송해야 합니다."""

        rule = self._create_rule(user=self.owner, eqpch="EQC_A")
        today = services._rule_local_today(rule, now=services.timezone.now()).isoformat()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_mail_sample(root, date=today)

            with override_settings(
                L3_SPIDER_DATA_ROOT=str(root),
                L3_SPIDER_MAIL_SENDER="sender@example.com",
                FRONTEND_BASE_URL="http://frontend.example.com",
            ), patch(
                "api.l3_spider.services.send_knox_mail_api",
                return_value={"ok": True},
            ) as mock_send:
                result = services.send_mail_rule_test(rule.id, user=self.owner)

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["sent"], 1)
        mock_send.assert_called_once()
        self.assertTrue(mock_send.call_args.kwargs["subject"].startswith("[TEST] "))
        self.assertEqual(L3SpiderMailDelivery.objects.filter(rule=rule).count(), 0)
        rule.refresh_from_db()
        self.assertIsNone(rule.last_sent_at)
        self.assertIsNone(rule.last_checked_at)

    def test_read_permission_cannot_test_send_mail_rule(self) -> None:
        """read 권한자는 테스트 발송을 실행할 수 없어야 합니다."""

        rule = self._create_rule(user=self.owner)
        L3SpiderMailRulePermission.objects.create(
            rule=rule,
            user=self.reader,
            access_level=L3SpiderMailRulePermission.AccessLevels.READ,
            granted_by=self.owner,
        )

        with patch("api.l3_spider.services.send_knox_mail_api") as mock_send:
            with self.assertRaises(services.L3SpiderServiceError) as context:
                services.send_mail_rule_test(rule.id, user=self.reader)

        self.assertEqual(context.exception.status_code, 403)
        mock_send.assert_not_called()

    def test_trigger_due_mail_rules_sends_high_risk_once(self) -> None:
        """due rule은 High Risk 이벤트를 한 번만 발송 이력으로 남겨야 합니다."""

        rule = self._create_rule(user=self.owner, eqpch="EQC_A")
        L3SpiderMailRule.objects.filter(pk=rule.pk).update(
            created_at=services.timezone.now() - timedelta(days=1),
        )
        rule.refresh_from_db()
        today = services._rule_local_today(rule, now=services.timezone.now()).isoformat()
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_mail_sample(root, date=today)

            with override_settings(
                L3_SPIDER_DATA_ROOT=str(root),
                L3_SPIDER_MAIL_SENDER="sender@example.com",
                FRONTEND_BASE_URL="http://frontend.example.com",
            ), patch(
                "api.l3_spider.services.send_knox_mail_api",
                return_value={"ok": True},
            ) as mock_send:
                first = services.trigger_due_mail_rules(limit=10)
                second = services.trigger_due_mail_rules(limit=10)

        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        mock_send.assert_called_once()
        self.assertIn(
            "http://frontend.example.com/l3_spider",
            mock_send.call_args.kwargs["html_content"],
        )
        html_content = mock_send.call_args.kwargs["html_content"]
        self.assertIn(f"date={today}", html_content)
        self.assertIn("lineId=L1", html_content)
        self.assertIn("processId=P1", html_content)
        self.assertIn("edsStep=EDS_M", html_content)
        self.assertIn("stepSeq=S1", html_content)
        self.assertIn("ppid=PPID_A", html_content)
        self.assertIn("eqpch=EQC_A", html_content)
        self.assertIn("binName=BIN_A", html_content)
        self.assertIn(">열기</a>", html_content)
        self.assertEqual(
            L3SpiderMailDelivery.objects.filter(
                rule=rule,
                status=L3SpiderMailDelivery.Statuses.SENT,
            ).count(),
            1,
        )
        rule.refresh_from_db()
        self.assertIsNotNone(rule.last_sent_at)
        self.assertIsNotNone(rule.last_checked_at)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.l3_spider.services.trigger_due_mail_rules")
    def test_mail_trigger_endpoint_requires_bearer_token(self, mock_trigger) -> None:
        """Airflow trigger endpoint는 Bearer token을 요구해야 합니다."""

        mock_trigger.return_value = {"processed": 0, "sent": 0, "claimed": 0, "results": []}
        url = reverse("l3-spider-mail-rule-trigger")

        denied = self.client.post(url, data='{"limit": 5}', content_type="application/json")
        allowed = self.client.post(
            url,
            data='{"limit": 5}',
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer expected-token",
        )

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(allowed.status_code, 200)
        mock_trigger.assert_called_once_with(limit=5)
