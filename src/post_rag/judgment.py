from __future__ import annotations

import re

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from post_rag.models import Evidence, Item, ItemDecision


JUDGE_SYSTEM = """당신은 국제우편 규정 판정기다.
제공된 근거만 사용해 물품 하나를 판정한다.
명시적 금지는 prohibited, 조건부·통관 확인 필요는 restricted로 판정한다.
검색 근거에 제한 내용이 없으면 no_restriction_found, 근거가 부족하면 insufficient_evidence다.
quote에는 요약하지 않은 원문의 연속 구절을 그대로 복사한다.
reason은 사용자에게 바로 보여 줄 수 있는 자연스러운 한국어 존댓말로 작성한다.
근거가 없는 내용을 추측하지 않는다."""


class ItemJudge:
    def __init__(self, model: BaseChatModel) -> None:
        self._model = model.with_structured_output(ItemDecision)

    def judge(self, item: Item, evidence: list[Evidence]) -> ItemDecision:
        context = "\n\n".join(
            f"[{entry.evidence_id}] {entry.title}\n{entry.content}" for entry in evidence
        )
        return self._model.invoke(
            [
                SystemMessage(content=JUDGE_SYSTEM),
                HumanMessage(content=f"판정 품목: {item.normalized_name}\n\n근거:\n{context}"),
            ]
        )


def normalize_quote(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def validate_decision(decision: ItemDecision, evidence: list[Evidence]) -> list[str]:
    by_id = {entry.evidence_id: entry for entry in evidence}
    errors: list[str] = []
    for cited in decision.evidence:
        source = by_id.get(cited.evidence_id)
        if source is None:
            errors.append(f"존재하지 않는 근거 ID: {cited.evidence_id}")
            continue
        quote = normalize_quote(cited.quote)
        if not quote or quote not in normalize_quote(source.content):
            errors.append(f"근거에 없는 인용문: {cited.evidence_id}")
    if decision.status.value in {"prohibited", "restricted", "conflicting"} and not decision.evidence:
        errors.append("판정에 필요한 인용문이 없음")
    return errors

