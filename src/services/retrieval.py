"""Pinecone adapter with metadata pre-filtering through LangChain."""

from typing import Protocol

from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone

from src.core.config import Settings
from src.core.models import Evidence, Library, Match, ServiceError
from src.services.embeddings import make_embeddings


class Retriever(Protocol):
    def retrieve(self, query: str) -> list[Evidence]: ...


def metadata_filter(owner: str, match: Match, model: str) -> dict:
    return {"$and": [
        {"owner": {"$eq": owner}},
        {"match_id": {"$eq": match.id}},
        {"sport": {"$eq": match.sport}},
        {"embedding_model": {"$eq": model}},
    ]}


def make_vector_store(settings: Settings, namespace: str) -> PineconeVectorStore:
    if settings.missing_credentials:
        raise ServiceError("Configure " + ", ".join(settings.missing_credentials) + " in .env.")
    pc = Pinecone(api_key=settings.pinecone_api_key.get_secret_value(), timeout=30)
    try:
        description = pc.describe_index(settings.pinecone_index_name)
        if description.dimension != settings.embedding_dimensions:
            raise ServiceError(
                "The Pinecone index dimension must equal EMBEDDING_DIMENSIONS "
                f"({settings.embedding_dimensions}). Use a matching index and re-index."
            )
        if description.metric != "cosine":
            raise ServiceError("Use a Pinecone index with the cosine similarity metric.")
        if not description.status["ready"]:
            raise ServiceError("The Pinecone index is not ready yet. Try again shortly.")
        return PineconeVectorStore(
            index=pc.Index(host=description.host),
            embedding=make_embeddings(settings),
            namespace=namespace,
            text_key="text",
        )
    except ServiceError:
        raise
    except Exception as exc:
        # Provider exceptions may contain request details; do not expose them in the UI.
        raise ServiceError(
            "Could not connect to Pinecone. Check the API key, index name, network, "
            "and that the index accepts externally generated dense vectors."
        ) from exc


class PineconeRetriever:
    def __init__(self, settings: Settings, library: Library, owner: str, match: Match):
        if (library.index_name, library.embedding_model, library.dimensions) != (
            settings.pinecone_index_name, settings.embedding_model, settings.embedding_dimensions
        ):
            raise ServiceError("Embedding or index settings changed. Re-index your documents first.")
        self.settings = settings
        self.store = make_vector_store(settings, library.namespace)
        self.filter = metadata_filter(owner, match, settings.embedding_model)

    def retrieve(self, query: str) -> list[Evidence]:
        try:
            results = self.store.similarity_search_with_score(
                query, k=self.settings.retrieval_top_k, filter=self.filter
            )
            return [Evidence(
                source=doc.metadata["source"],
                chunk=int(doc.metadata["chunk"]),
                text=doc.page_content,
                score=float(score),
            ) for doc, score in results if score >= self.settings.retrieval_min_score]
        except Exception as exc:
            raise ServiceError(
                "Retrieval failed. Check your Nebius and Pinecone credentials, "
                "quotas, and connection, then retry."
            ) from exc
