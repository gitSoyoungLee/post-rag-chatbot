from __future__ import annotations

import json
import re


CITATION_RE = re.compile(r"\[((?:I\d+)?E\d+|G\d+)\]")
MEASURE_RE = re.compile(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(kg|g|cm|m|원)", re.IGNORECASE)


def _measures(text: str) -> set[tuple[float, str]]:
    found: set[tuple[float, str]] = set()
    for raw, unit in MEASURE_RE.findall(text):
        value = float(raw.replace(",", ""))
        normalized_unit = unit.lower()
        if normalized_unit == "kg":
            value *= 1000
            normalized_unit = "g"
        elif normalized_unit == "m":
            value *= 100
            normalized_unit = "cm"
        found.add((round(value, 4), normalized_unit))
    return found


def validate_answer(answer: str, payload: dict) -> list[str]:
    errors: list[str] = []
    evidence = [
        entry
        for entries in payload.get("evidence", {}).values()
        for entry in entries
    ]
    valid_ids = {str(entry["evidence_id"]) for entry in evidence}
    invalid_citations = sorted(set(CITATION_RE.findall(answer)) - valid_ids)
    if invalid_citations:
        errors.append(f"존재하지 않는 인용: {', '.join(invalid_citations)}")

    allowed_text = json.dumps(payload, ensure_ascii=False, default=str)
    allowed = _measures(allowed_text)
    slots = payload.get("slots", {})
    if slots.get("actual_weight_g") is not None:
        allowed.add((float(slots["actual_weight_g"]), "g"))
    rate = payload.get("rate_result") or {}
    if rate.get("amount_krw") is not None:
        allowed.add((float(rate["amount_krw"]), "원"))
    if rate.get("bracket_kg") is not None:
        allowed.add((float(rate["bracket_kg"]) * 1000, "g"))
    unsupported = _measures(answer) - allowed
    if unsupported:
        values = ", ".join(f"{value:g}{unit}" for value, unit in sorted(unsupported))
        errors.append(f"출처 없는 수치: {values}")
    return errors


def safe_fallback(payload: dict) -> str:
    status_labels = {
        "prohibited": "발송 금지",
        "restricted": "제한 또는 확인 필요",
        "no_restriction_found": "금지·제한 근거를 찾지 못함",
        "conflicting": "출처별 규정이 다름",
        "insufficient_evidence": "판단할 근거가 부족함",
    }
    lines = ["확인한 국제우편 규정을 쉽게 정리해 드릴게요."]
    for decision in payload.get("item_decisions", []):
        label = status_labels.get(decision["status"], "확인 필요")
        lines.append(f"- **{decision['item']} — {label}**  \n  {decision['reason']}")
    rate = payload.get("rate_result")
    if rate:
        lines.append(
            f"- EMS 예상 기본요금: {rate['amount_krw']:,}원 "
            f"({rate['bracket_kg']:g}kg 구간, 시행일 {rate['effective_date']})"
        )
    return "\n".join(lines)

