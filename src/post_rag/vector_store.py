from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from post_rag.chunking import SERVICE_NAMES, DocumentChunk, split_markdown_document
from post_rag.clients import create_embeddings
from post_rag.config import CHROMA_DIR, COUNTRIES_PATH, DOCS_DIR
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
        self.country_names = {
            country["code"]: country["name_ko"]
            for country in json.loads(COUNTRIES_PATH.read_text(encoding="utf-8"))
        }
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
        country_name = self.country_names.get(country_code, country_code)
        country = self._hybrid(
            item_query(item, country_name, service_type), item, max(k * 2, 8), _where(country_code, service_type)
        )
        # 공통 문서는 모든 국가에 적용되므로 국가·서비스가 아니라 품목 중심으로 검색한다.
        common = self._hybrid(common_item_query(item), item, max(k, 4), _where("ALL", service_type))
        return _as_evidence(_merge_country_and_common(country, common, k, self.common_slots))

    def _hybrid(self, query: str, item: Item, k: int, where: dict) -> list[Document]:
        """품목명이 글자 그대로 들어 있는 청크를 먼저, 그 뒤에 의미 검색 결과를 둔다.

        의미 검색만 쓰면 '향수'처럼 짧은 품목명이 분류어(화장품·액체류)가 비슷한 다른
        행에 밀린다. 품목명이 원문에 없으면 의미 검색 결과만 남는다.
        """
        keyword = self.store.similarity_search(
            query, k=k, filter=where, where_document={"$contains": item.normalized_name}
        )
        semantic = self.store.similarity_search(query, k=k, filter=where)
        return _unique(keyword + semantic)

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


SERVICE_LABELS = {code: label for label, code in SERVICE_NAMES.items()}


def item_query(item: Item, country_name: str, service_type: str | None) -> str:
    """청크 앞머리(`경로: 미국 > 미국 국제특급(EMS) > 금지·제한품목`)와 같은 표현으로 검색한다.

    국가·서비스 코드(US, ems)로 검색하면 한글로 된 청크와 표현이 달라 재현율이 떨어진다.
    """
    service = SERVICE_LABELS.get(service_type or "", "국제우편")
    categories = " ".join(item.categories)
    return f"{country_name} {service} 금지·제한품목 {item.normalized_name} {categories}"


def common_item_query(item: Item) -> str:
    categories = " ".join(item.categories)
    return f"{item.normalized_name} {categories} 보낼 수 있는 물품 보낼 수 없는 물품"


def _unique(documents: list[Document]) -> list[Document]:
    """같은 청크가 키워드·의미 검색에 모두 나오면 하나만 남긴다(순서 유지)."""
    seen: set[tuple[str, str]] = set()
    result = []
    for document in documents:
        key = (str(document.metadata.get("document_id")), document.page_content)
        if key not in seen:
            seen.add(key)
            result.append(document)
    return result


def _merge_country_and_common(
    country: list[Document],
    common: list[Document],
    k: int,
    common_slots: int,
) -> list[Document]:
    """국가 문서와 공통 문서를 합치되, 공통 문서 자리를 최소한 보장한다.

    국가 문서 뒤에 공통 문서를 이어 붙이고 앞에서 k개를 자르면, 국가 문서가 k개 이상일 때
    공통 문서(리튬 배터리·향수 등 모든 국가에 적용되는 금지물품)가 항상 잘려 나간다.
    """
    reserved = common[: min(common_slots, k)]
    picked = country[: k - len(reserved)]
    picked += common[len(reserved) : len(reserved) + (k - len(reserved) - len(picked))]
    return picked + reserved


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

