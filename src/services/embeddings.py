"""Nebius embeddings through LangChain's OpenAI-compatible client."""

from langchain_openai import OpenAIEmbeddings

from src.core.config import Settings


def make_embeddings(settings: Settings) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        api_key=settings.nebius_api_key,
        base_url=settings.nebius_base_url,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        # Send strings, not token IDs from an unrelated OpenAI tokenizer.
        check_embedding_ctx_length=False,
        model_kwargs={"encoding_format": "float"},
        chunk_size=32,
        request_timeout=30,
        max_retries=2,
    )
