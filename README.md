# Sports AI Companion

A conversational football and tennis workspace for learning RAG with **LangChain, Nebius, and Pinecone**. Choose a match, discuss tactics and player performance, inspect the evidence, and watch highlights when a video is configured.

The user interface follows the approved navy-and-emerald design: branded header, local team crests and player portraits, match cards, a primary chat panel, compact video, and source-backed insights. Preferences live in the profile menu. **Users do not upload or index documents.**

Live requests immediately display the submitted question followed by an assistant message with a robot avatar and animated Thinking indicator inside the chat. The indicator respects reduced-motion preferences, is replaced by the response, and clears on failure. Source readers separate document headers from body text, format labelled statistics as tables, and retain exact text under **View original text**. These presentation changes do not modify indexed documents or citation numbering.

## Run

Use Python 3.11–3.13 (validated with 3.13). The selected LangChain–Pinecone integration does not support Python 3.14.

The workspace already has an installed `.venv`:

```powershell
.venv\Scripts\python.exe -m streamlit run app.py
```

For a fresh environment on Windows:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

On macOS/Linux, create the environment with a supported Python and use `.venv/bin/python`. `requirements.txt` specifies compatible ranges; `requirements-lock.txt` records the tested runtime environment. Optional browser-check dependencies are in `requirements-dev.txt`.

Without connected credentials and a current published library, the app shows a **curated preview**, explicitly identified as a prepared example rather than a live AI answer. The sample matches and analysis are fictional. Asking a question in preview returns an honest availability message, not fabricated AI analysis.

## Developer-managed context

You maintain three kinds of local content:

1. **`data/matches.json`** — match IDs, sport, participants, display assets, optional video URLs, and a context-manifest path.
2. **`data/context/<match-id>.json`** — source records, display metrics, tactical insights, suggested questions, known information gaps, and an optional example discussion.
3. **Markdown/text files** — the underlying reports, transcripts, and statistics used by RAG. The included examples live in `data/samples/`; `data/private/` is ignored by Git for private material.

For example, a source record in a context manifest looks like:

```json
{
  "id": "tactics",
  "title": "Tactical report",
  "path": "../samples/sample-football/tactical-report.md",
  "kind": "Match analysis",
  "summary": "Substitutions, positioning & player performance",
  "url": null
}
```

File paths are relative to the manifest and must remain inside `data/`. Source IDs and filenames must be unique within a match. Optional original URLs are attribution links, not instructions to fetch a page. The loader never browses or scrapes.

Match catalog entries also accept `match_date` (ISO `YYYY-MM-DD`) and `competition` for the selection cards. The date describes the fixture, not a report's publication date. Missing dates display “Date to be confirmed”; missing competitions fall back to the existing subtitle. These display fields do not change the indexed document content.

Metrics and insights reference a valid `source_id`. Their values are curated by you, not automatically computed or verified against the source text. Keep them aligned with the underlying files. Example answers cite sources in manifest order (`[1]`, `[2]`); these examples are displayed only in preview mode and are not injected as evidence into live conversations.

Validate everything locally, without API calls or registry writes:

```powershell
.venv\Scripts\python.exe -m src.cli.ingest --all --dry-run
```

## Publish to Pinecone

1. Copy `.env.example` to `.env` and configure `NEBIUS_API_KEY` and `PINECONE_API_KEY` locally. Keep `.env.example` free of secrets. If `.env` already exists, update it instead of overwriting it.
2. Create a Pinecone **dense, bring-your-own-vectors index** named `sports-companion-nebius`, using **4096 dimensions** and **cosine** similarity. Alternatively, change the settings to match your index. Do not use an integrated-embedding or document-schema index with this adapter. The app never creates/deletes indexes automatically.
3. Publish the curated files:

```powershell
.venv\Scripts\python.exe -m src.cli.ingest --all
# Or publish a single bundled sample (with MATCH_CATALOG_PATH=data/matches.json):
.venv\Scripts\python.exe -m src.cli.ingest --match sample-football
```

The command sends text to Nebius for embeddings and stores text, metadata, and vectors in Pinecone. It validates the entire selected batch locally before provider calls, then publishes each match independently. A failure after an earlier match succeeds does not roll back that earlier match.

4. Refresh the app. Once the shared library matches the current local context and embedding settings, chat uses connected RAG automatically. Pinecone may need a few seconds before newly indexed records are searchable. Restart Streamlit after configuration changes if needed.

Defaults are `Qwen/Qwen3-Embedding-8B` (4096 dimensions) and `Qwen/Qwen3-30B-A3B-Instruct-2507`. Check availability in your Nebius Token Factory account; you can change `CHAT_MODEL` independently of embeddings. The chat adapter uses Chat Completions, `temperature=0`, and a 1200-token output budget. Reasoning models may need different limits or parameters.

