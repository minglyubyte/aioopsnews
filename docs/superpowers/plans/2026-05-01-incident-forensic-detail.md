# Incident Forensic Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the abstract public incident detail card with a forensic brief backed by first-class analysis fields, synchronized English/Chinese translations, and reviewer-only `DeepSeek Flash V4` provenance.

**Architecture:** Extend the existing `incident_logs` record instead of adding a second analysis object. Store the richer forensic bundle in PostgreSQL, generate it in the review pipeline, translate the full bundle together, serve it through the existing public/admin APIs with legacy fallbacks, and render it differently on the public dashboard versus the internal reviewer route.

**Tech Stack:** FastAPI, Pydantic, PostgreSQL/Supabase SQL migrations, React 19, TypeScript, Vitest, pytest

---

## File Map

### Backend schema and contracts

- `infra/supabase/migrations/`
  - Add a migration that introduces the forensic analysis columns on `incident_logs`.
- `backend/app/models/incident.py`
  - Extend `IncidentRecord` with the new English/Chinese forensic fields.
- `backend/app/db/repository_protocol.py`
  - Expand repository method signatures for review-result application and translation updates.
- `backend/app/core/config.py`
  - Change the primary review model default to `deepseek-v4-flash` and add provider-neutral primary review settings if needed.

### Backend services and persistence

- `backend/app/services/incident_review.py`
  - Generate and persist the forensic bundle in primary review results.
- `backend/app/services/incident_translation.py`
  - Translate the full forensic bundle and return a bundle-aware translation result.
- `backend/app/scripts/run_incident_csv_workflow.py`
  - Point the primary review workflow at the real DeepSeek-backed default instead of changing display copy only.
- `backend/app/db/postgres_repository.py`
  - Persist the new columns, expose them in admin/public serializers, and add safe public fallbacks for legacy records.
- `backend/app/api/incidents.py`
  - Extend the public detail response model.
- `backend/app/api/admin.py`
  - Ensure reviewer payloads expose the forensic bundle and model provenance cleanly if needed by the page.

### Frontend rendering

- `frontend/src/types/incident.ts`
  - Extend `IncidentAnalysis`, `IncidentDetail`, and `AdminIncident`.
- `frontend/src/pages/PublicDashboardPage.tsx`
  - Replace the current detail-card structure with the forensic brief layout.
- `frontend/src/pages/public-dashboard.css`
  - Add styling for the new summary, AI-failure, and detail-section hierarchy.
- `frontend/src/pages/InternalReviewPage.tsx`
  - Show the richer forensic bundle and keep the model label only here.

### Tests

- `backend/tests/db/test_schema_bootstrap.py`
- `backend/tests/db/test_postgres_repository.py`
- `backend/tests/services/test_config.py`
- `backend/tests/services/test_incident_review.py`
- `backend/tests/workflows/test_incident_csv_workflow.py`
- `backend/tests/workflows/test_run_incident_csv_workflow_script.py`
- `backend/tests/api/test_incidents_api.py`
- `backend/tests/api/test_admin_api.py`
- `frontend/src/tests/PublicDashboardPage.test.tsx`
- `frontend/src/tests/InternalReviewPage.test.tsx`

## Task 1: Add forensic fields to schema, models, and config defaults

**Files:**
- Create: `infra/supabase/migrations/20260501120000_incident_forensic_fields.sql`
- Modify: `backend/app/models/incident.py`
- Modify: `backend/app/db/repository_protocol.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/scripts/run_incident_csv_workflow.py`
- Test: `backend/tests/db/test_schema_bootstrap.py`
- Test: `backend/tests/services/test_config.py`
- Test: `backend/tests/workflows/test_run_incident_csv_workflow_script.py`

- [ ] **Step 1: Write the failing schema and config tests**

