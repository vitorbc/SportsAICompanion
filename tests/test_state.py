from pydantic import ValidationError
import pytest

from src.core.auth import SessionIdentity, conversation
from src.core.config import Settings
from src.core.models import ChatMessage, Match, Preferences
from src.services.library import LibraryRegistry
from src.services.matches import filter_matches, load_matches


def test_profiles_do_not_share_mutable_preferences():
    state = {}
    identity = SessionIdentity(state)
    identity.get("vitor").preferences.following.append("New team")
    assert "New team" not in identity.get("guest").preferences.following
    assert "New team" in SessionIdentity(state).get("vitor").preferences.following


def test_conversations_are_isolated():
    state = {}
    chat = conversation(state, "vitor", "football", "live", "revision-1")
    chat.append(ChatMessage("user", "A question"))
    for key in [("guest", "football", "live", "revision-1"),
                ("vitor", "tennis", "live", "revision-1"),
                ("vitor", "football", "demo", "revision-1"),
                ("vitor", "football", "live", "revision-2")]:
        assert conversation(state, *key) == []
    assert len(conversation(state, "vitor", "football", "live", "revision-1")) == 1


def test_followed_and_sport_filters():
    prefs = Preferences(sports=["football"], following=["Sport Club do Recife"])
    assert [m.id for m in filter_matches(load_matches(), prefs, True)] == ["sample-football"]
    prefs.following = []
    assert filter_matches(load_matches(), prefs, True) == []


def test_custom_match_persists_only_for_owner(settings):
    registry = LibraryRegistry(settings.state_dir)
    match = Match("custom", "My fixture", "tennis", ("Player A", "Player B"))
    registry.add_match("vitor", match)
    assert LibraryRegistry(settings.state_dir).matches("vitor") == [match]
    assert registry.matches("guest") == []


def test_invalid_overlap_fails_fast():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, chunk_size=200, chunk_overlap=200)
