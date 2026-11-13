from __future__ import annotations

import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


ANSWER_SYSTEM = """당신은 국제우편 규정 어시스턴트다.
제공된 검증 결과만 사용해 한국어로 간결하게 답한다.
restricted를 금지로 과장하지 않고, no_restriction_found를 발송 가능이라고 단정하지 않는다.
근거는 [E1] 형식으로 표시한다. 요금은 예상 기본요금이며 실제 접수 조건에 따라 달라질 수 있다고 안내한다.
정보 기준일과 우체국 최종 확인 안내를 포함한다."""


def generate_answer(model: BaseChatModel, payload: dict) -> str:
    response = model.invoke(
        [
            SystemMessage(content=ANSWER_SYSTEM),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False, default=str)),
        ]
    )
    return str(response.content)


def clarification_message(missing_fields: list[str]) -> str:
    labels = {
        "destination": "목적지 국가",
        "items": "보낼 물품",
        "actual_weight_g": "포장 후 무게",
    }
    missing = ", ".join(labels.get(field, field) for field in missing_fields)
    return f"정확히 확인하려면 {missing} 정보가 더 필요해요."

