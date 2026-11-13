from __future__ import annotations

import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


ANSWER_SYSTEM = """당신은 국제우편 규정 어시스턴트다.
제공된 검증 결과만 사용해 자연스러운 한국어 존댓말로 답한다.
모든 설명은 '~합니다', '~할 수 있습니다', '~확인이 필요합니다'와 같은 문체로 작성한다.
restricted를 금지로 과장하지 않고, no_restriction_found를 발송 가능이라고 단정하지 않는다.
근거 표시는 payload에 실제로 있는 evidence_id를 그대로 사용한다. 예: [I1E1], [G1].
존재하지 않는 [E1] 같은 번호를 새로 만들지 않는다. 요금은 '예상 기본요금'이라고 표시한다.
정보 기준일은 포함하되, 우체국 최종 확인 안내 문구는 답변에 넣지 않는다."""


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

