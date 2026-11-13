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
    ) -> None:
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
        country_documents = self.store.similarity_search(
            query,
            k=max(k * 2, 8),
            filter=_where(country_code, service_type),
        )
        common_documents = self.store.similarity_search(
            query,
            k=max(k, 4),
            filter=_where("ALL", service_type),
        )
        documents = country_documents + common_documents
        unique: list[Document] = []
        seen: set[tuple[str, str]] = set()
        for document in documents:
            key = (str(document.metadata.get("document_id")), str(document.metadata.get("section_path")))
            if key not in seen:
                seen.add(key)
                unique.append(document)
        return _as_evidence(unique[:k])

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

