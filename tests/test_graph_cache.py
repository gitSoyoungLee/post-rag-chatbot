"""멀티턴에서 품목 판정 캐시가 재사용·재판정·근거 ID 재매김을 올바르게 하는지 검증한다.

LLM이 쓰이는 대화 분석, 품목 판정, 답변 생성은 스텁으로 대체한다.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import post_rag.graph as graph_module
from post_rag.graph import PostalAssistant
from post_rag.models import (
    Evidence,
    EvidenceQuote,
    Item,
    ItemDecision,
    RequestedOutput,
    SlotOperation,
    TurnAnalysis,
)


def _item(name: str) -> Item:
    return Item(original_name=name, normalized_name=name, categories=[])


class ScriptedAnalyzer:
    def __init__(self, turns: dict[str, TurnAnalysis]) -> None:
        self.turns = turns

    def analyze(self, query, slots) -> TurnAnalysis:
        return self.turns[query]


class StubRetriever:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def by_item(self, item, country_code, service_type=None, k=5):
        self.calls.append((country_code, item.normalized_name))
        return [
            Evidence(
                evidence_id="tmp",
                document_id=f"epost-country-{country_code}",
                title=f"{country_code} 발송조건",
                content=f"{country_code} 규정: {item.normalized_name} 제한",
                country_code=country_code,
                service_type=service_type or "ALL",
                source_type="우체국안내",
            )
        ]


class CountingJudge:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def judge(self, item, evidence) -> ItemDecision:
        self.calls.append(item.normalized_name)
        return ItemDecision(
            item=item.normalized_name,
            status="restricted",
            reason="스텁 판정",
            evidence=[EvidenceQuote(evidence_id=evidence[0].evidence_id, quote=evidence[0].content)],
        )


def _turn(**kwargs) -> TurnAnalysis:
    return TurnAnalysis(
        query_type="shipment_request",
        requested_outputs=[RequestedOutput.ITEM_POLICY],
        **kwargs,
    )


@pytest.fixture
def assistant(monkeypatch):
    monkeypatch.setattr(graph_module, "generate_answer", lambda model, payload: "확인했어요.")
    bot = PostalAssistant(model=MagicMock())
    bot.analyzer = ScriptedAnalyzer(
        {
            "미국에 립밤이랑 과자": _turn(
                destination_operation=SlotOperation.REPLACE,
                destination_code="US",
                items_operation=SlotOperation.REPLACE,
                items=[_item("립밤"), _item("과자")],
                service_operation=SlotOperation.REPLACE,
                preferred_service="ems",
            ),
            "앞치마도 추가": _turn(items_operation=SlotOperation.ADD, items=[_item("앞치마")]),
            "립밤은 빼줘": _turn(items_operation=SlotOperation.REMOVE, items=[_item("립밤")]),
            "그럼 일본은?": _turn(destination_operation=SlotOperation.REPLACE, destination_code="JP"),
        }
    )
    bot.retriever = StubRetriever()
    bot.judge = CountingJudge()
    return bot


def _assert_citations_resolve(state) -> None:
    """모든 판정 인용 ID가 같은 턴의 근거 목록에 존재하고, 품목 간 ID가 겹치지 않아야 한다."""
    all_ids = [entry["evidence_id"] for entries in state["evidence_by_item"].values() for entry in entries]
    assert len(all_ids) == len(set(all_ids))
    for decision in state["item_decisions"]:
        own = {entry["evidence_id"] for entry in state["evidence_by_item"][decision["item"]]}
        assert {quote["evidence_id"] for quote in decision["evidence"]} <= own


def test_decisions_are_reused_until_country_changes(assistant) -> None:
    thread = "t1"

    state = assistant.invoke("미국에 립밤이랑 과자", thread)
    assert assistant.judge.calls == ["립밤", "과자"]
    _assert_citations_resolve(state)

    # 품목 추가: 새 품목만 검색·판정
    state = assistant.invoke("앞치마도 추가", thread)
    assert assistant.judge.calls[2:] == ["앞치마"]
    assert [call[1] for call in assistant.retriever.calls[2:]] == ["앞치마"]
    assert [d["item"] for d in state["item_decisions"]] == ["립밤", "과자", "앞치마"]
    _assert_citations_resolve(state)

    # 품목 제거: 남은 품목은 모두 캐시에서 재사용, 근거 ID는 새 순서로 다시 매김
    state = assistant.invoke("립밤은 빼줘", thread)
    assert len(assistant.judge.calls) == 3
    assert state["evidence_by_item"]["과자"][0]["evidence_id"] == "I1E1"
    assert state["evidence_by_item"]["앞치마"][0]["evidence_id"] == "I2E1"
    _assert_citations_resolve(state)

    # 국가 변경: 캐시 키가 달라져 모든 품목 재판정
    state = assistant.invoke("그럼 일본은?", thread)
    assert assistant.judge.calls[3:] == ["과자", "앞치마"]
    assert {call[0] for call in assistant.retriever.calls[-2:]} == {"JP"}
    _assert_citations_resolve(state)


def test_insufficient_evidence_is_not_cached(assistant) -> None:
    assistant.retriever.by_item = lambda *args, **kwargs: []

    assistant.invoke("미국에 립밤이랑 과자", "t2")
    state = assistant.invoke("앞치마도 추가", "t2")

    assert state["decision_cache"] == {}
    assert all(d["status"] == "insufficient_evidence" for d in state["item_decisions"])
