"""정답 세트(evals/golden_items.json)로 품목 판정 정확도와 검색 재현율을 측정한다.

대화 분석(슬롯 추출)을 거치지 않고, 국가·서비스·품목을 정답 세트에서 바로 넣어
검색 → 판정 → 인용 검증 구간만 평가한다. 그래프의 judge_items 노드와 같은 규칙을 쓴다.

    uv run python scripts/evaluate_judgments.py
    uv run python scripts/evaluate_judgments.py --limit 5 --k 8
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

from post_rag.clients import create_chat_model
from post_rag.judgment import ItemJudge, validate_decision
from post_rag.models import Item, ItemDecision
from post_rag.vector_store import RegulationRetriever

from eval_common import ROOT, default_output, run_metadata

DEFAULT_CASES = ROOT / "evals" / "golden_items.json"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def judge_case(case: dict, retriever: RegulationRetriever, judge: ItemJudge, k: int) -> dict:
    item = Item(
        original_name=case["item"]["name"],
        normalized_name=case["item"]["name"],
        categories=case["item"]["categories"],
    )
    started = time.perf_counter()
    evidence = retriever.by_item(item, country_code=case["country_code"], service_type=case["service"], k=k)
    for index, entry in enumerate(evidence, 1):
        entry.evidence_id = f"I1E{index}"
    retrieval_s = time.perf_counter() - started

    # 검색 재현율: 정답 근거 문서의 정답 구절이 담긴 청크를 찾았는가
    phrase = case.get("expected_phrase")
    retrieval_hit = None
    if phrase:
        retrieval_hit = any(
            entry.document_id in case["expected_sources"] and _norm(phrase) in _norm(entry.content)
            for entry in evidence
        )

    started = time.perf_counter()
    citation_errors: list[str] = []
    if not evidence:
        decision = ItemDecision(item=item.normalized_name, status="insufficient_evidence", reason="근거 없음")
    else:
        decision = judge.judge(item, evidence)
        citation_errors = validate_decision(decision, evidence)
        if citation_errors:
            decision = ItemDecision(
                item=item.normalized_name,
                status="insufficient_evidence",
                reason="판정 인용문을 원문에서 확인하지 못했습니다.",
            )
    judge_s = time.perf_counter() - started

    status = decision.status.value
    return {
        "id": case["id"],
        "country_code": case["country_code"],
        "service": case["service"],
        "item": case["item"]["name"],
        "expected_status": case["expected_status"],
        "acceptable_statuses": case["acceptable_statuses"],
        "predicted_status": status,
        "correct": status in case["acceptable_statuses"],
        "strict_correct": status == case["expected_status"],
        "retrieval_hit": retrieval_hit,
        "citation_errors": citation_errors,
        "reason": decision.reason,
        "quotes": [quote.model_dump() for quote in decision.evidence],
        "retrieved": [
            {"evidence_id": e.evidence_id, "document_id": e.document_id, "service_type": e.service_type,
             "content": e.content[:300]}
            for e in evidence
        ],
        "latency_s": {"retrieval": round(retrieval_s, 2), "judge": round(judge_s, 2)},
    }


def summarize(results: list[dict]) -> dict:
    def rate(rows: list[dict], key: str) -> dict:
        n = len(rows)
        hits = sum(1 for r in rows if r[key])
        return {"correct": hits, "total": n, "rate": round(hits / n, 3) if n else None}

    by_status: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_status[r["expected_status"]].append(r)
    confusion = Counter((r["expected_status"], r["predicted_status"]) for r in results)
    with_phrase = [r for r in results if r["retrieval_hit"] is not None]
    hit = [r for r in with_phrase if r["retrieval_hit"]]
    miss = [r for r in with_phrase if not r["retrieval_hit"]]
    return {
        "accuracy": rate(results, "correct"),
        "strict_accuracy": rate(results, "strict_correct"),
        "accuracy_by_expected_status": {s: rate(rows, "correct") for s, rows in sorted(by_status.items())},
        "retrieval_recall": rate(with_phrase, "retrieval_hit"),
        "accuracy_when_retrieved": rate(hit, "correct"),
        "accuracy_when_missed": rate(miss, "correct"),
        "citation_failures": sum(1 for r in results if r["citation_errors"]),
        "confusion": [
            {"expected": e, "predicted": p, "count": n} for (e, p), n in sorted(confusion.items())
        ],
        "avg_latency_s": {
            "retrieval": round(sum(r["latency_s"]["retrieval"] for r in results) / len(results), 2),
            "judge": round(sum(r["latency_s"]["judge"] for r in results) / len(results), 2),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--k", type=int, default=5, help="품목당 근거 수(Top-k)")
    parser.add_argument("--output", type=Path, help="기본값: evals/results/judgments_<날짜>_<커밋>.json")
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))["cases"]
    if args.limit:
        cases = cases[: args.limit]
    retriever = RegulationRetriever()
    judge = ItemJudge(create_chat_model())

    results = []
    for index, case in enumerate(cases, 1):
        result = judge_case(case, retriever, judge, args.k)
        results.append(result)
        mark = "O" if result["correct"] else "X"
        hit = {True: "검색O", False: "검색X", None: "-"}[result["retrieval_hit"]]
        print(f"[{index}/{len(cases)}] {mark} {hit} {case['id']}: "
              f"정답 {case['expected_status']} / 예측 {result['predicted_status']}", flush=True)

    metadata = {**run_metadata(args.cases, args.limit), "top_k": args.k}
    report = {"meta": metadata, "summary": summarize(results), "results": results}
    output = args.output or default_output(metadata, prefix="judgments_")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = report["summary"]
    print(f"\n판정 정확도: {summary['accuracy']['correct']}/{summary['accuracy']['total']}"
          f" ({summary['accuracy']['rate']:.1%})")
    print(f"검색 재현율(Recall@{args.k}): {summary['retrieval_recall']['correct']}/"
          f"{summary['retrieval_recall']['total']}")
    print(f"상세 결과: {output}")


if __name__ == "__main__":
    main()
