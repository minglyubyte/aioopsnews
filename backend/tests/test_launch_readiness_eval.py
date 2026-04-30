from __future__ import annotations

from pathlib import Path

from app.evals.launch_readiness import (
    evaluate_gold_samples,
    format_launch_readiness_report,
    load_gold_samples,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "launch_readiness_gold_samples.json"


def test_load_gold_samples_reads_expected_cases() -> None:
    samples = load_gold_samples(FIXTURE_PATH)

    assert len(samples) == 4
    assert samples[0].headline == "AssistCo assistant exposes private billing notes"
    assert samples[0].expected_categories == ["Privacy/Security"]


def test_evaluate_gold_samples_returns_expected_metric_counts() -> None:
    samples = load_gold_samples(FIXTURE_PATH)

    result = evaluate_gold_samples(samples)

    assert result["category_accuracy"] == {"correct": 3, "total": 4}
    assert result["severity_exact_agreement"] == {"correct": 3, "total": 4}
    assert result["severity_within_one"] == {"correct": 4, "total": 4}
    assert result["claim_match_precision"] == {"correct": 1, "total": 1}
    assert result["summary_acceptability"] == {"acceptable": 4, "total": 4}


def test_format_launch_readiness_report_includes_threshold_status() -> None:
    samples = load_gold_samples(FIXTURE_PATH)
    result = evaluate_gold_samples(samples)

    report = format_launch_readiness_report(result)

    assert "Category accuracy: 3/4 (75.0%)" in report
    assert "Severity exact agreement: 3/4 (75.0%)" in report
    assert "Severity within-1 agreement: 4/4 (100.0%)" in report
    assert "Claim-match precision: 1/1 (100.0%)" in report
    assert "Summary acceptability: 4/4 (100.0%)" in report
    assert "Launch threshold status:" in report
