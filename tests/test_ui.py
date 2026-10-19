from unittest.mock import Mock

from streamlit.testing.v1 import AppTest

from src.core.config import ROOT
from src.core.models import ChatMessage, Library
from src.services.curation import CURATED_SCOPE, load_context
from src.services.library import LibraryRegistry
from src.services.matches import load_matches


def start_app(monkeypatch, tmp_path, connected=False):
    monkeypatch.setenv("NEBIUS_API_KEY", "fake" if connected else "")
    monkeypatch.setenv("PINECONE_API_KEY", "fake" if connected else "")
    monkeypatch.setenv("STATE_DIR", str(tmp_path))
    return AppTest.from_file(ROOT / "app.py", default_timeout=45).run()


def test_curated_preview_and_no_document_administration(monkeypatch, tmp_path):
    app = start_app(monkeypatch, tmp_path)
    assert not app.exception
    assert len(app.chat_message) == 2
    assert any("fictional sample report" in m.value for m in app.markdown)
    assert not app.get("file_uploader")
    assert not any("Index" in button.label or "Add match" == button.label for button in app.button)
    assert not any(w.label == "Your role" for w in app.selectbox)


def test_preview_chat_and_profile_isolation(monkeypatch, tmp_path):
    app = start_app(monkeypatch, tmp_path)
    app.chat_input[0].set_value("My personal question").run()
    assert not app.exception
    assert any("My personal question" in m.value for m in app.markdown)
    assert any("reply did not use AI retrieval" in m.value for m in app.markdown)
    next(w for w in app.selectbox if w.label == "Demo profile").select("guest").run()
    assert not app.exception
    assert not any("My personal question" in m.value for m in app.markdown)
    next(w for w in app.selectbox if w.label == "Demo profile").select("vitor").run()
    assert any("My personal question" in m.value for m in app.markdown)


def test_match_card_switches_chat_and_sources(monkeypatch, tmp_path):
    app = start_app(monkeypatch, tmp_path)
    app.chat_input[0].set_value("Football question").run()
    app.button(key="select-vitor-sample-tennis").click().run()
    assert not app.exception
    assert app.session_state["selected-match-vitor"] == "sample-tennis"
    assert not any("Football question" in m.value for m in app.markdown)
    assert any("return position change" in m.value for m in app.markdown)
    assert any(e.label == "Serve & return analysis" for e in app.expander)


def test_empty_preferences_and_recovery(monkeypatch, tmp_path):
    app = start_app(monkeypatch, tmp_path)
    next(w for w in app.multiselect if w.label == "Sports").set_value([]).run()
    assert not app.exception
    assert any("No matches fit" in i.value for i in app.info)
    next(w for w in app.multiselect if w.label == "Sports").set_value(["tennis"]).run()
    assert not app.exception
    assert app.session_state["selected-match-vitor"] == "sample-tennis"


def test_suggested_question_and_reset(monkeypatch, tmp_path):
    app = start_app(monkeypatch, tmp_path)
    next(b for b in app.button if b.label == "Evaluate the striker").click().run()
    assert not app.exception
    assert any(m.value == "Evaluate the striker" for m in app.markdown)
    app.button(key="reset-chat").click().run()
    assert not app.exception
    assert not any(m.value == "Evaluate the striker" for m in app.markdown)


def test_live_chat_uses_shared_scope_not_selected_profile(monkeypatch, tmp_path):
    match = load_matches()[0]
    context = load_context(match)
    registry = LibraryRegistry(tmp_path)
    registry.activate(CURATED_SCOPE, match.id, Library(
        "shared-snapshot", "sports-companion-nebius", "Qwen/Qwen3-Embedding-8B", 4096,
        [f.name for f in context.files], 3, context.revision,
    ))
    retriever = Mock()
    companion = Mock()
    companion.return_value.answer.return_value = ChatMessage("assistant", "Grounded test response.")
    monkeypatch.setattr("src.ui.components.chat.PineconeRetriever", retriever)
    monkeypatch.setattr("src.ui.components.chat.make_chat_model", Mock())
    monkeypatch.setattr("src.ui.components.chat.RagCompanion", companion)
    app = start_app(monkeypatch, tmp_path, connected=True)
    assert not app.exception
    assert not app.chat_message
    app.chat_input[0].set_value("Discuss the substitution").run()
    assert not app.exception
    assert retriever.call_args.args[2] == CURATED_SCOPE
    next(w for w in app.selectbox if w.label == "Demo profile").select("guest").run()
    assert not app.chat_message
    app.chat_input[0].set_value("Guest's question").run()
    assert retriever.call_args.args[2] == CURATED_SCOPE