```python
def test_incident_logs_includes_forensic_analysis_columns() -> None:
    columns = get_incident_log_columns()
    assert "incident_summary_en" in columns
    assert "incident_summary_zh" in columns
    assert "what_happened_en" in columns
    assert "what_happened_zh" in columns
    assert "ai_failure_point_en" in columns
    assert "ai_failure_point_zh" in columns
    assert "why_it_matters_en" in columns
    assert "why_it_matters_zh" in columns
    assert "evidence_summary_en" in columns
    assert "evidence_summary_zh" in columns


def test_get_settings_uses_deepseek_flash_v4_as_primary_review_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    backend_dir = repo_root / "backend"
    backend_dir.mkdir(parents=True)
    (repo_root / ".env").write_text(
        "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(backend_dir)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_PRIMARY_REVIEW_MODEL", raising=False)

    settings = get_settings()

    assert settings.openai_primary_review_model == "deepseek-v4-flash"


def test_workflow_script_uses_deepseek_for_primary_review_clients(
    monkeypatch,
) -> None:
    calls: list[tuple[str, str]] = []
    settings = Settings(
        database_url="postgresql://example/db",
        openai_api_key="unused-openai-key",
        deepseek_api_key="deepseek-key",
        openai_primary_review_model="deepseek-v4-flash",
    )
    monkeypatch.setattr(workflow_script, "get_settings", lambda: settings)
    monkeypatch.setattr(
        workflow_script,
        "AsyncOpenAIIncidentReviewClient",
        lambda api_key, base_url="https://api.openai.com/v1": calls.append(
            (api_key, base_url)
        )
        or object(),
    )

    workflow_script.main()

    assert calls[0] == ("deepseek-key", "https://api.deepseek.com/v1")
```

- [ ] **Step 2: Run the backend tests to verify they fail**

Run: `cd /Users/leo/Desktop/AI_Oops/backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/db/test_schema_bootstrap.py tests/services/test_config.py tests/workflows/test_run_incident_csv_workflow_script.py -q`
Expected: FAIL with missing forensic columns, the old `gpt-5.4-mini` default, or workflow wiring that still instantiates OpenAI-only primary review clients.

- [ ] **Step 3: Add the migration, model fields, protocol fields, and config default**

```sql
alter table incident_logs
    add column if not exists incident_summary_en text,
    add column if not exists incident_summary_zh text,
    add column if not exists what_happened_en text,
    add column if not exists what_happened_zh text,
    add column if not exists ai_failure_point_en text,
    add column if not exists ai_failure_point_zh text,
    add column if not exists why_it_matters_en text,
    add column if not exists why_it_matters_zh text,
    add column if not exists evidence_summary_en text,
    add column if not exists evidence_summary_zh text;
```

```python
class IncidentRecord(BaseModel):
    incident_summary_en: str | None = None
    incident_summary_zh: str | None = None
    what_happened_en: str | None = None
    what_happened_zh: str | None = None
    ai_failure_point_en: str | None = None
    ai_failure_point_zh: str | None = None
    why_it_matters_en: str | None = None
    why_it_matters_zh: str | None = None
    evidence_summary_en: str | None = None
    evidence_summary_zh: str | None = None
```

```python
@dataclass(frozen=True)
class Settings:
    openai_primary_review_model: str = "deepseek-v4-flash"
    primary_review_base_url: str = "https://api.deepseek.com/v1"
```

```python
review_client = AsyncOpenAIIncidentReviewClient(
    api_key=settings.deepseek_api_key or "",
    base_url=settings.primary_review_base_url,
)
```

- [ ] **Step 4: Re-run the backend tests to verify they pass**

Run: `cd /Users/leo/Desktop/AI_Oops/backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/db/test_schema_bootstrap.py tests/services/test_config.py tests/workflows/test_run_incident_csv_workflow_script.py -q`
Expected: PASS.

- [ ] **Step 5: Commit the schema/config checkpoint**

```bash
git add infra/supabase/migrations/20260501120000_incident_forensic_fields.sql backend/app/models/incident.py backend/app/db/repository_protocol.py backend/app/core/config.py backend/app/scripts/run_incident_csv_workflow.py backend/tests/db/test_schema_bootstrap.py backend/tests/services/test_config.py backend/tests/workflows/test_run_incident_csv_workflow_script.py
git commit -m "feat: add forensic incident analysis schema"
```

## Task 2: Generate and translate the full forensic analysis bundle

**Files:**
- Modify: `backend/app/services/incident_review.py`
- Modify: `backend/app/services/incident_translation.py`
- Modify: `backend/app/scripts/run_incident_csv_workflow.py`
- Test: `backend/tests/services/test_incident_review.py`
- Test: `backend/tests/workflows/test_incident_csv_workflow.py`

- [ ] **Step 1: Write the failing service tests for review-result parsing and translation coverage**

