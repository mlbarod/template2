# 앱 인벤토리

이 문서는 실제 코드 경로를 기준으로 앱의 route, model, command, env 계약을 한 곳에 모은 색인입니다. 상세 설명은 각 주제 문서와 모듈 문서를 봅니다.

## 백엔드 API route

모든 업무 API는 `apps/api/api/urls.py`에서 `/api/v1/` 아래로 include됩니다. Auth callback만 `apps/api/api/auth/callback_urls.py`를 통해 `/auth/google/callback/`을 사용합니다.

| 모듈 | Prefix | 실제 라우팅 파일 | 주요 endpoint |
| --- | --- | --- | --- |
| Auth | `/api/v1/auth/` | `apps/api/api/auth/urls.py` | `login`, `logout`, `me`, `config`, empty redirect |
| Account | `/api/v1/account/` | `apps/api/api/account/urls.py` | `overview`, `affiliation`, `affiliation/approve`, `affiliation/requests`, `affiliation/members`, `affiliation/reconfirm`, `external-affiliations/sync`, `access/grants`, `access/manageable`, `users`, `line-sdwt-options` |
| Emails | `/api/v1/emails/` | `apps/api/api/emails/urls.py` | `inbox/`, `sent/`, `mailboxes/`, `mailboxes/summary/`, `mailboxes/members/`, `unassigned/`, `unassigned/claim/`, `ingest/`, `outbox/process/`, `assets/ocr/claim/`, `assets/ocr/update/`, `bulk-delete/`, `move/`, `<email_id>/`, `<email_id>/assets/<sequence>/`, `<email_id>/html/` |
| Assistant | `/api/v1/assistant/` | `apps/api/api/assistant/urls.py` | `chat`, `rag-indexes` |
| Line Dashboard / Drone | `/api/v1/line-dashboard/` | `apps/api/api/drone/urls.py` | `early-inform`, `tables`, `tables/update`, `jira-keys`, `notification-targets`, `notification-target-mappings`, `jira-user-sdwt-prods`, `notification-recipients`, `notification-recipient-permissions`, `my-notification-recipient-targets`, `history`, `line-ids`, `sop/<sop_id>/instant-inform`, `sop/<sop_id>/retry-channel`, `sop/ingest/pop3/trigger`, `sop/precheck`, `sop/trigger` |
| L3 Spider | `/api/v1/l3_spider/` | `apps/api/api/l3_spider/urls.py` | `meta`, `summary`, `data` |
| Timeline | `/api/v1/timeline/` | `apps/api/api/timeline/urls.py` | `lines`, `sdwts`, `prc-groups`, `equipments`, `equipment-info/<line_id>/<eqp_id>`, `equipment-info/<eqp_id>`, `logs`, `logs/eqp`, `logs/tip`, `logs/ctttm`, `logs/racb`, `logs/drone` |
| AppStore | `/api/v1/appstore/` | `apps/api/api/appstore/urls.py` | `apps`, `apps/<app_id>`, `apps/<app_id>/cover`, `apps/<app_id>/like`, `apps/<app_id>/view`, `apps/<app_id>/comments`, `apps/<app_id>/comments/<comment_id>`, `apps/<app_id>/comments/<comment_id>/like` |
| VOC | `/api/v1/voc/` | `apps/api/api/voc/urls.py` | `posts`, `posts/<post_id>`, `posts/<post_id>/replies` |
| Activity | `/api/v1/activity/` | `apps/api/api/activity/urls.py` | `logs` |
| Health | `/api/v1/health/` | `apps/api/api/health/urls.py` | empty path |

## 프론트엔드 route

전역 route 조립은 `apps/web/src/routes/router.jsx`가 담당하고, 각 feature는 `apps/web/src/features/<feature>/routes.jsx`에서 route 배열을 공개합니다.

| Feature | Route | 실제 라우팅 파일 | 공개 facade |
| --- | --- | --- | --- |
| Home | `/` | `apps/web/src/features/home/routes.jsx` | `apps/web/src/features/home/index.js` |
| Auth | `/login` | `apps/web/src/features/auth/routes.jsx` | `apps/web/src/features/auth/index.js` |
| Account | `/settings`, `/settings/account`, `/settings/members` | `apps/web/src/features/account/routes.jsx` | `apps/web/src/features/account/index.js` |
| Emails | `/emails/inbox`, `/emails/sent`, `/emails/members` | `apps/web/src/features/emails/routes.jsx` | `apps/web/src/features/emails/index.js` |
| Assistant | `/assistant` | `apps/web/src/features/assistant/routes.jsx` | `apps/web/src/features/assistant/index.js` |
| Line Dashboard | `/ESOP_Dashboard`, `/ESOP_Dashboard/status/:lineId`, `/ESOP_Dashboard/history/:lineId`, `/ESOP_Dashboard/settings/:lineId`, `/ESOP_Dashboard/settings/notification/:lineId`, `/ESOP_Dashboard/settings/recipients/:lineId`, `/ESOP_Dashboard/overview` | `apps/web/src/features/line-dashboard/routes.jsx` | `apps/web/src/features/line-dashboard/index.js` |
| L3 Spider | `/l3_spider` | `apps/web/src/features/l3-spider/routes.jsx` | `apps/web/src/features/l3-spider/index.js` |
| Timeline | `/timeline`, `/timeline/:eqpId` | `apps/web/src/features/timeline/routes.jsx` | `apps/web/src/features/timeline/index.js` |
| AppStore | `/appstore` | `apps/web/src/features/appstore/routes.jsx` | `apps/web/src/features/appstore/index.js` |
| VOC | `/voc` | `apps/web/src/features/voc/routes.jsx` | `apps/web/src/features/voc/index.js` |
| Teamstaff | `/teamstaff` | `apps/web/src/features/teamstaff/routes.jsx` | `apps/web/src/features/teamstaff/index.js` |
| Errors | `*` | `apps/web/src/features/errors/routes.jsx` | `apps/web/src/features/errors/index.js` |

