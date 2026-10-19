"""Demo identity only. Replace this boundary with trusted login before deployment."""

from collections.abc import MutableMapping
from typing import Any, Protocol

from src.core.models import ChatMessage, User


class IdentityProvider(Protocol):
    def users(self) -> list[User]: ...

    def get(self, user_id: str) -> User: ...


class SessionIdentity:
    """Session-local profiles; the selector is NOT an authentication mechanism."""

    def __init__(self, state: MutableMapping[str, Any]):
        self.state = state
        if "profiles" not in state:
            state["profiles"] = {
                "vitor": User("vitor", "Vitor"),
                "guest": User("guest", "Guest"),
            }

    def users(self) -> list[User]:
        return list(self.state["profiles"].values())

    def get(self, user_id: str) -> User:
        return self.state["profiles"][user_id]


def conversation(
    state: MutableMapping[str, Any], user_id: str, match_id: str, mode: str, revision: str
) -> list[ChatMessage]:
    """Keep demo/live, users, matches, and library revisions separate."""
    chats = state.setdefault("conversations", {})
    return chats.setdefault((user_id, match_id, mode, revision), [])
