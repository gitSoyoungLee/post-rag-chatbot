"""GMS와 로컬 ChromaDB를 사용하는 대화 시나리오 평가."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from post_rag.clients import create_chat_model
from post_rag.graph import PostalAssistant
from post_rag.vector_store import RegulationRetriever


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "evals" / "questions.json"
FORBIDDEN_TEXT = ("[{'type':", "prohibited —", "restricted —", "근거 검증을 통과하지 못해")


def evaluate(cases_path: Path, limit: int | None = None) -> dict:
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if limit:
        cases = cases[:limit]
    assistant = PostalAssistant(model=create_chat_model(), retriever=RegulationRetriever())
    results = []

    for case in cases:
        thread_id = str(uuid.uuid4())
        turn_results = []
        final = {}
        for turn in case["turns"]:
            final = assistant.invoke(turn["query"], thread_id)
            answer = final.get("answer", "")
            actual_operations = final.get("plan", {}).get("operations", [])
            missing_fields = final.get("plan", {}).get("missing_fields", [])
            errors = []
            if not isinstance(answer, str) or not answer.strip():
                errors.append("빈 답변")
            for forbidden in FORBIDDEN_TEXT:
                if forbidden in answer:
                    errors.append(f"내부 표현 노출: {forbidden}")
            for operation in turn.get("expected_operations", []):
                if operation not in actual_operations:
                    errors.append(f"누락된 작업: {operation}")
            for field in turn.get("expected_missing_fields", []):
                if field not in missing_fields:
                    errors.append(f"누락 질문 대상이 아님: {field}")
            turn_results.append(
                {
                    "query": turn["query"],
                    "answer": answer,
                    "operations": actual_operations,
                    "missing_fields": missing_fields,
                    "errors": errors,
                }
            )

        slots = final.get("slots", {})
        case_errors = [error for turn in turn_results for error in turn["errors"]]
        for field, expected in case.get("expected_final_slots", {}).items():
            if slots.get(field) != expected:
                case_errors.append(f"최종 슬롯 불일치: {field}={slots.get(field)!r}, expected={expected!r}")
        if "expected_final_items" in case:
            actual_items = [item["normalized_name"] for item in slots.get("items", [])]
            if actual_items != case["expected_final_items"]:
                case_errors.append(f"최종 품목 불일치: {actual_items!r}")
        results.append(
            {
                "id": case["id"],
                "passed": not case_errors,
                "errors": case_errors,
                "turns": turn_results,
                "final_slots": slots,
            }
        )

    passed = sum(result["passed"] for result in results)
    return {"summary": {"passed": passed, "total": len(results)}, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path, default=ROOT / "evals" / "results-latest.json")
    args = parser.parse_args()
    report = evaluate(args.cases, args.limit)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = report["summary"]
    print(f"평가 완료: {summary['passed']}/{summary['total']} 시나리오 통과")
    print(f"상세 결과: {args.output}")


if __name__ == "__main__":
    main()
