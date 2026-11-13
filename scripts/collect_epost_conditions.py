"""우체국 국제우편 국가별 발송조건 원본 HTML 수집기.

서비스(EMS / 국제소포 / K-Packet)마다 도착국 목록을 읽고, 국가별 발송조건 페이지를
data/raw/epost/<service>/<국가코드>.html 로 저장한다.
이미 저장된 국가는 다시 요청하지 않는다(캐시). 요청 사이에는 간격을 둔다.

사용법:
    python scripts/collect_epost_conditions.py            # 전체 서비스
    python scripts/collect_epost_conditions.py ems        # 특정 서비스만
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

BASE = "https://ems.epost.go.kr"
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "epost"

DELAY_SEC = 2.5
RETRIES = 4
TIMEOUT = 30
HEADERS = {"User-Agent": "Mozilla/5.0 (post-rag-chatbot; educational project)"}

SERVICES: dict[str, dict] = {
    "ems": {
        "name": "국제특급(EMS)",
        "path": "/front.EmsApplyGoCondition.postal",
        "params": {},
    },
    "parcel": {
        "name": "국제소포(항공/선편)",
        "path": "/front.EmsParcelAirShipSendCondition.postal",
        "params": {"frnMailDivcdTab": "2", "frnTranspPartyDivcd": "1"},
    },
    "kpacket": {
        "name": "K-Packet",
        "path": "/front.EmsKPacketSendCondition.postal",
        "params": {"frnMailDivcdTab": "14", "frnTranspPartyDivcd": "1"},
    },
}

OPTION_RE = re.compile(r"<option[^>]*value=['\"]([A-Z0-9]{2,3})['\"][^>]*>\s*([^<]+?)\s*(?:<|$)")


def fetch(session: requests.Session, method: str, url: str, **kw) -> str:
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            r = session.request(method, url, headers=HEADERS, timeout=TIMEOUT, **kw)
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            return r.text
        except requests.RequestException as e:  # 네트워크 오류 시 지수 백오프
            last = e
            time.sleep(DELAY_SEC * (2 ** attempt))
    raise RuntimeError(f"요청 실패: {url} ({last})")


def country_list(session: requests.Session, svc: dict) -> list[tuple[str, str]]:
    url = BASE + svc["path"]
    html = fetch(session, "GET", url, params=svc["params"])
    seen, out = set(), []
    for code, name in OPTION_RE.findall(html):
        if code not in seen:
            seen.add(code)
            out.append((code, name.strip()))
    return out


def collect(service: str) -> None:
    svc = SERVICES[service]
    out_dir = RAW_DIR / service
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()

    countries = country_list(session, svc)
    (out_dir / "_countries.json").write_text(
        json.dumps([{"code": c, "name_ko": n} for c, n in countries], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[{service}] 도착국 {len(countries)}개", flush=True)

    failed = []
    for i, (code, name) in enumerate(countries, 1):
        path = out_dir / f"{code}.html"
        if path.exists() and path.stat().st_size > 5000:
            continue
        time.sleep(DELAY_SEC)
        data = {"nation": code, "findBtChk": "Y", **svc["params"]}
        try:
            html = fetch(session, "POST", BASE + svc["path"], data=data)
        except RuntimeError as e:
            print(f"  ! {code} {name}: {e}", flush=True)
            failed.append(code)
            continue
        path.write_text(html, encoding="utf-8")
        print(f"  [{i}/{len(countries)}] {code} {name}", flush=True)

    print(f"[{service}] 완료, 실패 {len(failed)}개 {failed}", flush=True)


if __name__ == "__main__":
    targets = sys.argv[1:] or list(SERVICES)
    for t in targets:
        collect(t)
