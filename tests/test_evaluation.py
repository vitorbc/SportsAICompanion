import json

import pytest

from src.services.evaluation import aggregate, score_retrieval, write_report


def test_metrics_account_for_rank_missing_slots_and_duplicate_sources():
    result = score_retrieval(["a", "b"], ["irrelevant", "a", "a"], 5)
    assert result["precision_at_k"] == 0.2
    assert result["recall_at_k"] == 0.5
    assert result["reciprocal_rank"] == 0.5
    assert result["hit_at_k"] == 1
    assert result["missing_sources"] == ["b"]


def test_negative_case_is_not_a_zero_or_perfect_score():
    result = score_retrieval([], ["a"], 5)
    assert result["precision_at_k"] is None
    assert result["recall_at_k"] is None
    assert result["reciprocal_rank"] is None


def test_empty_retrieval_and_cutoff_are_real_misses():
    assert score_retrieval(["a"], [], 5)["recall_at_k"] == 0
    assert score_retrieval(["a"], ["b", "c", "a"], 2)["reciprocal_rank"] == 0


def test_aggregate_excludes_provider_failures_and_negative_cases():
    rows = [
        dict(retrieval_status="ok", expected_sources=["a"], metrics=score_retrieval(["a"], ["a"], 5)),
        dict(retrieval_status="ok", expected_sources=["a"], metrics=score_retrieval(["a"], [], 5)),
        dict(retrieval_status="error", expected_sources=["a"]),
        dict(retrieval_status="ok", expected_sources=[], metrics=score_retrieval([], [], 5)),
    ]
    result = aggregate(rows)
    assert result["scored_questions"] == 2
    assert result["precision_at_k"] == pytest.approx(0.1)
    assert result["recall_at_k"] == 0.5
    assert aggregate([])["recall_at_k"] is None


def test_report_preserves_unmeasured_status_and_escapes_content(tmp_path):
    row = dict(id="Q01", match_id="test", question="<script>alert(1)</script>", category="test",
               expected_sources=["a"], expected_answer="expected", label_rationale="reason",
               retrieval_status="not_run", evidence=[])
    result = dict(run_id="test", started_at="test", status="unmeasured",
                  configuration={"retrieval_top_k": 5}, questions=[row])
    write_report(result, tmp_path)
    page = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "&lt;script&gt;" in page
    assert "<script>" not in page
    assert "Mean precision@5: N/A" in page
    assert json.loads((tmp_path / "results.json").read_text())["status"] == "unmeasured"
    assert (tmp_path / "scores.csv").exists()
