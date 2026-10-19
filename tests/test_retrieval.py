from unittest.mock import Mock

import pytest
from langchain_core.documents import Document

from src.core.models import Library, ServiceError
from src.services.retrieval import PineconeRetriever, make_vector_store, metadata_filter


def test_query_uses_pinecone_prefilters_and_score_cutoff(settings, match, monkeypatch):
    store = Mock()
    store.similarity_search_with_score.return_value = [
        (Document(page_content="Relevant passage", metadata={"source": "a.md", "chunk": 1}), 0.8),
        (Document(page_content="Unrelated", metadata={"source": "b.md", "chunk": 2}), 0.1),
    ]
    monkeypatch.setattr("src.services.retrieval.make_vector_store", lambda *_: store)
    library = Library("snapshot", settings.pinecone_index_name, settings.embedding_model,
                      settings.embedding_dimensions, ["a.md"], 2)
    result = PineconeRetriever(settings, library, "vitor", match).retrieve("substitutions")
    assert len(result) == 1
    assert result[0].source == "a.md"
    store.similarity_search_with_score.assert_called_once_with(
        "substitutions", k=settings.retrieval_top_k,
        filter=metadata_filter("vitor", match, settings.embedding_model),
    )
    assert {"match_id": {"$eq": match.id}} in store.similarity_search_with_score.call_args.kwargs["filter"]["$and"]
    assert {"owner": {"$eq": "vitor"}} in store.similarity_search_with_score.call_args.kwargs["filter"]["$and"]


def test_changed_embedding_model_requires_reindex(settings, match):
    library = Library("old", settings.pinecone_index_name, "other-model", 4096, [], 1)
    with pytest.raises(ServiceError, match="Re-index"):
        PineconeRetriever(settings, library, "vitor", match)


@pytest.mark.parametrize("dimension,metric,ready,error", [
    (512, "cosine", True, "dimension"),
    (4096, "dotproduct", True, "cosine"),
    (4096, "cosine", False, "not ready"),
])
def test_incompatible_index_rejected(settings, monkeypatch, dimension, metric, ready, error):
    from pydantic import SecretStr

    configured = settings.model_copy(update={"nebius_api_key": SecretStr("fake"),
                                             "pinecone_api_key": SecretStr("fake")})
    pc = Mock()
    pc.describe_index.return_value = Mock(dimension=dimension, metric=metric, status={"ready": ready})
    monkeypatch.setattr("src.services.retrieval.Pinecone", Mock(return_value=pc))
    with pytest.raises(ServiceError, match=error):
        make_vector_store(configured, "snapshot")
