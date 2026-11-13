"""우편규정 Markdown 문서를 ChromaDB에 색인한다."""

from post_rag.vector_store import build_vector_store


if __name__ == "__main__":
    count = build_vector_store()
    print(f"문서 청크 {count}개를 색인했습니다.")