```python
def test_parse_review_result_reads_forensic_bundle_fields() -> None:
    result = _parse_review_result(
        incident_id="incident-1",
        model="deepseek-v4-flash",
        content=(
            '{"verdict":"approved","score":0.94,"reasoning":"Strong evidence.",'
            '"source_quality_summary":"Two credible sources.",'
            '"date_confirmed":true,"company_confirmed":true,'
            '"headline_en":"Incident headline",'
            '"incident_summary_en":"Short forensic summary.",'
            '"what_happened_en":"Concrete event sequence.",'
            '"ai_failure_point_en":"Perception missed a grounded obstacle.",'
            '"why_it_matters_en":"The miss caused avoidable real-world harm.",'
            '"evidence_summary_en":"Primary report plus official filing.",'
            '"categories":["Autonomous Systems"],'
            '"suggested_severity_score":4,"severity_confidence":0.92,'
            '"severity_reasoning":"Severe physical harm.","severity_flags":["safety"],'
            '"needs_escalation":false}'
        ),
    )

    assert result.incident_summary_en == "Short forensic summary."
    assert result.ai_failure_point_en == "Perception missed a grounded obstacle."
    assert result.evidence_summary_en == "Primary report plus official filing."


def test_reconcile_incident_review_batch_translates_every_reader_facing_field() -> None:
    approved_incident = next(
        incident
        for incident in repository.incidents.values()
        if incident["external_id"] == "inc-openai-001"
    )
    assert approved_incident["incident_summary_zh"] == "ZH:Short forensic summary."
    assert approved_incident["what_happened_zh"] == "ZH:Concrete event sequence."
    assert approved_incident["ai_failure_point_zh"] == "ZH:Perception missed a grounded obstacle."
    assert approved_incident["why_it_matters_zh"] == "ZH:The miss caused avoidable real-world harm."
    assert approved_incident["evidence_summary_zh"] == "ZH:Primary report plus official filing."


def test_run_incident_csv_workflow_uses_deepseek_flash_v4_for_primary_review(
    tmp_path,
) -> None:
    asyncio.run(
        run_incident_csv_workflow(
            repository=repository,
            inbox_dir=inbox_dir,
            archive_dir=archive_dir,
            source_fetcher=FakeSourceFetcher(),
            review_client=review_client,
            escalation_client=FakeEscalationReviewClient(),
            translation_client=translation_client,
            embedding_client=FakeEmbeddingClient(),
            duplicate_judge_client=FakeDuplicateJudgeClient(),
            primary_model="deepseek-v4-flash",
            escalation_model="gpt-5.2",
        )
    )

    assert review_client.calls[0][1] == "deepseek-v4-flash"
```

- [ ] **Step 2: Run the incident review test file to verify it fails**

Run: `cd /Users/leo/Desktop/AI_Oops/backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/services/test_incident_review.py tests/workflows/test_incident_csv_workflow.py -q`
Expected: FAIL because `IncidentReviewResult`, translation payloads, and reconciliation logic do not know the new fields yet.

- [ ] **Step 3: Extend the review and translation services**

```python
@dataclass(frozen=True)
class IncidentReviewResult:
    incident_summary_en: str
    what_happened_en: str
    ai_failure_point_en: str
    why_it_matters_en: str
    evidence_summary_en: str
```

```python
@dataclass(frozen=True)
class IncidentTranslation:
    incident_summary_zh: str
    what_happened_zh: str
    ai_failure_point_zh: str
    why_it_matters_zh: str
    evidence_summary_zh: str
```

```python
"required": [
    "headline_en",
    "incident_summary_en",
    "what_happened_en",
    "ai_failure_point_en",
    "why_it_matters_en",
    "evidence_summary_en",
    "categories",
    "suggested_severity_score",
    "severity_confidence",
    "severity_reasoning",
    "severity_flags",
    "needs_escalation",
]
```

```python
translation = client.translate(
    company_involved_en=incident["company_involved"],
    headline_en=final_result.headline_en,
    incident_summary_en=final_result.incident_summary_en,
    what_happened_en=final_result.what_happened_en,
    ai_failure_point_en=final_result.ai_failure_point_en,
    why_it_matters_en=final_result.why_it_matters_en,
    evidence_summary_en=final_result.evidence_summary_en,
    legitimacy_reasoning_en=final_result.reasoning,
    source_validation_summary_en=final_result.source_quality_summary,
)
```

