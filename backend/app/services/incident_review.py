from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable, Protocol

import httpx

from app.db.repository_protocol import IncidentRepository
from app.services import review_prompts
from app.services.autonomous_vehicle_details import (
    assess_autonomous_vehicle_detail_quality,
)
from app.services.incident_deduplication import (
    IncidentDuplicateJudgeClient,
    IncidentEmbeddingClient,
    detect_and_merge_duplicate_incident,
)
from app.services.incident_translation import (
    IncidentTranslationClient,
    translate_incident_copy,
)
from app.services.source_evidence import (
    IncidentSourceFetcher,
    refresh_source_evidence,
)

ReviewResponseParseError = review_prompts.ReviewResponseParseError
REVIEW_MAX_OUTPUT_TOKENS = review_prompts.REVIEW_MAX_OUTPUT_TOKENS
REVIEW_RESPONSE_PARSE_MAX_ATTEMPTS = (
    review_prompts.REVIEW_RESPONSE_PARSE_MAX_ATTEMPTS
)
_build_review_messages = review_prompts.build_review_messages
_build_review_response_format = review_prompts.build_review_response_format
_parse_review_result = review_prompts.parse_review_result
_parse_review_result_from_provider_payload = (
    review_prompts.parse_review_result_from_provider_payload
)

AUTO_APPROVAL_LEGITIMACY_THRESHOLD = 0.95
AUTO_APPROVAL_SEVERITY_CONFIDENCE_THRESHOLD = 0.85
AUTO_APPROVAL_EVIDENCE_TIERS = {"official_documented", "court_or_regulator"}
ESCALATION_SEVERITY_CONFIDENCE_THRESHOLD = 0.75
@dataclass(frozen=True)
class IncidentReviewBatchSubmission:
    batch_id: str
    submitted: int
    model: str


@dataclass(frozen=True)
class IncidentReviewResult:
    incident_id: str
    verdict: str
    score: float
    reasoning: str
    source_quality_summary: str
    date_confirmed: bool
    company_confirmed: bool
    headline_en: str
    reality_summary_en: str
    incident_summary_en: str | None = None
    what_happened_en: str | None = None
    ai_failure_point_en: str | None = None
    why_it_matters_en: str | None = None
    evidence_summary_en: str | None = None
    categories: list[str] | None = None
    suggested_severity_score: int | None = None
    severity_confidence: float | None = None
    severity_reasoning: str | None = None
    severity_flags: list[str] | None = None
    publication_track: str | None = None
    evidence_tier: str | None = None
    source_family: str | None = None
    verification_summary: str | None = None
    needs_escalation: bool = False
    reviewed_model: str = ""


@dataclass(frozen=True)
class IncidentReviewBatchReconciliation:
    approved: int
    pending_review: int
    rejected: int
    escalated: int


@dataclass(frozen=True)
class IncidentReviewFailure:
    incident_id: str
    external_id: str | None
    error: str


@dataclass(frozen=True)
class IncidentReviewRunSummary:
    reviews_attempted: int
    reviews_completed: int
    reviews_failed: int
    approved: int
    pending_review: int
    rejected: int
    escalated: int
    translations_completed: int
    translations_failed: int
    review_failures: list[IncidentReviewFailure]
    adaptive_rate_limit_events: int = 0
    adaptive_peak_rps: float | None = None
    adaptive_final_rps: float | None = None


@dataclass(frozen=True)
class IncidentReviewDecision:
    result: IncidentReviewResult
    escalated: bool
    force_human_review: bool


@dataclass(frozen=True)
class IncidentReviewApplicationResult:
    approved: int
    pending_review: int
    rejected: int
    translations_completed: int
    translations_failed: int


