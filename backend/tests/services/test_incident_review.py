from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from types import SimpleNamespace

import httpx
import pytest

from app.core.incident_taxonomy import INCIDENT_CATEGORY_TAXONOMY
from app.services.incident_deduplication import DuplicateJudgeDecision
from app.services.incident_import import import_incidents_csv_text
from app.services.incident_review import (
    REVIEW_MAX_OUTPUT_TOKENS,
    AdaptiveReviewRateLimiter,
    AsyncOpenAIIncidentReviewClient,
    IncidentReviewResult,
    OpenAIIncidentReviewClient,
    ReviewResponseParseError,
    _build_review_messages,
    _build_review_response_format,
    _is_rate_limit_error,
    _parse_review_result,
    _review_incident_with_retries,
    reconcile_incident_review_batch,
    review_pending_incidents,
    submit_incident_review_batch,
)
from app.services.incident_translation import IncidentTranslation
from app.services.review_prompts import FORENSIC_MIN_WORD_COUNTS
from app.services.source_evidence import FetchedIncidentSource
from tests.support.fakes import InMemoryIncidentRepository
from tests.support.incident_csv_fixtures import VALID_IMPORT_CSV


def _wordy(prefix: str, *, count: int = 100) -> str:
    return " ".join(f"{prefix}{index}" for index in range(1, count + 1))


@dataclass
class FakeBatchSubmission:
    batch_id: str
    request_count: int
    model: str


class FakeSourceFetcher:
    def fetch(self, source_url: str) -> FetchedIncidentSource:
        return FetchedIncidentSource(
            source_url=source_url,
            canonical_url=f"{source_url}?canonical=1",
            fetch_status="fetched",
            http_status=200,
            evidence_text=f"Evidence for {source_url}",
        )


class FakeBatchReviewClient:
    def __init__(self) -> None:
        self.submissions: list[tuple[str, list[dict[str, object]]]] = []
        self.results_by_batch_id: dict[str, list[IncidentReviewResult]] = {}
        self.escalation_results: dict[str, IncidentReviewResult] = {}

    def submit_batch(
        self,
        *,
        incidents: list[dict[str, object]],
        model: str,
    ) -> FakeBatchSubmission:
        self.submissions.append((model, incidents))
        return FakeBatchSubmission(
            batch_id="batch-primary-1",
            request_count=len(incidents),
            model=model,
        )

    def get_batch_results(self, *, batch_id: str) -> list[IncidentReviewResult]:
        return self.results_by_batch_id[batch_id]

    def review_incident(
        self,
        *,
        incident: dict[str, object],
        model: str,
    ) -> IncidentReviewResult:
        return self.escalation_results[incident["id"]]


class FakeTranslationClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def translate(
        self,
        *,
        company_involved_en: str,
        headline_en: str,
        reality_summary_en: str,
        legitimacy_reasoning_en: str,
        source_validation_summary_en: str,
        incident_summary_en: str = "",
        what_happened_en: str = "",
        ai_failure_point_en: str = "",
        why_it_matters_en: str = "",
        evidence_summary_en: str = "",
    ) -> IncidentTranslation:
        self.calls.append(
            {
                "company_involved_en": company_involved_en,
                "headline_en": headline_en,
                "reality_summary_en": reality_summary_en,
                "legitimacy_reasoning_en": legitimacy_reasoning_en,
                "source_validation_summary_en": source_validation_summary_en,
                "incident_summary_en": incident_summary_en,
                "what_happened_en": what_happened_en,
                "ai_failure_point_en": ai_failure_point_en,
                "why_it_matters_en": why_it_matters_en,
                "evidence_summary_en": evidence_summary_en,
            }
        )
        return IncidentTranslation(
            company_involved_zh=f"ZH:{company_involved_en}",
            headline_zh=f"ZH:{headline_en}",
            reality_summary_zh=f"ZH:{reality_summary_en}",
            legitimacy_reasoning_zh=f"ZH:{legitimacy_reasoning_en}",
            source_validation_summary_zh=f"ZH:{source_validation_summary_en}",
            incident_summary_zh=f"ZH:{incident_summary_en}",
            what_happened_zh=f"ZH:{what_happened_en}",
            ai_failure_point_zh=f"ZH:{ai_failure_point_en}",
            why_it_matters_zh=f"ZH:{why_it_matters_en}",
            evidence_summary_zh=f"ZH:{evidence_summary_en}",
            status="completed",
        )


class FakeEmbeddingClient:
    def create_embedding(self, *, text: str, model: str) -> list[float]:
        if "OpenAI filing included fake legal citations" in text:
            return [1.0, 0.0]
        if "Federal court filing included fabricated citations" in text:
            return [0.99, 0.01]
        return [0.0, 1.0]


class FakeDuplicateJudgeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def judge_duplicate(
        self,
        *,
        incident: dict[str, object],
        candidate: dict[str, object],
        model: str,
    ) -> DuplicateJudgeDecision:
        self.calls.append((incident["id"], candidate["id"]))
        if candidate["id"] == "incident-canonical":
            return DuplicateJudgeDecision(
                is_duplicate=True,
                confidence=0.95,
                reasoning="Same underlying sanctions-related filing.",
                canonical_incident_id="incident-canonical",
            )
        return DuplicateJudgeDecision(
            is_duplicate=False,
            confidence=0.12,
            reasoning="Different real-world incident.",
            canonical_incident_id=None,
        )


class FakeAsyncReviewRetryClient:
    def __init__(self, responses: list[IncidentReviewResult | Exception]) -> None:
        self.responses = list(responses)
        self.calls = 0

    async def review_incident(
        self,
        *,
        incident: dict[str, object],
        model: str,
    ) -> IncidentReviewResult:
        del incident, model
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeRateLimitError(Exception):
    status_code = 429


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay


def _pending_review_result(*, incident_id: str = "incident-1") -> IncidentReviewResult:
    return IncidentReviewResult(
        incident_id=incident_id,
        verdict="pending_review",
        score=0.62,
        reasoning="Needs editor review.",
        source_quality_summary="Sources need review.",
        date_confirmed=True,
        company_confirmed=True,
        headline_en="Incident headline",
        reality_summary_en="Reporting describes the incident.",
        categories=["Hallucinations"],
        suggested_severity_score=None,
        severity_confidence=0.82,
        severity_reasoning="Needs review.",
        severity_flags=[],
        needs_escalation=False,
        reviewed_model="deepseek-test",
    )


def _official_fixed_source_incident() -> dict[str, object]:
    return {
        "id": "incident-official",
        "external_id": "official-fixed-source-1",
        "headline": "Court filing included AI-generated fake citations",
        "date_logged": "2026-05-01",
        "company_involved": "Example Firm",
        "claimant_name": None,
        "categories": ["Hallucinations"],
        "severity_score": 1,
        "reality_summary": "Court records document fabricated citations.",
        "status": "pending_llm_review",
        "translation_status": "not_requested",
        "publication_track": "verified_accident",
        "evidence_tier": "court_or_regulator",
        "source_family": "legal_hallucination",
        "verification_summary": "Court record from fixed source.",
        "sources": [
            {
                "id": "source-official",
                "source_url": "https://example.com/court-order.pdf",
                "source_type": "official",
                "publisher": "Court",
                "title": "Court order",
                "source_origin": "fixed_verified_source",
                "fetch_status": "fetched",
                "http_status": 200,
                "evidence_text": "Court order text confirming fabricated citations.",
            }
        ],
    }


