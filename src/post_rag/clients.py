from __future__ import annotations

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from post_rag.config import (
    GMS_BASE_URL,
    GMS_CHAT_MODEL,
    GMS_EMBEDDING_MODEL,
    GMS_KEY,
)


def require_gms_key() -> str:
    if not GMS_KEY:
        raise RuntimeError(".env 파일에 GMS_KEY를 설정해 주세요.")
    return GMS_KEY


def create_chat_model() -> ChatOpenAI:
    return ChatOpenAI(
        model=GMS_CHAT_MODEL,
        api_key=require_gms_key(),
        base_url=GMS_BASE_URL,
        use_responses_api=True,
        temperature=0,
    )


def create_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=GMS_EMBEDDING_MODEL,
        api_key=require_gms_key(),
        base_url=GMS_BASE_URL,
    )
