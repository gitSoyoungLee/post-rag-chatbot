import json
from pathlib import Path


def test_evaluation_cases_cover_single_and_multiturn_requests() -> None:
    cases = json.loads(Path("evals/questions.json").read_text(encoding="utf-8"))

    assert len(cases) >= 20
    assert sum(len(case["turns"]) for case in cases) >= 25
    assert any(len(case["turns"]) > 1 for case in cases)
    assert any("calculate_ems_rate" in turn.get("expected_operations", []) for case in cases for turn in case["turns"])
    assert any("retrieve_general_regulations" in turn.get("expected_operations", []) for case in cases for turn in case["turns"])
