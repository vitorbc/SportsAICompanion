"""Source-level retrieval metrics and a portable report; no provider calls here."""

import csv
import html
import json
from pathlib import Path
from statistics import mean


def score_retrieval(expected: list[str], retrieved: list[str], k: int) -> dict:
    """Binary source relevance, deduplicated in rank order, within k chunk slots.

    Missing slots count against precision@k. Negative questions have no relevant
    sources, so their retrieval metrics are undefined, rather than zero or 100%.
    """
    gold = set(expected)
    ranked = list(dict.fromkeys(retrieved[:k]))
    if not gold:
        return dict(precision_at_k=None, recall_at_k=None, reciprocal_rank=None,
                    hit_at_k=None, missing_sources=[], retrieved_sources=ranked)
    hits = gold.intersection(ranked)
    first = next((i for i, source in enumerate(ranked, 1) if source in gold), None)
    return dict(precision_at_k=len(hits) / k, recall_at_k=len(hits) / len(gold),
                reciprocal_rank=1 / first if first else 0.0,
                hit_at_k=float(bool(hits)), missing_sources=sorted(gold - hits),
                retrieved_sources=ranked)


def aggregate(rows: list[dict]) -> dict:
    valid = [r for r in rows if r.get("retrieval_status") == "ok" and r["expected_sources"]]
    keys = ("precision_at_k", "recall_at_k", "reciprocal_rank", "hit_at_k")
    return {"scored_questions": len(valid), **{
        key: mean(r["metrics"][key] for r in valid) if valid else None for key in keys
    }}


def _pct(value) -> str:
    return "N/A" if value is None else f"{value:.1%}"


