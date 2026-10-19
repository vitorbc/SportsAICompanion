"""Run the 15-question retrieval benchmark without modifying Pinecone vectors.

python -m src.cli.evaluate --dry-run
python -m src.cli.evaluate --answers
"""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

from src.core.config import ROOT, Settings
from src.core.models import ServiceError
from src.services.companion import RagCompanion, make_chat_model
from src.services.curation import CURATED_SCOPE, load_context
from src.services.evaluation import score_retrieval, write_report
from src.services.ingestion import prepare_documents
from src.services.library import LibraryRegistry
from src.services.matches import load_matches
from src.services.retrieval import PineconeRetriever


class CapturedRetriever:
    """Answer from the measured passages without issuing another vector query."""

    def __init__(self, evidence):
        self.evidence = evidence

    def retrieve(self, query):
        return self.evidence


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=ROOT / "data/private/evaluation/questions.json")
    parser.add_argument("--output", type=Path, help="New output directory; existing results are not overwritten")
    parser.add_argument("--dry-run", action="store_true", help="Validate corpus and produce an unmeasured report without API calls")
    parser.add_argument("--answers", action="store_true", help="Also generate answers with Nebius for qualitative review")
    parser.add_argument("--system-certificates", action="store_true", help="Use OS certificate trust via the optional truststore package; TLS verification stays enabled")
    args = parser.parse_args(argv)
    result, folder = None, None
    try:
        settings = Settings()
        suite_bytes = args.suite.read_bytes()
        cases = json.loads(suite_bytes)
        if len(cases) != 15 or len({c["id"] for c in cases}) != 15:
            raise ValueError("The report requires 15 questions with unique IDs.")
        if sum(bool(c["expected_sources"]) for c in cases) != 12:
            raise ValueError("Use 12 answerable questions and 3 negative tests for this report.")
        matches = {m.id: m for m in load_matches()}
        contexts = {}
        for case in cases:
            if case["match_id"] not in matches:
                raise ValueError(f"Match not found: {case['match_id']}. Check MATCH_CATALOG_PATH.")
            if case["match_id"] not in contexts:
                contexts[case["match_id"]] = load_context(matches[case["match_id"]])
            names = {f.name for f in contexts[case["match_id"]].files}
            if not set(case["expected_sources"]).issubset(names):
                raise ValueError(f"Unknown expected source in {case['id']}.")
        now = datetime.now(timezone.utc)
        run_id = now.strftime("%Y%m%dT%H%M%S%fZ")
        folder = args.output or settings.state_dir / "evaluation" / run_id
        if folder.exists() and any(folder.iterdir()):
            raise ValueError("Output directory is not empty. Choose a new directory to preserve prior results.")
        configuration = {key: getattr(settings, key) for key in (
            "embedding_model", "embedding_dimensions", "chat_model", "chunk_size", "chunk_overlap",
            "retrieval_top_k", "retrieval_min_score", "pinecone_index_name")}
        configuration.update(metric="cosine", retrieval="dense; production metadata filters and score cutoff",
                             chunk_units="characters", scope=CURATED_SCOPE,
                             suite_sha256=hashlib.sha256(suite_bytes).hexdigest(), answers_requested=args.answers,
                             certificate_trust="operating system" if args.system_certificates else "provider defaults",
                             history="empty for every question", sources={}, snapshots={})
        for match_id, context in contexts.items():
            configuration["sources"][match_id] = {
                "documents": len(context.files),
                "chunks": len(prepare_documents(context.files, matches[match_id], CURATED_SCOPE, settings)),
                "content_revision": context.revision,
            }
        result = dict(run_id=run_id, started_at=now.isoformat(), status="unmeasured" if args.dry_run else "running",
                      configuration=configuration,
                      questions=[{**c, "retrieval_status": "not_run", "evidence": []} for c in cases])
        write_report(result, folder)
        print(f"Report directory: {folder}", flush=True)
        if args.dry_run:
            print("15 cases validated. Scores are unmeasured; no API calls made.")
            return 0
        if settings.missing_credentials:
            raise ServiceError("Configure " + ", ".join(settings.missing_credentials))
        if args.system_certificates:
            try:
                import truststore
            except ImportError as exc:
                raise ServiceError("Install requirements-dev.txt to use --system-certificates.") from exc
            truststore.inject_into_ssl()
        registry = LibraryRegistry(settings.state_dir)
        libraries = {}
        for match_id, context in contexts.items():
            library = registry.get(CURATED_SCOPE, match_id)
            if not library or library.content_revision != context.revision:
                raise ServiceError(f"Publish current context for {match_id} before evaluation.")
            libraries[match_id] = library
            configuration["snapshots"][match_id] = asdict(library)
        retrievers, unavailable = {}, {}
        model = make_chat_model(settings) if args.answers else None
        for row in result["questions"]:
            match_id = row["match_id"]
            try:
                if match_id in unavailable:
                    raise ServiceError(unavailable[match_id])
                if match_id not in retrievers:
                    try:
                        retrievers[match_id] = PineconeRetriever(settings, libraries[match_id], CURATED_SCOPE, matches[match_id])
                    except ServiceError as exc:
                        unavailable[match_id] = str(exc)
                        raise
                start = perf_counter()
                evidence = retrievers[match_id].retrieve(row["question"])
                row.update(retrieval_status="ok", retrieval_seconds=round(perf_counter() - start, 3),
                           evidence=[asdict(e) for e in evidence],
                           metrics=score_retrieval(row["expected_sources"], [e.source for e in evidence], settings.retrieval_top_k))
                if args.answers:
                    try:
                        answer = RagCompanion(CapturedRetriever(evidence), model).answer(row["question"], [], matches[match_id])
                        row.update(answer=answer.content, answer_status="ok")
                    except ServiceError as exc:
                        row.update(answer_status="error", answer_error=str(exc))
            except ServiceError as exc:
                row.update(retrieval_status="error", error=str(exc))
            print(f"{row['id']}: retrieval={row['retrieval_status']}, answer={row.get('answer_status', 'not requested')}", flush=True)
            write_report(result, folder)  # Preserve partial work after every query.
        errors = any(r["retrieval_status"] != "ok" or r.get("answer_status") == "error" for r in result["questions"])
        result["status"] = "partial" if errors else "completed"
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_report(result, folder)
        return 1 if errors else 0
    except (ServiceError, ValueError, KeyError, OSError) as exc:
        if result is not None and folder is not None:
            result.update(status="failed", setup_error=str(exc))
            write_report(result, folder)
        print(f"Evaluation could not finish: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
