"""Tests use deterministic doubles; they must not spend API credits."""

import socket

import pytest

from src.core.config import Settings
from src.services.matches import load_matches


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    original_connect = socket.socket.connect

    def blocked(sock, address):
        # Windows asyncio uses a loopback socket pair for its own event loop.
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(sock, address)
        raise AssertionError("External network access is not allowed in tests.")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    # Public sample fixtures keep tests independent of private local documents.
    monkeypatch.setenv("MATCH_CATALOG_PATH", "data/matches.json")


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, nebius_api_key="", pinecone_api_key="", state_dir=tmp_path)


@pytest.fixture
def match():
    return load_matches()[0]
