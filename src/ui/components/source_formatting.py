"""Presentation-only parsing. Original source and retrieved text remain untouched."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SourcePresentation:
    metadata: dict[str, str]
    body: str


def present_source(text: str) -> SourcePresentation:
    lines = text.splitlines()
    metadata = {}
    for i, line in enumerate(lines):
        if line.strip() == "CONTENT:" and metadata:
            return SourcePresentation(metadata, "\n".join(lines[i + 1:]).strip())
        if not line.strip():
            continue
        match = re.fullmatch(r"(DOCUMENT_ID|SPORT|PLAYER_1|PLAYER_2|TEAM|OPPONENT|MATCH|SOURCE|DATE):\s*(.*)", line)
        if not match:
            break
        metadata[match[1]] = match[2]
    # Ordinary Markdown, partial passages and unknown formats are preserved.
    return SourcePresentation({}, text)


def display_title(title: str) -> str:
    return re.sub(r"^\d+\s*[·—–]\s*", "", title)


def readable_body(text: str) -> str:
    """Render consecutive labelled statistics as tables, keeping their values verbatim."""
    lines = text.splitlines()
    output = []
    i = 0
    while i < len(lines):
        rows = []
        end = i
        while end < len(lines):
            match = re.fullmatch(r"\s*[-*] ([^:\n]+):\s*(.+)", lines[end])
            if not match:
                break
            rows.append((match[1], match[2]))
            end += 1
        if len(rows) >= 2:
            output.extend(["", "| Detail | Reported value |", "| :--- | :--- |"])
            for label, value in rows:
                output.append("| " + label.replace("|", "\\|") + " | " + value.replace("|", "\\|") + " |")
            output.append("")
            i = end
        else:
            output.append(lines[i])
            i += 1
    return "\n".join(output)
