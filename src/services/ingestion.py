"""Local files -> LangChain Documents -> chunks -> versioned Pinecone namespace."""

import hashlib
import json
from pathlib import Path
from typing import Callable

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.core.config import Settings
from src.core.models import Library, Match, ServiceError, SourceFile
from src.services.library import LibraryRegistry
from src.services.retrieval import make_vector_store

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FILES = 20
MAX_CHUNKS = 2000


def prepare_documents(
    files: list[SourceFile], match: Match, owner: str, settings: Settings
) -> list[Document]:
    """Validate all files locally before starting any paid provider calls."""
    if not files or len(files) > MAX_FILES:
        raise ServiceError(f"Select between 1 and {MAX_FILES} documents.")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap,
        add_start_index=True,
    )
    chunks: list[Document] = []
    names: set[str] = set()
    for source in sorted(files, key=lambda item: item.name):
        # Treat filenames as labels; never write an uploaded filename to disk.
        name = source.name.replace("\\", "/").rsplit("/", 1)[-1]
        if Path(name).suffix.lower() not in {".txt", ".md"}:
            raise ServiceError("Only UTF-8 .txt and .md documents are supported for now.")
        if name.casefold() in names:
            raise ServiceError("Each document must have a distinct filename.")
        names.add(name.casefold())
        if len(source.content) > MAX_FILE_BYTES:
            raise ServiceError("Each document must be at most 2 MB.")
        try:
            content = source.content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ServiceError("Save your documents as UTF-8 text before uploading.") from exc
        if not content.strip() or "\x00" in content:
            raise ServiceError("Documents must contain non-empty plain text, without binary data.")
        doc = Document(page_content=content, metadata={
            "source": name, "owner": owner, "match_id": match.id, "sport": match.sport,
            "embedding_model": settings.embedding_model, "sample": match.sample,
        })
        for number, chunk in enumerate(splitter.split_documents([doc]), start=1):
            chunk.metadata["chunk"] = number
            chunks.append(chunk)
        if len(chunks) > MAX_CHUNKS:
            raise ServiceError(f"This learning app accepts at most {MAX_CHUNKS} chunks per library.")
    return chunks


def snapshot_namespace(chunks: list[Document], settings: Settings) -> str:
    payload = {
        "schema": 1, "index": settings.pinecone_index_name,
        "model": settings.embedding_model, "dimensions": settings.embedding_dimensions,
        "chunks": [(d.page_content, d.metadata) for d in chunks],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]
    return f"{settings.pinecone_namespace_prefix[:40]}-{digest}"


def index_documents(
    chunks: list[Document], settings: Settings, registry: LibraryRegistry,
    owner: str, match: Match, store_factory: Callable = make_vector_store,
    content_revision: str = "",
) -> Library:
    """Activate only a completely uploaded snapshot; retries use deterministic IDs."""
    if not chunks or any(
        d.metadata.get("owner") != owner or d.metadata.get("match_id") != match.id
        for d in chunks
    ):
        raise ServiceError("The prepared documents do not belong to the selected match and profile.")
    namespace = snapshot_namespace(chunks, settings)
    previous = registry.get(owner, match.id)
    if previous and previous.namespace == namespace and previous.content_revision == content_revision:
        return previous  # An unchanged library needs no additional embeddings.
    store = store_factory(settings, namespace)
    try:
        for offset in range(0, len(chunks), 32):
            # LangChain's Pinecone adapter adds the text field to metadata in place.
            # Preserve the prepared input so its content hash stays stable on retries.
            batch = [doc.model_copy(deep=True) for doc in chunks[offset:offset + 32]]
            store.add_documents(
                batch, ids=[f"chunk-{i}" for i in range(offset, offset + len(batch))],
                async_req=False,
            )
    except Exception as exc:
        raise ServiceError(
            "Indexing did not finish. Your previous library remains active. "
            "Check provider access and quotas, then retry with the same files."
        ) from exc
    library = Library(
        namespace=namespace, index_name=settings.pinecone_index_name,
        embedding_model=settings.embedding_model, dimensions=settings.embedding_dimensions,
        sources=sorted({d.metadata["source"] for d in chunks}), chunk_count=len(chunks),
        content_revision=content_revision,
    )
    registry.activate(owner, match.id, library)
    return library