class AdaptiveReviewRateLimiter:
    """Compatibility wrapper for DeepSeek 429-driven global cooldown."""

    def __init__(
        self,
        *,
        initial_rps: float,
        rps_step: float,
        max_rps: float,
        backoff_max_seconds: float,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        del initial_rps, rps_step, max_rps
        if backoff_max_seconds <= 0:
            raise ValueError("backoff_max_seconds must be greater than 0")

        self._backoff_max_seconds = float(backoff_max_seconds)
        self._monotonic = monotonic
        self._sleep = sleep
        self._lock = asyncio.Lock()
        now = self._monotonic()
        self._cooldown_until = now
        self._next_backoff_seconds = 1.0
        self._rate_limit_events = 0

    async def wait_for_slot(self) -> None:
        while True:
            async with self._lock:
                now = self._monotonic()
                if self._cooldown_until <= now:
                    return
                delay = self._cooldown_until - now
            await self._sleep(delay)

    async def record_rate_limit(self) -> None:
        async with self._lock:
            now = self._monotonic()
            cooldown_seconds = min(
                self._next_backoff_seconds,
                self._backoff_max_seconds,
            )
            cooldown_until = now + cooldown_seconds
            self._cooldown_until = max(self._cooldown_until, cooldown_until)
            self._next_backoff_seconds = min(
                cooldown_seconds * 2,
                self._backoff_max_seconds,
            )
            self._rate_limit_events += 1

    async def record_success(self) -> None:
        async with self._lock:
            self._next_backoff_seconds = 1.0

    def snapshot(self) -> dict[str, float | int]:
        return {
            "rate_limit_events": self._rate_limit_events,
        }


class IncidentBatchReviewClient(Protocol):
    def get_batch_status(self, *, batch_id: str) -> str: ...

    def submit_batch(
        self,
        *,
        incidents: list[dict[str, Any]],
        model: str,
    ) -> IncidentReviewBatchSubmission: ...

    def get_batch_results(self, *, batch_id: str) -> list[IncidentReviewResult]: ...


class AsyncIncidentReviewClient(Protocol):
    async def review_incident(
        self,
        *,
        incident: dict[str, Any],
        model: str,
    ) -> IncidentReviewResult: ...


class IncidentEscalationReviewClient(Protocol):
    def review_incident(
        self,
        *,
        incident: dict[str, Any],
        model: str,
    ) -> IncidentReviewResult: ...


class OpenAIIncidentReviewClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 120.0,
        max_output_tokens: int = review_prompts.REVIEW_MAX_OUTPUT_TOKENS,
        response_parse_max_attempts: int = (
            review_prompts.REVIEW_RESPONSE_PARSE_MAX_ATTEMPTS
        ),
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens
        self._response_parse_max_attempts = response_parse_max_attempts
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._response_format = review_prompts.build_review_response_format(
            base_url=self._base_url
        )

    def submit_batch(
        self,
        *,
        incidents: list[dict[str, Any]],
        model: str,
    ) -> IncidentReviewBatchSubmission:
        jsonl_body = "\n".join(
            json.dumps(
                {
                    "custom_id": incident["id"],
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": model,
                        "response_format": self._response_format,
                        "messages": review_prompts.build_review_messages(incident),
                        "max_tokens": self._max_output_tokens,
                    },
                }
            )
            for incident in incidents
        )
        input_file_id = self._upload_batch_file(jsonl_body)
        batch = self._post_json(
            "/batches",
            {
                "input_file_id": input_file_id,
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h",
                "metadata": {
                    "purpose": "incident_review",
                    "incident_count": str(len(incidents)),
                },
            },
        )
        return IncidentReviewBatchSubmission(
            batch_id=batch["id"],
            submitted=len(incidents),
            model=model,
        )

    def get_batch_results(self, *, batch_id: str) -> list[IncidentReviewResult]:
        batch = self._get_json(f"/batches/{batch_id}")
        if batch["status"] != "completed":
            raise RuntimeError(
                f"Batch {batch_id} is not complete yet; current status is "
                f"{batch['status']}"
            )
        output_file_id = batch.get("output_file_id")
        if not output_file_id:
            raise RuntimeError(f"Batch {batch_id} completed without output_file_id")

        response = httpx.get(
            f"{self._base_url}/files/{output_file_id}/content",
            headers=self._headers,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        results: list[IncidentReviewResult] = []
        for raw_line in response.text.splitlines():
            if not raw_line.strip():
                continue
            payload = json.loads(raw_line)
            if payload.get("error") is not None:
                continue
            body = payload["response"]["body"]
            content = body["choices"][0]["message"]["content"]
            results.append(
                review_prompts.parse_review_result(
                    incident_id=payload["custom_id"],
                    model=body["model"],
                    content=content,
                )
            )
        return results

    def get_batch_status(self, *, batch_id: str) -> str:
        batch = self._get_json(f"/batches/{batch_id}")
        return str(batch["status"])

    def review_incident(
        self,
        *,
        incident: dict[str, Any],
        model: str,
    ) -> IncidentReviewResult:
        last_error: ReviewResponseParseError | None = None
        for attempt in range(self._response_parse_max_attempts):
            payload = self._post_json(
                "/chat/completions",
                {
                    "model": model,
                    "response_format": self._response_format,
                    "messages": review_prompts.build_review_messages(incident),
                    "max_tokens": self._max_output_tokens,
                },
            )
            try:
                return review_prompts.parse_review_result_from_provider_payload(
                    incident_id=incident["id"],
                    payload=payload,
                )
            except ReviewResponseParseError as exc:
                last_error = exc
                if attempt == self._response_parse_max_attempts - 1:
                    break
        if last_error is None:
            raise RuntimeError("Review failed without a parse exception")
        raise last_error

    def _upload_batch_file(self, jsonl_body: str) -> str:
        response = httpx.post(
            f"{self._base_url}/files",
            headers=self._headers,
            files={
                "purpose": (None, "batch"),
                "file": (
                    "incident-review-batch.jsonl",
                    jsonl_body,
                    "application/jsonl",
                ),
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return response.json()["id"]

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self._base_url}{path}",
            headers={**self._headers, "Content-Type": "application/json"},
            json=payload,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def _get_json(self, path: str) -> dict[str, Any]:
        response = httpx.get(
            f"{self._base_url}{path}",
            headers=self._headers,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


class AsyncOpenAIIncidentReviewClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 120.0,
        max_output_tokens: int = review_prompts.REVIEW_MAX_OUTPUT_TOKENS,
        response_parse_max_attempts: int = (
            review_prompts.REVIEW_RESPONSE_PARSE_MAX_ATTEMPTS
        ),
    ) -> None:
        try:
            from openai import AsyncOpenAI
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "The openai package is required for async incident review."
            ) from exc

        self._base_url = base_url.rstrip("/")
        self._max_output_tokens = max_output_tokens
        self._response_parse_max_attempts = response_parse_max_attempts
        self._response_format = review_prompts.build_review_response_format(
            base_url=self._base_url
        )
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=self._base_url,
            timeout=timeout_seconds,
        )

    async def review_incident(
        self,
        *,
        incident: dict[str, Any],
        model: str,
    ) -> IncidentReviewResult:
        last_error: ReviewResponseParseError | None = None
        for attempt in range(self._response_parse_max_attempts):
            payload = await self._client.chat.completions.create(
                model=model,
                response_format=self._response_format,
                messages=review_prompts.build_review_messages(incident),
                max_tokens=self._max_output_tokens,
            )
            try:
                return review_prompts.parse_review_result_from_provider_payload(
                    incident_id=incident["id"],
                    payload=payload,
                )
            except ReviewResponseParseError as exc:
                last_error = exc
                if attempt == self._response_parse_max_attempts - 1:
                    break
        if last_error is None:
            raise RuntimeError("Review failed without a parse exception")
        raise last_error