def _strict_approved_result(
    *,
    incident_id: str = "incident-official",
    score: float = 0.98,
    severity: int | None = 1,
    severity_confidence: float | None = 0.96,
    severity_flags: list[str] | None = None,
    date_confirmed: bool = True,
    company_confirmed: bool = True,
    publication_track: str = "verified_accident",
    evidence_tier: str = "court_or_regulator",
) -> IncidentReviewResult:
    return IncidentReviewResult(
        incident_id=incident_id,
        verdict="approved",
        score=score,
        reasoning="Official court source confirms a low-risk AI citation incident.",
        source_quality_summary="Fixed court source includes fetched evidence text.",
        date_confirmed=date_confirmed,
        company_confirmed=company_confirmed,
        headline_en="Court filing included AI-generated fake citations",
        reality_summary_en="Court records document fabricated legal citations.",
        incident_summary_en="A court filing included fabricated citations.",
        what_happened_en="A filing relied on citations later found to be fabricated.",
        ai_failure_point_en=(
            "The drafting process failed to verify generated citations."
        ),
        why_it_matters_en="The court record documents a real but contained incident.",
        evidence_summary_en="The fixed court source confirms the issue.",
        categories=["Hallucinations"],
        suggested_severity_score=severity,
        severity_confidence=severity_confidence,
        severity_reasoning="Contained legal filing issue with clear source support.",
        severity_flags=severity_flags or [],
        publication_track=publication_track,
        evidence_tier=evidence_tier,
        source_family="legal_hallucination",
        verification_summary="Court record from fixed source.",
        needs_escalation=False,
        reviewed_model="deepseek-test",
    )


