from __future__ import annotations

import re

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from post_rag.models import Evidence, Item, ItemDecision


JUDGE_SYSTEM = """당신은 한국에서 외국으로 보내는 국제우편의 규정 판정기다.
제공된 근거만 사용해 물품 하나를 판정한다. 근거에 없는 내용은 추측하지 않는다.

상태는 다음 기준으로 고른다.
- prohibited: 목적지 국가의 금지품목에 이 물품의 이름이 직접 적혀 있거나, 공통 안내에서 이
  물품을 '불가'로 정한 경우. 이 물품이 속하는 분류(예: 과자는 음식물)로 금지돼 있고, 그 분류를
  조건부로 받는다는 다른 근거가 없는 경우도 여기에 해당한다.
- restricted: 수량·용기·허가서·성분·사전신고 등 조건을 갖춰야 보낼 수 있다고 정한 경우.
  제한품목, '확인필요', 조건부 접수 가능이 여기에 해당한다.
- conflicting: 이름이 직접 적힌 금지 규정과, 같은 물품을 조건부로 받는다는 다른 우체국 안내가
  함께 있어 어느 쪽인지 정할 수 없는 경우.
- no_restriction_found: 목적지 국가의 금지·제한품목과 공통 금지물품을 확인했지만 이 물품이나
  그 분류가 없는 경우.
- insufficient_evidence: 근거에 목적지 국가나 이 물품에 관한 금지·제한 내용이 아예 없어
  판단할 수 없는 경우에만 쓴다.

판단 원칙
- 금지 목록에 분류(예: 음식물)로만 묶여 있고, 같은 국가의 다른 안내(제한품목, 개인용 허용량,
  식품 사전신고 등)가 그 분류를 조건부로 받는다고 하면 restricted다.
- 국가 규정이 특정 물품을 조건부로 받는다고 따로 정했다면(예: 김치는 캔 용기만 접수)
  restricted다.
- 공통 안내 「항공탑재금지 물품」 표의 '가능'은 한국에서 비행기에 실을 수 있다는 뜻일 뿐이다.
  도착국에서 받아 준다는 근거로 쓰지 않는다. 반대로 이 표의 '불가'는 어느 나라로도 보낼 수 없다.
- '통관이 지연될 수 있다', '손해배상이 불가하다', '주의하라' 같은 일반 안내는 제한이 아니다.
- reason의 결론과 status가 반드시 같아야 한다. reason에 '금지'라고 쓰면 status도 prohibited다.

quote에는 판정 근거가 되는 원문 구절을 요약하지 않고 그대로 복사한다. 말줄임표(...)로
생략하지 말고, 판정에 필요한 한 구절만 인용한다.
reason은 규정을 모르는 사용자도 이해할 수 있는 자연스러운 한국어 해요체로 작성한다."""


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
# 모델 출력에 가끔 섞이는 보이지 않는 제어 문자(\x00 등)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_quote(text: str) -> str:
    text = _CONTROL_RE.sub(" ", text)
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

