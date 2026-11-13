from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
COUNTRIES_PATH = DATA_DIR / "countries.json"
DOCS_DIR = DATA_DIR / "docs"
CHROMA_DIR = ROOT / "chroma_db"

GMS_KEY = os.getenv("GMS_KEY", "")
GMS_BASE_URL = os.getenv("GMS_BASE_URL", "https://gms.ssafy.io/gmsapi/api.openai.com/v1")
GMS_CHAT_MODEL = os.getenv("GMS_CHAT_MODEL", "gpt-6.1-sol")
GMS_EMBEDDING_MODEL = os.getenv("GMS_EMBEDDING_MODEL", "text-embedding-3-small")


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