- [ ] **Step 4: Re-run the incident review tests to verify they pass**

Run: `cd /Users/leo/Desktop/AI_Oops/backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/services/test_incident_review.py tests/workflows/test_incident_csv_workflow.py -q`
Expected: PASS.

- [ ] **Step 5: Commit the service-layer checkpoint**

```bash
git add backend/app/services/incident_review.py backend/app/services/incident_translation.py backend/app/scripts/run_incident_csv_workflow.py backend/tests/services/test_incident_review.py backend/tests/workflows/test_incident_csv_workflow.py
git commit -m "feat: generate and translate forensic analysis bundle"
```

## Task 3: Persist the bundle and serve public/admin compatibility payloads

**Files:**
- Modify: `backend/app/db/postgres_repository.py`
- Modify: `backend/app/db/repository_protocol.py`
- Modify: `backend/app/api/incidents.py`
- Modify: `backend/app/api/admin.py`
- Test: `backend/tests/db/test_postgres_repository.py`
- Test: `backend/tests/api/test_incidents_api.py`
- Test: `backend/tests/api/test_admin_api.py`
- Test: `backend/tests/workflows/test_incident_csv_workflow.py`

- [ ] **Step 1: Write the failing repository and API tests**

```python
def test_get_public_incident_prefers_forensic_bundle_and_falls_back_for_legacy_rows(
    repository: PostgresIncidentRepository,
) -> None:
    incident = repository.get_public_incident("incident-1")

    assert incident["analysis"]["incident_summary_en"] == "Short forensic summary."
    assert incident["analysis"]["ai_failure_point_en"] == "Perception missed a grounded obstacle."


def test_public_incident_detail_response_includes_incident_summary_and_ai_failure_point(
    client: TestClient,
) -> None:
    response = client.get("/incidents/incident-1")
    payload = response.json()

    assert payload["analysis"]["incident_summary_en"] == "Short forensic summary."
    assert payload["analysis"]["ai_failure_point_en"] == "Perception missed a grounded obstacle."
```

- [ ] **Step 2: Run repository and API tests to verify they fail**

Run: `cd /Users/leo/Desktop/AI_Oops/backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/db/test_postgres_repository.py tests/api/test_incidents_api.py tests/api/test_admin_api.py tests/workflows/test_incident_csv_workflow.py -q`
Expected: FAIL because the repository serializer and API models do not expose the new forensic fields yet.

- [ ] **Step 3: Update persistence and serializers with legacy-safe fallbacks**

```python
class IncidentAnalysisResponse(BaseModel):
    incident_summary_en: str | None = None
    incident_summary_zh: str | None = None
    what_happened_en: str | None = None
    what_happened_zh: str | None = None
    ai_failure_point_en: str | None = None
    ai_failure_point_zh: str | None = None
    why_it_matters_en: str | None = None
    why_it_matters_zh: str | None = None
    evidence_summary_en: str | None = None
    evidence_summary_zh: str | None = None
```

```python
"analysis": {
    "incident_summary_en": row.get("incident_summary_en")
    or row.get("reality_summary_en")
    or row["reality_summary"],
    "incident_summary_zh": _sanitize_reader_text(row.get("incident_summary_zh")),
    "what_happened_en": row.get("what_happened_en")
    or row.get("reality_summary_en")
    or row["reality_summary"],
    "ai_failure_point_en": _sanitize_reader_text(row.get("ai_failure_point_en")),
    "why_it_matters_en": row.get("why_it_matters_en")
    or _sanitize_reader_text(row.get("legitimacy_reasoning")),
    "evidence_summary_en": row.get("evidence_summary_en")
    or _sanitize_reader_text(row.get("source_validation_summary"))
    or _fallback_public_evidence_summary(sources, locale="en"),
}
```

```python
def update_incident_translation(
    self,
    *,
    incident_id: str,
    company_involved_zh: str,
    headline_zh: str,
    incident_summary_zh: str,
    what_happened_zh: str,
    ai_failure_point_zh: str,
    why_it_matters_zh: str,
    evidence_summary_zh: str,
    legitimacy_reasoning_zh: str,
    source_validation_summary_zh: str,
    translation_status: str,
    translated_at: str,
) -> dict[str, Any] | None:
    cursor = connection.execute(
        """
        update incident_logs
        set
            company_involved_zh = %s,
            headline_zh = %s,
            incident_summary_zh = %s,
            what_happened_zh = %s,
            ai_failure_point_zh = %s,
            why_it_matters_zh = %s,
            evidence_summary_zh = %s,
            legitimacy_reasoning_zh = %s,
            source_validation_summary_zh = %s,
            translation_status = %s,
            translated_at = %s
        where id = %s
        """,
    )
```

