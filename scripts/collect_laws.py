"""국가법령정보센터에서 국제우편 관련 법령·고시 현행본을 받아 md로 변환한다.

출력: data/raw/law/<slug>.html, data/docs/law/<slug>.md
법령·고시는 저작권법 제7조에 따라 저작권 보호 대상이 아니다.
"""

from __future__ import annotations

import html as htmllib
import re
import time
from datetime import date
from pathlib import Path

import requests

from hwp_text import any_text

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "law"
MD_DIR = ROOT / "data" / "docs" / "law"
BASE = "https://www.law.go.kr"
HEADERS = {"User-Agent": "Mozilla/5.0 (post-rag-chatbot; educational project)"}
DELAY_SEC = 2.0
LICENSE = "법령·고시(저작권법 제7조, 보호대상 아님)"

# slug: 법령명(검색어와 정확히 일치해야 함)
LAWS = {
    "postal-act": "우편법",
    "postal-act-decree": "우편법 시행령",
    "postal-act-rule": "우편법 시행규칙",
    "international-postal-regulation": "국제우편규정",
}

# slug: 고시명
ADM_RULES = {
    "notice-mail-types-conditions": "국제우편물의 종류별 이용조건 및 취급절차",
    "notice-packaging-spec": "외국으로 발송하는 우편물의 규격·포장 및 외부기재사항",
    "notice-prohibited-items": "국제우편금지물품",
    "notice-domestic-prohibited-items": "우편금지물품의 내용에 관한 고시",
    "notice-compensation": "국제우편물 손해배상액과 국제특급우편 이용자에 대한 실비 지급기준",
    "notice-rates": "국제우편에 관한 요금",
    "notice-linked-service-rates": "국제우편 연계서비스 요금",
    "notice-discounts": "국제우편요금등을 감액할 수 있는 우편물의 종류·취급요건·감액범위",
    "notice-bulk-payment": "국제우편요금의 별납 및 후납의 표시와 취급우체국",
    "notice-fees": "국제우편 이용에 관한 수수료",
}


def fetch(method: str, url: str, **kw) -> requests.Response:
    for attempt in range(5):
        try:
            r = requests.request(method, url, headers=HEADERS, timeout=60, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException:
            time.sleep(DELAY_SEC * (2 ** attempt))
    raise RuntimeError(f"요청 실패: {url}")


def request(method: str, url: str, **kw) -> str:
    r = fetch(method, url, **kw)
    r.encoding = "utf-8"
    return r.text


def strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def find_law(name: str) -> tuple[str, str, str]:
    """현행 법령의 (lsiSeq, efYd, 제목줄)을 찾는다."""
    target = name.replace(" ", "")
    html = request("POST", f"{BASE}/LSW/lsScListR.do?menuId=1&subMenuId=15&tabMenuId=81",
                   data={"q": name, "outmax": "100", "pg": "1", "section": "lawNm"})
    for m in re.finditer(r"onclick=\"lsViewWideAll\('(\d+)','(\d+)','[^']*',\$\(this\),'(\d)'[^\"]*\"[^>]*>(.*?)</a>", html, re.S):
        seq, ef, cur, title = m.group(1), m.group(2), m.group(3), strip_tags(m.group(4))
        title_name = re.sub(r"^\d+\.\s*", "", title).split("[")[0].replace(" ", "")
        if title_name == target and cur == "3":  # 3 = 현행
            return seq, ef, re.sub(r"^\d+\.\s*", "", title)
    raise RuntimeError(f"현행 법령을 찾지 못함: {name}")


def find_adm_rule(name: str) -> tuple[str, str]:
    html = request("POST", f"{BASE}/LSW/admRulScListR.do?menuId=5&subMenuId=41&tabMenuId=183",
                   data={"q": name, "outmax": "100", "pg": "1", "section": "admRulNm",
                         "p6": "2,3", "admType": "N", "admRulSeq": "0"})
    for m in re.finditer(r"showAdmRulCts\('(\d+)'[^\"]*\"[^>]*>(.*?)</a>", html, re.S):
        title = re.sub(r"^\d+\.\s*", "", strip_tags(m.group(2)))
        if title.split("[")[0].strip().replace(" ", "") == name.replace(" ", ""):
            return m.group(1), title
    raise RuntimeError(f"현행 고시를 찾지 못함: {name}")


def body_to_md(html: str) -> str:
    html = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"<img[^>]*flDownload\.do\?flSeq=(\d+)[^>]*>",
                  lambda m: f"\n[표·그림: 원문 이미지 {BASE}/LSW/flDownload.do?flSeq={m.group(1)}]\n", html)
    html = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", html)
    text = htmllib.unescape(re.sub(r"<[^>]+>", "", html))
    lines = []
    for raw in text.split("\n"):
        line = re.sub(r"[ \t　]+", " ", raw).strip()
        if not line or line in {"판례", "연혁", "위임행정규칙", "규제", "한눈보기", "펼치기", "접기"}:
            continue
        # 이미지 alt/onclick 속성이 본문으로 새어 나온 잔재 제거
        line = re.sub(r"[^\"<>]*\"\s*src=\"[^\"]*\"\s*/?>", "", line)
        line = re.sub(r"^.*href=\"#AJAX\">", "", line).strip()
        if not line:
            continue
        if re.match(r"^제\d+장\s", line):
            line = "## " + line
        elif re.match(r"^제\d+조(의\d+)?\(", line):
            m = re.match(r"^(제\d+조(?:의\d+)?\([^)]*\))\s*(.*)$", line)
            line = f"### {m.group(1)}" + (f"\n\n{m.group(2)}" if m.group(2) else "")
        elif re.match(r"^부 ?칙", line):
            line = "## " + re.sub(r"^부 ?칙", "부칙", line)
        lines.append(line)
    md = "\n".join(lines)
    # 조문 참조가 별도 줄로 끊긴 것(예: "국제우편규정\n제15조\n제1항") 이어 붙이기
    md = re.sub(r"\n(제\d+조(?:의\d+)?)\n", r" \1 ", md)
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def attachments_md(slug: str, html: str) -> str:
    """본문에 연결된 별표(HWP/HWPX/PDF)를 받아 텍스트로 붙인다.

    같은 별표가 한글·PDF 두 형식으로 올라온 경우 표 행이 잘 유지되는 PDF를 우선한다.
    """
    by_name: dict[str, list[tuple[str, Path]]] = {}
    for m in re.finditer(r"flDownload\.do\?flSeq=(\d+)&amp;flNm=([^&\"']+)&amp;bylClsCd=200201", html):
        seq, name = m.group(1), requests.utils.unquote(m.group(2).replace("+", " ")).strip()
        files = by_name.setdefault(name, [])
        if any(s == seq for s, _ in files):
            continue
        path = RAW_DIR / f"{slug}-byl-{seq}.bin"
        if not path.exists():
            time.sleep(DELAY_SEC)
            r = fetch("GET", f"{BASE}/LSW/flDownload.do", params={"flSeq": seq, "bylClsCd": "200201"})
            path.write_bytes(r.content)
        files.append((seq, path))

    parts = []
    for name, files in by_name.items():
        files.sort(key=lambda f: 0 if f[1].read_bytes()[:4] == b"%PDF" else 1)
        text, url = "", ""
        for seq, path in files:
            url = url or f"{BASE}/LSW/flDownload.do?flSeq={seq}&bylClsCd=200201"
            try:
                text = any_text(str(path))
            except Exception:
                text = ""
            if text:
                url = f"{BASE}/LSW/flDownload.do?flSeq={seq}&bylClsCd=200201"
                break
        parts.append(f"## {name}\n\n원문: {url}\n\n" + (text or "(원문 파일 참조)"))
    return "\n\n".join(parts)


