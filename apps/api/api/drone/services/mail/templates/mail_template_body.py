# =============================================================================
# 모듈 설명: Drone SOP 메일 전용 본문 템플릿을 제공합니다.
# - 주요 대상: BODY_TEMPLATE
# - 핵심 전제: 메일은 Defect 링크 텍스트 대신 이미지 미리보기를 우선 표시합니다.
# =============================================================================

"""Drone SOP 메일 공통 본문 템플릿 정의 모음."""
from __future__ import annotations

BODY_TEMPLATE = """<div>
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
    <div style="font-size:14px; margin-top:12px;">💿 Defect Image :</div>
    {% if defect_urls %}
      <div style="margin-top:6px;">
        {% for item in defect_urls %}
          {% if item.image_urls %}
            {% for image_url in item.image_urls %}
              <a href="{{ item.map_url }}" target="_blank" rel="noopener noreferrer" style="display:inline-block; margin:0 8px 8px 0; text-decoration:none;">
                <img src="{{ image_url }}" alt="Defect {{ item.label }}" width="500" style="display:block; max-width:500px; width:100%; height:auto; border:1px solid #ddd;" />
              </a>
            {% endfor %}
          {% else %}
            <a href="{{ item.map_url }}" target="_blank" rel="noopener noreferrer" style="font-size:14px;">{{ item.label }}</a>{% if not forloop.last %},{% endif %}
          {% endif %}
        {% endfor %}
      </div>
    {% else %}
      <span style="font-size:14px; color:#999;">-</span>
    {% endif %}
  </div>

  {% if comment_raw %}
    <div style="margin:4px 0;">
      <div style="font-size:14px; margin-top:12px; white-space:pre-wrap;">🎨 Comment : {{ comment_raw }}</div>
      <div style="font-size:14px; margin-top:12px; white-space:pre-wrap;">💬 답변  :&nbsp; </div>
    </div>
  {% endif %}
</div>
"""


__all__ = ["BODY_TEMPLATE"]
