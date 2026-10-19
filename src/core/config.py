"""Typed configuration; constructing Settings never contacts a provider."""

from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    nebius_api_key: SecretStr = SecretStr("")
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    pinecone_api_key: SecretStr = SecretStr("")
    pinecone_index_name: str = "sports-companion-nebius"
    pinecone_namespace_prefix: str = "sports-companion"
    embedding_model: str = "Qwen/Qwen3-Embedding-8B"
    embedding_dimensions: int = Field(default=4096, ge=1, le=65536)
    chat_model: str = "Qwen/Qwen3-30B-A3B-Instruct-2507"
    retrieval_top_k: int = Field(default=5, ge=1, le=10)
    retrieval_min_score: float = Field(default=0.25, ge=-1, le=1)
    chunk_size: int = Field(default=1200, ge=200, le=4000)
    chunk_overlap: int = Field(default=200, ge=0)
    state_dir: Path = ROOT / ".local"
    match_catalog_path: Path = ROOT / "data" / "matches.json"

    @model_validator(mode="after")
    def validate_chunking(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE.")
        return self

    @property
    def missing_credentials(self) -> list[str]:
        return [
            name
            for name, value in (
                ("NEBIUS_API_KEY", self.nebius_api_key),
                ("PINECONE_API_KEY", self.pinecone_api_key),
            )
            if not value.get_secret_value().strip()
        ]
