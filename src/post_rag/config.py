from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
COUNTRIES_PATH = DATA_DIR / "countries.json"
DOCS_DIR = DATA_DIR / "docs"


def _env(name: str, default: str = "") -> str:
    """LLM_* 이름을 우선 읽고, 이전 이름(GMS_*)도 함께 읽는다."""
    return os.getenv(f"LLM_{name}") or os.getenv(f"GMS_{name}") or default


def _flag(name: str, default: bool) -> bool:
    value = _env(name)
    return default if not value else value.strip().lower() in {"1", "true", "yes", "on"}


# OpenAI 호환 API라면 어느 업체든 쓸 수 있다(GMS, Gemini 등).
LLM_KEY = _env("KEY")
LLM_BASE_URL = _env("BASE_URL", "https://gms.ssafy.io/gmsapi/api.openai.com/v1")
LLM_CHAT_MODEL = _env("CHAT_MODEL", "gpt-4o")
LLM_EMBEDDING_MODEL = _env("EMBEDDING_MODEL", "text-embedding-3-small")
# Responses API는 OpenAI 계열만 지원한다. Gemini 등은 false로 두고 Chat Completions를 쓴다.
LLM_USE_RESPONSES_API = _flag("USE_RESPONSES_API", False)
# 비워 두면 temperature를 보내지 않는다(일부 모델은 이 값을 거부한다).
LLM_TEMPERATURE = float(_env("TEMPERATURE")) if _env("TEMPERATURE") else None
# 한 번에 보내는 임베딩 문서 수. 업체마다 상한이 다르다(Gemini는 100).
LLM_EMBEDDING_BATCH_SIZE = int(_env("EMBEDDING_BATCH_SIZE", "100"))

# 임베딩 모델마다 벡터 공간이 다르므로 색인을 모델별 폴더에 따로 둔다.
CHROMA_DIR = ROOT / "chroma_db" / re.sub(r"[^A-Za-z0-9._-]+", "_", LLM_EMBEDDING_MODEL)


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