The existing `langchain-openai` dependency supplies the OpenAI-compatible protocol clients; all model calls go to `NEBIUS_BASE_URL` with your Nebius key. No OpenAI key is needed. Embeddings are sent as raw strings with float output, bypassing OpenAI-specific tokenization. `EMBEDDING_DIMENSIONS` must be supported by the selected model and match Pinecone. An old 1536-dimensional index cannot hold the new 4096-dimensional vectors: create a separate index and re-ingest; do not delete the old index.

Before publishing, run this explicit connection check:

```powershell
.venv\Scripts\python.exe -m src.cli.check_providers
```

It checks Pinecone readiness, metric and dimensions, makes one short Nebius embedding request to confirm the output dimensions, and makes one short chat request. These calls may use credits, but do not send match files or write vectors. Failed checks identify the stage without printing keys.

To isolate model failures, run `python -m src.cli.check_providers --nebius-only` with your virtual environment. The check prints the configuration path, endpoint and effective model names. Process environment variables take precedence over `.env`; it marks model overrides explicitly. Save your editor changes before running the command. An HTTP 404 can indicate a model unavailable to your key or an incorrect endpoint.

For your prepared 20 reports, set `MATCH_CATALOG_PATH=data/private/matches.json` in `.env`. This private catalog selects `context/sport-recife-ceara.json` and `context/alcaraz-djokovic.json` and treats them as supplied real-match reports, not fictional examples. Source provenance and historical accuracy remain unverified. The public default `data/matches.json` retains the bundled fictional samples so a fresh checkout still runs.

Then validate and publish the report catalog:

```powershell
.venv\Scripts\python.exe -m src.cli.ingest --all --dry-run
.venv\Scripts\python.exe -m src.cli.ingest --match sport-recife-ceara
.venv\Scripts\python.exe -m src.cli.ingest --match alcaraz-djokovic
```

The dry run should show 10 sources for each match. Restart Streamlit after changing `.env`. Updating an embedding model requires re-indexing; updating only the chat model does not.

## Architecture

```text
Developer-maintained catalog + manifests + local text
    → validate → LangChain Documents → recursive splitting
    → OpenAIEmbeddings (Nebius endpoint) → PineconeVectorStore
    → atomically activate a versioned shared match library

User question + recent personal conversation
    → rewrite follow-up question when necessary
    → retrieve with scope, match, sport, and embedding-model pre-filters
    → ChatPromptTemplate → ChatOpenAI (Nebius endpoint) → StrOutputParser
    → cited response + inspectable passages
```

**Knowledge is shared; conversations are personal.** Ingestion and retrieval use the fixed `curated:v1` publication scope. The existing registry and vector metadata call this partition `owner` for compatibility, but this scope is not a selectable user ID. Old profile-specific libraries remain untouched and are not used by the new UI. Publish the curated corpus once; all demo profiles use it. Conversations remain isolated by profile, match, preview/live mode, and library revision.

The local manifest and text content are fingerprinted. A changed corpus or relevant match identity stops the app using an outdated publication until you re-index. Each vector snapshot is content-addressed, with deterministic chunk IDs. The active SQLite pointer changes only after every upload batch succeeds. Failed uploads leave the previous library intact. Re-publishing an unchanged active set avoids duplicate embedding calls.

Old/partially uploaded namespaces remain in Pinecone; cleanup is manual and they may incur storage costs. `.local/libraries.sqlite3` stores active pointers. Back up `.local/` to preserve them. If you manually delete vectors, or change Pinecone accounts while retaining the same index name, reset the corresponding local pointer before republishing identical content.

Source references are checked for valid numeric IDs; this does not prove semantic support for every model claim. The model is instructed to distinguish tactical interpretation from observed facts and acknowledge missing evidence. Similarity cutoffs are retrieval heuristics, not confidence scores. Follow-up query rewriting may make an additional model call.

## Video and spoiler behavior

Add a highlights URL to a match's optional `video_url` field. The private match catalog includes the supplied YouTube videos for Sport Recife–Ceará and Alcaraz–Djokovic. The compact panel uses Streamlit's player; autoplay is requested only after clicking **Reveal highlights**. Public sample matches have no videos. Video metadata changes do not require re-ingestion into Pinecone.

The default video shield shows a neutral cover without loading the ordinary player or its thumbnail. **Reveal highlights** disables the shield for the displayed match and profile and requests immediate, muted playback to skip the idle thumbnail. Unmute using the player controls. Browsers may still block autoplay, requiring a press of the player's play button; YouTube may briefly show its thumbnail or title while loading. Turn the shield back on to remove the player and stop playback. An **Open original video** link is available when revealed if the provider blocks embedded playback.

This protects against spoilers **before revealing**; standard YouTube playback can show titles, burned-in scores and recommendations. To support shielded playback, provide a separate verified `spoiler_safe_video_url`. The shield does not filter chat/source content. Playing a video does not mean the AI has analyzed it.