CompatibleIncidentReviewClient = OpenAIIncidentReviewClient
AsyncCompatibleIncidentReviewClient = AsyncOpenAIIncidentReviewClient


def submit_incident_review_batch(
    repository: IncidentRepository,
    *,
    source_fetcher: IncidentSourceFetcher,
    batch_client: IncidentBatchReviewClient,
    primary_model: str,
) -> IncidentReviewBatchSubmission:
    incidents = [
        incident
        for incident in repository.list_incidents_pending_llm_review()
        if not incident.get("review_batch_id")
    ]
    refresh_source_evidence(
        repository,
        incidents=incidents,
        source_fetcher=source_fetcher,
    )

    refreshed_incidents = [
        incident
        for incident in repository.list_incidents_pending_llm_review()
        if not incident.get("review_batch_id")
    ]
    provider_submission = batch_client.submit_batch(
        incidents=refreshed_incidents,
        model=primary_model,
    )
    submission = IncidentReviewBatchSubmission(
        batch_id=provider_submission.batch_id,
        submitted=(
            provider_submission.submitted
            if hasattr(provider_submission, "submitted")
            else provider_submission.request_count
        ),
        model=provider_submission.model,
    )
    repository.mark_incidents_review_batch(
        incident_ids=[incident["id"] for incident in refreshed_incidents],
        review_batch_id=submission.batch_id,
        review_model=primary_model,
    )
    return submission


