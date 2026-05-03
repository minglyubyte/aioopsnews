from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from app.services.review_prompts import (
    REVIEW_MAX_OUTPUT_TOKENS,
    REVIEW_RESPONSE_PARSE_MAX_ATTEMPTS,
    ReviewResponseParseError,
    build_review_messages as _build_review_messages,
    build_review_response_format as _build_review_response_format,
    parse_review_result as _parse_review_result,
    parse_review_result_from_provider_payload as _parse_review_result_from_provider_payload,
)

from app.db.repository_protocol import IncidentRepository
from app.services.incident_deduplication import (
    IncidentDuplicateJudgeClient,
    IncidentEmbeddingClient,
    detect_and_merge_duplicate_incident,
)
from app.services.incident_translation import (
    IncidentTranslationClient,
    translate_incident_copy,
)

AUTO_APPROVAL_SEVERITY_THRESHOLD = 2
AUTO_APPROVAL_LEGITIMACY_THRESHOLD = 0.90
AUTO_APPROVAL_SEVERITY_CONFIDENCE_THRESHOLD = 0.85
ESCALATION_SEVERITY_CONFIDENCE_THRESHOLD = 0.75
HIGH_RISK_SEVERITY_FLAGS = {
    "safety",
    "privacy_breach",
    "legal_or_regulatory",
    "financial_harm",
    "core_system_outage",
    "unclear_real_world_impact",
}
DEFAULT_SOURCE_FETCH_HEADERS = {"User-Agent": "AIRealityCheckBot/1.0"}
BROWSER_SOURCE_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass(frozen=True)
class FetchedIncidentSource:
    source_url: str
    canonical_url: str | None
    fetch_status: str
    http_status: int | None
    evidence_text: str | None
    fetch_error: str | None = None


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


class IncidentSourceFetcher(Protocol):
    def fetch(self, source_url: str) -> FetchedIncidentSource: ...


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


class HttpIncidentSourceFetcher:
    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self._timeout_seconds = timeout_seconds

    def fetch(self, source_url: str) -> FetchedIncidentSource:
        try:
            response = self._get(source_url, headers=DEFAULT_SOURCE_FETCH_HEADERS)
            if response.status_code == 403:
                response = self._get(
                    source_url,
                    headers=BROWSER_SOURCE_FETCH_HEADERS,
                )
        except httpx.HTTPError as exc:
            return FetchedIncidentSource(
                source_url=source_url,
                canonical_url=None,
                fetch_status="failed",
                http_status=None,
                evidence_text=None,
                fetch_error=str(exc),
            )

        evidence_text = _extract_evidence_text(response.text)
        fetch_status = "fetched" if response.is_success else "failed"
        return FetchedIncidentSource(
            source_url=source_url,
            canonical_url=str(response.url),
            fetch_status=fetch_status,
            http_status=response.status_code,
            evidence_text=evidence_text if response.is_success else None,
            fetch_error=None if response.is_success else response.reason_phrase,
        )

    def _get(
        self,
        source_url: str,
        *,
        headers: dict[str, str],
    ) -> httpx.Response:
        return httpx.get(
            source_url,
            follow_redirects=True,
            timeout=self._timeout_seconds,
            headers=headers,
        )


class OpenAIIncidentReviewClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 120.0,
        max_output_tokens: int = REVIEW_MAX_OUTPUT_TOKENS,
        response_parse_max_attempts: int = REVIEW_RESPONSE_PARSE_MAX_ATTEMPTS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens
        self._response_parse_max_attempts = response_parse_max_attempts
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._response_format = _build_review_response_format(base_url=self._base_url)

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
                        "messages": _build_review_messages(incident),
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
                _parse_review_result(
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
                    "messages": _build_review_messages(incident),
                    "max_tokens": self._max_output_tokens,
                },
            )
            try:
                return _parse_review_result_from_provider_payload(
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
        max_output_tokens: int = REVIEW_MAX_OUTPUT_TOKENS,
        response_parse_max_attempts: int = REVIEW_RESPONSE_PARSE_MAX_ATTEMPTS,
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
        self._response_format = _build_review_response_format(base_url=self._base_url)
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
                messages=_build_review_messages(incident),
                max_tokens=self._max_output_tokens,
            )
            try:
                return _parse_review_result_from_provider_payload(
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
    _refresh_source_evidence(
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
    concurrency: int = 8,
    max_attempts: int = 3,
    approval_threshold: float = AUTO_APPROVAL_LEGITIMACY_THRESHOLD,
) -> IncidentReviewRunSummary:
    incidents = repository.list_incidents_pending_llm_review()
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

    _refresh_source_evidence(
        repository,
        incidents=incidents,
        source_fetcher=source_fetcher,
    )
    refreshed_incidents = repository.list_incidents_pending_llm_review()
    semaphore = asyncio.Semaphore(concurrency)

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
    approval_threshold: float,
) -> str:
    if result.verdict == "rejected":
        return "rejected"
    if _can_auto_approve(result, approval_threshold=approval_threshold):
        return "approved"
    if _requires_editor_review(result):
        return "pending_editor_review"
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
        needs_escalation=result.needs_escalation,
        reviewed_model=result.reviewed_model,
    )


