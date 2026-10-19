from dataclasses import replace
from unittest.mock import Mock

import pytest
from pydantic import SecretStr, ValidationError

from src.cli.ingest import main
from src.core.models import Library
from src.services.curation import ContextManifest, CURATED_SCOPE, data_path, load_context
from src.services.matches import load_matches
from src.ui.components.chat import library_is_ready
from src.ui.components.media import playable_url
from src.ui.components.primitives import asset_uri, esc


def test_every_curated_source_is_readable_and_has_provenance():
    for match in load_matches():
        context = load_context(match)
        assert context.files
        assert context.manifest.sources
        assert all(f.content for f in context.files)
        assert context.revision == load_context(match).revision


def test_manifest_rejects_unknown_metric_source():
    with pytest.raises(ValidationError, match="Unknown source reference"):
        ContextManifest(sources=[], metrics=[{"label": "Shots", "value": "12", "source_id": "missing"}])


def test_manifest_rejects_duplicate_sources_and_unsafe_urls():
    source = {"id": "one", "title": "Report", "path": "report.md"}
    with pytest.raises(ValidationError, match="unique"):
        ContextManifest(sources=[source, source])
    with pytest.raises(ValidationError, match="HTTP"):
        ContextManifest(sources=[{**source, "url": "javascript:alert(1)"}])


def test_example_cannot_reference_a_nonexistent_source():
    with pytest.raises(ValidationError, match="Example citations"):
        ContextManifest(sources=[{"id": "one", "title": "Report", "path": "report.md"}],
                        example={"question": "What changed?", "answer": "A new shape. [2]"})


def test_data_and_asset_paths_cannot_escape_workspace():
    with pytest.raises(ValueError):
        data_path("../../.env")
    assert asset_uri("../.env") is None
    assert esc('<script>"unsafe"</script>') == '&lt;script&gt;&quot;unsafe&quot;&lt;/script&gt;'


def test_dry_run_does_not_create_state_or_contact_providers(settings, monkeypatch, capsys):
    monkeypatch.setattr("src.cli.ingest.Settings", lambda: settings)
    factory = Mock(side_effect=AssertionError("Dry run must not open the registry"))
    monkeypatch.setattr("src.cli.ingest.LibraryRegistry", factory)
    assert main(["--all", "--dry-run"]) == 0
    factory.assert_not_called()
    assert "sample-football" in capsys.readouterr().out


def test_cli_publishes_shared_context_and_source_metadata(settings, monkeypatch):
    settings = settings.model_copy(update={"nebius_api_key": SecretStr("fake"), "pinecone_api_key": SecretStr("fake")})
    monkeypatch.setattr("src.cli.ingest.Settings", lambda: settings)
    publish = Mock()
    monkeypatch.setattr("src.cli.ingest.index_documents", publish)
    assert main(["--match", "sample-football"]) == 0
    args = publish.call_args
    assert args.args[3] == CURATED_SCOPE
    assert args.kwargs["content_revision"] == load_context(load_matches()[0]).revision
    assert all(c.metadata["source_id"] and c.metadata["source_title"] for c in args.args[0])


def test_live_chat_requires_current_content_and_matching_models(settings, match):
    context = load_context(match)
    settings = settings.model_copy(update={"nebius_api_key": SecretStr("fake"), "pinecone_api_key": SecretStr("fake")})
    library = Library("snapshot", settings.pinecone_index_name, settings.embedding_model,
                      settings.embedding_dimensions, [], 3, context.revision)
    assert library_is_ready(library, context, settings)
    assert not library_is_ready(replace(library, content_revision="old"), context, settings)
    assert not library_is_ready(replace(library, embedding_model="other"), context, settings)
    assert not library_is_ready(None, context, settings)


def test_video_shield_never_plays_ordinary_embed(match):
    match = replace(match, video_url="https://www.youtube.com/watch?v=example")
    assert playable_url(match, False) == match.video_url
    assert playable_url(match, True) is None
    safe = replace(match, spoiler_safe_video_url="https://media.example.com/safe.mp4")
    assert playable_url(safe, True) == safe.spoiler_safe_video_url
    assert playable_url(replace(match, video_url="javascript:alert(1)"), False) is None
