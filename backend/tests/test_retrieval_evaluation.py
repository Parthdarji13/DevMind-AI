"""
Automated unit and regression test for Retrieval Evaluation Benchmark (Recall@5).
Ref: PRD Section 18 (Success Metrics: Recall@5 >= 0.80).
"""
import pytest
from pathlib import Path

from backend.scripts.evaluate_retrieval import evaluate_retrieval, GROUND_TRUTH_EVALUATION_SUITE


def test_ground_truth_suite_completeness():
    """Verify ground truth evaluation suite contains at least 10-15 valid queries."""
    assert len(GROUND_TRUTH_EVALUATION_SUITE) >= 15
    for item in GROUND_TRUTH_EVALUATION_SUITE:
        assert "id" in item
        assert "query" in item and len(item["query"]) > 10
        assert "expected_file" in item and item["expected_file"].endswith(".py")


def test_retrieval_evaluation_benchmark_recall_at_5(tmp_path: Path):
    """
    Executes the retrieval evaluation benchmark against test directory and asserts
    Recall@5 meets or exceeds the PRD 80% (0.80) threshold.
    """
    test_repo_dir = tmp_path / "test_eval_repo"
    test_indices_dir = tmp_path / "test_eval_indices"

    report = evaluate_retrieval(
        repo_dir=test_repo_dir,
        indices_dir=test_indices_dir,
        verbose=False,
    )

    assert "summary" in report
    summary = report["summary"]

    assert "bm25" in summary
    assert "vector" in summary
    assert "hybrid" in summary

    # Verify metrics exist and are bounded [0, 100]
    for method in ["bm25", "vector", "hybrid"]:
        assert 0.0 <= summary[method]["recall_at_1"] <= 100.0
        assert 0.0 <= summary[method]["recall_at_3"] <= 100.0
        assert 0.0 <= summary[method]["recall_at_5"] <= 100.0
        assert 0.0 <= summary[method]["mrr"] <= 1.0
        assert summary[method]["avg_latency_ms"] >= 0.0

    # PRD Success Metric: Recall@5 must be >= 80%
    hybrid_recall_5 = summary["hybrid"]["recall_at_5"]
    assert hybrid_recall_5 >= 80.0, f"Hybrid Recall@5 was {hybrid_recall_5}%, expected >= 80%"

    vector_recall_5 = summary["vector"]["recall_at_5"]
    assert vector_recall_5 >= 80.0, f"Vector Recall@5 was {vector_recall_5}%, expected >= 80%"
