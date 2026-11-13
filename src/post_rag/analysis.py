from __future__ import annotations

import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from post_rag.config import ITEM_CATEGORIES
from post_rag.models import (
    RequestAnalysis,
    ShipmentSlots,
    SlotOperation,
    SlotUpdate,
    TurnAnalysis,
)


SYSTEM_PROMPT = """당신은 국제우편 어시스턴트의 요청 분석기다.
최신 사용자 발화와 현재 상태를 비교해 변경분만 구조화한다.
사용자가 이전 조건을 생략하면 keep을 사용한다.
국가 변경은 ISO 2자리 국가코드로 반환한다.
preferred_service는 ems, premium, parcel, letter, kpacket 중 하나의 소문자 코드로 반환한다.
물품 카테고리는 다음 값 중 복수 선택한다: {categories}
일반적인 발송 가능 여부는 item_policy, 서비스 목록·중량 조건 요청은 available_services,
EMS 가격 요청만 ems_rate를 요청 결과에 넣는다. 묻지 않은 결과를 추가하지 않는다.
지원 범위는 한국에서 외국으로 보내는 국제우편이다."""


class TurnAnalyzer:
    def __init__(self, model: BaseChatModel) -> None:
        self._model = model.with_structured_output(TurnAnalysis)

    def analyze(self, query: str, slots: ShipmentSlots) -> TurnAnalysis:
        return self._model.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT.format(categories=", ".join(ITEM_CATEGORIES))),
                HumanMessage(
                    content=(
                        f"현재 상태:\n{json.dumps(slots.model_dump(), ensure_ascii=False)}"
                        f"\n\n최신 사용자 발화:\n{query}"
                    )
                ),
            ]
        )


def to_request_analysis(turn: TurnAnalysis) -> RequestAnalysis:
    updates: list[SlotUpdate] = []
    if turn.destination_operation != SlotOperation.KEEP:
        updates.append(
            SlotUpdate(
                field="destination",
                operation=turn.destination_operation,
                value=turn.destination_code,
            )
        )
    if turn.items_operation != SlotOperation.KEEP:
        updates.append(
            SlotUpdate(
                field="items",
                operation=turn.items_operation,
                value=[item.model_dump() for item in turn.items],
            )
        )
    if turn.weight_operation != SlotOperation.KEEP:
        updates.append(
            SlotUpdate(
                field="actual_weight_g",
                operation=turn.weight_operation,
                value=turn.actual_weight_g,
            )
        )
    if turn.service_operation != SlotOperation.KEEP:
        service_aliases = {
            "EMS": "ems",
            "국제특급": "ems",
            "EMS프리미엄": "premium",
            "국제소포": "parcel",
            "국제통상": "letter",
            "K-Packet": "kpacket",
        }
        service = turn.preferred_service
        if service:
            service = service_aliases.get(service, service.lower())
        updates.append(
            SlotUpdate(
                field="preferred_service",
                operation=turn.service_operation,
                value=service,
            )
        )
    return RequestAnalysis(
        query_type=turn.query_type,
        requested_outputs=turn.requested_outputs,
        updates=updates,
    )

