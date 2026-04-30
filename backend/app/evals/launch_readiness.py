from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.models.claim import ClaimRecord
from app.services.claim_matcher import match_incident_to_claim
from app.services.classifier import classify_incident
from app.services.summarizer import summarize_incident

THRESHOLDS = {
    "category_accuracy": 0.75,
    "severity_exact_agreement": 0.75,
    "severity_within_one": 0.95,
    "claim_match_precision": 0.85,
    "summary_acceptability": 0.9,
}

METRIC_LABELS = {
    "category_accuracy": "Category accuracy",
    "severity_exact_agreement": "Severity exact agreement",
    "severity_within_one": "Severity within-1 agreement",
    "claim_match_precision": "Claim-match precision",
    "summary_acceptability": "Summary acceptability",
}

DEFAULT_GOLD_SAMPLE_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "launch_readiness_gold_samples.json"
)


@dataclass(frozen=True)
class GoldSample:
    headline: str
    source_summary: str
    incident_date: date
    expected_company: str
    expected_categories: list[str]
    expected_severity_score: int
    claim_expected: bool
    summary_acceptable: bool


def load_gold_samples(path: Path) -> list[GoldSample]:
    raw_samples = json.loads(path.read_text())
    return [
        GoldSample(
            headline=raw_sample["headline"],
            source_summary=raw_sample["source_summary"],
            incident_date=date.fromisoformat(raw_sample["incident_date"]),
            expected_company=raw_sample["expected_company"],
            expected_categories=list(raw_sample["expected_categories"]),
            expected_severity_score=raw_sample["expected_severity_score"],
            claim_expected=raw_sample["claim_expected"],
            summary_acceptable=raw_sample["summary_acceptable"],
        )
        for raw_sample in raw_samples
    ]


def evaluate_gold_samples(samples: list[GoldSample]) -> dict[str, dict[str, int]]:
    category_correct = 0
    severity_exact = 0
    severity_within_one = 0
    claim_correct = 0
    claim_total = 0
    acceptable_summaries = 0
    curated_claims = _seed_claims()

    for sample in samples:
        classification = classify_incident(
            headline=sample.headline,
            source_summary=sample.source_summary,
        )
        summary = summarize_incident(
            headline=sample.headline,
            source_summary=sample.source_summary,
        )
        claim_match = match_incident_to_claim(
            claims=curated_claims,
            headline=sample.headline,
            source_summary=sample.source_summary,
            company_involved=classification.company_involved,
            categories=classification.categories,
            incident_date=sample.incident_date,
        )

        if classification.categories == sample.expected_categories:
            category_correct += 1
        if classification.severity_score == sample.expected_severity_score:
            severity_exact += 1
        if abs(classification.severity_score - sample.expected_severity_score) <= 1:
            severity_within_one += 1
        if claim_match is not None:
            claim_total += 1
            if sample.claim_expected:
                claim_correct += 1
        if sample.summary_acceptable and _summary_matches_input(summary, sample):
            acceptable_summaries += 1

    total = len(samples)
    return {
        "category_accuracy": {"correct": category_correct, "total": total},
        "severity_exact_agreement": {"correct": severity_exact, "total": total},
        "severity_within_one": {"correct": severity_within_one, "total": total},
        "claim_match_precision": {"correct": claim_correct, "total": claim_total},
        "summary_acceptability": {
            "acceptable": acceptable_summaries,
            "total": total,
        },
    }


def format_launch_readiness_report(metrics: dict[str, dict[str, int]]) -> str:
    lines = ["Launch readiness evaluation", ""]

    for metric_key in (
        "category_accuracy",
        "severity_exact_agreement",
        "severity_within_one",
        "claim_match_precision",
        "summary_acceptability",
    ):
        counts = metrics[metric_key]
        successful = _successful_count(metric_key, counts)
        total = counts["total"]
        percent = (successful / total * 100) if total else 0.0
        lines.append(
            f"{METRIC_LABELS[metric_key]}: {successful}/{total} ({percent:.1f}%)"
        )

    lines.extend(["", "Launch threshold status:"])

    for metric_key, threshold in THRESHOLDS.items():
        counts = metrics[metric_key]
        successful = _successful_count(metric_key, counts)
        total = counts["total"]
        rate = (successful / total) if total else 0.0
        status = "PASS" if rate >= threshold else "FAIL"
        lines.append(
            f"- {METRIC_LABELS[metric_key]}: {status} "
            f"(threshold {threshold * 100:.1f}%)"
        )

    return "\n".join(lines)


def run_launch_readiness_evaluation(
    path: Path = DEFAULT_GOLD_SAMPLE_PATH,
) -> tuple[dict[str, dict[str, int]], str]:
    samples = load_gold_samples(path)
    metrics = evaluate_gold_samples(samples)
    report = format_launch_readiness_report(metrics)
    return metrics, report


def _summary_matches_input(summary: str, sample: GoldSample) -> bool:
    expected_summary = summarize_incident(
        headline=sample.headline,
        source_summary=sample.source_summary,
    )
    return summary == expected_summary


def _seed_claims() -> list[ClaimRecord]:
    return [
        ClaimRecord(
            id="claim-support",
            claimant_name="AssistCo",
            company_involved="AssistCo",
            original_claim=(
                "Our assistant will eliminate repetitive support escalations."
            ),
            claim_date=date(2026, 1, 15),
            claim_topic="job automation",
            status="approved",
        ),
        ClaimRecord(
            id="claim-robotics",
            claimant_name="RoboFleet",
            company_involved="RoboFleet",
            original_claim=(
                "Our fleet will operate safely without sidewalk supervisors."
            ),
            claim_date=date(2026, 2, 20),
            claim_topic="autonomous operations",
            status="approved",
        ),
    ]


def _successful_count(metric_key: str, counts: dict[str, int]) -> int:
    if metric_key == "summary_acceptability":
        return counts["acceptable"]
    return counts["correct"]


def main() -> int:
    _, report = run_launch_readiness_evaluation()
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