def test_adaptive_review_rate_limiter_does_not_sleep_before_successful_calls() -> None:
    clock = FakeClock()
    limiter = AdaptiveReviewRateLimiter(
        initial_rps=1,
        rps_step=1,
        max_rps=2,
        backoff_max_seconds=60,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    async def run() -> None:
        await limiter.wait_for_slot()
        await limiter.wait_for_slot()
        await limiter.wait_for_slot()
        await limiter.wait_for_slot()
        await limiter.record_success()

    asyncio.run(run())

    assert clock.sleeps == []
    assert limiter.snapshot()["rate_limit_events"] == 0


def test_adaptive_review_rate_limiter_uses_global_cooldown_after_429() -> None:
    clock = FakeClock()
    limiter = AdaptiveReviewRateLimiter(
        initial_rps=1,
        rps_step=1,
        max_rps=20,
        backoff_max_seconds=60,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    async def run() -> None:
        await limiter.wait_for_slot()
        await limiter.record_rate_limit()
        await limiter.wait_for_slot()
        await limiter.record_rate_limit()
        await limiter.wait_for_slot()
        await limiter.record_success()
        await limiter.record_rate_limit()
        await limiter.wait_for_slot()

    asyncio.run(run())

    assert clock.sleeps == [1.0, 2.0, 1.0]
    assert limiter.snapshot()["rate_limit_events"] == 3


def test_review_retries_rate_limits_with_adaptive_limiter() -> None:
    rate_limit_error = FakeRateLimitError("rate limited")
    result = _pending_review_result()
    client = FakeAsyncReviewRetryClient([rate_limit_error, result])
    clock = FakeClock()
    limiter = AdaptiveReviewRateLimiter(
        initial_rps=1,
        rps_step=1,
        max_rps=20,
        backoff_max_seconds=60,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    reviewed = asyncio.run(
        _review_incident_with_retries(
            client,
            incident={"id": "incident-1"},
            model="deepseek-test",
            max_attempts=3,
            rate_limiter=limiter,
        )
    )

    assert reviewed is result
    assert client.calls == 2
    assert limiter.snapshot()["rate_limit_events"] == 1
    assert clock.sleeps == [1.0]


def test_rate_limit_detection_accepts_status_code_and_response_status() -> None:
    assert _is_rate_limit_error(SimpleNamespace(status_code=429)) is True
    assert (
        _is_rate_limit_error(
            SimpleNamespace(response=SimpleNamespace(status_code=429))
        )
        is True
    )
    assert _is_rate_limit_error(SimpleNamespace(status_code=500)) is False


def test_parse_review_result_accepts_qualitative_severity_confidence() -> None:
    result = _parse_review_result(
        incident_id="incident-1",
        model="gpt-5.4-mini",
        content=(
            '{"verdict":"approved","score":0.94,"reasoning":"Strong evidence.",'
            '"source_quality_summary":"Two credible sources.",'
            '"date_confirmed":true,"company_confirmed":true,'
            '"headline_en":"Incident headline","reality_summary_en":"Summary.",'
            f'"incident_summary_en":"{_wordy("summary", count=40)}",'
            f'"what_happened_en":"{_wordy("happened")}",'
            f'"ai_failure_point_en":"{_wordy("failure")}",'
            f'"why_it_matters_en":"{_wordy("matters")}",'
            f'"evidence_summary_en":"{_wordy("evidence", count=40)}",'
            '"categories":["Hallucinations"],'
            '"suggested_severity_score":2,"severity_confidence":"low",'
            '"severity_reasoning":"Limited confidence.","severity_flags":[],'
            '"needs_escalation":false}'
        ),
    )

    assert result.categories == ["Hallucinations"]
    assert result.severity_confidence == 0.25
    assert result.needs_escalation is False


def test_build_review_response_format_uses_json_object_mode() -> None:
    response_format = _build_review_response_format()

    assert response_format == {"type": "json_object"}


def test_build_review_messages_include_json_guidance_example() -> None:
    messages = _build_review_messages(
        {
            "id": "incident-1",
            "external_id": "ext-1",
            "company_involved": "OpenAI",
            "incident_topic": "Hallucinations",
            "date_logged": "2026-05-01",
            "headline": "Headline",
            "reality_summary": "Summary",
            "sources": [],
        }
    )

    system_prompt = messages[0]["content"].lower()
    user_payload = json.loads(messages[1]["content"])

    assert "json" in system_prompt
    assert '"verdict"' in messages[0]["content"]
    assert '"incident_summary_en"' in messages[0]["content"]
    assert '"ai_failure_point_en"' in messages[0]["content"]
    assert (
        f"at least {FORENSIC_MIN_WORD_COUNTS['what_happened_en']} words"
        in system_prompt
    )
    assert '"needs_escalation"' in messages[0]["content"]
    assert user_payload["approved_categories"] == list(INCIDENT_CATEGORY_TAXONOMY)


def test_build_review_messages_distinguish_verified_and_watch_tracks() -> None:
    messages = _build_review_messages(
        {
            "id": "incident-1",
            "external_id": "ext-1",
            "company_involved": "OpenAI",
            "incident_topic": "Hallucinations",
            "date_logged": "2026-05-01",
            "headline": "Headline",
            "reality_summary": "Summary",
            "publication_track": "accident_watch",
            "evidence_tier": "reported_unconfirmed",
            "source_family": "legal_hallucination",
            "verification_summary": (
                "Reported by media; court record not linked yet."
            ),
            "sources": [
                {
                    "source_url": "https://example.com/story",
                    "canonical_url": None,
                    "fetch_status": "fetched",
                    "http_status": 200,
                    "evidence_text": "News report text.",
                    "source_origin": "search_discovery",
                    "source_registry_key": "google_search",
                }
            ],
        }
    )

    system_prompt = messages[0]["content"].lower()
    user_payload = json.loads(messages[1]["content"])

    assert "verified_accident" in system_prompt
    assert "accident_watch" in system_prompt
    assert "watch items must not be upgraded to verified" in system_prompt
    assert user_payload["publication_track"] == "accident_watch"
    assert user_payload["evidence_tier"] == "reported_unconfirmed"
    assert user_payload["source_family"] == "legal_hallucination"
    assert user_payload["verification_summary"] == (
        "Reported by media; court record not linked yet."
    )
    assert user_payload["sources"][0]["source_origin"] == "search_discovery"
    assert user_payload["sources"][0]["source_registry_key"] == "google_search"


def test_build_review_messages_caps_evidence_context_for_review() -> None:
    messages = _build_review_messages(
        {
            "id": "incident-1",
            "external_id": "ca-dmv-waymo-2026-04-12",
            "company_involved": "Waymo",
            "incident_topic": "autonomous_vehicle",
            "date_logged": "2026-04-12",
            "headline": "Waymo collision report",
            "reality_summary": "California DMV published a collision report.",
            "source_family": "autonomous_vehicle",
            "sources": [
                {
                    "source_url": "https://www.dmv.ca.gov/report.pdf",
                    "canonical_url": None,
                    "fetch_status": "fetched",
                    "http_status": 200,
                    "evidence_text": (
                        ("boilerplate " * 4000)
                        + "Structured autonomous vehicle facts: collision "
                        + "object: bicyclist; automation state: autonomous mode. "
                        + ("extra evidence " * 4000)
                    ),
                    "source_origin": "fixed_verified_source",
                    "source_registry_key": "ca_dmv_av_collisions",
                }
            ],
        }
    )

    user_payload = json.loads(messages[1]["content"])
    evidence_text = user_payload["sources"][0]["evidence_text"]

    assert len(evidence_text) <= 30_000
    assert "Structured autonomous vehicle facts" in evidence_text


def test_build_review_messages_warn_autonomous_reviews_against_generic_copy() -> None:
    messages = _build_review_messages(
        {
            "id": "incident-1",
            "external_id": "ca-dmv-waymo-2026-04-12",
            "company_involved": "Waymo",
            "incident_topic": "autonomous_vehicle",
            "date_logged": "2026-04-12",
            "headline": "Waymo collision report",
            "reality_summary": "California DMV published a collision report.",
            "source_family": "autonomous_vehicle",
            "sources": [
                {
                    "source_url": "https://www.dmv.ca.gov/report.pdf",
                    "canonical_url": None,
                    "fetch_status": "fetched",
                    "http_status": 200,
                    "evidence_text": (
                        "Structured autonomous vehicle facts: collision object: "
                        "bicyclist; location: Market Street near 5th Street"
                    ),
                    "source_origin": "fixed_verified_source",
                    "source_registry_key": "ca_dmv_av_collisions",
                }
            ],
        }
    )

    system_prompt = messages[0]["content"].lower()

    assert "autonomous vehicle incidents" in system_prompt
    assert "collision object" in system_prompt
    assert "human takeover" in system_prompt
    assert "do not write generic" in system_prompt


def test_parse_review_result_reads_structured_forensic_fields() -> None:
    result = _parse_review_result(
        incident_id="incident-1",
        model="gpt-5.4-mini",
        content=(
            '{"verdict":"approved","score":0.94,"reasoning":"Strong evidence.",'
            '"source_quality_summary":"Two credible sources.",'
            '"date_confirmed":true,"company_confirmed":true,'
            '"headline_en":"Incident headline","reality_summary_en":"Summary.",'
            f'"incident_summary_en":"{_wordy("summary", count=40)}",'
            f'"what_happened_en":"{_wordy("happened")}",'
            f'"ai_failure_point_en":"{_wordy("failure")}",'
            f'"why_it_matters_en":"{_wordy("matters")}",'
            f'"evidence_summary_en":"{_wordy("evidence", count=40)}",'
            '"categories":["Hallucinations"],'
            '"suggested_severity_score":2,"severity_confidence":0.92,'
            '"severity_reasoning":"High confidence.","severity_flags":[],'
            '"needs_escalation":false}'
        ),
    )

    assert result.incident_summary_en == _wordy("summary", count=40)
    assert result.what_happened_en == _wordy("happened")
    assert result.ai_failure_point_en == _wordy("failure")
    assert result.why_it_matters_en == _wordy("matters")
    assert result.evidence_summary_en == _wordy("evidence", count=40)


def test_parse_review_result_rejects_short_forensic_sections() -> None:
    min_words = FORENSIC_MIN_WORD_COUNTS["what_happened_en"]
    with pytest.raises(ReviewResponseParseError) as exc_info:
        _parse_review_result(
            incident_id="incident-1",
            model="gpt-5.4-mini",
            content=(
                '{"verdict":"approved","score":0.94,"reasoning":"Strong evidence.",'
                '"source_quality_summary":"Two credible sources.",'
                '"date_confirmed":true,"company_confirmed":true,'
                '"headline_en":"Incident headline","reality_summary_en":"Summary.",'
                f'"incident_summary_en":"{_wordy("summary", count=40)}",'
                f'"what_happened_en":"{_wordy("short", count=min_words - 1)}",'
                f'"ai_failure_point_en":"{_wordy("failure")}",'
                f'"why_it_matters_en":"{_wordy("matters")}",'
                f'"evidence_summary_en":"{_wordy("evidence", count=40)}",'
                '"categories":["Hallucinations"],'
                '"suggested_severity_score":2,"severity_confidence":0.92,'
                '"severity_reasoning":"High confidence.","severity_flags":[],'
                '"needs_escalation":false}'
            ),
        )

    assert "what_happened_en" in str(exc_info.value)
    assert f"{min_words} words" in str(exc_info.value)


def test_parse_review_result_marks_unknown_categories_for_escalation() -> None:
    result = _parse_review_result(
        incident_id="incident-1",
        model="gpt-5.4-mini",
        content=(
            '{"verdict":"approved","score":0.94,"reasoning":"Strong evidence.",'
            '"source_quality_summary":"Two credible sources.",'
            '"date_confirmed":true,"company_confirmed":true,'
            '"headline_en":"Incident headline","reality_summary_en":"Summary.",'
            f'"incident_summary_en":"{_wordy("summary", count=40)}",'
            f'"what_happened_en":"{_wordy("happened")}",'
            f'"ai_failure_point_en":"{_wordy("failure")}",'
            f'"why_it_matters_en":"{_wordy("matters")}",'
            f'"evidence_summary_en":"{_wordy("evidence", count=40)}",'
            '"categories":["Made Up Category"],'
            '"suggested_severity_score":2,"severity_confidence":0.92,'
            '"severity_reasoning":"High confidence.","severity_flags":[],'
            '"needs_escalation":false}'
        ),
    )

    assert result.categories is None
    assert result.needs_escalation is True


def test_parse_review_result_preserves_explicit_needs_escalation() -> None:
    result = _parse_review_result(
        incident_id="incident-1",
        model="gpt-5.4-mini",
        content=(
            '{"verdict":"pending_review","score":0.51,'
            '"reasoning":"Evidence remains weak.",'
            '"source_quality_summary":"Sources conflict.",'
            '"date_confirmed":false,"company_confirmed":true,'
            '"headline_en":"Incident headline","reality_summary_en":"Summary.",'
            f'"incident_summary_en":"{_wordy("summary", count=40)}",'
            f'"what_happened_en":"{_wordy("happened")}",'
            f'"ai_failure_point_en":"{_wordy("failure")}",'
            f'"why_it_matters_en":"{_wordy("matters")}",'
            f'"evidence_summary_en":"{_wordy("evidence", count=40)}",'
            '"categories":["Hallucinations"],'
            '"suggested_severity_score":3,"severity_confidence":0.61,'
            '"severity_reasoning":"Signals conflict.","severity_flags":[],'
            '"needs_escalation":true}'
        ),
    )

    assert result.needs_escalation is True


def test_autonomous_vehicle_review_with_generic_detail_stays_pending() -> None:
    repository = InMemoryIncidentRepository(
        incidents=[
            {
                "id": "incident-av",
                "external_id": "ca-dmv-waymo-2026-04-12",
                "headline": "Waymo collision report",
                "date_logged": "2026-04-12",
                "company_involved": "Waymo",
                "claimant_name": None,
                "categories": ["Autonomous Systems"],
                "severity_score": 2,
                "reality_summary": (
                    "California DMV published an autonomous vehicle collision "
                    "report for Waymo dated 2026-04-12."
                ),
                "status": "pending_llm_review",
                "translation_status": "not_requested",
                "publication_track": "verified_accident",
                "evidence_tier": "official_documented",
                "source_family": "autonomous_vehicle",
                "verification_summary": "Official DMV collision report.",
                "sources": [
                    {
                        "id": "source-av",
                        "source_url": "https://www.dmv.ca.gov/report.pdf",
                        "source_type": "official",
                        "publisher": "California DMV",
                        "title": "Waymo collision report",
                    }
                ],
            }
        ]
    )
    translation_client = FakeTranslationClient()
    generic_result = IncidentReviewResult(
        incident_id="incident-av",
        verdict="approved",
        score=0.95,
        reasoning="Official source supports the incident.",
        source_quality_summary="Official DMV report.",
        date_confirmed=True,
        company_confirmed=True,
        headline_en="Waymo collision report",
        reality_summary_en="California DMV published a collision report.",
        incident_summary_en="California DMV published a collision report.",
        what_happened_en="California DMV published a collision report.",
        ai_failure_point_en="An autonomous vehicle system failed.",
        why_it_matters_en="This shows autonomous vehicle risk.",
        evidence_summary_en="Official DMV report.",
        categories=["Autonomous Systems"],
        suggested_severity_score=2,
        severity_confidence=0.9,
        severity_reasoning="No major harm described.",
        severity_flags=[],
        needs_escalation=False,
        reviewed_model="deepseek-test",
    )

    summary = asyncio.run(
        review_pending_incidents(
            repository,
            source_fetcher=FakeSourceFetcher(),
            review_client=FakeAsyncReviewRetryClient([generic_result]),
            escalation_client=FakeBatchReviewClient(),
            translation_client=translation_client,
            embedding_client=FakeEmbeddingClient(),
            duplicate_judge_client=FakeDuplicateJudgeClient(),
            primary_model="deepseek-test",
            escalation_model="deepseek-pro-test",
            embedding_model="embedding-test",
            duplicate_judge_model="duplicate-test",
        )
    )

    assert summary.approved == 0
    assert summary.pending_review == 1
    assert translation_client.calls == []
    assert repository.incidents["incident-av"]["status"] == "pending_review"


def test_review_auto_approves_high_confidence_fixed_source_incident() -> None:
    incident = _official_fixed_source_incident()
    incident["sources"][0]["fetch_status"] = None  # type: ignore[index]
    incident["sources"][0]["http_status"] = None  # type: ignore[index]
    incident["sources"][0]["evidence_text"] = None  # type: ignore[index]
    repository = InMemoryIncidentRepository(incidents=[incident])
    translation_client = FakeTranslationClient()

    summary = asyncio.run(
        review_pending_incidents(
            repository,
            source_fetcher=FakeSourceFetcher(),
            review_client=FakeAsyncReviewRetryClient([_strict_approved_result()]),
            escalation_client=FakeBatchReviewClient(),
            translation_client=translation_client,
            embedding_client=FakeEmbeddingClient(),
            duplicate_judge_client=FakeDuplicateJudgeClient(),
            primary_model="deepseek-test",
            escalation_model="deepseek-pro-test",
            embedding_model="embedding-test",
            duplicate_judge_model="duplicate-test",
        )
    )

    incident = repository.incidents["incident-official"]
    assert summary.approved == 1
    assert summary.pending_review == 0
    assert incident["status"] == "approved"
    assert incident["severity_score"] == 1
    assert incident["severity_decision_source"] == "primary_llm"
    assert incident["translation_status"] == "completed"
    assert translation_client.calls


def test_review_auto_approves_high_confidence_higher_severity_incident() -> None:
    repository = InMemoryIncidentRepository(
        incidents=[_official_fixed_source_incident()]
    )
    translation_client = FakeTranslationClient()

    summary = asyncio.run(
        review_pending_incidents(
            repository,
            source_fetcher=FakeSourceFetcher(),
            review_client=FakeAsyncReviewRetryClient(
                [
                    _strict_approved_result(
                        severity=4,
                        severity_confidence=0.85,
                        severity_flags=["legal_or_regulatory"],
                    )
                ]
            ),
            escalation_client=FakeBatchReviewClient(),
            translation_client=translation_client,
            embedding_client=FakeEmbeddingClient(),
            duplicate_judge_client=FakeDuplicateJudgeClient(),
            primary_model="deepseek-test",
            escalation_model="deepseek-pro-test",
            embedding_model="embedding-test",
            duplicate_judge_model="duplicate-test",
        )
    )

    incident = repository.incidents["incident-official"]
    assert summary.approved == 1
    assert summary.pending_review == 0
    assert incident["status"] == "approved"
    assert incident["severity_score"] == 4
    assert translation_client.calls


@pytest.mark.parametrize(
    ("result", "source_overrides"),
    [
        (_strict_approved_result(score=0.94), {}),
        (_strict_approved_result(severity=None), {}),
        (_strict_approved_result(severity_confidence=0.84), {}),
        (_strict_approved_result(date_confirmed=False), {}),
        (_strict_approved_result(company_confirmed=False), {}),
        (_strict_approved_result(evidence_tier="reported_unconfirmed"), {}),
        (
            _strict_approved_result(),
            {"source_origin": "search_discovery"},
        ),
    ],
)
def test_review_routes_uncertain_candidates_to_pending_review(
    result: IncidentReviewResult,
    source_overrides: dict[str, object],
) -> None:
    incident = _official_fixed_source_incident()
    incident["sources"][0].update(source_overrides)  # type: ignore[index, union-attr]
    repository = InMemoryIncidentRepository(incidents=[incident])
    translation_client = FakeTranslationClient()

    summary = asyncio.run(
        review_pending_incidents(
            repository,
            source_fetcher=FakeSourceFetcher(),
            review_client=FakeAsyncReviewRetryClient([result]),
            escalation_client=FakeBatchReviewClient(),
            translation_client=translation_client,
            embedding_client=FakeEmbeddingClient(),
            duplicate_judge_client=FakeDuplicateJudgeClient(),
            primary_model="deepseek-test",
            escalation_model="deepseek-pro-test",
            embedding_model="embedding-test",
            duplicate_judge_model="duplicate-test",
        )
    )

    assert summary.approved == 0
    assert summary.pending_review == 1
    assert repository.incidents["incident-official"]["status"] == (
        "pending_review"
    )
    assert translation_client.calls == []


def test_review_requires_fetched_fixed_source_evidence_to_auto_approve() -> None:
    class FailingSourceFetcher:
        def fetch(self, source_url: str) -> FetchedIncidentSource:
            return FetchedIncidentSource(
                source_url=source_url,
                canonical_url=source_url,
                fetch_status="failed",
                http_status=403,
                evidence_text=None,
                fetch_error="Forbidden",
            )

    incident = _official_fixed_source_incident()
    incident["sources"][0]["fetch_status"] = None  # type: ignore[index]
    incident["sources"][0]["http_status"] = None  # type: ignore[index]
    incident["sources"][0]["evidence_text"] = None  # type: ignore[index]
    repository = InMemoryIncidentRepository(incidents=[incident])
    translation_client = FakeTranslationClient()

    summary = asyncio.run(
        review_pending_incidents(
            repository,
            source_fetcher=FailingSourceFetcher(),
            review_client=FakeAsyncReviewRetryClient([_strict_approved_result()]),
            escalation_client=FakeBatchReviewClient(),
            translation_client=translation_client,
            embedding_client=FakeEmbeddingClient(),
            duplicate_judge_client=FakeDuplicateJudgeClient(),
            primary_model="deepseek-test",
            escalation_model="deepseek-pro-test",
            embedding_model="embedding-test",
            duplicate_judge_model="duplicate-test",
        )
    )

    assert summary.approved == 0
    assert summary.pending_review == 1
    assert repository.incidents["incident-official"]["status"] == (
        "pending_review"
    )
    assert translation_client.calls == []


def test_review_auto_approve_uses_legitimacy_floor_when_threshold_is_lower() -> None:
    repository = InMemoryIncidentRepository(
        incidents=[_official_fixed_source_incident()]
    )
    translation_client = FakeTranslationClient()

    summary = asyncio.run(
        review_pending_incidents(
            repository,
            source_fetcher=FakeSourceFetcher(),
            review_client=FakeAsyncReviewRetryClient(
                [_strict_approved_result(score=0.96)]
            ),
            escalation_client=FakeBatchReviewClient(),
            translation_client=translation_client,
            embedding_client=FakeEmbeddingClient(),
            duplicate_judge_client=FakeDuplicateJudgeClient(),
            primary_model="deepseek-test",
            escalation_model="deepseek-pro-test",
            embedding_model="embedding-test",
            duplicate_judge_model="duplicate-test",
            approval_threshold=0.90,
        )
    )

    assert summary.approved == 1
    assert summary.pending_review == 0
    assert repository.incidents["incident-official"]["status"] == "approved"
    assert translation_client.calls


def test_sync_review_client_retries_malformed_json_and_uses_higher_max_tokens(
    monkeypatch,
) -> None:
    client = OpenAIIncidentReviewClient(
        api_key="test-key",
        base_url="https://api.deepseek.com/v1",
    )
    calls: list[dict[str, object]] = []
    contents = [
        "",
        '{"verdict":"approved","score":0.96,"reasoning":"Strong evidence.',
        (
            '{"verdict":"approved","score":0.96,"reasoning":"Strong evidence.",'
            '"source_quality_summary":"Multiple sources agree.",'
            '"date_confirmed":true,"company_confirmed":true,'
            '"headline_en":"Incident headline","reality_summary_en":"Summary.",'
            f'"incident_summary_en":"{_wordy("summary", count=40)}",'
            f'"what_happened_en":"{_wordy("happened")}",'
            f'"ai_failure_point_en":"{_wordy("failure")}",'
            f'"why_it_matters_en":"{_wordy("matters")}",'
            f'"evidence_summary_en":"{_wordy("evidence", count=40)}",'
            '"categories":["Hallucinations"],'
            '"suggested_severity_score":2,"severity_confidence":0.91,'
            '"severity_reasoning":"Confirmed by multiple sources.",'
            '"severity_flags":[],"needs_escalation":false}'
        ),
    ]

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> httpx.Response:
        del headers, timeout
        calls.append({"url": url, "payload": json})
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={
                "model": "deepseek-v4-pro",
                "choices": [{"message": {"content": contents[len(calls) - 1]}}],
            },
        )

    monkeypatch.setattr("app.services.incident_review.httpx.post", fake_post)

    result = client.review_incident(
        incident={
            "id": "incident-1",
            "external_id": "ext-1",
            "company_involved": "OpenAI",
            "incident_topic": "Hallucinations",
            "date_logged": "2026-05-01",
            "headline": "Headline",
            "reality_summary": "Summary",
            "sources": [],
        },
        model="deepseek-v4-pro",
    )

    assert result.reviewed_model == "deepseek-v4-pro"
    assert result.verdict == "approved"
    assert len(calls) == 3
    assert all(
        call["payload"]["max_tokens"] == REVIEW_MAX_OUTPUT_TOKENS  # type: ignore[index]
        for call in calls
    )


def test_async_review_client_retries_malformed_json_and_uses_higher_max_tokens(
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []
    contents = [
        "",
        '{"verdict":"approved","score":0.96,"reasoning":"Strong evidence.',
        (
            '{"verdict":"approved","score":0.96,"reasoning":"Strong evidence.",'
            '"source_quality_summary":"Multiple sources agree.",'
            '"date_confirmed":true,"company_confirmed":true,'
            '"headline_en":"Incident headline","reality_summary_en":"Summary.",'
            f'"incident_summary_en":"{_wordy("summary", count=40)}",'
            f'"what_happened_en":"{_wordy("happened")}",'
            f'"ai_failure_point_en":"{_wordy("failure")}",'
            f'"why_it_matters_en":"{_wordy("matters")}",'
            f'"evidence_summary_en":"{_wordy("evidence", count=40)}",'
            '"categories":["Hallucinations"],'
            '"suggested_severity_score":2,"severity_confidence":0.91,'
            '"severity_reasoning":"Confirmed by multiple sources.",'
            '"severity_flags":[],"needs_escalation":false}'
        ),
    ]

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs: object) -> None:
            del kwargs
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self.create)
            )

        async def create(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            return SimpleNamespace(
                model="deepseek-v4-flash",
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=contents[len(calls) - 1])
                    )
                ],
            )

    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI),
    )
    client = AsyncOpenAIIncidentReviewClient(
        api_key="test-key",
        base_url="https://api.deepseek.com/v1",
    )

    result = asyncio.run(
        client.review_incident(
            incident={
                "id": "incident-1",
                "external_id": "ext-1",
                "company_involved": "OpenAI",
                "incident_topic": "Hallucinations",
                "date_logged": "2026-05-01",
                "headline": "Headline",
                "reality_summary": "Summary",
                "sources": [],
            },
            model="deepseek-v4-flash",
        )
    )

    assert result.reviewed_model == "deepseek-v4-flash"
    assert result.verdict == "approved"
    assert len(calls) == 3
    assert all(call["max_tokens"] == REVIEW_MAX_OUTPUT_TOKENS for call in calls)


