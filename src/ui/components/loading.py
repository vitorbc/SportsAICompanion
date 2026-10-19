"""Visible, accessible feedback for the synchronous RAG request."""

from contextlib import contextmanager

import streamlit as st

def loading_markup() -> str:
    return '''<div class="chat-thinking" role="status" aria-live="polite" aria-atomic="true">
        <span>Thinking<span class="sr-only">… Reviewing match evidence.</span></span>
        <span class="loading-dots" aria-hidden="true"><i></i><i></i><i></i></span>
    </div>'''


@contextmanager
def companion_loading():
    placeholder = st.empty()
    placeholder.html(loading_markup())
    try:
        yield
    finally:
        # Clear on success and failure, so errors/retry controls stay usable.
        placeholder.empty()
