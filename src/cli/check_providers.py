"""Check Nebius and Pinecone without uploading any match documents.

Run explicitly: python -m src.cli.check_providers
Uses one short embedding and one short chat request (provider usage may be billed).
"""

import argparse
import os
import sys
from urllib.parse import urlsplit

from openai import APIConnectionError, APIStatusError, APITimeoutError

from src.core.config import ROOT, Settings
from src.core.models import ServiceError
from src.services.companion import make_chat_model
from src.services.embeddings import make_embeddings
from src.services.retrieval import make_vector_store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check model and vector database connectivity.")
    parser.add_argument("--nebius-only", action="store_true", help="Check models without contacting Pinecone")
    args = parser.parse_args(argv)
    stage = "configuration"
    try:
        settings = Settings()
        print(f"Configuration file: {ROOT / '.env'}", flush=True)
        endpoint = urlsplit(settings.nebius_base_url)
        # Omit URL credentials and query parameters from diagnostics.
        print(f"Nebius endpoint: {endpoint.scheme}://{endpoint.hostname}{endpoint.path}", flush=True)
        for name, value in (("EMBEDDING_MODEL", settings.embedding_model),
                            ("CHAT_MODEL", settings.chat_model)):
            overridden = any(key.casefold() == name.casefold() for key in os.environ)
            origin = "process environment overrides .env" if overridden else ".env or application default"
            print(f"{name}: {value} ({origin})", flush=True)
        print(f"Expected embedding dimensions: {settings.embedding_dimensions}", flush=True)
        missing = [name for name in settings.missing_credentials
                   if not args.nebius_only or name == "NEBIUS_API_KEY"]
        if missing:
            raise ServiceError("Configure " + ", ".join(missing) + " in .env.")
        if not args.nebius_only:
            stage = "Pinecone index access"
            # Describes the index and constructs a client; never inserts vectors.
            make_vector_store(settings, "setup-check")
            print("Pinecone index: accessible, ready, cosine metric and configured dimension match.")
        stage = "Nebius embeddings"
        vector = make_embeddings(settings).embed_query("Football tactics and tennis strategy.")
        if len(vector) != settings.embedding_dimensions:
            raise ServiceError(
                f"Nebius returned {len(vector)} dimensions; expected {settings.embedding_dimensions}. "
                "Match EMBEDDING_DIMENSIONS and the Pinecone index to the model output."
            )
        print(f"Nebius embeddings: {len(vector)} dimensions confirmed.")
        stage = "Nebius chat"
        response = make_chat_model(settings).invoke("Reply with the single word OK.")
        if not response.content:
            raise ServiceError("Nebius chat returned no visible answer. Check the model and output budget.")
        print("Nebius chat: response received.")
        print("Setup checks passed. No match documents were sent or vectors written.")
        return 0
    except ServiceError as exc:
        print(f"Setup check failed: {exc}", file=sys.stderr)
    except APIStatusError as exc:
        # Describe status codes, never echo arbitrary provider bodies or headers.
        guidance = {
            400: "The request was rejected. Check model parameters and embedding dimensions.",
            401: "Nebius rejected authentication. Check NEBIUS_API_KEY in .env.",
            403: "Access denied. Check the key's project and model permissions.",
            404: "The model or endpoint was not found. Check EMBEDDING_MODEL or CHAT_MODEL "
                 "against your Nebius model catalog, and check NEBIUS_BASE_URL.",
            422: "The request parameters were rejected. Check model support for the configured dimensions.",
            429: "Rate limit or quota reached. Check Nebius credits and usage limits before retrying.",
        }.get(exc.status_code, "Nebius returned a provider error. Check service status and retry later.")
        print(f"Setup check failed during {stage} (HTTP {exc.status_code}). {guidance}", file=sys.stderr)
    except APITimeoutError:
        print(f"Setup check timed out during {stage}. Retry or check Nebius service status.", file=sys.stderr)
    except APIConnectionError:
        print(f"Setup check could not connect during {stage}. Check the endpoint, network, "
              "proxy and TLS certificate configuration.", file=sys.stderr)
    except Exception:
        # Provider errors can contain request details. Keep credentials out of logs.
        print(f"Setup check failed during {stage}. Check configuration, model availability, "
              "credentials, quota and network access.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
