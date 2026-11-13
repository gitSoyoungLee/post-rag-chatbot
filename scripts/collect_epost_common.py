"""우체국 국제우편 공통 안내 페이지(모든 국가 공통) 수집 → md 변환.

출력: data/raw/epost/common/<slug>.html, data/docs/epost/common/<slug>.md
"""

from __future__ import annotations

import re
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "epost" / "common"
MD_DIR = ROOT / "data" / "docs" / "epost" / "common"
BASE = "https://ems.epost.go.kr"
HEADERS = {"User-Agent": "Mozilla/5.0 (post-rag-chatbot; educational project)"}
DELAY_SEC = 2.5
LICENSE = "공공저작물(과학기술정보통신부 우정사업본부), 출처 표시 후 비상업적 교육 목적 이용"

MAIN = "#sbody_layout .contents"  # ePost 일반 페이지 본문 영역

# slug: (제목, 경로, 본문 CSS 선택자)
PAGES = {
    "ems-common-notice": ("EMS 국가별 공통사항", "/ems/front/survey/pafao04b09.jsp", "body"),
    "sendable-items": ("보낼 수 있는 물품 / 보낼 수 없는 물품(항공탑재금지물품)", "/front.Introduction04Newpop.postal", "#contents_layout3"),
    # 우편 종류별 서비스 안내
    "service-ems": ("국제특급(EMS) 서비스 안내", "/front.Introduction01.postal", MAIN),
    "service-parcel": ("국제소포 서비스 안내", "/front.Introduction10.postal", MAIN),
    "service-ems-premium": ("EMS프리미엄 서비스 안내", "/front.Introduction15.postal", MAIN),
    "service-small-packet": ("소형포장물 서비스 안내", "/front.Introduction20.postal", MAIN),
    "service-kpacket": ("K-Packet 서비스 안내", "/front.Introduction14.postal", MAIN),
    # 손해배상·부가취급·통관 관련 안내
    "compensation": ("국제우편 손해배상 규정", "/front.Tracking05.postal", MAIN),
    "extra-service-fees": ("국제우편 부가취급 수수료", "/front.Delivery03.postal", MAIN),
    "commercial-invoice": ("상업송장 쓰는 법", "/front.Info_01.postal", MAIN),
    "export-confirmation": ("수출우편물 발송확인", "/front.Info_05.postal", MAIN),
    "us-food-prior-notice": ("미국행 식품 사전신고", "/front.Info_06.postal", MAIN),
    "quarantine": ("국제우편물 동·식물 검역 안내", "/front.Info_07.postal", MAIN),
    "rate-zones": ("국가별 요금적용 지역", "/front.EmsDeliveryDelivery04.postal", MAIN),
}


def fetch(url: str) -> str:
    for attempt in range(4):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            return r.text
        except requests.RequestException:
            time.sleep(DELAY_SEC * (2 ** attempt))
    raise RuntimeError(f"요청 실패: {url}")


def html_to_md(html: str, selector: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "button", "select", "input"]):
        tag.decompose()
    for a in soup.find_all("a", string=re.compile(r"닫기|열기|검색")):
        a.decompose()
    root = soup.select_one(selector) or soup.body
    for nav in root.select("ul.tab_menu, ul.tabs, div.tab_wrap, .location, .page_navi"):
        nav.decompose()
    md = markdownify(str(root), heading_style="ATX", strip=["a", "img"])
    md = re.sub(r"^\* (한국어|English|中国话|日本語|ภาษาไทย)\n", "", md, flags=re.M)  # 언어 탭
    md = re.sub(r"^(국제특급\(EMS\)|국제소포|EMS프리미엄|소형포장물|K-Packet)\n", "", md, count=5, flags=re.M)  # 상단 탭
    md = re.sub(r"^:\s{3}", "", md, flags=re.M)  # dl/dd 변환 잔재
    md = re.sub(r"^ {4}\* ", "* ", md, flags=re.M)
    md = re.sub(r"^>\s*$", "", md, flags=re.M)
    md = re.sub(r"^\* - ", "* ", md, flags=re.M)
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    MD_DIR.mkdir(parents=True, exist_ok=True)
    for slug, (title, path, selector) in PAGES.items():
        raw = RAW_DIR / f"{slug}.html"
        if not raw.exists():
            time.sleep(DELAY_SEC)
            raw.write_text(fetch(BASE + path), encoding="utf-8")
        body = html_to_md(raw.read_text(encoding="utf-8"), selector)
        front = "\n".join([
            "---",
            f"doc_id: epost-common-{slug}",
            f"title: {title}",
            "source_type: 우체국안내",
            f"source_url: {BASE + path}",
            "country_codes: [ALL]",
            f"collected_at: {date.today().isoformat()}",
            f"license: {LICENSE}",
            "---",
            "",
            f"# {title}",
            "",
        ])
        (MD_DIR / f"{slug}.md").write_text(front + body + "\n", encoding="utf-8")
        print(f"{slug}: {len(body)}자")


if __name__ == "__main__":
    main()