async def review_pending_incidents(
    repository: IncidentRepository,
    *,
    source_fetcher: IncidentSourceFetcher,
    review_client: AsyncIncidentReviewClient,
    escalation_client: IncidentEscalationReviewClient,
    translation_client: IncidentTranslationClient,
    embedding_client: IncidentEmbeddingClient,
    duplicate_judge_client: IncidentDuplicateJudgeClient,
    primary_model: str,
    escalation_model: str,
    embedding_model: str,
    duplicate_judge_model: str,
    concurrency: int = 10,
    max_attempts: int = 3,
    max_reviews: int | None = None,
    approval_threshold: float = AUTO_APPROVAL_LEGITIMACY_THRESHOLD,
    adaptive_deepseek_rate: bool = False,
    adaptive_initial_rps: float = 1.0,
    adaptive_rps_step: float = 1.0,
    adaptive_max_rps: float = 20.0,
    adaptive_backoff_max_seconds: float = 60.0,
) -> IncidentReviewRunSummary:
    incidents = repository.list_incidents_pending_llm_review()
    if max_reviews is not None:
        incidents = incidents[:max_reviews]
    if not incidents:
        return IncidentReviewRunSummary(
            reviews_attempted=0,
            reviews_completed=0,
            reviews_failed=0,
            approved=0,
            pending_review=0,
            rejected=0,
            escalated=0,
            translations_completed=0,
            translations_failed=0,
            review_failures=[],
        )

    refresh_source_evidence(
        repository,
        incidents=incidents,
        source_fetcher=source_fetcher,
    )
    refreshed_incidents = repository.list_incidents_pending_llm_review()
    refreshed_incident_ids = {str(incident["id"]) for incident in incidents}
    refreshed_incidents = [
        incident
        for incident in refreshed_incidents
        if str(incident["id"]) in refreshed_incident_ids
    ]
    semaphore = asyncio.Semaphore(concurrency)
    rate_limiter = (
        AdaptiveReviewRateLimiter(
            initial_rps=adaptive_initial_rps,
            rps_step=adaptive_rps_step,
            max_rps=adaptive_max_rps,
            backoff_max_seconds=adaptive_backoff_max_seconds,
        )
    )
    del adaptive_deepseek_rate

    async def _process_incident(
        incident: dict[str, Any],
    ) -> tuple[IncidentReviewApplicationResult, bool, IncidentReviewFailure | None]:
        async with semaphore:
            def _failure_result(
                exc: Exception,
            ) -> tuple[
                IncidentReviewApplicationResult,
                bool,
                IncidentReviewFailure | None,
            ]:
                return (
                    IncidentReviewApplicationResult(
                        approved=0,
                        pending_review=0,
                        rejected=0,
                        translations_completed=0,
                        translations_failed=0,
                    ),
                    False,
                    IncidentReviewFailure(
                        incident_id=incident["id"],
                        external_id=incident.get("external_id"),
                        error=str(exc),
                    ),
                )

            try:
                primary_result = await _review_incident_with_retries(
                    review_client,
                    incident=incident,
                    model=primary_model,
                    max_attempts=max_attempts,
                    rate_limiter=rate_limiter,
                )
            except Exception as exc:
                return _failure_result(exc)

            try:
                decision = _resolve_review_decision(
                    incident=incident,
                    initial_result=primary_result,
                    escalation_client=escalation_client,
                    escalation_model=escalation_model,
                    approval_threshold=approval_threshold,
                )
                application_result = _apply_review_decision(
                    repository,
                    incident=incident,
                    decision=decision,
                    translation_client=translation_client,
                    embedding_client=embedding_client,
                    duplicate_judge_client=duplicate_judge_client,
                    embedding_model=embedding_model,
                    duplicate_judge_model=duplicate_judge_model,
                    escalation_model=escalation_model,
                    approval_threshold=approval_threshold,
                    review_batch_id=incident.get("review_batch_id"),
                )
            except Exception as exc:
                return _failure_result(exc)
            return application_result, decision.escalated, None

    results = await asyncio.gather(
        *(_process_incident(incident) for incident in refreshed_incidents)
    )

    approved = 0
    pending_review = 0
    rejected = 0
    escalated = 0
    translations_completed = 0
    translations_failed = 0
    review_failures: list[IncidentReviewFailure] = []
    for application_result, was_escalated, failure in results:
        approved += application_result.approved
        pending_review += application_result.pending_review
        rejected += application_result.rejected
        translations_completed += application_result.translations_completed
        translations_failed += application_result.translations_failed
        if was_escalated:
            escalated += 1
        if failure is not None:
            review_failures.append(failure)

    limiter_snapshot = rate_limiter.snapshot() if rate_limiter is not None else {}
    return IncidentReviewRunSummary(
        reviews_attempted=len(refreshed_incidents),
        reviews_completed=len(refreshed_incidents) - len(review_failures),
        reviews_failed=len(review_failures),
        approved=approved,
        pending_review=pending_review,
        rejected=rejected,
        escalated=escalated,
        translations_completed=translations_completed,
        translations_failed=translations_failed,
        review_failures=review_failures,
        adaptive_rate_limit_events=int(
            limiter_snapshot.get("rate_limit_events", 0)
        ),
        adaptive_peak_rps=(
            float(limiter_snapshot["peak_rps"])
            if "peak_rps" in limiter_snapshot
            else None
        ),
        adaptive_final_rps=(
            float(limiter_snapshot["current_rps"])
            if "current_rps" in limiter_snapshot
            else None
        ),
    )