def write_report(result: dict, folder: Path) -> None:
    """Keep raw evidence, CSV scores, and a printable HTML report together."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["id", "match_id", "question", "retrieval_status", "precision_at_k",
              "recall_at_k", "reciprocal_rank", "hit_at_k", "returned_chunks", "review"]
    with (folder / "scores.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in result["questions"]:
            writer.writerow({**{key: row.get(key, "") for key in fields[:4]},
                             **{key: row.get("metrics", {}).get(key) for key in fields[4:8]},
                             "returned_chunks": len(row.get("evidence", [])),
                             "review": row.get("review", "Not reviewed")})
    esc = lambda value: html.escape(str(value))
    k = result["configuration"]["retrieval_top_k"]
    totals = aggregate(result["questions"])
    rows_html, details = [], []
    for row in result["questions"]:
        metrics = row.get("metrics", {})
        if row.get("retrieval_status") != "ok":
            finding = "Not measured: " + row.get("error", "not run")
        elif not row["expected_sources"]:
            finding = f"Negative test: {len(row['evidence'])} candidates; inspect answer for abstention."
        else:
            missing = metrics["missing_sources"]
            finding = "All expected sources retrieved." if not missing else "Missed: " + ", ".join(missing)
            distractors = [s for s in metrics["retrieved_sources"] if s not in row["expected_sources"]]
            if distractors:
                finding += f" {len(distractors)} non-relevant source(s) under the benchmark labels."
        cells = [row["id"], row["question"], _pct(metrics.get("precision_at_k")),
                 _pct(metrics.get("recall_at_k")),
                 "N/A" if metrics.get("reciprocal_rank") is None else f"{metrics['reciprocal_rank']:.3f}", finding]
        rows_html.append("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in cells) + "</tr>")
        passages = "".join(
            f"<details><summary>[{i}] {esc(e['source'])}, chunk {e['chunk']}, cosine {e['score']:.4f}</summary>"
            f"<pre>{esc(e['text'])}</pre></details>" for i, e in enumerate(row.get("evidence", []), 1))
        details.append(
            f"<article><h3>{esc(row['id'])}: {esc(row['question'])}</h3>"
            f"<p><b>Match / type:</b> {esc(row['match_id'])} / {esc(row['category'])}</p>"
            f"<p><b>Expected evidence:</b> {esc(', '.join(row['expected_sources']) or 'None in this match corpus')}</p>"
            f"<p><b>Expected answer / behavior:</b> {esc(row['expected_answer'])}</p>"
            f"<p><b>Label rationale:</b> {esc(row['label_rationale'])}</p>"
            f"<p><b>Retrieval diagnosis:</b> {esc(finding)}</p>"
            f"<p><b>Qualitative answer review:</b> {esc(row.get('review', 'Not reviewed; no faithfulness score assigned.'))}</p>"
            f"<p><b>Generated answer:</b></p><pre>{esc(row.get('answer') or row.get('answer_error') or 'Not generated.')}</pre>"
            f"{passages}</article>")
    complete = sum(r.get("retrieval_status") == "ok" for r in result["questions"])
    observations = "".join(f"<li>{esc(note)}</li>" for note in result.get("analysis", []))
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>Sports AI Companion — 15-question RAG evaluation</title>
<style>body{{font:16px/1.6 system-ui,sans-serif;color:#152536;max-width:1200px;margin:40px auto;padding:0 24px}}
h1,h2,h3{{line-height:1.25}}h1{{color:#075b56}}table{{border-collapse:collapse;width:100%;font-size:14px}}
td,th{{border:1px solid #cbd5df;padding:10px;text-align:left;vertical-align:top;overflow-wrap:anywhere}}th{{background:#eaf5f2}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 system-ui;background:#f3f6f8;padding:12px}}
article{{border-top:2px solid #d5e7e3;margin-top:28px;padding-top:12px}}summary{{cursor:pointer}}
.summary{{padding:20px;background:#eaf5f2;border-radius:12px}}@media print{{body{{margin:0}}article{{break-inside:avoid}}}}</style>
<h1>Sports AI Companion: 15-question RAG evaluation</h1>
<p>Run: {esc(result['run_id'])} · {esc(result.get('local_started_at', result['started_at']))} · Status: {esc(result['status'])}</p>
{f"<p><b>Setup error:</b> {esc(result['setup_error'])}</p>" if result.get('setup_error') else ''}
<p>Scope: developer-curated Sport Recife–Ceará and Alcaraz–Djokovic reports; 12 answerable questions and 3 negative tests.
This evaluates faithfulness to the supplied corpus, not independently verified sporting facts or publisher authenticity.</p>
<div class="summary"><b>{complete}/15 retrieval calls completed; {totals['scored_questions']}/12 answerable questions scored.</b><br>
Mean precision@{k}: {_pct(totals['precision_at_k'])} · Mean recall@{k}: {_pct(totals['recall_at_k'])} ·
MRR@{k}: {'N/A' if totals['reciprocal_rank'] is None else f"{totals['reciprocal_rank']:.3f}"} ·
Hit rate@{k}: {_pct(totals['hit_at_k'])}</div>
<h2>Method and scoring</h2>
<p>Expected sources and answer outlines were assigned by the coding assistant after inspecting all 20 local documents,
before retrieval was run. They are provisional binary relevance labels for developer review, not independent human judgments.
Related match text alone does not count as relevant: it must support a requested fact or interpretation. Partial supporting sources are included.</p>
<ul><li>Precision@{k} = relevant distinct sources in the first {k} returned chunk slots / {k}; missing slots count as non-relevant.</li>
<li>Recall@{k} = expected sources retrieved / all expected sources.</li>
<li>Reciprocal rank = 1 / rank of the first relevant source (0 if absent); MRR is its mean.</li>
<li>Hit rate = fraction of answerable questions retrieving at least one relevant source.</li>
<li>Results use the production score cutoff. Source IDs are deduplicated in rank order; the current corpus has one chunk per file.</li>
<li>Negative tests have no gold sources: precision, recall and reciprocal rank are N/A and excluded from averages. Returning topical candidates is not itself an answer hallucination.</li>
<li>Provider failures are recorded as unmeasured and excluded, not converted into zeros. Report completion counts alongside averages.</li></ul>
<p>Questions use empty conversation history, so follow-up rewriting is not tested. Optional answers use the existing companion with exactly the retrieved evidence;
no second retrieval or automatic LLM judge is used. Similarity scores are not relevance percentages. No numeric faithfulness or answer-relevance score is claimed.</p>
<h2>Configuration and reproducibility</h2><pre>{esc(json.dumps(result['configuration'], indent=2))}</pre>
<p>Corpus and suite hashes, snapshot namespaces, full retrieved passages, and generated answers are retained in results.json.
Only successful retrievals are scored; check status before treating this as a completed report.</p>
<h2>Question-level retrieval results</h2><table><thead><tr><th>ID</th><th>Question</th><th>P@{k}</th><th>R@{k}</th><th>RR</th><th>Finding</th></tr></thead>
<tbody>{''.join(rows_html)}</tbody></table>
<h2>Failure analysis and next steps</h2><ul>{observations or '<li>Review pending. Inspect the per-question findings below.</li>'}</ul>
<p>{esc(result.get('review_method', 'Qualitative answer review has not been performed.'))}</p>
<p>Limitations: a small, hand-selected development set covering two matches; no held-out test set, repeated-run analysis,
or external verification. With only one or two relevant documents, precision@5 has a low ceiling even when retrieval succeeds.
Do not tune on these questions and then present the same scores as unseen-test performance.</p>
<h2>Evidence and answer review</h2>{''.join(details)}</html>"""
    (folder / "report.html").write_text(page, encoding="utf-8")
