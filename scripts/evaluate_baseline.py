"""비교 기준선: 근거 검색·코드 계산 없이 LLM에게만 물었을 때의 성능.

같은 모델에게 근거 문서를 주지 않고 다음 두 가지를 묻는다.
1. 정답 세트(evals/golden_items.json)의 물품 판정 → 정확도, 금지 물품을 '제한 없음'으로 안내한 수
2. EMS 예상 기본요금 질문(evals/rate_questions.json) → 고시 요금표와 일치한 수

    uv run python scripts/evaluate_baseline.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from post_rag.clients import create_chat_model
from post_rag.judgment import JUDGE_SYSTEM
from post_rag.models import ItemStatus

from eval_common import ROOT, default_output, run_metadata

GOLDEN = ROOT / "evals" / "golden_items.json"
RATES = ROOT / "evals" / "rate_questions.json"
SERVICE_LABELS = {"ems": "국제특급(EMS)", "parcel": "국제소포", "letter": "국제통상"}

# 판정 기준은 시스템과 같은 문장을 쓰고, '제공된 근거만 사용' 부분만 뺀다.
_criteria = JUDGE_SYSTEM[JUDGE_SYSTEM.index("상태는 다음 기준으로 고른다.") : JUDGE_SYSTEM.index("quote에는")]
BASELINE_JUDGE_SYSTEM = (
    "당신은 한국에서 외국으로 보내는 국제우편의 규정 판정기다. 알고 있는 지식으로 물품 하나를 판정한다.\n\n"
    + _criteria.replace("근거에 목적지 국가나 이 물품에 관한 금지·제한 내용이 아예 없어", "알고 있는 정보로")
    + "reason은 자연스러운 한국어 해요체로 작성한다."
)
RATE_SYSTEM = (
    "당신은 한국 우체국 국제우편 안내원이다. 한국에서 외국으로 보내는 EMS(비서류) 예상 기본요금을 "
    "원 단위 숫자 하나로 답한다. 부가수수료는 제외한다."
)


class BaselineDecision(BaseModel):
    status: ItemStatus
    reason: str


class BaselineRate(BaseModel):
    amount_krw: int = Field(description="예상 기본요금(원)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="기본값: evals/results/baseline_<날짜>_<커밋>.json")
    args = parser.parse_args()

    model = create_chat_model()
    judge = model.with_structured_output(BaselineDecision)
    rate_model = model.with_structured_output(BaselineRate)

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["cases"]
    judgments = []
    for index, case in enumerate(golden, 1):
        question = (
            f"목적지: {case['country_code']}\n서비스: {SERVICE_LABELS[case['service']]}\n"
            f"판정 품목: {case['item']['name']}"
        )
        decision = judge.invoke([SystemMessage(content=BASELINE_JUDGE_SYSTEM), HumanMessage(content=question)])
        status = decision.status.value
        judgments.append({
            "id": case["id"],
            "expected_status": case["expected_status"],
            "acceptable_statuses": case["acceptable_statuses"],
            "predicted_status": status,
            "correct": status in case["acceptable_statuses"],
            "dangerous": case["expected_status"] == "prohibited" and status == "no_restriction_found",
            "reason": decision.reason,
        })
        print(f"[판정 {index}/{len(golden)}] {'O' if judgments[-1]['correct'] else 'X'} {case['id']}: "
              f"정답 {case['expected_status']} / 예측 {status}", flush=True)

    rate_cases = json.loads(RATES.read_text(encoding="utf-8"))["cases"]
    rates = []
    for case in rate_cases:
        question = f"{case['country_name']}으로 비서류 {case['weight_g'] / 1000:g}kg을 EMS로 보내면 예상 기본요금은 얼마인가요?"
        answer = rate_model.invoke([SystemMessage(content=RATE_SYSTEM), HumanMessage(content=question)])
        rates.append({
            "id": case["id"],
            "question": question,
            "expected_krw": case["expected_krw"],
            "answered_krw": answer.amount_krw,
            "correct": answer.amount_krw == case["expected_krw"],
            "error_rate": round(abs(answer.amount_krw - case["expected_krw"]) / case["expected_krw"], 3),
        })
        print(f"[요금] {'O' if rates[-1]['correct'] else 'X'} {question} 정답 {case['expected_krw']:,} / 답 {answer.amount_krw:,}",
              flush=True)

    correct = sum(r["correct"] for r in judgments)
    summary = {
        "judgment_accuracy": {"correct": correct, "total": len(judgments), "rate": round(correct / len(judgments), 3)},
        "dangerous_errors": [r["id"] for r in judgments if r["dangerous"]],
        "rate_exact_match": {"correct": sum(r["correct"] for r in rates), "total": len(rates)},
        "rate_mean_error_rate": round(sum(r["error_rate"] for r in rates) / len(rates), 3),
    }
    metadata = run_metadata(GOLDEN, None)
    report = {"meta": metadata, "summary": summary, "judgments": judgments, "rates": rates}
    output = args.output or default_output(metadata, prefix="baseline_")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\n[근거 없이] 판정 정확도: {correct}/{len(judgments)} ({correct / len(judgments):.1%})")
    print(f"[근거 없이] 금지 물품을 '제한 없음'으로 안내: {len(summary['dangerous_errors'])}건")
    print(f"[근거 없이] 요금 정확히 일치: {summary['rate_exact_match']['correct']}/{len(rates)}, "
          f"평균 오차율 {summary['rate_mean_error_rate']:.1%}")
    print(f"상세 결과: {output}")


if __name__ == "__main__":
    main()
