from urllib.parse import urlparse

import streamlit as st

from src.core.models import Match, User
from src.ui.components.primitives import icon, section_title


def playable_url(match: Match, shield: bool) -> str | None:
    # A safe rendition must be provided explicitly; an ordinary embed is never
    # relabeled safe. No CSS overlay can remove a video's burned-in score.
    candidate = match.spoiler_safe_video_url if shield else match.video_url
    if candidate and urlparse(candidate).scheme in {"http", "https"}:
        return candidate
    return None


def _reveal_highlights(shield_key: str) -> None:
    """Update the toggle before Streamlit rerenders this match's player."""
    st.session_state[shield_key] = False
    st.session_state[f"autoplay-{shield_key}"] = True


def render_media(match: Match, user: User) -> None:
    shield_key = f"shield-{user.id}-{match.id}"
    autoplay_key = f"autoplay-{shield_key}"
    if shield_key not in st.session_state:
        st.session_state[shield_key] = user.preferences.shield
        st.session_state[autoplay_key] = False
    standard_url = playable_url(match, False)
    with st.container(key="video-panel", gap="small"):
        with st.container(key="video-controls"):
            title_col, shield_col = st.columns([2, 1], vertical_alignment="center")
            with title_col:
                st.html(section_title("Match highlights", "play"))
            with shield_col:
                shield = st.toggle("Video shield", key=shield_key,
                                   help="Hide standard highlights until you choose to reveal them. Chat and sources may contain spoilers.")
        url = playable_url(match, shield)
        if shield:
            st.session_state[autoplay_key] = False
        if url:
            # Keep these options stable across chat reruns so the player isn't
            # recreated. Muting makes click-to-reveal autoplay more reliable.
            autoplay = st.session_state.get(autoplay_key, False)
            st.video(url, autoplay=autoplay, muted=autoplay)
            if autoplay:
                st.caption("Starts muted · Unmute in the player. If playback is blocked, press play.")
            if not shield:
                st.caption("Standard highlights · Titles, scores and recommendations may reveal the result.")
                st.link_button("Open original video", url,
                               help="Use this if the video provider does not allow embedded playback.")
        else:
            protected = shield and bool(standard_url)
            title = "Highlights protected" if protected else "Highlights coming soon"
            text = "The player and thumbnail stay hidden until you reveal them." if protected else "No video has been added for this match yet."
            st.html(f'<div class="video-placeholder"><span class="video-symbol">{icon("shield" if shield else "play",25)}</span><strong>{title}</strong><p>{text}</p></div>')
            if protected:
                st.button("Reveal highlights", key=f"reveal-video-{user.id}-{match.id}",
                          icon=":material/play_circle:", use_container_width=True,
                          on_click=_reveal_highlights, args=(shield_key,),
                          help="Turns off the shield and starts playback muted. The video may reveal the result.")
        st.html(f'<div class="quiet-caption">{icon("info",14)} Video shield applies to playback, not chat or sources.</div>')
