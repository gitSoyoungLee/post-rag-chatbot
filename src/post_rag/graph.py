from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from post_rag.analysis import TurnAnalyzer, to_request_analysis
from post_rag.answering import clarification_message, generate_answer
from post_rag.countries import CountryRepository
from post_rag.judgment import ItemJudge, validate_decision
from post_rag.models import (
    CountryConditions,
    EmsRate,
    Evidence,
    ItemDecision,
    OperationPlan,
    ShipmentSlots,
)
from post_rag.planner import plan_operations
from post_rag.rates import EmsRateCalculator
from post_rag.state import CACHEABLE_STATUSES, apply_updates, decision_cache_key, relabel_evidence
from post_rag.vector_store import RegulationRetriever
from post_rag.validation import safe_fallback, validate_answer


class GraphState(TypedDict, total=False):
    query: str
    slots: dict[str, Any]
    plan: dict[str, Any]
    country_conditions: dict[str, Any] | None
    evidence_by_item: dict[str, list[dict[str, Any]]]
    item_decisions: list[dict[str, Any]]
    rate_result: dict[str, Any] | None
    answer: str
    query_type: str
    # 대화 내내 유지: (국가|서비스|품목) → {decision, evidence}
    decision_cache: dict[str, dict[str, Any]]


class PostalAssistant:
    def __init__(
        self,
        model: BaseChatModel,
        retriever: RegulationRetriever | None = None,
        checkpointer: MemorySaver | None = None,
    ) -> None:
        self.model = model
        self.analyzer = TurnAnalyzer(model)
        self.judge = ItemJudge(model)
        self.countries = CountryRepository()
        self.rates = EmsRateCalculator()
        self.retriever = retriever
        self.graph = self._build(checkpointer or MemorySaver())

    def _build(self, checkpointer: MemorySaver):
        builder = StateGraph(GraphState)
        builder.add_node("update_and_plan", self._update_and_plan)
        builder.add_node("lookup_conditions", self._lookup_conditions)
        builder.add_node("retrieve_items", self._retrieve_items)
        builder.add_node("judge_items", self._judge_items)
        builder.add_node("calculate_rate", self._calculate_rate)
        builder.add_node("answer", self._answer)
        builder.add_edge(START, "update_and_plan")
        builder.add_conditional_edges(
            "update_and_plan",
            lambda state: "answer" if OperationPlan.model_validate(state["plan"]).missing_fields else "lookup",
            {"answer": "answer", "lookup": "lookup_conditions"},
        )
        builder.add_edge("lookup_conditions", "retrieve_items")
        builder.add_edge("retrieve_items", "judge_items")
        builder.add_edge("judge_items", "calculate_rate")
        builder.add_edge("calculate_rate", "answer")
        builder.add_edge("answer", END)
        return builder.compile(checkpointer=checkpointer)

    def invoke(self, query: str, thread_id: str) -> GraphState:
        return self.graph.invoke(
            {"query": query},
            config={"configurable": {"thread_id": thread_id}},
        )

    def _update_and_plan(self, state: GraphState) -> GraphState:
        slots = ShipmentSlots.model_validate(state.get("slots") or {})
        turn = self.analyzer.analyze(state["query"], slots)
        analysis = to_request_analysis(turn)
        slots, _ = apply_updates(slots, analysis.updates)
        plan = plan_operations(analysis, slots)
        return {
            "slots": slots.model_dump(),
            "plan": plan.model_dump(),
            "query_type": analysis.query_type.value,
            "country_conditions": None,
            "evidence_by_item": {},
            "item_decisions": [],
            "rate_result": None,
        }

    def _lookup_conditions(self, state: GraphState) -> GraphState:
        plan = OperationPlan.model_validate(state["plan"])
        if "lookup_conditions" not in plan.operations:
            return {}
        slots = ShipmentSlots.model_validate(state["slots"])
        result = self.countries.find(slots.destination_code or "")
        return {"country_conditions": result.model_dump() if result else None}

    def _retrieve_items(self, state: GraphState) -> GraphState:
        plan = OperationPlan.model_validate(state["plan"])
        retrieval_operations = {"retrieve_by_item", "retrieve_general_regulations"}
        if not retrieval_operations.intersection(plan.operations) or self.retriever is None:
            return {}
        slots = ShipmentSlots.model_validate(state["slots"])
        found: dict[str, list[dict[str, Any]]] = {}
        if "retrieve_general_regulations" in plan.operations:
            entries = self.retriever.general(state["query"])
            for evidence_index, entry in enumerate(entries, 1):
                entry.evidence_id = f"G{evidence_index}"
            found["__general__"] = [entry.model_dump() for entry in entries]
        cache = state.get("decision_cache") or {}
        reuse = "judge_items" in plan.operations
        for item_index, item in enumerate(slots.items, 1):
            key = decision_cache_key(slots.destination_code, slots.preferred_service, item)
            if reuse and key in cache:
                continue  # 판정을 재사용하므로 검색도 생략
            entries = self.retriever.by_item(
                item,
                country_code=slots.destination_code or "ALL",
                service_type=slots.preferred_service,
            )
            for evidence_index, entry in enumerate(entries, 1):
                entry.evidence_id = f"I{item_index}E{evidence_index}"
            found[item.normalized_name] = [entry.model_dump() for entry in entries]
        return {"evidence_by_item": found}

    def _judge_items(self, state: GraphState) -> GraphState:
        plan = OperationPlan.model_validate(state["plan"])
        if "judge_items" not in plan.operations:
            return {}
        slots = ShipmentSlots.model_validate(state["slots"])
        by_item = dict(state.get("evidence_by_item", {}))
        cache = dict(state.get("decision_cache") or {})
        decisions: list[dict[str, Any]] = []
        for item_index, item in enumerate(slots.items, 1):
            key = decision_cache_key(slots.destination_code, slots.preferred_service, item)
            if key in cache:
                cached_decision, cached_evidence = relabel_evidence(
                    cache[key]["decision"], cache[key]["evidence"], item_index
                )
                by_item[item.normalized_name] = cached_evidence
                decisions.append(cached_decision)
                continue
            evidence = [Evidence.model_validate(entry) for entry in by_item.get(item.normalized_name, [])]
            if not evidence:
                decision = ItemDecision(
                    item=item.normalized_name,
                    status="insufficient_evidence",
                    reason="검색된 규정 근거가 없습니다.",
                )
            else:
                decision = self.judge.judge(item, evidence)
                if validate_decision(decision, evidence):
                    decision = ItemDecision(
                        item=item.normalized_name,
                        status="insufficient_evidence",
                        reason="판정 인용문을 원문에서 확인하지 못했습니다.",
                    )
            decisions.append(decision.model_dump())
            # 근거 부족은 일시적 검색 실패일 수 있어 캐시하지 않고 다음 턴에 다시 판정한다.
            if decision.status.value in CACHEABLE_STATUSES:
                cache[key] = {
                    "decision": decision.model_dump(),
                    "evidence": by_item.get(item.normalized_name, []),
                }
        return {"item_decisions": decisions, "evidence_by_item": by_item, "decision_cache": cache}

    def _calculate_rate(self, state: GraphState) -> GraphState:
        plan = OperationPlan.model_validate(state["plan"])
        if "calculate_ems_rate" not in plan.operations:
            return {}
        slots = ShipmentSlots.model_validate(state["slots"])
        result = self.rates.calculate(slots.destination_code or "", slots.actual_weight_g or 0)
        return {"rate_result": result.model_dump() if result else None}

    def _answer(self, state: GraphState) -> GraphState:
        plan = OperationPlan.model_validate(state["plan"])
        if plan.missing_fields:
            return {"answer": clarification_message(plan.missing_fields)}
        if state.get("query_type") == "out_of_scope":
            return {"answer": "현재는 한국에서 외국으로 보내는 국제우편 규정만 안내할 수 있어요."}
        payload = {
            "question": state["query"],
            "slots": state.get("slots", {}),
            "country_conditions": state.get("country_conditions"),
            "item_decisions": state.get("item_decisions", []),
            "rate_result": state.get("rate_result"),
            "evidence": state.get("evidence_by_item", {}),
        }
        answer = generate_answer(self.model, payload)
        errors = validate_answer(answer, payload)
        if errors:
            repair_payload = {
                **payload,
                "previous_answer": answer,
                "validation_errors": errors,
                "instruction": "검증 오류를 제거해 답변을 다시 작성하세요.",
            }
            answer = generate_answer(self.model, repair_payload)
            if validate_answer(answer, payload):
                answer = safe_fallback(payload)
        return {"answer": answer}

