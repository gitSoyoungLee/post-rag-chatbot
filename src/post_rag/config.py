from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
COUNTRIES_PATH = DATA_DIR / "countries.json"
DOCS_DIR = DATA_DIR / "docs"
CHROMA_DIR = ROOT / "chroma_db"


ITEM_CATEGORIES = (
    "식품",
    "화장품",
    "배터리",
    "액체류",
    "의약품",
    "건강보조식품",
    "식물",
    "문구류",
    "의류",
    "전자제품",
    "귀중품",
    "위험물",
    "기타",
)

