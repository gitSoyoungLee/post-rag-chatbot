"""평가 스크립트 공통: 실행 조건(커밋, 모델 등) 기록과 결과 파일 경로."""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from post_rag.config import LLM_BASE_URL, LLM_CHAT_MODEL, LLM_EMBEDDING_MODEL, LLM_TEMPERATURE

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "evals" / "results"


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def run_metadata(cases_path: Path, limit: int | None) -> dict:
    """결과를 재현·비교할 수 있도록 실행 조건을 함께 기록한다."""
    return {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "git_commit": _git("rev-parse", "--short", "HEAD") or "unknown",
        # 커밋되지 않은 코드 변경이 있으면 결과가 해당 커밋과 일치하지 않음을 표시
        "git_dirty": bool(_git("status", "--porcelain", "--", "src", "scripts", "evals/questions.json")),
        "llm_base_url": LLM_BASE_URL,
        "chat_model": LLM_CHAT_MODEL,
        "temperature": LLM_TEMPERATURE,
        "embedding_model": LLM_EMBEDDING_MODEL,
        "cases": str(cases_path.relative_to(ROOT)) if cases_path.is_relative_to(ROOT) else str(cases_path),
        "limit": limit,
    }


def default_output(metadata: dict, prefix: str = "") -> Path:
    date = metadata["run_at"][:10]
    suffix = "-dirty" if metadata["git_dirty"] else ""
    partial = f"-limit{metadata['limit']}" if metadata["limit"] else ""
    return RESULTS_DIR / f"{prefix}{date}_{metadata['git_commit']}{suffix}{partial}.json"
