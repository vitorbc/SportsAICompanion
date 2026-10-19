"""The shield must not mount a third-party player before explicit reveal."""

from streamlit.testing.v1 import AppTest


def media_app():
    import streamlit as st

    from src.core.models import Match, User
    from src.ui.components.media import render_media

    match_id = st.selectbox("Match", ["football", "tennis", "missing", "safe"])
    profile = st.selectbox("Profile", ["vitor", "guest"])
    urls = {
        "football": "https://www.youtube.com/watch?v=G6dj3UH8zdY",
        "tennis": "https://www.youtube.com/watch?v=64WsO9LKE-A",
        "safe": "https://www.youtube.com/watch?v=G6dj3UH8zdY",
    }
    render_media(
        Match(
            id=match_id, title="Match", sport="football", participants=(),
            video_url=urls.get(match_id),
            spoiler_safe_video_url="https://media.example.com/safe.mp4" if match_id == "safe" else None,
        ),
        User(profile, profile),
    )


def test_reveal_then_reshield_removes_player_and_link():
    app = AppTest.from_function(media_app).run()
    assert not app.exception
    assert app.toggle[0].value is True
    assert not app.get("video")
    assert not app.get("link_button")

    app.button[0].click().run()
    assert not app.exception
    assert app.toggle[0].value is False
    assert len(app.get("video")) == 1
    assert "G6dj3UH8zdY" in app.get("video")[0].proto.url
    assert app.get("video")[0].proto.autoplay
    assert app.get("video")[0].proto.muted
    assert len(app.get("link_button")) == 1

    player_id = app.get("video")[0].proto.id
    app.run()
    assert app.get("video")[0].proto.id == player_id
    assert app.get("video")[0].proto.autoplay

    app.toggle[0].set_value(True).run()
    assert not app.exception
    assert not app.get("video")
    assert not app.get("link_button")
    assert app.button[0].label == "Reveal highlights"

    # A manual shield toggle must not inherit the previous reveal's autoplay.
    app.toggle[0].set_value(False).run()
    assert not app.get("video")[0].proto.autoplay


def test_revealing_one_match_does_not_reveal_another_or_another_profile():
    app = AppTest.from_function(media_app).run()
    app.button[0].click().run()
    app.selectbox[0].select("tennis").run()
    assert app.toggle[0].value is True
    assert not app.get("video")
    app.button[0].click().run()
    assert "64WsO9LKE-A" in app.get("video")[0].proto.url
    app.selectbox[1].select("guest").run()
    assert not app.exception
    assert app.toggle[0].value is True
    assert not app.get("video")


def test_missing_video_has_no_reveal_action():
    app = AppTest.from_function(media_app).run()
    app.selectbox[0].select("missing").run()
    assert not app.exception
    assert not app.get("video")
    assert not app.button


def test_explicit_safe_rendition_is_used_with_shield_enabled():
    app = AppTest.from_function(media_app).run()
    app.selectbox[0].select("safe").run()
    assert not app.exception
    assert app.toggle[0].value is True
    assert app.get("video")[0].proto.url == "https://media.example.com/safe.mp4"
    assert not app.get("video")[0].proto.autoplay
    assert not app.get("link_button")
