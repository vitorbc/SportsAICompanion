"""Load the workspace design system; no dynamic or user-supplied CSS."""

import streamlit as st

from src.core.config import ROOT


def apply_theme() -> None:
    st.html(ROOT / "src" / "ui" / "styles.css")
