import streamlit as st
from datetime import date

from src.core.models import Match, User
from src.ui.components.primitives import esc, icon, portrait


def choose_match(user_id: str, match_id: str) -> None:
    st.session_state[f"selected-match-{user_id}"] = match_id


def render_matches(matches: list[Match], user: User) -> Match:
    key = f"selected-match-{user.id}"
    by_id = {m.id: m for m in matches}
    if st.session_state.get(key) not in by_id:
        st.session_state[key] = matches[0].id
    selected = by_id[st.session_state[key]]
    st.html(f'<div class="strip-label"><span class="eyebrow">{icon("calendar",16)} Your matches</span><span class="status-pill">{len(matches)} curated matches</span></div>')
    featured = matches[:2] if selected in matches[:2] else [matches[0], selected]
    columns = st.columns([1, 1, .8], gap="small")
    for col, match in zip(columns, featured):
        with col, st.container(key=f"match-card-{match.id}", gap="xsmall"):
            css = "participant player" if match.sport == "tennis" else "participant"
            images = [portrait(match.participant_assets[i] if i < len(match.participant_assets) else "", name, css)
                      for i, name in enumerate(match.participants[:2])]
            competition = match.competition or match.subtitle or match.sport.title()
            if match.match_date:
                played_on = date.fromisoformat(match.match_date)
                date_label = f"{played_on.day} {played_on:%b %Y}"
                date_markup = f'<time datetime="{esc(match.match_date)}">{esc(date_label)}</time>'
            else:
                date_markup = '<span>Date to be confirmed</span>'
            st.html(f'<div class="match-card">{images[0] if images else ""}<div class="match-names"><strong>{esc(match.title)}</strong><p>{esc(competition)}</p><p class="match-date">{icon("calendar",14)}{date_markup}</p></div>{images[1] if len(images)>1 else ""}</div>')
            active = match.id == selected.id
            if active:
                st.html(f'<style>.st-key-match-card-{match.id} {{border-color:#00e5ab;box-shadow:inset 0 0 0 1px #00e5ab30;}} .st-key-match-card-{match.id} button {{color:#00e5ab !important;}}</style>')
            st.button("Selected match" if active else "Discuss this match", icon=":material/check_circle:" if active else ":material/arrow_forward:",
                      key=f"select-{user.id}-{match.id}", on_click=choose_match,
                      args=(user.id, match.id), use_container_width=True)
    with columns[-1], st.container(key="match-card-browse", gap="xsmall"):
        st.html(f'<div class="browse-card"><span class="browse-icon">{icon("arrow",24)}</span><div><strong>Browse matches</strong><p>Find your next conversation</p></div></div>')
        with st.popover("All matches", use_container_width=True):
            for match in matches:
                st.button(match.title, key=f"browse-{user.id}-{match.id}",
                          on_click=choose_match, args=(user.id, match.id), use_container_width=True)
    return selected
