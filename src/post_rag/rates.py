from __future__ import annotations

import re
from pathlib import Path

from post_rag.config import DATA_DIR
from post_rag.countries import CountryRepository
from post_rag.models import EmsRate


RATE_PATH = DATA_DIR / "docs" / "law" / "notice-rates.md"
RATE_SOURCE_URL = "https://www.law.go.kr/LSW/admRulInfoP.do?admRulSeq=2100000281734"

HEADER_CODES = {
    "호주": "AU",
    "브라질": "BR",
    "캐나다": "CA",
    "중국": "CN",
    "프랑스": "FR",
    "독일": "DE",
    "홍콩": "HK",
    "인도네시아": "ID",
    "일본": "JP",
    "말레이시아": "MY",
    "뉴질랜드": "NZ",
    "필리핀": "PH",
    "러시아": "RU",
    "싱가포르": "SG",
    "스페인": "ES",
    "대만": "TW",
    "태국": "TH",
    "영국": "GB",
    "미국": "US",
    "베트남": "VN",
    "1지역": "1",
    "2지역": "2",
    "3지역": "3",
    "4지역": "4",
}


def _normalize_headers(text: str) -> list[str]:
    text = text.replace("인도\n네시아", "인도네시아").replace("말레\n이시아", "말레이시아")
    return [name for name in HEADER_CODES if name in text]


def parse_ems_nondocument_rates(path: Path = RATE_PATH) -> dict[str, list[tuple[float, int]]]:
    text = path.read_text(encoding="utf-8")
    section = text.split("2. 특급우편요금(비서류)", 1)[1].split("## [별표 6]", 1)[0]
    lines = section.splitlines()
    rates: dict[str, list[tuple[float, int]]] = {}
    headers: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index].strip()
        if "(kg)" in line:
            header_text = line.split("(kg)", 1)[1]
            next_index = index + 1
            while next_index < len(lines) and not re.match(r"^\d+(?:\.\d+)?\s+(?:까지|〃)", lines[next_index].strip()):
                candidate = lines[next_index].strip()
                if not candidate or "중량단계" in candidate or "요금" in candidate:
                    break
                header_text += candidate
                next_index += 1
            headers = _normalize_headers(header_text)
            index = next_index
            continue

        row = re.match(r"^(\d+(?:\.\d+)?)\s+(?:까지|〃)\s+(.+)$", line)
        if row and headers:
            weight = float(row.group(1))
            amounts = [int(value.replace(",", "")) for value in re.findall(r"\d[\d,]*", row.group(2))]
            if len(amounts) == len(headers):
                for header, amount in zip(headers, amounts, strict=True):
                    rates.setdefault(HEADER_CODES[header], []).append((weight, amount))
        index += 1

    return rates


class EmsRateCalculator:
    def __init__(self, rate_path: Path = RATE_PATH) -> None:
        self._rates = parse_ems_nondocument_rates(rate_path)
        self._countries = CountryRepository()

    def calculate(self, destination_code: str, weight_g: int) -> EmsRate | None:
        country = self._countries.find(destination_code)
        if country is None:
            return None
        ems = next((service for service in country.services if service.service == "ems"), None)
        if ems is None:
            return None
        key = destination_code.upper()
        if key not in self._rates and ems.rate_zone:
            match = re.search(r"([1-4])\s*지역", ems.rate_zone)
            key = match.group(1) if match else key
        brackets = self._rates.get(key, [])
        weight_kg = weight_g / 1000
        bracket = next(((limit, amount) for limit, amount in brackets if weight_kg <= limit), None)
        if bracket is None:
            return None
        limit, amount = bracket
        return EmsRate(
            destination_code=country.code,
            destination_name=country.name_ko,
            weight_g=weight_g,
            bracket_kg=limit,
            amount_krw=amount,
            effective_date="2026-07-01",
            source_url=RATE_SOURCE_URL,
        )

