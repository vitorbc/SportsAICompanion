"""Developer-managed match context, shared by readers and independent of the UI.

Future feed collectors should produce this same manifest format. No networking here.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.config import ROOT
from src.core.models import ChatMessage, Evidence, Match, SourceFile

# Reuse the registry/metadata partition as a shared publication scope. This is
# intentionally NOT a user ID. Existing private libraries are never selected.
CURATED_SCOPE = "curated:v1"
DATA_ROOT = ROOT / "data"


class SourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    path: str
    kind: str = "Report"
    summary: str = ""
    url: str | None = None

    @model_validator(mode="after")
    def safe_link(self):
        if self.url and urlparse(self.url).scheme not in {"https", "http"}:
            raise ValueError("Source links must be HTTP(S) URLs.")
        return self


class Metric(BaseModel):
    label: str
    value: str
    source_id: str


class Insight(BaseModel):
    title: str
    text: str
    source_id: str


class Example(BaseModel):
    question: str
    answer: str


class ContextManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sources: list[SourceSpec]
    metrics: list[Metric] = Field(default_factory=list)
    insights: list[Insight] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    missing_information: str = ""
    example: Example | None = None

    @model_validator(mode="after")
    def source_references_exist(self):
        ids = [s.id for s in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("Source IDs must be unique.")
        for item in [*self.metrics, *self.insights]:
            if item.source_id not in ids:
                raise ValueError(f"Unknown source reference: {item.source_id}")
        if self.example:
            citations = [int(n) for n in re.findall(r"\[(\d+)\]", self.example.answer)]
            if not citations or any(n < 1 or n > len(ids) for n in citations):
                raise ValueError("Example citations must reference numbered sources in the manifest.")
        return self


@dataclass(frozen=True)
class CuratedContext:
    manifest: ContextManifest
    files: list[SourceFile]
    revision: str

    def evidence(self) -> list[Evidence]:
        return [Evidence(f.name, 0, f.content.decode("utf-8-sig"), 0)
                for f in self.files]


def data_path(relative: str, base: Path = DATA_ROOT) -> Path:
    path = (base / relative).resolve()
    if not path.is_relative_to(DATA_ROOT.resolve()):
        raise ValueError("Curated files must stay inside the data directory.")
    return path


def load_context(match: Match) -> CuratedContext:
    if not match.context_path:
        return CuratedContext(ContextManifest(sources=[]), [], "empty")
    manifest_path = data_path(match.context_path)
    manifest = ContextManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    files = []
    for source in manifest.sources:
        path = data_path(source.path, manifest_path.parent)
        files.append(SourceFile(path.name, path.read_bytes()))
    if len({f.name.casefold() for f in files}) != len(files):
        raise ValueError("Source filenames must be unique within a match.")
    digest = hashlib.sha256(manifest.model_dump_json().encode())
    digest.update(json.dumps({"id": match.id, "title": match.title,
                              "sport": match.sport, "sample": match.sample}, sort_keys=True).encode())
    for file in files:
        digest.update(file.name.encode())
        digest.update(file.content)
    return CuratedContext(manifest, files, digest.hexdigest())


def example_messages(context: CuratedContext) -> list[ChatMessage]:
    example = context.manifest.example
    if not example:
        return []
    return [ChatMessage("user", example.question),
            ChatMessage("assistant", example.answer, context.evidence())]


def source_metadata(context: CuratedContext) -> dict[str, dict]:
    return {file.name: {"source_id": source.id, "source_title": source.title,
                        "source_kind": source.kind, "source_url": source.url or ""}
            for source, file in zip(context.manifest.sources, context.files, strict=True)}