## 주요 DB 모델

| Django app | 모델 |
| --- | --- |
| `api.account` | `User`, `UserProfile`, `Affiliation`, `UserCurrentAffiliation`, `UserSdwtProdAccess`, `UserSdwtProdChange`, `ExternalAffiliationSnapshot` |
| `api.activity` | `ActivityLog` |
| `api.appstore` | `AppStoreApp`, `AppStoreLike`, `AppStoreComment`, `AppStoreCommentLike` |
| `api.drone` | `DroneSOP`, `DroneSopTarget`, `DroneSopTargetChannelConfig`, `DroneSopNeedToSendRule`, `DroneSopTargetMapping`, `DroneSopTargetRecipient`, `DroneSopTargetDispatch`, `DroneSopDelivery`, `DroneEarlyInform` |
| `api.emails` | `Email`, `EmailOutbox`, `EmailAsset` |
| `api.voc` | `VocPost`, `VocReply` |
| `api.auth`, `api.assistant`, `api.rag`, `api.timeline`, `api.l3_spider`, `api.health`, `api.common` | 자체 업무 model 없이 account/common/external DB 또는 외부 API/파일을 사용 |

## Management command

| Command | 위치 | 목적 |
| --- | --- | --- |
| `seed_dummy_emails` | `apps/api/api/emails/management/commands/seed_dummy_emails.py` | 로컬 개발용 더미 이메일 생성과 dummy RAG 등록 |
| `process_email_outbox` | `apps/api/api/emails/management/commands/process_email_outbox.py` | pending `EmailOutbox`를 RAG insert/delete 호출로 처리 |
| `seed_drone_dummy_data` | `apps/api/api/drone/management/commands/seed_drone_dummy_data.py` | Drone 개발용 샘플 데이터 생성 |
| `seed_drone_affiliation_notifications` | `apps/api/api/drone/management/commands/seed_drone_affiliation_notifications.py` | account 소속 기준 Drone SOP 알림 대상/채널/수신자 기본값 생성 |
| `seed_drone_targets_from_file` | `apps/api/api/drone/management/commands/seed_drone_targets_from_file.py` | JSON 기준 Drone SOP/발송 이력/알림 설정 초기화 후 대상/채널/수신자 생성 |
| `prune_drone_sop` | `apps/api/api/drone/management/commands/prune_drone_sop.py` | 보관 기간을 초과한 Drone SOP 데이터 정리 |
| `purge_drone_sop` | `apps/api/api/drone/management/commands/purge_drone_sop.py` | Drone SOP 데이터를 수동 전체 삭제 또는 dry-run 확인 |

## Env 파일과 설정 그룹

| 파일 | 역할 |
| --- | --- |
| `env/api.common.env` | API 공통 기본값, DB, auth, POP3, Drone, RAG, LLM, Mail API 기본 설정 |
| `env/api.dev.env` | 로컬 dummy ADFS/RAG/LLM/Mail/Jira 개발 설정 |
| `env/api.oidc.dev.env` | 실제 OIDC 개발 연결용 API 설정 |
| `env/api.prod.env` | 운영 배포용 API 설정 템플릿 |
| `env/web.dev.env` | 로컬 web 개발 설정 |
| `env/web.oidc.dev.env` | 실제 OIDC 개발 연결용 web 설정 |
| `env/web.prod.env` | 운영 web 설정 템플릿 |
| `minio.env` | 로컬 MinIO 계정과 endpoint |

주요 env group은 `DJANGO_*`, `DJANGO_DB_*`, `TIMELINE_DB_*`, `L3_SPIDER_*`, `OIDC_*`, `ADFS_*`, `AIRFLOW_TRIGGER_TOKEN`, `EMAIL_POP3_*`, `DRONE_*`, `KNOX_MESSENGER_*`, `ASSISTANT_*`, `RAG_*`, `MAIL_API_*`, `MINIO_*`, `VITE_*`입니다.