- [ ] **Step 4: Re-run repository and API tests to verify they pass**

Run: `cd /Users/leo/Desktop/AI_Oops/backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/db/test_postgres_repository.py tests/api/test_incidents_api.py tests/api/test_admin_api.py tests/workflows/test_incident_csv_workflow.py -q`
Expected: PASS.

- [ ] **Step 5: Commit the persistence/API checkpoint**

```bash
git add backend/app/db/postgres_repository.py backend/app/db/repository_protocol.py backend/app/api/incidents.py backend/app/api/admin.py backend/tests/db/test_postgres_repository.py backend/tests/api/test_incidents_api.py backend/tests/api/test_admin_api.py backend/tests/workflows/test_incident_csv_workflow.py
git commit -m "feat: serve forensic incident analysis bundle"
```

## Task 4: Render the forensic brief on the public dashboard

**Files:**
- Modify: `frontend/src/types/incident.ts`
- Modify: `frontend/src/pages/PublicDashboardPage.tsx`
- Modify: `frontend/src/pages/public-dashboard.css`
- Test: `frontend/src/tests/PublicDashboardPage.test.tsx`

- [ ] **Step 1: Write the failing public-dashboard tests**

```tsx
it("renders incident summary and AI failure point in the public forensic brief", async () => {
  render(<PublicDashboardPage />);

  expect(
    await screen.findByRole("heading", { name: "Full context" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Failure point in the AI stack")).toBeInTheDocument();
  expect(
    screen.getByText("Perception missed a grounded obstacle."),
  ).toBeInTheDocument();
  expect(
    screen.queryByText(/Primary analysis:/i),
  ).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run: `cd /Users/leo/Desktop/AI_Oops/frontend && npm run test -- PublicDashboardPage.test.tsx`
Expected: FAIL because the current page has no `incident_summary` or `ai_failure_point` section and still uses the older generic detail structure.

- [ ] **Step 3: Update shared types, detail helpers, JSX, and CSS**

```ts
export type IncidentAnalysis = {
  incident_summary_en?: string | null;
  incident_summary_zh?: string | null;
  what_happened_en?: string | null;
  what_happened_zh?: string | null;
  ai_failure_point_en?: string | null;
  ai_failure_point_zh?: string | null;
  why_it_matters_en?: string | null;
  why_it_matters_zh?: string | null;
  evidence_summary_en?: string | null;
  evidence_summary_zh?: string | null;
};
```

```tsx
<div className="public-detail-card">
  <p className="public-kicker">{copy.detailKicker}</p>
  <h2>{copy.detailTitle}</h2>
  <p className="public-detail-summary">
    {getLocalizedAnalysisText(incidentDetail.analysis, "incident_summary", readerLocale)}
  </p>
</div>
<div className="public-claim-block">
  <p className="public-claim-kicker">{copy.aiFailurePointTitle}</p>
  <p>
    {getLocalizedAnalysisText(incidentDetail.analysis, "ai_failure_point", readerLocale)}
  </p>
</div>
```

```css
.public-detail-summary {
  margin: 0;
  font-size: 1.05rem;
  line-height: 1.65;
  color: var(--public-text);
}
```

- [ ] **Step 4: Re-run the public-dashboard test to verify it passes**

Run: `cd /Users/leo/Desktop/AI_Oops/frontend && npm run test -- PublicDashboardPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit the public-reader checkpoint**

```bash
git add frontend/src/types/incident.ts frontend/src/pages/PublicDashboardPage.tsx frontend/src/pages/public-dashboard.css frontend/src/tests/PublicDashboardPage.test.tsx
git commit -m "feat: render forensic public incident detail"
```

## Task 5: Show provenance only in the internal reviewer panel

**Files:**
- Modify: `frontend/src/types/incident.ts`
- Modify: `frontend/src/pages/InternalReviewPage.tsx`
- Test: `frontend/src/tests/InternalReviewPage.test.tsx`