def reconcile_incident_review_batch(
    repository: IncidentRepository,
    *,
    batch_id: str,
    batch_client: IncidentBatchReviewClient,
    escalation_client: IncidentEscalationReviewClient,
    translation_client: IncidentTranslationClient,
    embedding_client: IncidentEmbeddingClient,
    duplicate_judge_client: IncidentDuplicateJudgeClient,
    embedding_model: str,
    duplicate_judge_model: str,
    escalation_model: str,
    approval_threshold: float = AUTO_APPROVAL_LEGITIMACY_THRESHOLD,
) -> IncidentReviewBatchReconciliation:
    incidents_by_id = {
        incident["id"]: incident
        for incident in repository.list_incidents_pending_llm_review()
    }
    approved = 0
    pending_review = 0
    rejected = 0
    escalated = 0

    for result in batch_client.get_batch_results(batch_id=batch_id):
        incident = incidents_by_id.get(result.incident_id)
        if incident is None:
            continue

        decision = _resolve_review_decision(
            incident=incident,
            initial_result=result,
            escalation_client=escalation_client,
            escalation_model=escalation_model,
            approval_threshold=approval_threshold,
        )
        application_result = _apply_review_decision(
            repository,
            incident=incident,
            decision=decision,
            translation_client=translation_client,
            embedding_client=embedding_client,
            duplicate_judge_client=duplicate_judge_client,
            embedding_model=embedding_model,
            duplicate_judge_model=duplicate_judge_model,
            escalation_model=escalation_model,
            approval_threshold=approval_threshold,
            review_batch_id=batch_id,
        )
        approved += application_result.approved
        pending_review += application_result.pending_review
        rejected += application_result.rejected
        if decision.escalated:
            escalated += 1

    return IncidentReviewBatchReconciliation(
        approved=approved,
        pending_review=pending_review,
        rejected=rejected,
        escalated=escalated,
    )


def _should_escalate(
    result: IncidentReviewResult,
    *,
    approval_threshold: float,
) -> bool:
    if result.needs_escalation:
        return True
    if (not result.date_confirmed) or (not result.company_confirmed):
        return True
    if result.severity_confidence is not None and (
        result.severity_confidence < ESCALATION_SEVERITY_CONFIDENCE_THRESHOLD
    ):
        return True
    if result.verdict == "approved":
        return result.score < approval_threshold
    return result.verdict not in {"rejected", "pending_review"}


def _resolve_final_status(
    result: IncidentReviewResult,
    *,
    incident: dict[str, Any],
    approval_threshold: float,
) -> str:
    if result.verdict == "rejected":
        return "rejected"
    if _can_auto_approve(
        result,
        incident=incident,
        approval_threshold=approval_threshold,
    ):
        return "approved"
    return "pending_review"




