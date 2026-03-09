# =============================================================================
# 모듈 설명: H1용 Jira 템플릿/요약 문자열을 제공합니다.
# - 주요 대상: TEMPLATE_KEY, DESCRIPTION_TEMPLATE, SUMMARY_TEMPLATE
# - 불변 조건: TEMPLATE_KEY는 "H1"로 고정입니다.
# =============================================================================

"""H1 Jira 템플릿 정의 모음."""
from __future__ import annotations

from typing import Any

TEMPLATE_KEY = "H1"

_LAYER_DEFAULT = "[BEOL 인폼 필요]"
_LAYER_RULES: tuple[tuple[str, int | str, int | str, str], ...] = (
    ("A", "000320", "058120", "FA"),
    ("A", "120140", "130120", "FA"),
    ("A", "065120", "078120", "FG"),
    ("A", "130360", "195140", "FB"),
    ("N", "000000", "090000", "DF"),
    ("U", "000000", "090000", "DF"),
    ("T", "000000", "090000", "DF"),
    ("N", "090001", "140110", "DC"),
    ("U", "090001", "140110", "DC"),
    ("T", "090001", "140110", "DC"),
)

SUMMARY_TEMPLATE = "{sdwt_initial} {layer} {main_step} {lot_id}"


def find_layer(value: str) -> str:
    """주어진 값에서 규칙에 맞는 part(layer)를 찾아 반환합니다.

    규칙은 prefix와 숫자 범위를 함께 사용합니다.
    """

    if not value or len(value) < 3:
        return _LAYER_DEFAULT

    prefix = value[0]
    try:
        num_part = int(value[2:])
    except ValueError:
        return _LAYER_DEFAULT

    for rule_prefix, start, end, part in _LAYER_RULES:
        start_num = _parse_rule_number(start)
        end_num = _parse_rule_number(end)
        if start_num is None or end_num is None:
            continue
        if prefix == rule_prefix and start_num <= num_part <= end_num:
            return part
    return _LAYER_DEFAULT


def _parse_rule_number(value: int | str) -> int | None:
    """룰 경계값을 정수로 정규화합니다.

    문자열 경계값(예: "000320")도 허용합니다.
    """

    if isinstance(value, int):
        return value
    normalized = value.strip()
    if not normalized or not normalized.isdigit():
        return None
    return int(normalized)

DESCRIPTION_TEMPLATE = """<div>
  <div style="margin:8px 0;">
    <table style="border:1px solid #ccc; border-collapse:collapse; width:auto;">
      <caption style="caption-side:bottom; text-align:right; font-size:11px; color:#888; margin:0; padding:0;">
        SOP by : {{ knoxid|default:"-" }} ({{ user_sdwt_prod|default:"-" }})
      </caption>
      <thead>
        <tr>
          <th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">Step_seq</th>
          <th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">PPID</th>
          <th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">EQP_CB</th>
          <th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">Lot_id</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{{ main_step|default:"-" }}</td>
          <td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{{ ppid|default:"-" }}</td>
          <td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{{ eqp_cb|default:"-" }}</td>
          <td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{{ lot_id|default:"-" }}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div style="margin:4px 0;">
    <div style="font-size:14px;">
      📄 CTTTM URL :
      {% if ctttm_urls %}
        {% for item in ctttm_urls %}
          <a href="{{ item.url }}" target="_blank" rel="noopener noreferrer" style="font-size:14px;">{{ item.label }}</a>{% if not forloop.last %},{% endif %}
        {% endfor %}
      {% else %}
        <span style="font-size:14px; color:#999;">-</span>
      {% endif %}
    </div>
  </div>

  <div style="margin:4px 0;">
    <div style="font-size:14px; margin-top:12px;">
      💿 Defect URL :
      {% if defect_url %}
        <a href="{{ defect_url }}" target="_blank" rel="noopener noreferrer" style="font-size:14px;">{{ lot_id|default:"-" }}</a>
      {% else %}
        <span style="font-size:14px; color:#999;">-</span>
      {% endif %}
    </div>
  </div>

  {% if comment_raw %}
    <div style="margin:4px 0;">
      <div style="font-size:14px; margin-top:12px; white-space:pre-wrap;">🎨 Comment : {{ comment_raw }}</div>
      <div style="font-size:14px; margin-top:12px; white-space:pre-wrap;">💬 답변  :&nbsp; </div>
    </div>
  {% endif %}
</div>
"""


def _build_summary_context(row: dict[str, Any]) -> dict[str, str]:
    """H1 summary 템플릿에 사용할 컨텍스트를 구성합니다.

    인자:
        row: Drone SOP 행 dict(행 데이터).

    반환:
        summary 컨텍스트 dict.

    부작용:
        없음. 순수 구성입니다.
    """

    sdwt = str(row.get("sdwt_prod") or "?").strip() or "?"
    step = str(row.get("main_step") or "??").strip() or "??"
    ppid = str(row.get("ppid") or "").strip()
    normalized_step = step[2:].upper() if len(step) >= 3 else step.upper()
    return {
        "sdwt_initial": sdwt[:1],
        "layer": find_layer(step),
        "normalized_step": normalized_step,
        "main_step": step,
        "sdwt_prod": sdwt,
        "line_id": str(row.get("line_id") or "").strip(),
        "eqp_id": str(row.get("eqp_id") or "").strip(),
        "lot_id": str(row.get("lot_id") or "").strip(),
        "ppid": ppid,
    }


def build_summary(row: dict[str, Any]) -> str:
    """H1 summary 문자열을 생성합니다.

    인자:
        row: Drone SOP 행 dict(행 데이터).

    반환:
        summary 문자열.

    부작용:
        없음. 순수 문자열 구성입니다.
    """

    context = _build_summary_context(row)
    return SUMMARY_TEMPLATE.format_map(context)