- [ ] **Step 1: Write the failing reviewer-panel test**

```tsx
it("shows the forensic bundle and review model only on the internal route", async () => {
  render(<InternalReviewPage />);
  fireEvent.change(screen.getByLabelText("Admin token"), {
    target: { value: "secret-token" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Unlock admin" }));

  expect(
    await screen.findByText(/Review model deepseek-v4-flash/i),
  ).toBeInTheDocument();
  expect(screen.getByText("Failure point in the AI stack")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the internal-review test to verify it fails**

Run: `cd /Users/leo/Desktop/AI_Oops/frontend && npm run test -- InternalReviewPage.test.tsx`
Expected: FAIL because the reviewer page does not yet render the richer forensic sections or the updated primary review model label.

- [ ] **Step 3: Render the reviewer-only provenance and forensic sections**

```tsx
<section className="public-detail-card">
  <p className="public-kicker">Analysis provenance</p>
  <p>Review model {activeIncident.review_model}</p>
  <p>Translation status {activeIncident.translation_status}</p>
</section>

<section className="public-detail-card">
  <h3>Failure point in the AI stack</h3>
  <p>{activeIncident.analysis?.ai_failure_point_en ?? "Not generated yet."}</p>
</section>
```

```ts
export type AdminIncident = PublicIncidentBase & {
  analysis?: IncidentAnalysis | null;
  review_model?: string | null;
};
```

- [ ] **Step 4: Re-run the internal-review test to verify it passes**

Run: `cd /Users/leo/Desktop/AI_Oops/frontend && npm run test -- InternalReviewPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit the reviewer checkpoint**

```bash
git add frontend/src/types/incident.ts frontend/src/pages/InternalReviewPage.tsx frontend/src/tests/InternalReviewPage.test.tsx
git commit -m "feat: add forensic provenance to internal review"
```

## Task 6: Run targeted regression verification across backend and frontend

**Files:**
- Modify: none
- Test: `backend/tests/services/test_incident_review.py`
- Test: `backend/tests/db/test_postgres_repository.py`
- Test: `backend/tests/api/test_incidents_api.py`
- Test: `backend/tests/api/test_admin_api.py`
- Test: `backend/tests/workflows/test_incident_csv_workflow.py`
- Test: `backend/tests/workflows/test_run_incident_csv_workflow_script.py`
- Test: `frontend/src/tests/PublicDashboardPage.test.tsx`
- Test: `frontend/src/tests/InternalReviewPage.test.tsx`

- [ ] **Step 1: Run the backend regression bundle**

Run: `cd /Users/leo/Desktop/AI_Oops/backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/services/test_incident_review.py tests/db/test_postgres_repository.py tests/api/test_incidents_api.py tests/api/test_admin_api.py tests/services/test_config.py tests/db/test_schema_bootstrap.py tests/workflows/test_incident_csv_workflow.py tests/workflows/test_run_incident_csv_workflow_script.py -q`
Expected: PASS.

- [ ] **Step 2: Run the frontend regression bundle**

Run: `cd /Users/leo/Desktop/AI_Oops/frontend && npm run test -- PublicDashboardPage.test.tsx InternalReviewPage.test.tsx`
Expected: PASS.

- [ ] **Step 3: Run the production-shape build checks**

Run: `cd /Users/leo/Desktop/AI_Oops/frontend && npm run build`
Expected: PASS.

Run: `cd /Users/leo/Desktop/AI_Oops/backend && UV_CACHE_DIR=../.uv-cache uv run pytest -q`
Expected: PASS or a documented pre-existing failure unrelated to this feature.

- [ ] **Step 4: Commit the verification checkpoint**

```bash
git add -A
git commit -m "test: verify forensic incident detail rollout"
```

## Self-Review Checklist

- Spec coverage:
  - public forensic brief: Tasks 3 and 4
  - reviewer-only model provenance: Task 5
  - `DeepSeek Flash V4` real default: Tasks 1 and 2
  - translation sync for every new field: Tasks 2 and 3
  - legacy compatibility and migration safety: Task 3
- Placeholder scan:
  - no `TODO`, `TBD`, or "similar to previous task" shortcuts remain
- Type consistency:
  - canonical field names are `incident_summary`, `what_happened`, `ai_failure_point`, `why_it_matters`, and `evidence_summary` across schema, API, and frontend
