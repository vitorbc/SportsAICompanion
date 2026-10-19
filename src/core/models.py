"""Small domain models shared by the UI and services."""

from dataclasses import dataclass, field
from typing import Literal

Sport = Literal["football", "tennis"]


@dataclass(frozen=True)
class Match:
    id: str
    title: str
    sport: Sport
    participants: tuple[str, ...]
    sample: bool = False
    video_url: str | None = None
    spoiler_safe_video_url: str | None = None
    subtitle: str = ""
    participant_assets: tuple[str, ...] = ()
    context_path: str | None = None
    # Curated card metadata; dates use ISO YYYY-MM-DD, not source publication dates.
    match_date: str | None = None
    competition: str = ""


@dataclass
class Preferences:
    sports: list[str] = field(default_factory=lambda: ["football", "tennis"])
    following: list[str] = field(default_factory=lambda: [
        "Sport Club do Recife", "Carlos Alcaraz", "Novak Djokovic"
    ])
    shield: bool = True


@dataclass
class User:
    id: str
    name: str
    preferences: Preferences = field(default_factory=Preferences)


@dataclass(frozen=True)
class SourceFile:
    name: str
    content: bytes


@dataclass(frozen=True)
class Library:
    namespace: str
    index_name: str
    embedding_model: str
    dimensions: int
    sources: list[str]
    chunk_count: int
    content_revision: str = ""


@dataclass(frozen=True)
class Evidence:
    source: str
    chunk: int
    text: str
    score: float


@dataclass
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str
    evidence: list[Evidence] = field(default_factory=list)
    query: str = ""


class ServiceError(Exception):
    """An actionable, safe-to-display application error."""
