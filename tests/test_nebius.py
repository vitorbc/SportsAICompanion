"""Exercise actual LangChain request serialization against a local HTTP double."""

import json

import httpx
import pytest
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import SecretStr

from src.core.config import Settings
from src.services.companion import make_chat_model
from src.services.embeddings import make_embeddings


def test_nebius_chat_uses_chat_completions(monkeypatch, settings):
    settings = settings.model_copy(update={"nebius_api_key": SecretStr("test-nebius-key")})
    def respond(request):
        assert str(request.url) == settings.nebius_base_url + "chat/completions"
        body = json.loads(request.content)
        assert body["model"] == settings.chat_model
        assert "store" not in body
        assert body["messages"][-1]["content"] == "Hello"
        return httpx.Response(200, json={
            "id": "chat-test", "object": "chat.completion", "created": 1,
            "model": settings.chat_model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"},
                         "finish_reason": "stop"}],
        })

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr("src.services.companion.ChatOpenAI",
                        lambda **kwargs: ChatOpenAI(**kwargs, http_client=client))
    assert make_chat_model(settings).invoke("Hello").content == "OK"
    client.close()


def test_nebius_embeddings_send_strings_and_float_encoding(monkeypatch, settings):
    settings = settings.model_copy(update={"nebius_api_key": SecretStr("test-nebius-key")})
    requests = []

    def respond(request):
        assert str(request.url) == settings.nebius_base_url + "embeddings"
        body = json.loads(request.content)
        requests.append(body)
        assert all(isinstance(text, str) for text in body["input"])
        assert body["encoding_format"] == "float"
        assert body["model"] == settings.embedding_model
        assert body["dimensions"] == settings.embedding_dimensions
        return httpx.Response(200, json={"object": "list", "data": [
            {"object": "embedding", "index": i, "embedding": [0.1] * settings.embedding_dimensions}
            for i in range(len(body["input"]))
        ], "model": settings.embedding_model, "usage": {"prompt_tokens": 5, "total_tokens": 5}})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr("src.services.embeddings.OpenAIEmbeddings",
                        lambda **kwargs: OpenAIEmbeddings(**kwargs, http_client=client))
    adapter = make_embeddings(settings)
    assert len(adapter.embed_documents(["Football tactics", "Tennis serve"])) == 2
    assert len(adapter.embed_query("What changed?")) == settings.embedding_dimensions
    assert len(requests) == 2
    client.close()


def test_openai_key_does_not_satisfy_nebius_credentials(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "old-provider-key")
    settings = Settings(_env_file=None, nebius_api_key="", pinecone_api_key="fake")
    assert settings.missing_credentials == ["NEBIUS_API_KEY"]


def test_setup_check_rejects_wrong_embedding_dimension(monkeypatch, settings, capsys):
    from unittest.mock import Mock
    from pydantic import SecretStr
    from src.cli.check_providers import main

    configured = settings.model_copy(update={"nebius_api_key": SecretStr("fake"),
                                             "pinecone_api_key": SecretStr("fake")})
    monkeypatch.setattr("src.cli.check_providers.Settings", lambda: configured)
    monkeypatch.setattr("src.cli.check_providers.make_vector_store", Mock())
    embeddings = Mock()
    embeddings.embed_query.return_value = [0.1] * 512
    monkeypatch.setattr("src.cli.check_providers.make_embeddings", lambda _: embeddings)
    chat = Mock(side_effect=AssertionError("Do not continue after a dimension mismatch"))
    monkeypatch.setattr("src.cli.check_providers.make_chat_model", chat)
    assert main([]) == 1
    assert "512 dimensions" in capsys.readouterr().err
    chat.assert_not_called()


@pytest.mark.parametrize("status,hint", [
    (401, "authentication"), (403, "permissions"), (404, "model catalog"),
    (422, "parameters"), (429, "quota"), (503, "service status"),
])
def test_setup_check_explains_http_errors_without_echoing_secrets(
    monkeypatch, settings, capsys, status, hint
):
    from unittest.mock import Mock
    from openai import APIStatusError
    from src.cli.check_providers import main

    configured = settings.model_copy(update={"nebius_api_key": SecretStr("test-secret"),
                                             "pinecone_api_key": SecretStr("fake")})
    monkeypatch.setattr("src.cli.check_providers.Settings", lambda: configured)
    monkeypatch.setattr("src.cli.check_providers.make_vector_store", Mock())
    response = httpx.Response(status, request=httpx.Request("POST", "https://example.test/embeddings"))
    failure = APIStatusError("test-secret", response=response, body={"detail": "test-secret"})
    embeddings = Mock()
    embeddings.embed_query.side_effect = failure
    monkeypatch.setattr("src.cli.check_providers.make_embeddings", lambda _: embeddings)
    assert main([]) == 1

    error = capsys.readouterr().err
    assert f"HTTP {status}" in error
    assert hint in error
    assert "test-secret" not in error


def test_nebius_only_skips_pinecone_and_shows_environment_override(monkeypatch, settings, capsys):
    from unittest.mock import Mock
    from src.cli.check_providers import main

    monkeypatch.setenv("EMBEDDING_MODEL", "test-model")
    configured = Settings(_env_file=None, nebius_api_key="test-secret", pinecone_api_key="")
    monkeypatch.setattr("src.cli.check_providers.Settings", lambda: configured)
    pinecone = Mock(side_effect=AssertionError("Nebius-only must not contact Pinecone"))
    monkeypatch.setattr("src.cli.check_providers.make_vector_store", pinecone)
    embeddings = Mock()
    embeddings.embed_query.return_value = [0.1] * configured.embedding_dimensions
    monkeypatch.setattr("src.cli.check_providers.make_embeddings", lambda _: embeddings)
    chat = Mock()
    chat.invoke.return_value.content = "OK"
    monkeypatch.setattr("src.cli.check_providers.make_chat_model", lambda _: chat)
    assert main(["--nebius-only"]) == 0
    output = capsys.readouterr().out
    assert "test-model (process environment overrides .env)" in output
    assert "test-secret" not in output
    pinecone.assert_not_called()
