from unittest.mock import Mock

import pytest

from src.core.models import ServiceError, SourceFile
from src.services.ingestion import index_documents, prepare_documents, snapshot_namespace
from src.services.library import LibraryRegistry
from src.services.matches import sample_files


def test_chunks_keep_source_and_match_metadata(settings, match):
    files = sample_files(match)
    chunks = prepare_documents(files, match, "vitor", settings)
    assert len(chunks) > len(files)
    assert all(len(c.page_content) <= settings.chunk_size for c in chunks)
    assert all(c.metadata["match_id"] == match.id for c in chunks)
    assert all(c.metadata["owner"] == "vitor" for c in chunks)
    assert {c.metadata["source"] for c in chunks} == {f.name for f in files}
    originals = {f.name: f.content.decode() for f in files}
    for chunk in chunks:
        start = chunk.metadata["start_index"]
        assert start >= 0
        assert originals[chunk.metadata["source"]][start:start + len(chunk.page_content)] == chunk.page_content


@pytest.mark.parametrize("files", [
    [], [SourceFile("a.pdf", b"text")], [SourceFile("a.txt", b"")],
    [SourceFile("a.md", b"\xff")], [SourceFile("a.txt", b"binary\x00")],
    [SourceFile("a.txt", b"text"), SourceFile("A.txt", b"different")],
    [SourceFile("big.txt", b"a" * (2 * 1024 * 1024 + 1))],
])
def test_invalid_files_fail_before_provider_access(files, settings, match):
    with pytest.raises(ServiceError):
        prepare_documents(files, match, "vitor", settings)


def test_names_are_labels_not_paths(settings, match):
    chunks = prepare_documents([SourceFile("../../report.md", b"A local report.")], match, "vitor", settings)
    assert chunks[0].metadata["source"] == "report.md"


def test_snapshots_are_stable_and_isolated(settings, match):
    files = sample_files(match)
    chunks = prepare_documents(files, match, "vitor", settings)
    namespace = snapshot_namespace(chunks, settings)
    assert namespace == snapshot_namespace(prepare_documents(list(reversed(files)), match, "vitor", settings), settings)
    assert namespace != snapshot_namespace(prepare_documents(files, match, "guest", settings), settings)
    assert namespace != snapshot_namespace(chunks, settings.model_copy(update={"embedding_dimensions": 512}))
    modified = [SourceFile(f.name, f.content + b" Additional notes.") for f in files]
    assert namespace != snapshot_namespace(prepare_documents(modified, match, "vitor", settings), settings)


def test_successful_indexing_is_idempotent(settings, match):
    registry = LibraryRegistry(settings.state_dir)
    chunks = prepare_documents(sample_files(match), match, "vitor", settings)
    factory = Mock()
    first = index_documents(chunks, settings, registry, "vitor", match, factory)
    second = index_documents(chunks, settings, registry, "vitor", match, factory)
    assert first == second == registry.get("vitor", match.id)
    factory.assert_called_once()
    assert factory.return_value.add_documents.call_args.kwargs["async_req"] is False
    assert len(factory.return_value.add_documents.call_args.kwargs["ids"]) == len(chunks)


def test_failed_upload_preserves_previous_snapshot(settings, match):
    registry = LibraryRegistry(settings.state_dir)
    chunks = prepare_documents(sample_files(match), match, "vitor", settings)
    previous = index_documents(chunks, settings, registry, "vitor", match, Mock())
    replacement = prepare_documents([SourceFile("new.md", b"Updated tactical evidence.")], match, "vitor", settings)
    factory = Mock()
    factory.return_value.add_documents.side_effect = RuntimeError("provider failure")
    with pytest.raises(ServiceError, match="previous library remains active"):
        index_documents(replacement, settings, registry, "vitor", match, factory)
    assert registry.get("vitor", match.id) == previous


def test_chunks_cannot_be_activated_for_another_profile(settings, match):
    chunks = prepare_documents(sample_files(match), match, "vitor", settings)
    with pytest.raises(ServiceError):
        index_documents(chunks, settings, LibraryRegistry(settings.state_dir), "guest", match, Mock())


def test_adapter_metadata_mutation_does_not_change_snapshot(settings, match):
    chunks = prepare_documents(sample_files(match), match, "vitor", settings)
    original_namespace = snapshot_namespace(chunks, settings)
    factory = Mock()

    def mutating_upload(documents, **kwargs):
        for doc in documents:
            doc.metadata["text"] = doc.page_content

    factory.return_value.add_documents.side_effect = mutating_upload
    index_documents(chunks, settings, LibraryRegistry(settings.state_dir), "vitor", match, factory)
    assert snapshot_namespace(chunks, settings) == original_namespace
    assert all("text" not in doc.metadata for doc in chunks)
