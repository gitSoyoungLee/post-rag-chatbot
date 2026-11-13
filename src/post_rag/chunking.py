from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


SERVICE_NAMES = {
    "국제특급(EMS)": "ems",
    "EMS프리미엄": "premium",
    "국제소포": "parcel",
    "국제통상": "letter",
    "K-Packet": "kpacket",
}


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    content: str
    metadata: dict[str, str]


def _frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    _, raw, body = text.split("---", 2)
    return yaml.safe_load(raw) or {}, body.strip()


def _service_type(section_path: list[str]) -> str:
    joined = " ".join(section_path)
    for label, value in SERVICE_NAMES.items():
        if label in joined:
            return value
    return "ALL"


def _source_url(metadata: dict) -> str:
    value = metadata.get("source_url") or metadata.get("source_urls")
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and value:
        return str(next(iter(value.values())))
    return ""


def split_markdown_document(path: Path, max_chars: int = 1200, overlap: int = 120) -> list[DocumentChunk]:
    metadata, body = _frontmatter(path.read_text(encoding="utf-8"))
    headings: list[str] = []
    sections: list[tuple[list[str], list[str]]] = []
    current: list[str] = []

    for line in body.splitlines():
        match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if match:
            if current:
                sections.append((list(headings), current))
            level = len(match.group(1))
            headings = headings[: level - 1] + [match.group(2).strip()]
            current = []
        else:
            current.append(line)
    if current:
        sections.append((list(headings), current))

    country_codes = metadata.get("country_codes") or ["ALL"]
    country_code = str(country_codes[0]) if isinstance(country_codes, list) else str(country_codes)
    document_id = str(metadata.get("doc_id") or path.stem)
    title = str(metadata.get("title") or path.stem)
    chunks: list[DocumentChunk] = []

    for section_index, (section_path, lines) in enumerate(sections):
        content = "\n".join(lines).strip()
        if not content:
            continue
        prefix = f"문서: {title}\n경로: {' > '.join(section_path)}\n\n"
        available = max(200, max_chars - len(prefix))
        starts = list(range(0, len(content), max(1, available - overlap)))
        for part_index, start in enumerate(starts):
            part = content[start : start + available].strip()
            if not part:
                continue
            chunk_id = f"{document_id}:{section_index}:{part_index}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    content=prefix + part,
                    metadata={
                        "document_id": document_id,
                        "title": title,
                        "country_code": country_code,
                        "service_type": _service_type(section_path),
                        "source_type": str(metadata.get("source_type") or "문서"),
                        "source_url": _source_url(metadata),
                        "collected_at": str(metadata.get("collected_at") or ""),
                        "section_path": " > ".join(section_path),
                    },
                )
            )
    return chunks

