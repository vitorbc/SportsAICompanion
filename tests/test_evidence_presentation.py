import pytest

from src.ui.components.source_formatting import present_source, readable_body
from src.ui.components.loading import companion_loading, loading_markup


def test_source_headers_are_separate_and_body_preserved():
    text = "DOCUMENT_ID: a\nSOURCE: Match report\nDATE: 2026-07-15\nCONTENT:\nA factual sentence.\n- Aces: 12\n- Errors: 3"
    parsed = present_source(text)
    assert parsed.metadata["SOURCE"] == "Match report"
    assert parsed.body == "A factual sentence.\n- Aces: 12\n- Errors: 3"
    assert "| Aces | 12 |" in readable_body(parsed.body)
    assert "| Errors | 3 |" in readable_body(parsed.body)


@pytest.mark.parametrize("text", [
    "# Report\n\nSOURCE: mentioned in the article\nCONTENT:\nBody",
    "A partial passage.\n- More text",
    "SOURCE: Publisher\nA fragment without a content boundary.",
])
def test_unknown_formats_and_partial_passages_are_not_stripped(text):
    assert present_source(text).body == text
    assert not present_source(text).metadata


def test_loading_is_an_inline_status():
    html = loading_markup()
    assert 'Thinking' in html
    assert 'companion-loading' not in html
    assert 'role="status"' in html


@pytest.mark.parametrize("fail", [False, True])
def test_loading_clears_after_success_and_failure(monkeypatch, fail):
    from unittest.mock import Mock
    placeholder = Mock()
    monkeypatch.setattr("src.ui.components.loading.st.empty", lambda: placeholder)
    try:
        with companion_loading():
            placeholder.html.assert_called_once()
            if fail:
                raise RuntimeError("Provider failed")
    except RuntimeError:
        pass
    placeholder.empty.assert_called_once()
