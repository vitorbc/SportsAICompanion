"""Sports AI Companion. Run: python -m streamlit run app.py"""

import streamlit as st
from pydantic import ValidationError

from src.core.auth import SessionIdentity
from src.core.config import Settings
from src.services.curation import load_context
from src.services.library import LibraryRegistry
from src.services.matches import filter_matches, load_matches
from src.ui.components.header import render_header
from src.ui.components.match_cards import render_matches
from src.ui.theme import apply_theme
from src.ui.views import render_workspace


def main() -> None:
    st.set_page_config(page_title="Sports AI Companion", page_icon="⚽", layout="wide")
    apply_theme()
    try:
        settings = Settings()
        catalog = load_matches()
    except (ValidationError, ValueError, OSError):
        st.error("This workspace could not load its configuration. Please check the local catalog and settings.")
        st.stop()
    user, followed_only = render_header(SessionIdentity(st.session_state), catalog)
    visible = filter_matches(catalog, user.preferences, followed_only)
    if not visible:
        st.info("No matches fit your preferences. Choose a sport or turn off the followed-only filter in your profile menu.")
        return
    match = render_matches(visible, user)
    try:
        context = load_context(match)
        registry = LibraryRegistry(settings.state_dir)
    except (ValueError, OSError):
        st.error("The curated context for this match is temporarily unavailable.")
        st.stop()
    render_workspace(match, user, context, registry, settings)
    st.html('<footer class="workspace-footer"><span>Sports AI Companion · See the game differently.</span><span>Learning edition</span></footer>')


if __name__ == "__main__":
    main()