def test_submit_batch_uses_higher_max_tokens_in_jsonl_payload(monkeypatch) -> None:
    client = OpenAIIncidentReviewClient(
        api_key="test-key",
        base_url="https://api.deepseek.com/v1",
    )
    captured: dict[str, str] = {}

    def fake_upload_batch_file(jsonl_body: str) -> str:
        captured["jsonl_body"] = jsonl_body
        return "file-123"

    def fake_post_json(path: str, payload: dict[str, object]) -> dict[str, str]:
        assert path == "/batches"
        assert payload["input_file_id"] == "file-123"
        return {"id": "batch-123"}

    monkeypatch.setattr(client, "_upload_batch_file", fake_upload_batch_file)
    monkeypatch.setattr(client, "_post_json", fake_post_json)

    submission = client.submit_batch(
        incidents=[
            {
                "id": "incident-1",
                "external_id": "ext-1",
                "company_involved": "OpenAI",
                "incident_topic": "Hallucinations",
                "date_logged": "2026-05-01",
                "headline": "Headline",
                "reality_summary": "Summary",
                "sources": [],
            }
        ],
        model="deepseek-v4-flash",
    )

    request_body = json.loads(captured["jsonl_body"].splitlines()[0])

    assert submission.batch_id == "batch-123"
    assert request_body["body"]["max_tokens"] == REVIEW_MAX_OUTPUT_TOKENS