## Project layout

```text
app.py                         # Compose the consumer workspace
.streamlit/config.toml         # Dark theme and Streamlit configuration
assets/
  teams/                       # Locally bundled crests
  players/                     # Locally bundled portraits
  credits.json                 # Attribution shown in the profile menu
  CREDITS.md
data/
  matches.json                 # Developer-maintained match catalog
  context/                     # Typed source and insight manifests
  samples/                     # Fictional source material
src/
  core/                        # Configuration, identity boundary, shared models
  cli/ingest.py                # Developer-only ingestion entry point
  services/
    curation.py                # Manifest validation and content fingerprints
    ingestion.py               # Chunking and atomic snapshot publication
    embeddings.py              # LangChain embeddings adapter for Nebius
    retrieval.py               # LangChain Pinecone retrieval adapter
    companion.py               # Grounded chat prompt pipeline
    library.py                 # SQLite active-library registry
    matches.py                 # Local catalog and preference filtering
    agents.py                  # Future external-tool boundary
  ui/
    theme.py, styles.css       # Design system and responsive styling
    views.py                   # Conversation + supporting-content layout
    components/
      header.py                # Branding and profile preferences
      match_cards.py           # Match selection and browsing
      chat.py                  # Personal chat state, prompts, citations
      media.py                 # Visible video panel and shield behavior
      evidence.py              # Insights, sources, and retrieved passages
      primitives.py            # Escaped HTML, local assets, line icons
tests/                         # Service and Streamlit interaction tests
```

## Validation and current boundaries

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Tests block external networking and use provider doubles. They cover ingestion failures/idempotency, metadata filters, citation guards, shared corpus selection, stale content, private chat state, match switching, preferences, and video shielding. Desktop/mobile layouts were also checked in headless Chrome. Live Nebius/Pinecone access and real media playback require configured credentials/media; mocked tests do not validate those external services.

Demo profiles are not secure authentication. Preferences and conversations last for the browser session; there is no production multi-user authorization. The retained legacy custom-match registry is not exposed in the consumer UI. Text ingestion accepts UTF-8 `.txt`/`.md` files, up to 20 files, 2 MB per file, and 2,000 chunks per match. There is no PDF/OCR processing or statistical computation tool yet.

Future phases can add selected website/RSS/transcript collectors that produce the same manifests, followed by agent-driven research/tool selection. This version is an explicit RAG pipeline, with no autonomous web collection.

## 15-question evaluation

The developer-managed benchmark lives in `data/private/evaluation/questions.json`: 12 answerable questions with expected sources and answer outlines, plus 3 missing-information/wrong-match tests. Labels were assigned from the local documents before retrieval; review them before treating them as a formal gold standard.

```powershell
# Validate the suite and create an unmeasured report without API calls:
.venv\Scripts\python.exe -m src.cli.evaluate --dry-run

# Measure retrieval and generate answers for qualitative review:
.venv\Scripts\python.exe -m src.cli.evaluate --answers
```

Use `MATCH_CATALOG_PATH=data/private/matches.json` and publish the current documents first. The live evaluation uses the configured Nebius/Pinecone credentials, makes paid API calls, and does not change vectors. Omit `--answers` for retrieval-only evaluation.

If the provider connection fails because Python cannot validate the certificate issuer, append `--system-certificates` to use the operating system's trusted certificate store (requires `requirements-dev.txt`). Certificate verification remains enabled; this option affects only the evaluation process.

Each run writes a new directory under `.local/evaluation/` containing `report.html` (open in a browser; print to PDF for submission), `scores.csv`, and `results.json` with full passages, model answers, configuration, and corpus fingerprints. These artifacts and the private suite are ignored by Git. A partial run is marked as partial; failed calls are not reported as measured scores.

Metrics are source-level precision@k, recall@k, reciprocal rank and hit rate, using the production similarity cutoff. The current corpus has one chunk per document. Negative questions are excluded from retrieval averages and require answer review for abstention. Similarity values and citation-ID checks are not faithfulness scores; no numerical answer-quality claim is generated. Each question starts with empty history, so this benchmark does not test follow-up rewriting.

## References

- [LangChain Pinecone integration](https://docs.langchain.com/oss/python/integrations/vectorstores/pinecone)
- [Nebius quickstart](https://docs.tokenfactory.nebius.com/quickstart)
- [Nebius embedding API](https://docs.tokenfactory.nebius.com/api-reference/inference/create-embeddings)
- [LangChain OpenAI-compatible integration](https://docs.langchain.com/oss/python/integrations/chat/openai)
- [Streamlit themes](https://docs.streamlit.io/develop/concepts/configuration/theming)
- [Streamlit containers and stable styling keys](https://docs.streamlit.io/develop/api-reference/layout/st.container)
- [Local image credits](assets/CREDITS.md)
