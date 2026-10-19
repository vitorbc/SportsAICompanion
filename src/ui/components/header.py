import streamlit as st

from src.core.auth import SessionIdentity
from src.core.models import Match, User
from src.ui.components.primitives import esc, icon, portrait


def render_header(identity: SessionIdentity, catalog: list[Match]) -> tuple[User, bool]:
    user = identity.get(st.session_state.get("profile", "vitor"))
    assets = {name: asset for match in catalog for name, asset in zip(match.participants, match.participant_assets)}
    short = {"Sport Club do Recife": "Sport Recife", "Carlos Alcaraz": "Alcaraz", "Novak Djokovic": "Djokovic"}
    with st.container(key="toolbar"):
        brand, controls = st.columns([9, 1.4], vertical_alignment="center")
        with brand:
            chips = "".join(
                f'<span class="follow-chip">{portrait(assets.get(name,""), name, "follow-avatar" + (" crest" if "teams/" in assets.get(name,"") else ""))}{esc(short.get(name,name))}</span>'
                for name in user.preferences.following[:3]
            )
            st.html(f'<header class="topbar"><div class="brand"><span class="brand-mark">{icon("ball",29)}</span><span class="brand-name">Sports <em>AI</em> Companion</span></div><div class="following"><span class="eyebrow">Following</span>{chips}</div></header>')
        with controls:
            with st.popover(user.name, icon=":material/tune:", use_container_width=True):
                st.markdown("**Your preferences**")
                names = {u.id: u.name for u in identity.users()}
                selected = st.selectbox("Demo profile", list(names), format_func=names.get, key="profile")
                if selected != user.id:
                    st.rerun()
                prefs = user.preferences
                prefs.sports = st.multiselect("Sports", ["football", "tennis"], default=prefs.sports,
                                             format_func=str.title, key=f"sports-{user.id}")
                options = sorted({p for m in catalog for p in m.participants} | set(prefs.following))
                prefs.following = st.multiselect("Following", options, default=prefs.following,
                                                key=f"following-{user.id}")
                st.toggle("Only followed matches", key=f"follow-filter-{user.id}")
                prefs.shield = st.toggle("Default video shield", value=prefs.shield,
                                         key=f"default-shield-{user.id}")
                st.caption("Preferences and conversations are saved for this session. Demo profiles are not secure logins.")
                with st.expander("Image credits"):
                    from src.core.config import ROOT
                    import json
                    for credit in json.loads((ROOT / "assets" / "credits.json").read_text(encoding="utf-8")):
                        st.markdown(f"[{credit['asset']}]({credit['file_page']})")
                        if credit.get("attribution"):
                            st.caption(credit["attribution"])
                        if credit.get("license_url"):
                            st.markdown(f"[License]({credit['license_url']})")
    return user, st.session_state.get(f"follow-filter-{user.id}", False)
