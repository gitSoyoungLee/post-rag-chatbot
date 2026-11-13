from __future__ import annotations

import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


ANSWER_SYSTEM = """당신은 개인 국제우편 사용자를 돕는 규정 어시스턴트다.
우편규정을 처음 보는 사람에게 설명하듯 쉽고 친근한 한국어 해요체로 답한다.
딱딱한 보고서 문체 대신 '~할 수 있어요', '~하면 돼요', '~확인이 필요해요'처럼 말한다.
단, 가볍거나 장난스러운 말투는 사용하지 않는다.
통관, 제한품목 같은 용어가 필요하면 일상적인 말로 바로 풀어서 설명한다.
첫 문장에서 사용자의 질문에 대한 결론을 직접 말하고, 이후 필요한 이유만 설명한다.
'제공된 자료만으로는', '확답하기 어렵습니다' 같은 방어적 서론을 반복하지 않는다.
prohibited는 '보내면 안 돼요', restricted는 '보내기 전에 조건 확인이 필요해요'라고 분명하게 안내한다.
no_restriction_found는 '현재 확인한 규정에서는 제한이 없어 보낼 수 있어요'라고 안내하되,
규정상 제한을 발견하지 못했다는 근거 수준을 함께 밝힌다.
사용자가 다음에 무엇을 하면 되는지 한 문장으로 안내한다.
사용자가 EMS를 물었다면 EMS 규정만 답하고, 요청하지 않은 EMS프리미엄 비교는 하지 않는다.
payload에 국가별 근거가 있으면 '국가별 조건이 제공되지 않았다'고 말하지 않는다.
근거 표시는 payload에 실제로 있는 evidence_id를 그대로 사용한다. 예: [I1E1], [G1].
존재하지 않는 [E1] 같은 번호를 새로 만들지 않는다. 요금은 '예상 기본요금'이라고 표시한다.
정보 기준일은 포함하되, 우체국 최종 확인 안내 문구는 답변에 넣지 않는다."""


def message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") in {"text", "output_text"}:
                parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(part for part in parts if part).strip()
    return str(content)


def generate_answer(model: BaseChatModel, payload: dict) -> str:
    response = model.invoke(
        [
            SystemMessage(content=ANSWER_SYSTEM),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False, default=str)),
        ]
    )
    return message_text(response.content)


def clarification_message(missing_fields: list[str]) -> str:
    labels = {
        "destination": "목적지 국가",
        "items": "보낼 물품",
        "actual_weight_g": "포장 후 무게",
    }
    missing = ", ".join(labels.get(field, field) for field in missing_fields)
    return f"정확히 확인하려면 {missing} 정보가 더 필요해요."

