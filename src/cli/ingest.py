"""python -m src.cli.ingest --all [--dry-run]"""

import argparse
import sys

from src.core.config import Settings
from src.core.models import ServiceError
from src.services.curation import CURATED_SCOPE, load_context, source_metadata
from src.services.ingestion import index_documents, prepare_documents
from src.services.library import LibraryRegistry
from src.services.matches import load_matches


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish curated local match files to Pinecone.")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true", help="Publish every catalog match")
    selection.add_argument("--match", help="Match ID from data/matches.json")
    parser.add_argument("--dry-run", action="store_true", help="Validate and preview locally; no API calls")
    args = parser.parse_args(argv)
    try:
        settings = Settings()
        catalog = load_matches()
        selected = catalog if args.all else [m for m in catalog if m.id == args.match]
        if not selected:
            parser.error("No matching catalog entry.")
        # Validate the full selected batch before any network activity.
        prepared = []
        for match in selected:
            context = load_context(match)
            chunks = prepare_documents(context.files, match, CURATED_SCOPE, settings)
            metadata = source_metadata(context)
            for chunk in chunks:
                chunk.metadata.update(metadata[chunk.metadata["source"]])
            prepared.append((match, context, chunks))
            print(f"{match.id}: {len(context.files)} sources, {len(chunks)} chunks")
        if args.dry_run:
            print("Validation complete. No provider calls or registry writes were made.")
            return 0
        if settings.missing_credentials:
            raise ServiceError("Configure " + ", ".join(settings.missing_credentials) + " in .env.")
        registry = LibraryRegistry(settings.state_dir)
        for match, context, chunks in prepared:
            library = index_documents(chunks, settings, registry, CURATED_SCOPE, match,
                                      content_revision=context.revision)
            print(f"Published {match.id}: {library.namespace}")
        print("Pinecone may take a few seconds to make new vectors searchable.")
        return 0
    except (ServiceError, ValueError, OSError) as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