def test_submit_incident_review_batch_fetches_source_evidence_and_marks_batch() -> None:
    repository = InMemoryIncidentRepository()
    import_incidents_csv_text(repository, VALID_IMPORT_CSV, dry_run=False)
    batch_client = FakeBatchReviewClient()

    summary = submit_incident_review_batch(
        repository,
        source_fetcher=FakeSourceFetcher(),
        batch_client=batch_client,
        primary_model="gpt-5.4-mini",
    )

    assert summary.batch_id == "batch-primary-1"
    assert summary.submitted == 2
    assert batch_client.submissions[0][0] == "gpt-5.4-mini"

    first_incident = next(iter(repository.incidents.values()))
    assert first_incident["review_batch_id"] == "batch-primary-1"
    assert first_incident["review_model"] == "gpt-5.4-mini"
    assert first_incident["sources"][0]["fetch_status"] == "fetched"
    assert first_incident["sources"][0]["canonical_url"].endswith("?canonical=1")
    assert first_incident["sources"][0]["evidence_text"].startswith("Evidence for ")


def test_reconcile_incident_review_batch_routes_non_fixed_results_to_review() -> None:
    repository = InMemoryIncidentRepository()
    import_incidents_csv_text(repository, VALID_IMPORT_CSV, dry_run=False)
    batch_client = FakeBatchReviewClient()
    submit_incident_review_batch(
        repository,
        source_fetcher=FakeSourceFetcher(),
        batch_client=batch_client,
        primary_model="gpt-5.4-mini",
    )

    incidents_by_external_id = {
        incident["external_id"]: incident for incident in repository.incidents.values()
    }
    batch_client.results_by_batch_id["batch-primary-1"] = [
        IncidentReviewResult(
            incident_id=incidents_by_external_id["inc-openai-001"]["id"],
            verdict="approved",
            score=0.96,
            reasoning="Primary review found strong source support.",
            source_quality_summary="3 fetched sources agree on the event.",
            date_confirmed=True,
            company_confirmed=True,
            headline_en="OpenAI filing included fake legal citations",
            reality_summary_en=(
                "Court records and reporting confirm the filing incident."
            ),
            incident_summary_en=(
                "A court filing incident exposed fabricated legal citations."
            ),
            what_happened_en=(
                "Court submissions and coverage show that fabricated citations "
                "were included in a federal filing."
            ),
            ai_failure_point_en=(
                "The drafting workflow failed to verify cited cases before "
                "including them in the filing."
            ),
            why_it_matters_en=(
                "The incident affected a real legal proceeding and required "
                "human correction."
            ),
            evidence_summary_en=(
                "Court records and multiple reports confirm the error."
            ),
            categories=["Hallucinations"],
            suggested_severity_score=2,
            severity_confidence=0.92,
            severity_reasoning=(
                "Legal filing incident with reputational impact but no evidence "
                "of broader downstream harm."
            ),
            severity_flags=[],
            needs_escalation=False,
            reviewed_model="gpt-5.4-mini",
        ),
        IncidentReviewResult(
            incident_id=incidents_by_external_id["inc-school-002"]["id"],
            verdict="approved",
            score=0.94,
            reasoning="Primary review found strong source support.",
            source_quality_summary="Multiple sources agree on the incident details.",
            date_confirmed=True,
            company_confirmed=True,
            headline_en="School chatbot gave inaccurate enrollment guidance",
            reality_summary_en=(
                "School staff had to intervene after students received "
                "inaccurate enrollment guidance."
            ),
            categories=["Autonomous Systems", "Missed Timelines"],
            suggested_severity_score=3,
            severity_confidence=0.89,
            severity_reasoning=(
                "The incident caused operational disruption that required "
                "staff intervention."
            ),
            severity_flags=[],
            needs_escalation=False,
            reviewed_model="gpt-5.4-mini",
        ),
    ]
    translation_client = FakeTranslationClient()

    summary = reconcile_incident_review_batch(
        repository,
        batch_id="batch-primary-1",
        batch_client=batch_client,
        escalation_client=batch_client,
        translation_client=translation_client,
        embedding_client=FakeEmbeddingClient(),
        duplicate_judge_client=FakeDuplicateJudgeClient(),
        embedding_model="text-embedding-3-small",
        duplicate_judge_model="gpt-5.2",
        escalation_model="gpt-5.2",
    )

    assert summary.approved == 0
    assert summary.pending_review == 2
    assert summary.rejected == 0
    assert summary.escalated == 0

    approved_incident = incidents_by_external_id["inc-openai-001"]
    queued_incident = incidents_by_external_id["inc-school-002"]

    assert approved_incident["status"] == "pending_review"
    assert approved_incident["translation_status"] == "not_requested"
    assert approved_incident.get("company_involved_zh") is None
    assert approved_incident.get("headline_zh") is None
    assert approved_incident["incident_summary_en"] == (
        "A court filing incident exposed fabricated legal citations."
    )
    assert approved_incident["ai_failure_point_en"] == (
        "The drafting workflow failed to verify cited cases before including "
        "them in the filing."
    )
    assert approved_incident.get("incident_summary_zh") is None
    assert approved_incident.get("ai_failure_point_zh") is None
    assert approved_incident.get("legitimacy_reasoning_zh") is None
    assert approved_incident.get("source_validation_summary_zh") is None
    assert approved_incident["legitimacy_score"] == 0.96
    assert approved_incident["review_model"] == "gpt-5.4-mini"
    assert approved_incident["categories"] == ["Hallucinations"]
    assert approved_incident["severity_score"] == 3
    assert approved_incident["suggested_severity_score"] == 2
    assert approved_incident["severity_decision_source"] is None

    assert queued_incident["status"] == "pending_review"
    assert queued_incident["categories"] == [
        "Autonomous Systems",
        "Missed Timelines",
    ]
    assert queued_incident["translation_status"] == "not_requested"
    assert queued_incident["legitimacy_score"] == 0.94
    assert queued_incident["review_model"] == "gpt-5.4-mini"
    assert queued_incident["suggested_severity_score"] == 3
    assert queued_incident["severity_confidence"] == 0.89
    assert queued_incident["severity_decision_source"] is None
    assert translation_client.calls == []


