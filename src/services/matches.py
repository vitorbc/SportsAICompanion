"""Local catalog. No schedules, scores, or other web content are fetched."""

import json
import re
from datetime import date
from pathlib import Path

from src.core.config import ROOT, Settings
from src.core.models import Match, Preferences, SourceFile


def load_matches(path: Path | None = None) -> list[Match]:
    if path is None:
        path = Settings().match_catalog_path
        if not path.is_absolute():
            path = ROOT / path
    matches = []
    for row in json.loads(path.read_text(encoding="utf-8")):
        if not re.fullmatch(r"[a-z0-9-]+", row["id"]):
            raise ValueError("Match IDs must contain only lowercase letters, digits, and hyphens.")
        if row["sport"] not in {"football", "tennis"}:
            raise ValueError("Unsupported sport in the match catalog.")
        if row.get("match_date") is not None:
            value = row["match_date"]
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("Match dates must use YYYY-MM-DD.")
            date.fromisoformat(value)
        matches.append(Match(**{**row, "participants": tuple(row["participants"]),
                               "participant_assets": tuple(row.get("participant_assets", []))}))
    if len({m.id for m in matches}) != len(matches):
        raise ValueError("Match IDs must be unique.")
    return matches


def filter_matches(matches: list[Match], prefs: Preferences, followed_only: bool) -> list[Match]:
    return [m for m in matches if m.sport in prefs.sports and (
        not followed_only or set(m.participants).intersection(prefs.following)
    )]


def sample_files(match: Match) -> list[SourceFile]:
    if not match.sample:
        return []
    folder = ROOT / "data" / "samples" / match.id
    return [SourceFile(p.name, p.read_bytes()) for p in sorted(folder.glob("*.md"))]
