from __future__ import annotations

import re

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from post_rag.models import Evidence, Item, ItemDecision


JUDGE_SYSTEM = """당신은 국제우편 규정 판정기다.
제공된 근거만 사용해 물품 하나를 판정한다.
명시적 금지는 prohibited, 조건부·통관 확인 필요는 restricted로 판정한다.
검색 근거에 제한 내용이 없으면 no_restriction_found, 근거가 부족하면 insufficient_evidence다.
quote에는 요약하지 않은 원문의 연속 구절을 그대로 복사한다. 말줄임표(...)로 생략하지 말고, 판정에 필요한 한 구절만 인용한다.
reason은 규정을 모르는 사용자도 이해할 수 있는 자연스러운 한국어 해요체로 작성한다.
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


# Markdown 서식·이스케이프 기호. 모델이 표(`| ... |`)나 굵게(`**`)를 빼고 인용해도 인정한다.
_MARKUP_RE = re.compile(r"[|*#`>_\\]+")
# 앞뒤가 띄어진 목록 기호(` - 용기는`)는 모델이 자주 생략한다. `리튬 이온·리튬`처럼 붙은 기호는 유지.
_BULLET_RE = re.compile(r"(?:^|(?<=\s))[-•·ㅇ](?=\s)")
# 생략 표시로 이어 붙인 인용은 조각마다 원문에 있어야 한다.
_ELLIPSIS_RE = re.compile(r"\[\s*(?:\.{2,}|…)\s*\]|\(\s*(?:\.{2,}|…)\s*\)|\.{2,}|…|⋯")
_MIN_FRAGMENT_CHARS = 2


def normalize_quote(text: str) -> str:
    text = _MARKUP_RE.sub(" ", text)
    text = _BULLET_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip(" -·:")


def _compact(text: str) -> str:
    """띄어쓰기 차이(`(식육가공품) : 소고기` ↔ `(식육가공품): 소고기`)를 무시하고 글자 순서만 비교한다."""
    return re.sub(r"\s+", "", normalize_quote(text))


def quote_in_source(quote: str, source: str) -> bool:
    """인용문의 모든 조각(생략 표시 기준)이 원문에 같은 글자 순서로 있는지 확인한다."""
    compact_source = _compact(source)
    fragments = [_compact(part) for part in _ELLIPSIS_RE.split(quote)]
    fragments = [part for part in fragments if len(part) >= _MIN_FRAGMENT_CHARS]
    return bool(fragments) and all(part in compact_source for part in fragments)


def validate_decision(decision: ItemDecision, evidence: list[Evidence]) -> list[str]:
    by_id = {entry.evidence_id: entry for entry in evidence}
    errors: list[str] = []
    for cited in decision.evidence:
        source = by_id.get(cited.evidence_id)
        if source is None:
            errors.append(f"존재하지 않는 근거 ID: {cited.evidence_id}")
            continue
        # 모델에게는 제목과 본문을 함께 보여주므로 제목을 포함해 대조한다.
        if not quote_in_source(cited.quote, f"{source.title}\n{source.content}"):
            errors.append(f"근거에 없는 인용문: {cited.evidence_id}")
    if decision.status.value in {"prohibited", "restricted", "conflicting"} and not decision.evidence:
        errors.append("판정에 필요한 인용문이 없음")
    return errors