def test_reconcile_incident_review_batch_skips_second_phase_for_low_confidence_rows(  # noqa: E501
) -> None:
    repository = InMemoryIncidentRepository()
    import_incidents_csv_text(repository, VALID_IMPORT_CSV, dry_run=False)
    batch_client = FakeBatchReviewClient()
    submit_incident_review_batch(
        repository,
        source_fetcher=FakeSourceFetcher(),
        batch_client=batch_client,
        primary_model="gpt-5.4-mini",
    )

    incidents_by_external_id = {
        incident["external_id"]: incident for incident in repository.incidents.values()
    }
    target_incident = incidents_by_external_id["inc-school-002"]
    batch_client.results_by_batch_id["batch-primary-1"] = [
        IncidentReviewResult(
            incident_id=target_incident["id"],
            verdict="approved",
            score=0.91,
            reasoning=(
                "Primary review found decent support but could not resolve the "
                "downstream impact level."
            ),
            source_quality_summary=(
                "Reporting confirms the incident but the scope of harm remains "
                "fuzzy."
            ),
            date_confirmed=True,
            company_confirmed=True,
            headline_en="School chatbot gave inaccurate enrollment guidance",
            reality_summary_en=(
                "Students received inaccurate enrollment guidance and staff had "
                "to correct the information manually."
            ),
        categories=["Autonomous Systems", "Missed Timelines"],
            suggested_severity_score=3,
            severity_confidence=0.61,
            severity_reasoning=(
                "There was real operational impact, but source evidence does "
                "not clearly bound the scope."
            ),
            severity_flags=["unclear_real_world_impact"],
            needs_escalation=False,
            reviewed_model="gpt-5.4-mini",
        ),
    ]
    batch_client.escalation_results[target_incident["id"]] = IncidentReviewResult(
        incident_id=target_incident["id"],
        verdict="approved",
        score=0.95,
        reasoning=(
            "Escalation confirmed the incident and agreed that it requires "
            "editor review due to severity."
        ),
        source_quality_summary=(
            "Escalation confirmed the incident and clarified the source chronology."
        ),
        date_confirmed=True,
        company_confirmed=True,
        headline_en="School chatbot gave inaccurate enrollment guidance",
        reality_summary_en=(
            "Escalation confirmed the incident and the need for staff correction."
        ),
        incident_summary_en=(
            "Students received incorrect enrollment guidance that required "
            "staff intervention."
        ),
        what_happened_en=(
            "The chatbot gave students inaccurate guidance and staff had to "
            "step in to correct it."
        ),
        ai_failure_point_en=(
            "The assistant failed to ground enrollment advice in current school "
            "policy."
        ),
        why_it_matters_en=(
            "Students depended on the answer for enrollment decisions and staff "
            "had to recover manually."
        ),
        evidence_summary_en=(
            "District reporting and local coverage align on the incident."
        ),
        categories=["Autonomous Systems", "Missed Timelines"],
        suggested_severity_score=3,
        severity_confidence=0.84,
        severity_reasoning=(
            "The incident caused meaningful operational harm requiring "
            "intervention, but not the kind of irreversible harm that merits "
            "Severity 4."
        ),
        severity_flags=[],
        needs_escalation=False,
        reviewed_model="gpt-5.2",
    )

    summary = reconcile_incident_review_batch(
        repository,
        batch_id="batch-primary-1",
        batch_client=batch_client,
        escalation_client=batch_client,
        translation_client=FakeTranslationClient(),
        embedding_client=FakeEmbeddingClient(),
        duplicate_judge_client=FakeDuplicateJudgeClient(),
        embedding_model="text-embedding-3-small",
        duplicate_judge_model="gpt-5.2",
        escalation_model="gpt-5.2",
    )

    assert summary.approved == 0
    assert summary.pending_review == 1
    assert summary.rejected == 0
    assert summary.escalated == 0
    assert target_incident["status"] == "pending_review"
    assert target_incident["categories"] == [
        "Autonomous Systems",
        "Missed Timelines",
    ]
    assert target_incident["incident_summary_en"] is None
    assert target_incident["ai_failure_point_en"] is None
    assert target_incident["review_model"] == "gpt-5.4-mini"
    assert target_incident["suggested_severity_score"] == 3
    assert target_incident["severity_decision_source"] is None


