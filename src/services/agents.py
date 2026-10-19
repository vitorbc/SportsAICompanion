"""Future tool boundary. No web tools are registered or executed in this version."""

from typing import Protocol


class ExternalTool(Protocol):
    name: str

    def invoke(self, query: str) -> str: ...
