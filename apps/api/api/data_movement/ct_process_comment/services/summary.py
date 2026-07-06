"""ct_process_comment OpenWebUI 요약 배치 서비스입니다."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from api.data_movement.ct_process_comment import selectors
from api.data_movement.ct_process_comment.models import CtProcessComment

logger = logging.getLogger(__name__)


SUMMARY_STATUS_SUCCESS = "success"
SUMMARY_STATUS_FAILED = "failed"
SUMMARY_STATUS_SKIPPED = "skipped"
SUMMARY_STATUS_DRY_RUN = "dry_run"
CONTENTS_EVENT_HEADER_PATTERN = re.compile(
    r"^\[\s*(?P<time>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*/\s*(?P<author>[^\]]+?)\s*\]\s*$"
)
SUMMARY_SECTION_PREFIX_PATTERN = re.compile(r"^(원인|조치사항|결과)\s*:")
SUMMARY_TIME_LINE_PATTERN = re.compile(
    r"^(?P<time>(?:\d{4}[-/.]\d{2}[-/.]\d{2}\s+)?\d{1,2}:\d{2}(?::\d{2})?)\s+(?P<event>.+)$"
)

SUMMARY_SYSTEM_PROMPT = """당신은 설비 점검 이력 요약기입니다.
입력으로 제공된 이벤트 목록에 실제로 포함된 사실만 사용하세요.
입력에 없는 원인, 조치사항, 결과, 시간, 장비 상태를 절대로 추정하거나 생성하지 마세요.

작업:
1. 설비 점검 이력을 확인 가능한 시간 순서대로 정리하세요.
2. 입력 이벤트는 모두 출력하되, 각 시간 이벤트의 내용만 한 줄로 짧게 요약하세요.
3. 각 줄은 반드시 "[YYYY-MM-DD HH:MM] 이벤트" 형식으로 쓰세요.
4. 한 줄에는 하나의 이벤트만 쓰고, 이벤트 사이에는 줄바꿈만 사용하세요.
5. 대괄호 안 시간은 입력 이벤트의 시간을 그대로 사용하세요.
6. 입력 이벤트끼리 합치거나 누락하지 마세요.
7. 같은 시간 이벤트 안에서 같은 의미의 중복 내용만 합치세요.
8. 출력 형식 외의 설명, 추론 과정, 사과문, 안내문은 쓰지 마세요.