def test_reconcile_incident_review_batch_routes_uncertain_rows_without_second_phase(  # noqa: E501
) -> None:
    repository = InMemoryIncidentRepository()
    import_incidents_csv_text(repository, VALID_IMPORT_CSV, dry_run=False)
    batch_client = FakeBatchReviewClient()
    submit_incident_review_batch(
        repository,
        source_fetcher=FakeSourceFetcher(),
        batch_client=batch_client,
        primary_model="gpt-5.4-mini",
    )

    incidents_by_external_id = {
        incident["external_id"]: incident for incident in repository.incidents.values()
    }
    target_incident = incidents_by_external_id["inc-school-002"]
    batch_client.results_by_batch_id["batch-primary-1"] = [
        IncidentReviewResult(
            incident_id=incidents_by_external_id["inc-openai-001"]["id"],
            verdict="rejected",
            score=0.1,
            reasoning="Not substantiated.",
            source_quality_summary="Weak evidence.",
            date_confirmed=True,
            company_confirmed=True,
            headline_en="Rejected",
            reality_summary_en="Rejected",
            categories=["Hallucinations"],
            suggested_severity_score=None,
            severity_confidence=None,
            severity_reasoning="Rejected",
            severity_flags=[],
            needs_escalation=False,
            reviewed_model="gpt-5.4-mini",
        ),
        IncidentReviewResult(
            incident_id=target_incident["id"],
            verdict="pending_review",
            score=0.58,
            reasoning="Primary review remains uncertain.",
            source_quality_summary="Conflicting source details.",
            date_confirmed=False,
            company_confirmed=True,
            headline_en="School chatbot gave inaccurate enrollment guidance",
            reality_summary_en="Primary review found unresolved ambiguity.",
            categories=["Autonomous Systems"],
            suggested_severity_score=3,
            severity_confidence=0.61,
            severity_reasoning="Evidence conflicts.",
            severity_flags=[],
            needs_escalation=True,
            reviewed_model="gpt-5.4-mini",
        ),
    ]
    batch_client.escalation_results[target_incident["id"]] = IncidentReviewResult(
        incident_id=target_incident["id"],
        verdict="pending_review",
        score=0.69,
        reasoning="Escalation still cannot resolve the ambiguity.",
        source_quality_summary="Escalation found the event plausible but unresolved.",
        date_confirmed=False,
        company_confirmed=True,
        headline_en="School chatbot gave inaccurate enrollment guidance",
        reality_summary_en="Escalation still requires an editor to decide.",
        categories=["Autonomous Systems"],
        suggested_severity_score=3,
        severity_confidence=0.73,
        severity_reasoning="Human review still required.",
        severity_flags=[],
        needs_escalation=True,
        reviewed_model="gpt-5.2",
    )

    summary = reconcile_incident_review_batch(
        repository,
        batch_id="batch-primary-1",
        batch_client=batch_client,
        escalation_client=batch_client,
        translation_client=FakeTranslationClient(),
        embedding_client=FakeEmbeddingClient(),
        duplicate_judge_client=FakeDuplicateJudgeClient(),
        embedding_model="text-embedding-3-small",
        duplicate_judge_model="gpt-5.2",
        escalation_model="gpt-5.2",
    )

    assert summary.approved == 0
    assert summary.pending_review == 1
    assert summary.rejected == 1
    assert summary.escalated == 0
    assert incidents_by_external_id["inc-openai-001"]["status"] == (
        "rejected"
    )
    assert target_incident["status"] == "pending_review"
    assert target_incident["review_model"] == "gpt-5.4-mini"
    assert target_incident["translation_status"] == "not_requested"