def write_md(slug: str, title: str, doc_type: str, url: str, header: str, body: str) -> None:
    front = "\n".join([
        "---",
        f"doc_id: law-{slug}",
        f"title: {title}",
        f"source_type: {doc_type}",
        f"source_url: {url}",
        "country_codes: [ALL]",
        f"collected_at: {date.today().isoformat()}",
        f"license: {LICENSE}",
        "---",
        "",
        f"# {title}",
        "",
        header,
        "",
    ])
    (MD_DIR / f"{slug}.md").write_text(front + body + "\n", encoding="utf-8")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    MD_DIR.mkdir(parents=True, exist_ok=True)

    for slug, name in LAWS.items():
        raw = RAW_DIR / f"{slug}.html"
        seq, ef, header = find_law(name)
        time.sleep(DELAY_SEC)
        if not raw.exists():
            raw.write_text(request("POST", f"{BASE}/LSW/lsInfoR.do",
                                   data={"lsiSeq": seq, "efYd": ef, "chrClsCd": "010202", "ancYnChk": "0"}),
                           encoding="utf-8")
            time.sleep(DELAY_SEC)
        url = f"{BASE}/LSW/lsInfoP.do?lsiSeq={seq}&efYd={ef}"
        body = body_to_md(raw.read_text(encoding="utf-8"))
        write_md(slug, name, "법령", url, header, body)
        print(f"[법령] {name}: {header} ({len(body)}자)")

    for slug, name in ADM_RULES.items():
        raw = RAW_DIR / f"{slug}.html"
        seq, header = find_adm_rule(name)
        time.sleep(DELAY_SEC)
        if not raw.exists():
            raw.write_text(request("POST", f"{BASE}/LSW/admRulInfoR.do", data={"admRulSeq": seq}),
                           encoding="utf-8")
            time.sleep(DELAY_SEC)
        url = f"{BASE}/LSW/admRulInfoP.do?admRulSeq={seq}"
        raw_html = raw.read_text(encoding="utf-8")
        body = body_to_md(raw_html)
        extra = attachments_md(slug, raw_html)
        if extra:
            body += "\n\n" + extra
        write_md(slug, name, "고시", url, header, body)
        print(f"[고시] {name} ({len(body)}자)")


if __name__ == "__main__":
    main()