def _normalize_review_result(
    result: IncidentReviewResult,
    *,
    incident: dict[str, Any],
) -> IncidentReviewResult:
    fallback_severity = incident.get("suggested_severity_score")
    fallback_categories = list(incident.get("categories", []))
    return IncidentReviewResult(
        incident_id=result.incident_id,
        verdict=result.verdict,
        score=result.score,
        reasoning=result.reasoning,
        source_quality_summary=result.source_quality_summary,
        date_confirmed=result.date_confirmed,
        company_confirmed=result.company_confirmed,
        headline_en=result.headline_en,
        reality_summary_en=result.reality_summary_en,
        incident_summary_en=result.incident_summary_en,
        what_happened_en=result.what_happened_en,
        ai_failure_point_en=result.ai_failure_point_en,
        why_it_matters_en=result.why_it_matters_en,
        evidence_summary_en=result.evidence_summary_en,
        categories=result.categories or fallback_categories,
        suggested_severity_score=result.suggested_severity_score or fallback_severity,
        severity_confidence=result.severity_confidence,
        severity_reasoning=result.severity_reasoning,
        severity_flags=list(result.severity_flags or []),
        publication_track=result.publication_track or incident.get("publication_track"),
        evidence_tier=result.evidence_tier or incident.get("evidence_tier"),
        source_family=result.source_family or incident.get("source_family"),
        verification_summary=(
            result.verification_summary or incident.get("verification_summary")
        ),
        needs_escalation=result.needs_escalation,
        reviewed_model=result.reviewed_model,
    )


def _can_auto_approve(
    result: IncidentReviewResult,
    *,
    incident: dict[str, Any],
    approval_threshold: float,
) -> bool:
    if result.verdict != "approved":
        return False
    if result.score < max(approval_threshold, AUTO_APPROVAL_LEGITIMACY_THRESHOLD):
        return False
    if result.suggested_severity_score is None:
        return False
    if result.severity_confidence is None:
        return False
    if result.severity_confidence < AUTO_APPROVAL_SEVERITY_CONFIDENCE_THRESHOLD:
        return False
    if (not result.date_confirmed) or (not result.company_confirmed):
        return False
    if (result.publication_track or incident.get("publication_track")) != (
        "verified_accident"
    ):
        return False
    if (
        result.evidence_tier or incident.get("evidence_tier")
    ) not in AUTO_APPROVAL_EVIDENCE_TIERS:
        return False
    return any(
        source.get("source_origin") == "fixed_verified_source"
        and source.get("fetch_status") == "fetched"
        and bool(source.get("evidence_text"))
        for source in incident.get("sources", [])
    )


async def _review_incident_with_retries(
    review_client: AsyncIncidentReviewClient,
    *,
    incident: dict[str, Any],
    model: str,
    max_attempts: int,
    rate_limiter: AdaptiveReviewRateLimiter | None = None,
) -> IncidentReviewResult:
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            if rate_limiter is not None:
                await rate_limiter.wait_for_slot()
            result = await review_client.review_incident(incident=incident, model=model)
            if rate_limiter is not None:
                await rate_limiter.record_success()
            return result
        except ReviewResponseParseError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if rate_limiter is not None and _is_rate_limit_error(exc):
                await rate_limiter.record_rate_limit()
                if attempt == max_attempts - 1:
                    break
                continue
            if attempt == max_attempts - 1:
                break
            await asyncio.sleep(2**attempt)
    if last_error is None:
        raise RuntimeError("Review failed without an exception")
    raise last_error


def _is_rate_limit_error(exc: BaseException | Any) -> bool:
    if getattr(exc, "status_code", None) == 429:
        return True
    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) == 429:
        return True
    return exc.__class__.__name__ == "RateLimitError"


def _resolve_review_decision(
    *,
    incident: dict[str, Any],
    initial_result: IncidentReviewResult,
    escalation_client: IncidentEscalationReviewClient,
    escalation_model: str,
    approval_threshold: float,
) -> IncidentReviewDecision:
    del escalation_client, escalation_model
    normalized_result = _normalize_review_result(initial_result, incident=incident)
    return IncidentReviewDecision(
        result=normalized_result,
        escalated=False,
        force_human_review=not _can_auto_approve(
            normalized_result,
            incident=incident,
            approval_threshold=approval_threshold,
        ),
    )