def test_reconcile_incident_review_batch_hides_confirmed_duplicates_and_skips_translation(  # noqa: E501
) -> None:
    repository = InMemoryIncidentRepository(
        incidents=[
            {
                "id": "incident-canonical",
                "external_id": "inc-existing-001",
                "headline": "Federal court filing included fabricated citations",
                "headline_en": "Federal court filing included fabricated citations",
                "headline_zh": None,
                "date_logged": "2023-05-03",
                "company_involved": "OpenAI",
                "incident_topic": "legal hallucination",
                "claimant_name": None,
                "categories": [],
                "severity_score": 3,
                "reality_summary": "Existing canonical incident.",
                "reality_summary_en": "Existing canonical incident.",
                "reality_summary_zh": None,
                "status": "approved",
                "review_notes": None,
                "matched_claim_id": None,
                "claim_match_confidence": None,
                "legitimacy_score": 0.94,
                "legitimacy_label": "approved",
                "legitimacy_reasoning": "Already approved.",
                "source_validation_summary": "Validated 3 distinct sources.",
                "legitimacy_flag": "ACCEPT",
                "confidence_level": "high",
                "import_notes": "Canonical note.",
                "translation_status": "completed",
                "review_batch_id": "historic-batch",
                "review_model": "gpt-5.4-mini",
                "reviewed_at": None,
                "translated_at": None,
                "duplicate_status": None,
                "duplicate_of_incident_id": None,
                "canonical_incident_id": None,
                "embedding_model": None,
                "embedding_vector": None,
                "duplicate_candidates": [],
                "sources": [
                    {
                        "id": "canonical-source-1",
                        "source_url": "https://example.com/canonical-source",
                        "canonical_url": None,
                        "source_type": "imported",
                        "publisher": None,
                        "title": None,
                        "fetch_status": None,
                        "http_status": None,
                        "evidence_text": None,
                        "fetch_error": None,
                        "is_primary": True,
                    }
                ],
            }
        ]
    )
    import_incidents_csv_text(repository, VALID_IMPORT_CSV, dry_run=False)
    batch_client = FakeBatchReviewClient()
    submit_incident_review_batch(
        repository,
        source_fetcher=FakeSourceFetcher(),
        batch_client=batch_client,
        primary_model="gpt-5.4-mini",
    )
    imported_incident = next(
        incident
        for incident in repository.incidents.values()
        if incident.get("external_id") == "inc-openai-001"
    )
    second_incident = next(
        incident
        for incident in repository.incidents.values()
        if incident.get("external_id") == "inc-school-002"
    )
    batch_client.results_by_batch_id["batch-primary-1"] = [
        IncidentReviewResult(
            incident_id=imported_incident["id"],
            verdict="approved",
            score=0.96,
            reasoning="Primary review found strong source support.",
            source_quality_summary="3 fetched sources agree on the event.",
            date_confirmed=True,
            company_confirmed=True,
            headline_en="OpenAI filing included fake legal citations",
            reality_summary_en=(
                "Court records and reporting confirm the filing incident."
            ),
            needs_escalation=False,
            reviewed_model="gpt-5.4-mini",
        ),
        IncidentReviewResult(
            incident_id=second_incident["id"],
            verdict="pending_review",
            score=0.62,
            reasoning="Primary review found unresolved source ambiguity.",
            source_quality_summary="One source is weak and requires closer review.",
            date_confirmed=False,
            company_confirmed=True,
            headline_en="School chatbot gave inaccurate enrollment guidance",
            reality_summary_en=(
                "Local reporting suggests the issue happened but details conflict."
            ),
            needs_escalation=True,
            reviewed_model="gpt-5.4-mini",
        ),
    ]
    batch_client.escalation_results[second_incident["id"]] = IncidentReviewResult(
        incident_id=second_incident["id"],
        verdict="pending_review",
        score=0.74,
        reasoning="Escalation review agrees the row should wait for editor approval.",
        source_quality_summary=(
            "Escalation confirmed the event but found date ambiguity."
        ),
        date_confirmed=False,
        company_confirmed=True,
        headline_en="School chatbot gave inaccurate enrollment guidance",
        reality_summary_en=(
            "Escalation confirmed the incident but left date ambiguity unresolved."
        ),
        needs_escalation=False,
        reviewed_model="gpt-5.2",
    )
    translation_client = FakeTranslationClient()

    summary = reconcile_incident_review_batch(
        repository,
        batch_id="batch-primary-1",
        batch_client=batch_client,
        escalation_client=batch_client,
        translation_client=translation_client,
        escalation_model="gpt-5.2",
        embedding_client=FakeEmbeddingClient(),
        duplicate_judge_client=FakeDuplicateJudgeClient(),
        embedding_model="text-embedding-3-small",
        duplicate_judge_model="gpt-5.2",
    )

    assert summary.approved == 0
    assert summary.pending_review == 2
    assert summary.rejected == 0
    assert imported_incident["status"] == "pending_review"
    assert imported_incident["duplicate_of_incident_id"] is None
    assert imported_incident["translation_status"] == "not_requested"
    assert len(repository.incidents["incident-canonical"]["sources"]) == 1
    assert translation_client.calls == []
