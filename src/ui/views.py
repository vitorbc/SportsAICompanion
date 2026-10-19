"""The consumer workspace contains no ingestion or knowledge-administration controls."""

import streamlit as st

from src.core.config import Settings
from src.core.models import Match, User
from src.services.curation import CURATED_SCOPE, CuratedContext
from src.services.library import LibraryRegistry
from src.ui.components.chat import render_chat
from src.ui.components.evidence import render_evidence
from src.ui.components.media import render_media


def render_workspace(match: Match, user: User, context: CuratedContext,
                     registry: LibraryRegistry, settings: Settings) -> None:
    library = registry.get(CURATED_SCOPE, match.id)
    with st.container(key="workspace"):
        chat, supporting = st.columns([1.55, 1], gap="medium")
        with chat:
            latest = render_chat(match, user, context, library, settings)
        with supporting:
            render_media(match, user)
            render_evidence(match, context, latest)
