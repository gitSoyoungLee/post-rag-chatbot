"""수집한 우체국 발송조건 HTML → 국가 메타데이터(JSON) + 국가별 문서(md).

입력:  data/raw/epost/<service>/<CODE>.html  (collect_epost_conditions.py 결과)
출력:  data/countries.json                   (항목 메타데이터, 컬렉션 1)
       data/docs/epost/countries/<CODE>.md   (국가별 발송조건 문서, 컬렉션 2)
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "epost"
OUT_JSON = ROOT / "data" / "countries.json"
OUT_MD_DIR = ROOT / "data" / "docs" / "epost" / "countries"

BASE = "https://ems.epost.go.kr"
SERVICES = {
    "ems": ("국제특급(EMS)", "/front.EmsApplyGoCondition.postal"),
    "premium": ("EMS프리미엄", "/front.EmsApplyGoConditionPremium.postal"),
    "parcel": ("국제소포(항공/선편)", "/front.EmsParcelAirShipSendCondition.postal?frnMailDivcdTab=2&frnTranspPartyDivcd=1"),
    "letter": ("국제통상(서신·인쇄물·소형포장물 등)", "/front.EmsParcelAirShipSendCondition.postal?frnMailDivcdTab=1&frnTranspPartyDivcd=1"),
    "kpacket": ("K-Packet", "/front.EmsKPacketSendCondition.postal?frnMailDivcdTab=14&frnTranspPartyDivcd=1"),
}
TABS = {
    "tab-1": "접수 시 주의사항",
    "tab-2": "금지·제한품목",
    "tab-3": "배달특이사항",
    "tab-4": "세관·통관사항",
}
LICENSE = "공공저작물(과학기술정보통신부 우정사업본부), 출처 표시 후 비상업적 교육 목적 이용"


def clean_text(text: str) -> str:
    """textarea 원문을 md 목록 형태로 정리한다."""
    lines = []
    for raw in text.replace("\r", "").split("\n"):
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        line = re.sub(r"^(ㅇ|o|O|●|•)\s*", "- ", line)
        line = re.sub(r"^-\s+-\s*", "  - ", line)
        if line.startswith("※"):
            line = "  " + line
        lines.append(line)
    return "\n".join(lines)


def parse_page(path: Path) -> dict:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")

    fields: dict[str, str] = {}
    table = soup.find("table", class_="table_row")
    if table:
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            for th, td in zip(cells[::2], cells[1::2]):
                key = th.get_text(" ", strip=True).replace("예시", "").strip()
                val = " ".join(td.get_text(" ", strip=True).split())
                val = val.replace("요금 조회", "").strip()
                if key:
                    fields[key] = val

    notice = ""
    h = soup.find("h4", string=lambda t: t and "긴급공지" in t)
    if h:
        ta = h.parent.find_next("textarea")
        if ta:
            notice = clean_text(ta.get_text())

    sections: dict[str, str] = {}
    for tab_id, title in TABS.items():
        div = soup.find(id=tab_id)
        if div:
            ta = div.find("textarea")
            sections[title] = clean_text(ta.get_text() if ta else div.get_text("\n"))

    return {"fields": fields, "notice": notice, "sections": sections}


def split_items(text: str, label: str) -> list[str]:
    """'금지품목 : a, b, c' 형태에서 품목 목록을 뽑는다."""
    m = re.search(label + r"\s*[:：]\s*(.+)", text)
    if not m:
        return []
    items = re.split(r",(?![^()]*\))|/(?![^()]*\))", m.group(1))
    return [i.strip(" .") for i in items if i.strip(" .")]


def to_int(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"\d[\d,]*", text)
    return int(m.group().replace(",", "")) if m else None


def main() -> None:
    names: dict[str, str] = {}
    pages: dict[str, dict[str, dict]] = {}
    collected: dict[str, str] = {}

    for svc in SERVICES:
        d = RAW_DIR / svc
        if not d.exists():
            continue
        lst = d / "_countries.json"
        if lst.exists():
            for c in json.loads(lst.read_text(encoding="utf-8")):
                names.setdefault(c["code"], c["name_ko"])
        for f in sorted(d.glob("*.html")):
            code = f.stem
            pages.setdefault(code, {})[svc] = parse_page(f)
            ts = datetime.fromtimestamp(f.stat().st_mtime).date().isoformat()
            collected[code] = max(collected.get(code, ts), ts)

    OUT_MD_DIR.mkdir(parents=True, exist_ok=True)
    countries = []
    for code in sorted(pages):
        svc_pages = pages[code]
        name = names.get(code, code)

        # 금지·제한품목은 소포 → EMS → K-Packet 순으로 우선 사용
        prohibited, restricted, texts = [], [], {}
        for svc in ("parcel", "ems", "premium", "letter", "kpacket"):
            text = svc_pages.get(svc, {}).get("sections", {}).get("금지·제한품목", "")
            if text:
                texts[svc] = text
            if text and not prohibited:
                prohibited = split_items(text, "금지품목")
                restricted = split_items(text, "제한품목")

        services = {}
        for svc, page in svc_pages.items():
            f = page["fields"]
            weight_key = next((k for k in f if "제한중량" in k), None)
            services[svc] = {
                "max_weight_g": to_int(f.get(weight_key)) if weight_key else None,
                "max_size": f.get("최대규격"),
                "rate_zone": f.get("요금적용지역"),
                "fields": f,
            }

        countries.append({
            "code": code,
            "name_ko": name,
            "services": services,
            "available_services": [SERVICES[s][0] for s in SERVICES if s in svc_pages],
            "prohibited": prohibited,
            "restricted": restricted,
            # 정형 추출이 안 되는 국가를 위해 서비스별 원문도 보관
            "prohibited_text": texts,
            "source":"우체국 국제우편 국가별 발송조건",
            "source_urls": {s: BASE + SERVICES[s][1] for s in svc_pages},
            "collected_at": collected[code],
        })

        # --- 국가별 md 문서 ---
        fm = [
            "---",
            f"doc_id: epost-country-{code}",
            f"title: {name} 국제우편 발송조건",
            "source_type: 우체국안내",
            "source_name: 우체국 국제우편 국가별 발송조건",
            "source_urls:",
            *[f"  {s}: {BASE + SERVICES[s][1]}" for s in svc_pages],
            f"country_codes: [{code}]",
            f"collected_at: {collected[code]}",
            f"license: {LICENSE}",
            "---",
            "",
            f"# {name}({code}) 국제우편 발송조건",
            "",
            f"한국에서 {name}(으)로 보낼 수 있는 서비스: {', '.join(SERVICES[s][0] for s in SERVICES if s in svc_pages)}",
            "",
        ]
        body = []
        for svc in SERVICES:
            if svc not in svc_pages:
                continue
            page = svc_pages[svc]
            body += [f"## {name} {SERVICES[svc][0]}", "", "### 기본 조건", ""]
            body += [f"- {k}: {v}" for k, v in page["fields"].items() if v]
            body.append("")
            if page["notice"]:
                body += ["### 긴급공지", "", page["notice"], ""]
            for title, text in page["sections"].items():
                if text:
                    body += [f"### {title}", "", text, ""]
        (OUT_MD_DIR / f"{code}.md").write_text("\n".join(fm + body), encoding="utf-8")

    OUT_JSON.write_text(json.dumps(countries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"국가 {len(countries)}개 → {OUT_JSON.relative_to(ROOT)}, {OUT_MD_DIR.relative_to(ROOT)}/ (기준일 {date.today()})")


if __name__ == "__main__":
    main()
