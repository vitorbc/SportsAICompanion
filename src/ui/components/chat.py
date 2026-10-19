"""Conversation state remains personal while the retrieved corpus is shared."""

import streamlit as st

from src.core.auth import conversation
from src.core.config import Settings
from src.core.models import ChatMessage, Library, Match, ServiceError, User
from src.services.companion import RagCompanion, demo_answer, make_chat_model
from src.services.curation import CURATED_SCOPE, CuratedContext, example_messages
from src.services.retrieval import PineconeRetriever
from src.ui.components.evidence import render_passages
from src.ui.components.loading import companion_loading
from src.ui.components.source_formatting import display_title
from src.ui.components.primitives import esc, icon, section_title


def library_is_ready(library: Library | None, context: CuratedContext, settings: Settings) -> bool:
    return bool(library and not settings.missing_credentials and
                library.content_revision == context.revision and
                (library.index_name, library.embedding_model, library.dimensions) ==
                (settings.pinecone_index_name, settings.embedding_model, settings.embedding_dimensions))


def queue_prompt(key: str, question: str) -> None:
    st.session_state[key] = question


def render_message(message: ChatMessage, context: CuratedContext) -> None:
    with st.chat_message(message.role):
        st.markdown(message.content)
        if message.evidence:
            names = {f.name: s.title for s, f in zip(context.manifest.sources, context.files, strict=True)}
            st.html('<div class="source-chips">' + ''.join(
                f'<span class="source-chip"><b>[{i}]</b>{esc(display_title(names.get(e.source,e.source)))}</span>'
                for i, e in enumerate(message.evidence, 1)) + '</div>')


def render_chat(match: Match, user: User, context: CuratedContext,
                library: Library | None, settings: Settings) -> ChatMessage | None:
    live = library_is_ready(library, context, settings)
    mode = "live" if live else "preview"
    revision = library.namespace if live else context.revision
    history = conversation(st.session_state, user.id, match.id, mode, revision)
    pending_key = f"pending-{user.id}-{match.id}-{mode}"
    error = None
    pending_question = st.session_state.pop(pending_key, None)
    examples = example_messages(context) if not live else []
    messages = history or (examples if not pending_question else [])
    latest = next((m for m in reversed(messages) if m.role == "assistant"), None)
    with st.container(key="chat-panel", gap="small"):
        title, reset = st.columns([10, 1], vertical_alignment="center")
        with title:
            st.html(section_title("Tactical Companion", "ball", "Discuss the game. Explore the evidence."))
        with reset:
            if st.button("Reset conversation", icon=":material/restart_alt:", key="reset-chat", help="Clear this match's conversation", type="tertiary"):
                history.clear()
                st.session_state.pop(f"retry-{pending_key}", None)
                st.rerun()
        badge = "Grounded conversation" if live else "Curated preview · not a live AI answer"
        st.html(f'<div class="context-line"><span>{esc(match.title)}</span><span class="status-pill {"live" if live else "sample"}">{badge}</span></div>')
        with st.container(height=460, border=False, key="chat-history"):
            if not messages and not pending_question:
                st.html(f'<div class="welcome"><span class="brand-mark">{icon("spark",28)}</span><h3>Every match has a story.</h3><p>Explore a tactical change, a player’s performance,<br>or what the numbers really tell us.</p></div>')
            for message in messages:
                render_message(message, context)
            if pending_question:
                # Render the submitted question before the blocking provider calls.
                render_message(ChatMessage("user", pending_question), context)
                response_slot = st.empty()
                try:
                    if live:
                        with response_slot.container(), st.chat_message("assistant"):
                            with companion_loading():
                                retriever = PineconeRetriever(settings, library, CURATED_SCOPE, match)
                                answer = RagCompanion(retriever, make_chat_model(settings)).answer(pending_question, history, match)
                    else:
                        answer = demo_answer()
                    with response_slot.container():
                        render_message(answer, context)
                    history.extend([ChatMessage("user", pending_question), answer])
                    latest = answer
                    st.session_state.pop(f"retry-{pending_key}", None)
                except ServiceError as exc:
                    response_slot.empty()
                    error = str(exc)
                    st.session_state[f"retry-{pending_key}"] = pending_question
        if error:
            st.error(error)
        retry = st.session_state.get(f"retry-{pending_key}")
        if retry:
            if st.button("Retry last question", key=f"retry-button-{pending_key}"):
                st.session_state[pending_key] = retry
                st.session_state.pop(f"retry-{pending_key}", None)
                st.rerun()
        if latest and latest.evidence:
            render_passages(latest, context)
        st.html('<div class="eyebrow">Suggested questions</div>')
        with st.container(key="suggestions"):
            questions = context.manifest.questions[:3]
            if questions:
                for col, question in zip(st.columns(len(questions), gap="small"), questions):
                    col.button(question, key=f"prompt-{match.id}-{question}",
                               on_click=queue_prompt, args=(pending_key, question), use_container_width=True)
        question = st.chat_input("Ask about tactics, players, or turning points…", max_chars=2000,
                                 key=f"chat-{user.id}-{match.id}-{mode}")
        if question and question.strip():
            st.session_state[pending_key] = question.strip()
            st.rerun()
        st.html(f'<div class="quiet-caption">{icon("shield",14)} Match insights with source references{ " · Fictional sample" if match.sample else ""}</div>')
    return latest