def _can_auto_approve(
    result: IncidentReviewResult,
    *,
    approval_threshold: float,
) -> bool:
    if result.verdict != "approved":
        return False
    if result.score < approval_threshold:
        return False
    if result.suggested_severity_score is None:
        return result.date_confirmed and result.company_confirmed
    if result.suggested_severity_score > AUTO_APPROVAL_SEVERITY_THRESHOLD:
        return False
    if result.severity_confidence is None:
        return False
    if result.severity_confidence < AUTO_APPROVAL_SEVERITY_CONFIDENCE_THRESHOLD:
        return False
    if (not result.date_confirmed) or (not result.company_confirmed):
        return False
    return not any(
        flag in HIGH_RISK_SEVERITY_FLAGS for flag in result.severity_flags or []
    )


def _requires_editor_review(result: IncidentReviewResult) -> bool:
    if result.suggested_severity_score is None:
        return False
    if (
        result.suggested_severity_score is not None
        and result.suggested_severity_score >= 3
    ):
        return True
    return any(flag in HIGH_RISK_SEVERITY_FLAGS for flag in result.severity_flags or [])


def _extract_evidence_text(html: str) -> str:
    text = html.replace("\x00", " ").replace("\r", " ").replace("\n", " ")
    collapsed = " ".join(text.split())
    return collapsed[:4000]


def _refresh_source_evidence(
    repository: IncidentRepository,
    *,
    incidents: list[dict[str, Any]],
    source_fetcher: IncidentSourceFetcher,
) -> None:
    for incident in incidents:
        for source in incident.get("sources", []):
            fetched = source_fetcher.fetch(source["source_url"])
            repository.update_incident_source_evidence(
                source_id=source["id"],
                canonical_url=fetched.canonical_url,
                fetch_status=fetched.fetch_status,
                http_status=fetched.http_status,
                evidence_text=fetched.evidence_text,
                fetch_error=fetched.fetch_error,
                fetched_at=_now_isoformat(),
            )


async def _review_incident_with_retries(
    review_client: AsyncIncidentReviewClient,
    *,
    incident: dict[str, Any],
    model: str,
    max_attempts: int,
) -> IncidentReviewResult:
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await review_client.review_incident(incident=incident, model=model)
        except ReviewResponseParseError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == max_attempts - 1:
                break
            await asyncio.sleep(2**attempt)
    if last_error is None:
        raise RuntimeError("Review failed without an exception")
    raise last_error


def _resolve_review_decision(
    *,
    incident: dict[str, Any],
    initial_result: IncidentReviewResult,
    escalation_client: IncidentEscalationReviewClient,
    escalation_model: str,
    approval_threshold: float,
) -> IncidentReviewDecision:
    normalized_result = _normalize_review_result(initial_result, incident=incident)
    if not _should_escalate(
        normalized_result,
        approval_threshold=approval_threshold,
    ):
        return IncidentReviewDecision(
            result=normalized_result,
            escalated=False,
            force_human_review=False,
        )

    escalation_result = escalation_client.review_incident(
        incident=incident,
        model=escalation_model,
    )
    normalized_escalation_result = _normalize_review_result(
        escalation_result,
        incident=incident,
    )
    return IncidentReviewDecision(
        result=normalized_escalation_result,
        escalated=True,
        force_human_review=normalized_escalation_result.needs_escalation,
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
    final_status = (
        "pending_editor_review"
        if decision.force_human_review
        else _resolve_final_status(
            final_result,
            approval_threshold=approval_threshold,
        )
    )
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
