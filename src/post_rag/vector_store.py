from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from post_rag.chunking import DocumentChunk, split_markdown_document
from post_rag.clients import create_embeddings
from post_rag.config import CHROMA_DIR, DOCS_DIR
from post_rag.models import Evidence, Item


COLLECTION_NAME = "postal-regulations"


def build_vector_store(
    docs_dir: Path = DOCS_DIR,
    persist_directory: Path = CHROMA_DIR,
    embeddings: Embeddings | None = None,
) -> int:
    store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings or create_embeddings(),
        persist_directory=str(persist_directory),
    )
    chunks: list[DocumentChunk] = []
    for path in sorted(docs_dir.rglob("*.md")):
        chunks.extend(split_markdown_document(path))
    store.add_documents(
        documents=[Document(page_content=chunk.content, metadata=chunk.metadata) for chunk in chunks],
        ids=[chunk.chunk_id for chunk in chunks],
    )
    return len(chunks)


class RegulationRetriever:
    def __init__(
        self,
        persist_directory: Path = CHROMA_DIR,
        embeddings: Embeddings | None = None,
        common_slots: int = 2,
    ) -> None:
        # 공통 문서(모든 국가에 적용되는 금지물품 등)에 항상 남겨 둘 근거 자리 수
        self.common_slots = common_slots
        self.store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings or create_embeddings(),
            persist_directory=str(persist_directory),
        )

    def by_item(
        self,
        item: Item,
        country_code: str,
        service_type: str | None = None,
        k: int = 5,
    ) -> list[Evidence]:
        categories = " ".join(item.categories)
        service = service_type or "국제우편"
        query = f"{country_code} {service} {item.normalized_name} {categories} 금지 제한 통관"
        country = self.store.similarity_search_with_score(
            query, k=max(k * 2, 8), filter=_where(country_code, service_type)
        )
        common = self.store.similarity_search_with_score(
            query, k=max(k, 4), filter=_where("ALL", service_type)
        )
        return _as_evidence(_merge_country_and_common(country, common, k, self.common_slots))

    def general(self, query: str, k: int = 5) -> list[Evidence]:
        return _as_evidence(self.store.similarity_search(query, k=k))


def _where(country_code: str, service_type: str | None) -> dict:
    """국가·서비스 조건을 검색 단계에서 함께 건다.

    검색 후 파이썬에서 서비스를 거르면, 여러 서비스가 섞인 국가 문서에서 상위 k개가
    다른 서비스 청크로 채워져 요청한 서비스의 근거가 사라질 수 있다.
    """
    if not service_type:
        return {"country_code": country_code}
    return {
        "$and": [
            {"country_code": country_code},
            {"service_type": {"$in": [service_type, "ALL"]}},
        ]
    }


def _unique(scored: list[tuple[Document, float]]) -> list[tuple[Document, float]]:
    """같은 문서·섹션에서 나온 청크는 가장 가까운 하나만 남긴다."""
    seen: set[tuple[str, str]] = set()
    result = []
    for document, score in scored:
        key = (str(document.metadata.get("document_id")), str(document.metadata.get("section_path")))
        if key not in seen:
            seen.add(key)
            result.append((document, score))
    return result


def _merge_country_and_common(
    country: list[tuple[Document, float]],
    common: list[tuple[Document, float]],
    k: int,
    common_slots: int,
) -> list[Document]:
    """국가 문서와 공통 문서를 거리 순으로 합치되, 공통 문서 자리를 최소한 보장한다.

    국가 문서 뒤에 공통 문서를 이어 붙이고 앞에서 k개를 자르면, 국가 문서가 k개 이상일 때
    공통 문서(리튬 배터리·향수 등 모든 국가에 적용되는 금지물품)가 항상 잘려 나간다.
    """
    country, common = _unique(country), _unique(common)
    reserved = common[: min(common_slots, k)]
    rest = sorted(country + common[len(reserved):], key=lambda pair: pair[1])
    picked = reserved + rest[: k - len(reserved)]
    return [document for document, _ in sorted(picked, key=lambda pair: pair[1])]


def _as_evidence(documents: Iterable[Document]) -> list[Evidence]:
    evidence: list[Evidence] = []
    for index, document in enumerate(documents, 1):
        metadata = document.metadata
        evidence.append(
            Evidence(
                evidence_id=f"E{index}",
                document_id=str(metadata["document_id"]),
                title=str(metadata["title"]),
                content=document.page_content,
                country_code=str(metadata["country_code"]),
                service_type=str(metadata["service_type"]),
                source_type=str(metadata["source_type"]),
                source_url=str(metadata.get("source_url") or "") or None,
                collected_at=str(metadata.get("collected_at") or "") or None,
            )
        )
    return evidence