def _apply_review_decision(
    repository: IncidentRepository,
    *,
    incident: dict[str, Any],
    decision: IncidentReviewDecision,
    translation_client: IncidentTranslationClient,
    embedding_client: IncidentEmbeddingClient,
    duplicate_judge_client: IncidentDuplicateJudgeClient,
    embedding_model: str,
    duplicate_judge_model: str,
    escalation_model: str,
    approval_threshold: float,
    review_batch_id: str | None,
) -> IncidentReviewApplicationResult:
    final_result = decision.result
    final_status = _resolve_final_status(
        final_result,
        incident=incident,
        approval_threshold=approval_threshold,
    )
    if final_status == "approved" and _has_insufficient_autonomous_vehicle_detail(
        incident,
        final_result,
    ):
        final_status = "pending_review"
    final_severity_score = (
        final_result.suggested_severity_score
        if final_status == "approved"
        and final_result.suggested_severity_score is not None
        else incident.get("severity_score")
    )
    severity_decision_source = (
        "escalation_llm"
        if final_status == "approved"
        and final_result.reviewed_model == escalation_model
        and final_result.suggested_severity_score is not None
        else "primary_llm"
        if final_status == "approved"
        and final_result.suggested_severity_score is not None
        else None
    )
    repository.apply_incident_review_result(
        incident_id=incident["id"],
        status=final_status,
        legitimacy_score=final_result.score,
        legitimacy_label=final_result.verdict,
        legitimacy_reasoning=final_result.reasoning,
        source_validation_summary=final_result.source_quality_summary,
        headline_en=final_result.headline_en,
        reality_summary_en=final_result.reality_summary_en,
        incident_summary_en=final_result.incident_summary_en,
        what_happened_en=final_result.what_happened_en,
        ai_failure_point_en=final_result.ai_failure_point_en,
        why_it_matters_en=final_result.why_it_matters_en,
        evidence_summary_en=final_result.evidence_summary_en,
        publication_track=final_result.publication_track,
        evidence_tier=final_result.evidence_tier,
        source_family=final_result.source_family,
        verification_summary=final_result.verification_summary,
        categories=final_result.categories or list(incident.get("categories", [])),
        severity_score=final_severity_score,
        suggested_severity_score=final_result.suggested_severity_score,
        severity_confidence=final_result.severity_confidence,
        severity_reasoning=final_result.severity_reasoning,
        severity_flags=final_result.severity_flags or [],
        severity_model=final_result.reviewed_model,
        severity_decision_source=severity_decision_source,
        severity_suggested_at=_now_isoformat(),
        review_model=final_result.reviewed_model,
        review_batch_id=review_batch_id,
        reviewed_at=_now_isoformat(),
    )
    incident.update(
        {
            "status": final_status,
            "headline_en": final_result.headline_en,
            "reality_summary_en": final_result.reality_summary_en,
            "incident_summary_en": final_result.incident_summary_en,
            "what_happened_en": final_result.what_happened_en,
            "ai_failure_point_en": final_result.ai_failure_point_en,
            "why_it_matters_en": final_result.why_it_matters_en,
            "evidence_summary_en": final_result.evidence_summary_en,
            "publication_track": (
                final_result.publication_track
                or incident.get("publication_track")
            ),
            "evidence_tier": (
                final_result.evidence_tier or incident.get("evidence_tier")
            ),
            "source_family": (
                final_result.source_family or incident.get("source_family")
            ),
            "verification_summary": (
                final_result.verification_summary
                or incident.get("verification_summary")
            ),
            "categories": final_result.categories
            or list(incident.get("categories", [])),
            "legitimacy_score": final_result.score,
            "legitimacy_label": final_result.verdict,
            "legitimacy_reasoning": final_result.reasoning,
            "source_validation_summary": final_result.source_quality_summary,
            "severity_score": final_severity_score,
            "suggested_severity_score": final_result.suggested_severity_score,
            "severity_confidence": final_result.severity_confidence,
            "severity_reasoning": final_result.severity_reasoning,
            "severity_flags": final_result.severity_flags or [],
            "severity_model": final_result.reviewed_model,
            "severity_decision_source": severity_decision_source,
            "review_model": final_result.reviewed_model,
            "review_batch_id": review_batch_id,
        }
    )

    if final_status != "approved":
        if final_status == "rejected":
            return IncidentReviewApplicationResult(
                approved=0,
                pending_review=0,
                rejected=1,
                translations_completed=0,
                translations_failed=0,
            )
        return IncidentReviewApplicationResult(
            approved=0,
            pending_review=1,
            rejected=0,
            translations_completed=0,
            translations_failed=0,
        )

    duplicate_outcome = detect_and_merge_duplicate_incident(
        repository,
        incident_id=incident["id"],
        embedding_client=embedding_client,
        duplicate_judge_client=duplicate_judge_client,
        embedding_model=embedding_model,
        duplicate_judge_model=duplicate_judge_model,
    )
    if duplicate_outcome.is_duplicate:
        incident["status"] = "duplicate_confirmed"
        incident["duplicate_of_incident_id"] = duplicate_outcome.canonical_incident_id
        incident["translation_status"] = "not_requested"
        return IncidentReviewApplicationResult(
            approved=0,
            pending_review=0,
            rejected=0,
            translations_completed=0,
            translations_failed=0,
        )

    translation = translate_incident_copy(
        company_involved_en=incident["company_involved"],
        headline_en=final_result.headline_en,
        reality_summary_en=final_result.reality_summary_en,
        legitimacy_reasoning_en=final_result.reasoning,
        source_validation_summary_en=final_result.source_quality_summary,
        incident_summary_en=final_result.incident_summary_en or "",
        what_happened_en=final_result.what_happened_en or "",
        ai_failure_point_en=final_result.ai_failure_point_en or "",
        why_it_matters_en=final_result.why_it_matters_en or "",
        evidence_summary_en=final_result.evidence_summary_en or "",
        client=translation_client,
    )
    repository.update_incident_translation(
        incident_id=incident["id"],
        company_involved_zh=translation.company_involved_zh,
        headline_zh=translation.headline_zh,
        reality_summary_zh=translation.reality_summary_zh,
        incident_summary_zh=translation.incident_summary_zh,
        what_happened_zh=translation.what_happened_zh,
        ai_failure_point_zh=translation.ai_failure_point_zh,
        why_it_matters_zh=translation.why_it_matters_zh,
        evidence_summary_zh=translation.evidence_summary_zh,
        legitimacy_reasoning_zh=translation.legitimacy_reasoning_zh,
        source_validation_summary_zh=translation.source_validation_summary_zh,
        translation_status=translation.status,
        translated_at=_now_isoformat(),
    )
    incident["translation_status"] = translation.status
    incident["company_involved_zh"] = translation.company_involved_zh
    incident["headline_zh"] = translation.headline_zh
    incident["reality_summary_zh"] = translation.reality_summary_zh
    incident["incident_summary_zh"] = translation.incident_summary_zh
    incident["what_happened_zh"] = translation.what_happened_zh
    incident["ai_failure_point_zh"] = translation.ai_failure_point_zh
    incident["why_it_matters_zh"] = translation.why_it_matters_zh
    incident["evidence_summary_zh"] = translation.evidence_summary_zh
    incident["legitimacy_reasoning_zh"] = translation.legitimacy_reasoning_zh
    incident["source_validation_summary_zh"] = (
        translation.source_validation_summary_zh
    )
    return IncidentReviewApplicationResult(
        approved=1,
        pending_review=0,
        rejected=0,
        translations_completed=1 if translation.status == "completed" else 0,
        translations_failed=0 if translation.status == "completed" else 1,
    )


def _now_isoformat() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def _has_insufficient_autonomous_vehicle_detail(
    incident: dict[str, Any],
    result: IncidentReviewResult,
) -> bool:
    assessment = assess_autonomous_vehicle_detail_quality(
        {
            **incident,
            "incident_summary_en": result.incident_summary_en,
            "what_happened_en": result.what_happened_en,
            "ai_failure_point_en": result.ai_failure_point_en,
            "why_it_matters_en": result.why_it_matters_en,
            "evidence_summary_en": result.evidence_summary_en,
        }
    )
    return assessment.detail_quality == "insufficient"
