# =============================================================================
# 모듈: 어시스턴트 기능 테스트
# 주요 대상: RAG 인덱스 조회, 채팅 권한 검증, 응답/정규화 처리
# 주요 가정: 외부 호출은 mock으로 대체합니다.
# =============================================================================
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase

import api.account.services as account_services
from api.assistant import services as assistant_services
from api.assistant.services import AssistantChatConfig, AssistantChatService, AssistantConfigError
from api.assistant.views import AssistantChatView
import api.rag.services as rag_services


class AssistantRagIndexViewsTests(TestCase):
    """RAG 인덱스/권한 그룹 API 동작을 검증합니다."""

    def setUp(self) -> None:
        """테스트용 사용자/권한 데이터를 준비합니다."""
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S90000",
            password="test-password",
            email="s90000@example.com",
        )
        self.user.user_sdwt_prod = "group-a"
        self.user.knox_id = "knox-90000"
        self.user.save(update_fields=["user_sdwt_prod", "knox_id"])

        manager = User.objects.create_user(sabun="S90010", password="test-password")
        manager.user_sdwt_prod = "group-b"
        manager.save(update_fields=["user_sdwt_prod"])
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-b",
            target_user=self.user,
            action="grant",
            role="member",
        )
        self.assertEqual(status_code, 200)

    def test_rag_index_list_returns_accessible_user_sdwt_prods(self) -> None:
        """접근 가능한 user_sdwt_prod가 응답에 포함되는지 확인합니다."""
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/assistant/rag-indexes")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload.get("currentUserSdwtProd"), "group-a")
        self.assertEqual(
            set(payload.get("permissionGroups", [])),
            {"group-a", "group-b", "knox-90000", rag_services.RAG_PUBLIC_GROUP},
        )
        self.assertEqual(payload.get("ragIndexes"), rag_services.get_rag_index_candidates())
        self.assertEqual(payload.get("defaultRagIndex"), rag_services.resolve_rag_index_name(None))
        self.assertEqual(
            payload.get("emailRagIndex"),
            rag_services.resolve_rag_index_name(rag_services.RAG_INDEX_EMAILS),
        )

    def test_chat_accepts_accessible_user_sdwt_prod_override(self) -> None:
        """접근 가능한 permission_groups override가 허용되는지 확인합니다."""
        self.client.force_login(self.user)

        with patch("api.assistant.views.assistant_chat_service.generate_reply") as mocked_generate:
            mocked_generate.return_value = SimpleNamespace(
                reply="OK",
                contexts=[],
                sources=[],
                is_dummy=True,
            )
            default_index = rag_services.resolve_rag_index_name(None)

            response = self.client.post(
                "/api/v1/assistant/chat",
                data=json.dumps(
                    {
                        "prompt": "hello",
                        "permission_groups": ["group-b"],
                        "rag_index_name": default_index,
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mocked_generate.call_count, 1)
        kwargs = mocked_generate.call_args.kwargs
        self.assertEqual(kwargs.get("permission_groups"), ["group-b"])
        self.assertEqual(kwargs.get("rag_index_names"), [default_index])

    def test_chat_rejects_inaccessible_user_sdwt_prod_override(self) -> None:
        """접근 불가능한 permission_groups override는 거부되는지 확인합니다."""
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/v1/assistant/chat",
            data=json.dumps({"prompt": "hello", "permission_groups": ["group-x"]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertIn("error", payload)

    def test_rag_index_list_returns_all_known_user_sdwt_prods_for_superuser(self) -> None:
        """슈퍼유저는 모든 user_sdwt_prod가 노출되는지 확인합니다."""
        User = get_user_model()
        superuser = User.objects.create_superuser(
            sabun="S90001",
            password="test-password",
            email="s90001@example.com",
        )
        superuser.user_sdwt_prod = "group-admin"
        superuser.knox_id = "knox-super"
        superuser.save(update_fields=["user_sdwt_prod", "knox_id"])

        other_user = User.objects.create_user(
            sabun="S90002",
            password="test-password",
            email="s90002@example.com",
        )
        other_user.user_sdwt_prod = "group-c"
        other_user.save(update_fields=["user_sdwt_prod"])
        manager = User.objects.create_user(sabun="S90011", password="test-password")
        manager.user_sdwt_prod = "group-d"
        manager.save(update_fields=["user_sdwt_prod"])
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-d",
            target_user=other_user,
            action="grant",
            role="member",
        )
        self.assertEqual(status_code, 200)

        self.client.force_login(superuser)

        response = self.client.get("/api/v1/assistant/rag-indexes")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload.get("currentUserSdwtProd"), "group-admin")
        permission_groups = payload.get("permissionGroups")
        self.assertEqual(permission_groups, sorted(permission_groups))
        self.assertEqual(
            set(permission_groups),
            {
                "group-a",
                "group-b",
                "group-c",
                "group-d",
                "group-admin",
                "knox-super",
                rag_services.RAG_PUBLIC_GROUP,
            },
        )

    def test_chat_accepts_user_sdwt_prod_override_for_superuser(self) -> None:
        """슈퍼유저는 permission_groups override가 허용되는지 확인합니다."""
        User = get_user_model()
        superuser = User.objects.create_superuser(
            sabun="S90001",
            password="test-password",
            email="s90001@example.com",
        )
        superuser.user_sdwt_prod = "group-admin"
        superuser.knox_id = "knox-super"
        superuser.save(update_fields=["user_sdwt_prod", "knox_id"])

        other_user = User.objects.create_user(
            sabun="S90002",
            password="test-password",
            email="s90002@example.com",
        )
        other_user.user_sdwt_prod = "group-c"
        other_user.save(update_fields=["user_sdwt_prod"])

        self.client.force_login(superuser)

        with patch("api.assistant.views.assistant_chat_service.generate_reply") as mocked_generate:
            mocked_generate.return_value = SimpleNamespace(
                reply="OK",
                contexts=[],
                sources=[],
                is_dummy=True,
            )
            default_index = rag_services.resolve_rag_index_name(None)

            response = self.client.post(
                "/api/v1/assistant/chat",
                data=json.dumps(
                    {
                        "prompt": "hello",
                        "permission_groups": ["group-c"],
                        "rag_index_name": [default_index],
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        kwargs = mocked_generate.call_args.kwargs
        self.assertEqual(kwargs.get("permission_groups"), ["group-c"])
        self.assertEqual(kwargs.get("rag_index_names"), [default_index])


class AssistantChatServiceSourceFilteringTests(TestCase):
    """LLM 응답/출처 필터링 동작을 검증합니다."""

    def test_generate_llm_payload_sets_temperature_zero_when_background_knowledge_exists(self) -> None:
        """배경지식이 있으면 temperature가 0으로 설정되는지 확인합니다."""
        service = AssistantChatService(
            config=AssistantChatConfig(
                use_dummy=False,
                llm_url="http://example.com",
                llm_credential="token",
                temperature=0.7,
            )
        )

        payload_with_context = service._generate_llm_payload("질문입니다", ["context"], email_ids=["E1"])
        self.assertEqual(payload_with_context.get("temperature"), 0.0)
        messages = payload_with_context.get("messages")
        self.assertEqual([entry.get("role") for entry in messages], ["system", "system", "system", "user"])

        payload_without_context = service._generate_llm_payload("질문입니다", [], email_ids=["E1"])
        self.assertEqual(payload_without_context.get("temperature"), 0.7)

    def test_generate_reply_builds_segments_and_filters_sources(self) -> None:
        """segments 기반 출처 필터링이 올바른지 확인합니다."""
        service = AssistantChatService(
            config=AssistantChatConfig(
                use_dummy=False,
                llm_url="http://example.com",
                llm_credential="token",
            )
        )

        contexts = ["[emailId: E1]\ncontext 1", "[emailId: E2]\ncontext 2"]
        sources = [
            {"doc_id": "E1", "title": "메일 1", "snippet": "내용 1"},
            {"doc_id": "E2", "title": "메일 2", "snippet": "내용 2"},
        ]

        with patch.object(service, "_retrieve_documents", return_value=(contexts, {"hits": {}}, sources)):
            with patch.object(
                service,
                "_call_llm",
                return_value=(
                    json.dumps(
                        {
                            "answer": "통합 답변입니다",
                            "segments": [
                                {"answer": "메일 2 기반 답변", "usedEmailIds": ["E2"]},
                                {"answer": "메일 1+2 기반 답변", "usedEmailIds": ["E1", "E2", "E3"]},
                            ],
                        },
                        ensure_ascii=False,
                    ),
                    {"choices": []},
                ),
            ):
                result = service.generate_reply("질문입니다")

        self.assertEqual(result.reply, "통합 답변입니다")
        self.assertEqual(len(result.segments), 2)
        self.assertEqual(result.segments[0]["reply"], "메일 2 기반 답변")
        self.assertEqual([entry["doc_id"] for entry in result.segments[0]["sources"]], ["E2"])
        self.assertEqual(result.segments[1]["reply"], "메일 1+2 기반 답변")
        self.assertEqual([entry["doc_id"] for entry in result.segments[1]["sources"]], ["E1", "E2"])
        self.assertEqual([entry["doc_id"] for entry in result.sources], ["E1", "E2"])

    def test_generate_reply_hides_sources_on_unparseable_reply(self) -> None:
        """파싱 불가 응답일 때 출처가 숨겨지는지 확인합니다."""
        service = AssistantChatService(
            config=AssistantChatConfig(
                use_dummy=False,
                llm_url="http://example.com",
                llm_credential="token",
            )
        )

        sources = [{"doc_id": "E1", "title": "메일 1", "snippet": "내용 1"}]

        with patch.object(service, "_retrieve_documents", return_value=(["context"], {"hits": {}}, sources)):
            with patch.object(service, "_call_llm", return_value=("그냥 텍스트 응답", {"choices": []})):
                result = service.generate_reply("질문입니다")

        self.assertEqual(result.reply, "그냥 텍스트 응답")
        self.assertEqual(result.sources, [])
        self.assertEqual(result.segments, [])

    def test_generate_reply_treats_empty_segments_as_no_sources(self) -> None:
        """segments가 비어 있으면 출처가 비워지는지 확인합니다."""
        service = AssistantChatService(
            config=AssistantChatConfig(
                use_dummy=False,
                llm_url="http://example.com",
                llm_credential="token",
            )
        )

        sources = [{"doc_id": "E1", "title": "메일 1", "snippet": "내용 1"}]

        with patch.object(service, "_retrieve_documents", return_value=(["context"], {"hits": {}}, sources)):
            with patch.object(service, "_call_llm", return_value=('{"answer":"OK","segments":[]}', {"choices": []})):
                result = service.generate_reply("질문입니다")

        self.assertEqual(result.reply, "OK")
        self.assertEqual(result.sources, [])
        self.assertEqual(result.segments, [])

    def test_generate_reply_supports_legacy_used_email_ids_format(self) -> None:
        """레거시 usedEmailIds 포맷을 처리하는지 확인합니다."""
        service = AssistantChatService(
            config=AssistantChatConfig(
                use_dummy=False,
                llm_url="http://example.com",
                llm_credential="token",
            )
        )

        sources = [
            {"doc_id": "E1", "title": "메일 1", "snippet": "내용 1"},
            {"doc_id": "E2", "title": "메일 2", "snippet": "내용 2"},
        ]

        with patch.object(service, "_retrieve_documents", return_value=(["context"], {"hits": {}}, sources)):
            with patch.object(
                service,
                "_call_llm",
                return_value=('{"answer":"OK","usedEmailIds":["E2","E3"]}', {"choices": []}),
            ):
                result = service.generate_reply("질문입니다")

        self.assertEqual(result.reply, "OK")
        self.assertEqual(len(result.segments), 1)
        self.assertEqual(result.segments[0]["reply"], "OK")
        self.assertEqual([entry["doc_id"] for entry in result.segments[0]["sources"]], ["E2"])
        self.assertEqual([entry["doc_id"] for entry in result.sources], ["E2"])


class AssistantRagIntegrationTests(SimpleTestCase):
    """Assistant와 RAG 연동 경로를 검증합니다."""

    def test_generate_reply_uses_rag_services_search(self) -> None:
        """generate_reply가 RAG 검색을 호출하는지 확인합니다."""
        # -------------------------------------------------------------------------
        # 1) RAG 응답 더미 준비
        # -------------------------------------------------------------------------
        rag_response = {
            "hits": {
                "hits": [
                    {
                        "_id": "doc-1",
                        "_source": {
                            "doc_id": "email-1",
                            "title": "첫번째",
                            "merge_title_content": "컨텍스트1",
                        },
                    },
                    {
                        "_id": "doc-2",
                        "_source": {
                            "doc_id": "email-2",
                            "title": "두번째",
                            "merge_title_content": "컨텍스트2",
                        },
                    },
                ]
            }
        }

        # -------------------------------------------------------------------------
        # 2) Assistant 설정 구성
        # -------------------------------------------------------------------------
        config = AssistantChatConfig(
            use_dummy=True,
            dummy_use_rag=True,
            rag_index_names=["idx-user"],
            rag_num_docs=5,
        )

        # -------------------------------------------------------------------------
        # 3) RAG 검색 patch 및 호출
        # -------------------------------------------------------------------------
        with patch("api.rag.services.RAG_SEARCH_URL", "http://rag/search"), patch(
            "api.rag.services.search_rag", return_value=rag_response
        ) as search_mock:
            service = AssistantChatService(config=config)
            result = service.generate_reply("hello")

        # -------------------------------------------------------------------------
        # 4) 호출 파라미터/응답 검증
        # -------------------------------------------------------------------------
        search_mock.assert_called_once_with("hello", index_name=["idx-user"], num_result_doc=5, timeout=30)
        self.assertTrue(result.is_dummy)
        self.assertEqual(
            result.contexts,
            [
                "[emailId: email-1 | title: 첫번째]\n컨텍스트1",
                "[emailId: email-2 | title: 두번째]\n컨텍스트2",
            ],
        )

    def test_generate_reply_passes_permission_group_override(self) -> None:
        """permission_groups 오버라이드가 전달되는지 확인합니다."""
        # -------------------------------------------------------------------------
        # 1) RAG 응답/설정 준비
        # -------------------------------------------------------------------------
        rag_response = {"hits": {"hits": []}}
        config = AssistantChatConfig(
            use_dummy=True,
            dummy_use_rag=True,
            rag_index_names=["idx-default"],
            rag_num_docs=5,
        )

        # -------------------------------------------------------------------------
        # 2) RAG 검색 patch 및 호출
        # -------------------------------------------------------------------------
        with patch("api.rag.services.RAG_SEARCH_URL", "http://rag/search"), patch(
            "api.rag.services.search_rag", return_value=rag_response
        ) as search_mock:
            service = AssistantChatService(config=config)
            result = service.generate_reply("hello", permission_groups=["group-a"])

        # -------------------------------------------------------------------------
        # 3) 호출 파라미터/응답 검증
        # -------------------------------------------------------------------------
        search_mock.assert_called_once_with(
            "hello",
            index_name=["idx-default"],
            num_result_doc=5,
            timeout=30,
            permission_groups=["group-a"],
        )
        self.assertEqual(result.sources, [])
        self.assertEqual(result.rag_response, rag_response)


class AssistantChatViewTests(TestCase):
    """AssistantChatView API 응답을 검증합니다."""

    def setUp(self) -> None:
        """테스트용 사용자/요청 팩토리를 준비합니다."""
        self.factory = RequestFactory()
        User = get_user_model()
        self.user = User.objects.create_user(
            sabun="S77777",
            password="test-password",
            email="dummy.user@example.com",
        )
        self.user.user_sdwt_prod = "group-a"
        self.user.knox_id = "knox-77777"
        self.user.save(update_fields=["knox_id", "user_sdwt_prod"])

    def test_chat_view_returns_response_without_rag_url_attribute_error(self) -> None:
        """정상 요청 시 응답 페이로드가 생성되는지 확인합니다."""
        # -------------------------------------------------------------------------
        # 1) 요청 객체 구성
        # -------------------------------------------------------------------------
        request = self.factory.post(
            "/api/v1/assistant/chat",
            data=json.dumps({"prompt": "hello"}),
            content_type="application/json",
        )
        request.user = self.user

        # -------------------------------------------------------------------------
        # 2) 서비스 응답 patch 및 호출
        # -------------------------------------------------------------------------
        with patch(
            "api.assistant.views.assistant_chat_service.generate_reply",
            return_value=Mock(reply="안녕", contexts=[], sources=[], is_dummy=True),
        ):
            response = AssistantChatView().post(request)

        # -------------------------------------------------------------------------
        # 3) 응답 검증
        # -------------------------------------------------------------------------
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertEqual(payload["reply"], "안녕")
        self.assertIn("meta", payload)

    def test_chat_view_returns_503_when_assistant_config_error(self) -> None:
        """설정 오류 발생 시 503을 반환하는지 확인합니다."""
        # -------------------------------------------------------------------------
        # 1) 요청 객체 구성
        # -------------------------------------------------------------------------
        request = self.factory.post(
            "/api/v1/assistant/chat",
            data=json.dumps({"prompt": "hello"}),
            content_type="application/json",
        )
        request.user = self.user

        # -------------------------------------------------------------------------
        # 2) 서비스 오류 patch 및 호출
        # -------------------------------------------------------------------------
        with patch(
            "api.assistant.views.assistant_chat_service.generate_reply",
            side_effect=AssistantConfigError("missing config"),
        ):
            response = AssistantChatView().post(request)

        # -------------------------------------------------------------------------
        # 3) 응답 코드 검증
        # -------------------------------------------------------------------------
        self.assertEqual(response.status_code, 503)


class AssistantNormalizationTests(TestCase):
    """정규화 유틸 동작을 검증합니다."""

    def test_normalize_room_id_defaults_to_default(self) -> None:
        """room_id가 비면 기본값으로 대체되는지 확인합니다."""
        self.assertEqual(assistant_services.normalize_room_id(None), "default")
        self.assertEqual(assistant_services.normalize_room_id(""), "default")

    def test_normalize_room_id_sanitizes(self) -> None:
        """room_id가 허용 문자로 정규화되는지 확인합니다."""
        self.assertEqual(assistant_services.normalize_room_id(" room$% "), "room--")

    def test_normalize_sources_dedupes(self) -> None:
        """normalize_sources가 doc_id 기준으로 중복 제거하는지 확인합니다."""
        sources = [
            {"doc_id": "DOC1", "title": "T1", "snippet": "S1"},
            {"docId": "DOC1", "title": "T1b", "snippet": "S1b"},
            {"doc_id": "DOC2", "title": "T2", "snippet": "S2"},
        ]
        normalized = assistant_services.normalize_sources(sources)
        self.assertEqual(len(normalized), 2)
        self.assertEqual({item["docId"] for item in normalized}, {"DOC1", "DOC2"})
