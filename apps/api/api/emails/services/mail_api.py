# =============================================================================
# 모듈 설명: 공용 Knox 메일 발송 어댑터의 emails 호환 export를 제공합니다.
# - 주요 함수: send_knox_mail_api
# - 불변 조건: 실제 구현은 api.common.services.mail_api에 둡니다.
# =============================================================================

from __future__ import annotations

from api.common.services.mail_api import MailSendError, requests, send_knox_mail_api

__all__ = ["MailSendError", "requests", "send_knox_mail_api"]