출력 형식:
[2026-06-19 13:44] 점검 시작
[2026-06-19 18:37] 조치 완료"""


class OpenWebUIConfigError(RuntimeError):
    """OpenWebUI 설정이 부족할 때 발생합니다."""


class OpenWebUIRequestError(RuntimeError):
    """OpenWebUI 요청 또는 응답 처리에 실패했을 때 발생합니다."""


@dataclass(frozen=True)
class OpenWebUISummaryConfig:
    """OpenWebUI 요약 호출에 필요한 설정 묶음입니다."""

    url: str
    model: str
    api_token: str = ""
    common_headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 120

    @classmethod
    def from_settings(cls) -> "OpenWebUISummaryConfig":
        """Django settings에서 OpenWebUI 설정을 로드합니다."""

        return cls(
            url=(getattr(settings, "OPENWEBUI_URL", "") or "").strip(),
            model=(getattr(settings, "OPENWEBUI_MODEL", "") or "").strip(),
            api_token=(getattr(settings, "OPENWEBUI_API_TOKEN", "") or "").strip(),
            common_headers=_parse_headers(
                getattr(settings, "OPENWEBUI_COMMON_HEADERS", "{}"),
                "OPENWEBUI_COMMON_HEADERS",
            ),
            timeout_seconds=max(1, int(getattr(settings, "OPENWEBUI_TIMEOUT_SECONDS", 120) or 120)),
        )


@dataclass(frozen=True)
class SummaryRowOutcome:
    """요약 batch에서 row 1건의 처리 결과를 표현합니다."""

    workorder_id: str
    status: str
    summary: str = ""
    error_message: str = ""


@dataclass(frozen=True)
class SummaryRunSummary:
    """요약 batch 실행 결과 집계입니다."""

    outcomes: list[SummaryRowOutcome] = field(default_factory=list)

    @property
    def processed_count(self) -> int:
        """처리 결과가 기록된 row 수를 반환합니다."""

        return len(self.outcomes)

    @property
    def success_count(self) -> int:
        """요약 저장에 성공한 row 수를 반환합니다."""

        return sum(1 for outcome in self.outcomes if outcome.status == SUMMARY_STATUS_SUCCESS)

    @property
    def failure_count(self) -> int:
        """외부 호출 또는 저장에 실패한 row 수를 반환합니다."""

        return sum(1 for outcome in self.outcomes if outcome.status == SUMMARY_STATUS_FAILED)

    @property
    def skipped_count(self) -> int:
        """요약 요청 없이 건너뛴 row 수를 반환합니다."""

        return sum(1 for outcome in self.outcomes if outcome.status == SUMMARY_STATUS_SKIPPED)

    @property
    def dry_run_count(self) -> int:
        """dry-run으로 확인한 row 수를 반환합니다."""

        return sum(1 for outcome in self.outcomes if outcome.status == SUMMARY_STATUS_DRY_RUN)


def _parse_headers(raw: str | None, source: str) -> dict[str, str]:
    """JSON 문자열 기반 header 설정을 문자열 dict로 정규화합니다."""

    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("%s 환경변수를 JSON 객체로 파싱하지 못했습니다.", source)
        return {}
    if not isinstance(parsed, dict):
        logger.warning("%s 값이 JSON 객체 형식이 아닙니다.", source)
        return {}

    headers: dict[str, str] = {}
    for key, value in parsed.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, (str, int, float, bool)):
            headers[key] = str(value)
    return headers


def _build_headers(config: OpenWebUISummaryConfig) -> dict[str, str]:
    """OpenWebUI 요청 header를 구성합니다."""

    headers = {"Content-Type": "application/json", **config.common_headers}
    if config.api_token:
        token = config.api_token
        headers["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    return headers


def _build_timestamped_event_text(contents_text: str) -> str:
    """comment header 기준으로 내용 block을 timestamp 확정 이벤트로 변환합니다."""

    events: list[str] = []
    current_time = ""
    current_lines: list[str] = []

    def flush_current_event() -> None:
        if not current_time or not current_lines:
            return
        event_text = " ".join(" ".join(current_lines).split())
        if event_text:
            events.append(f"[{current_time}] {event_text}")

    for raw_line in contents_text.splitlines():
        line = raw_line.strip()
        match = CONTENTS_EVENT_HEADER_PATTERN.match(line)
        if match:
            flush_current_event()
            current_time = match.group("time")
            current_lines = []
            continue
        if current_time and line:
            current_lines.append(line)

    flush_current_event()
    return "\n".join(events)


def build_summary_prompt(contents_text: str) -> list[dict[str, str]]:
    """OpenWebUI chat completions용 고정 message 목록을 생성합니다."""

    timestamped_events = _build_timestamped_event_text(contents_text)
    prompt_source = timestamped_events or contents_text
    source_label = "timestamped_events:" if timestamped_events else "contents_text:"

    return [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "\n".join(
                [
                    source_label,
                    "<<<",
                    prompt_source,
                    ">>>",
                ]
            ),
        },
    ]


def _extract_summary(resp_json: dict[str, Any]) -> str:
    """OpenAI 호환 응답에서 assistant content를 추출합니다."""

    try:
        choices = resp_json["choices"]
        if not choices:
            raise OpenWebUIRequestError("OpenWebUI 응답 choices가 비어 있습니다.")
        content = choices[0]["message"]["content"]
        if not isinstance(content, str):
            raise OpenWebUIRequestError("OpenWebUI 응답 content가 문자열이 아닙니다.")
    except (KeyError, IndexError, TypeError) as exc:
        raise OpenWebUIRequestError(f"OpenWebUI 응답 포맷이 기대와 다릅니다. raw={resp_json!r}") from exc

    summary = content.strip()
    if not summary:
        raise OpenWebUIRequestError("OpenWebUI 응답 content가 비어 있습니다.")
    return _normalize_summary_text(summary)


def _format_summary_event_line(raw_line: str) -> str:
    """요약 이벤트 한 줄을 Log Detail 표시 형식으로 정규화합니다."""

    line = raw_line.strip().strip("-•, ")
    if not line:
        return ""
    if line.startswith("["):
        return line

    match = SUMMARY_TIME_LINE_PATTERN.match(line)
    if match:
        return f"[{match.group('time')}] {match.group('event').strip()}"
    return line


def _normalize_summary_text(summary: str) -> str:
    """OpenWebUI 응답을 짧은 streaming 표시용 요약 문자열로 정리합니다."""

    normalized_lines: list[str] = []
    for raw_line in summary.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        split_by_comma = False
        if line.startswith("시간순 요약:"):
            line = line.split(":", 1)[1].strip()
            split_by_comma = True
        if not line or SUMMARY_SECTION_PREFIX_PATTERN.match(line):
            continue

        candidates = [part.strip() for part in line.split(",") if part.strip()] if split_by_comma else [line]
        for candidate in candidates:
            event_line = _format_summary_event_line(candidate)
            if event_line:
                normalized_lines.append(event_line)

    return "\n".join(normalized_lines) or summary.strip()


def request_summary(
    *,
    session: requests.Session,
    config: OpenWebUISummaryConfig,
    contents_text: str,
) -> str:
    """OpenWebUI에 contents_text 요약을 요청하고 요약 문자열을 반환합니다."""

    if not config.url:
        raise OpenWebUIConfigError("OPENWEBUI_URL 설정이 비어 있습니다.")
    if not config.model:
        raise OpenWebUIConfigError("OPENWEBUI_MODEL 설정이 비어 있습니다.")

    payload = {
        "model": config.model,
        "messages": build_summary_prompt(contents_text),
        "temperature": 0.0,
        "stream": False,
    }

    try:
        response = session.post(
            config.url,
            headers=_build_headers(config),
            json=payload,
            timeout=config.timeout_seconds,
        )
        response.raise_for_status()
        try:
            resp_json = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise OpenWebUIRequestError(
                f"OpenWebUI 응답 JSON 파싱 실패: status={response.status_code}, text={response.text[:500]!r}"
            ) from exc
    except requests.HTTPError as exc:
        status = response.status_code if "response" in locals() else "unknown"
        text_preview = getattr(response, "text", "")[:500]
        raise OpenWebUIRequestError(f"OpenWebUI HTTP 오류 [{status}]: {text_preview!r}") from exc
    except requests.RequestException as exc:
        raise OpenWebUIRequestError(f"OpenWebUI 요청 실패: {exc}") from exc

    return _extract_summary(resp_json)


def summarize_pending_ct_process_comments(
    *,
    limit: int | None = None,
    workorder_id: str | None = None,
    dry_run: bool = False,
    session: requests.Session | None = None,
    config: OpenWebUISummaryConfig | None = None,
) -> SummaryRunSummary:
    """요약 대상 comment row를 OpenWebUI로 요약하고 성공 row의 flag를 완료 처리합니다."""

    resolved_limit = limit or int(getattr(settings, "OPENWEBUI_SUMMARY_BATCH_SIZE", 100) or 100)
    if resolved_limit < 1:
        raise ValueError("limit은 1 이상이어야 합니다.")

    active_session = session or requests.Session()
    active_config = config or OpenWebUISummaryConfig.from_settings()
    outcomes: list[SummaryRowOutcome] = []

    for comment in selectors.list_pending_summary_comments(limit=resolved_limit, workorder_id=workorder_id):
        contents_text = (comment.contents_text or "").strip()
        if not contents_text:
            outcomes.append(
                SummaryRowOutcome(
                    workorder_id=comment.workorder_id,
                    status=SUMMARY_STATUS_SKIPPED,
                    error_message="contents_text가 비어 있습니다.",
                )
            )
            continue

        if dry_run:
            outcomes.append(SummaryRowOutcome(workorder_id=comment.workorder_id, status=SUMMARY_STATUS_DRY_RUN))
            continue

        try:
            summary = request_summary(
                session=active_session,
                config=active_config,
                contents_text=contents_text,
            )
            with transaction.atomic():
                updated_count = CtProcessComment.objects.filter(pk=comment.pk, update_flag="Y").update(
                    llm_summary=summary,
                    update_flag="N",
                    updated_at=timezone.now(),
                )
            if updated_count != 1:
                raise OpenWebUIRequestError("요약 저장 대상 row가 이미 변경되었습니다.")
            outcomes.append(
                SummaryRowOutcome(
                    workorder_id=comment.workorder_id,
                    status=SUMMARY_STATUS_SUCCESS,
                    summary=summary,
                )
            )
        except (OpenWebUIConfigError, OpenWebUIRequestError) as exc:
            outcomes.append(
                SummaryRowOutcome(
                    workorder_id=comment.workorder_id,
                    status=SUMMARY_STATUS_FAILED,
                    error_message=str(exc),
                )
            )

    return SummaryRunSummary(outcomes=outcomes)
