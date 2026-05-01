# Company Name Chinese Translation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `company_involved_zh` field so the daily runner stores Chinese company names and the public Chinese toggle renders them everywhere readers see incident metadata.

**Architecture:** Extend the existing translation data model instead of mutating the canonical `company_involved` field. Persist `company_involved_zh` alongside the other translated fields, expose it through the public incident API, and add a small frontend locale helper so Chinese mode prefers `company_involved_zh` with a clean fallback to `company_involved`.

**Tech Stack:** Python 3, FastAPI, psycopg, Pydantic, React 19, TypeScript, Vitest, Testing Library

---

### Task 1: Add the schema and model contract for `company_involved_zh`

**Files:**
- Modify: `backend/tests/db/test_schema_bootstrap.py`
- Modify: `backend/app/models/incident.py`
- Modify: `backend/app/db/postgres_repository.py`
- Modify: `infra/supabase/migrations/20260429170000_initial_incident_schema.sql`
- Test: `backend/tests/db/test_schema_bootstrap.py`

- [ ] **Step 1: Write the failing schema and model assertions**

```python
def test_postgres_schema_defines_claim_sources_notes_and_core_tables() -> None:
    normalized = _POSTGRES_SCHEMA.lower()
    assert "company_involved_zh text" in normalized


def test_initial_migration_bootstraps_same_core_tables() -> None:
    migration_sql = migration_path.read_text().lower()
    assert "company_involved_zh text" in migration_sql


def test_incident_claim_and_source_models_capture_mvp_schema() -> None:
    incident = IncidentRecord(
        id="incident-1",
        external_id="inc-openai-001",
        headline="Agent rollout causes bad customer escalations",
        date_logged=date(2026, 4, 29),
        company_involved="OpenAI",
        company_involved_zh="开放人工智能",
        incident_topic="job automation",
        claimant_name="OpenAI",
        categories=["Job Automation Fails", "Missed Timelines"],
        severity_score=4,
        reality_summary="A supervised launch produced repeated escalations.",
    )

    assert incident.company_involved_zh == "开放人工智能"
```

- [ ] **Step 2: Run the schema test to verify it fails**

Run: `cd /Users/leo/Desktop/AI_Oops/backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/db/test_schema_bootstrap.py -q`
Expected: FAIL because the schema, migration, and `IncidentRecord` do not define `company_involved_zh` yet.

- [ ] **Step 3: Add the minimal schema and model support**

```python
class IncidentRecord(BaseModel):
    id: str
    external_id: str | None = None
    headline: str
    headline_en: str | None = None
    headline_zh: str | None = None
    date_logged: date
    company_involved: str
    company_involved_zh: str | None = None
    incident_topic: str | None = None
```

```sql
create table if not exists incident_logs (
    id text primary key,
    external_id text,
    headline text not null,
    headline_en text,
    headline_zh text,
    date_logged date not null,
    company_involved text not null,
    company_involved_zh text,
    incident_topic text,
    claimant_name text,
    categories text not null default '[]',
    severity_score integer not null,
    reality_summary text not null,
    status text not null
);
```

- [ ] **Step 4: Re-run the schema test to verify it passes**

Run: `cd /Users/leo/Desktop/AI_Oops/backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/db/test_schema_bootstrap.py -q`
Expected: PASS

- [ ] **Step 5: Commit the schema contract**

```bash
git add backend/tests/db/test_schema_bootstrap.py backend/app/models/incident.py backend/app/db/postgres_repository.py infra/supabase/migrations/20260429170000_initial_incident_schema.sql
git commit -m "feat: add chinese company field to incident schema"
```

### Task 2: Extend the translation workflow to produce and persist `company_involved_zh`

**Files:**
- Modify: `backend/tests/services/test_incident_review.py`
- Modify: `backend/tests/workflows/test_incident_csv_workflow.py`
- Modify: `backend/tests/support/fakes.py`
- Modify: `backend/app/services/incident_translation.py`
- Modify: `backend/app/services/incident_review.py`
- Test: `backend/tests/services/test_incident_review.py`
- Test: `backend/tests/workflows/test_incident_csv_workflow.py`

- [ ] **Step 1: Write the failing workflow tests**

```python
class FakeTranslationClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, str, str]] = []

    def translate(
        self,
        *,
        headline_en: str,
        company_involved_en: str,
        reality_summary_en: str,
        legitimacy_reasoning_en: str,
        source_validation_summary_en: str,
    ) -> IncidentTranslation:
        self.calls.append(
            (
                headline_en,
                company_involved_en,
                reality_summary_en,
                legitimacy_reasoning_en,
                source_validation_summary_en,
            )
        )
        return IncidentTranslation(
            headline_zh=f"ZH:{headline_en}",
            company_involved_zh=f"ZH:{company_involved_en}",
            reality_summary_zh=f"ZH:{reality_summary_en}",
            legitimacy_reasoning_zh=f"ZH:{legitimacy_reasoning_en}",
            source_validation_summary_zh=f"ZH:{source_validation_summary_en}",
            status="completed",
        )


assert approved_incident["company_involved_zh"] == "ZH:OpenAI"
assert translation_client.calls == [
    (
        "OpenAI filing included fake legal citations",
        "OpenAI",
        "Court records confirm the filing incident.",
        "Strong source support.",
        "3 fetched sources agree on the event.",
    )
]
```

- [ ] **Step 2: Run the workflow-focused tests to verify they fail**

Run: `cd /Users/leo/Desktop/AI_Oops/backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/services/test_incident_review.py tests/workflows/test_incident_csv_workflow.py -q`
Expected: FAIL because the translation contract and review application path do not accept or store `company_involved_zh`.

- [ ] **Step 3: Update the translation contract and review application**

```python
@dataclass(frozen=True)
class IncidentTranslation:
    headline_zh: str
    company_involved_zh: str
    reality_summary_zh: str
    legitimacy_reasoning_zh: str
    source_validation_summary_zh: str
    status: str = "completed"


class IncidentTranslationClient(Protocol):
    def translate(
        self,
        *,
        headline_en: str,
        company_involved_en: str,
        reality_summary_en: str,
        legitimacy_reasoning_en: str,
        source_validation_summary_en: str,
    ) -> IncidentTranslation:
        pass
```

```python
translation = translate_incident_copy(
    headline_en=final_result.headline_en,
    company_involved_en=str(incident["company_involved"]),
    reality_summary_en=final_result.reality_summary_en,
    legitimacy_reasoning_en=final_result.reasoning,
    source_validation_summary_en=final_result.source_quality_summary,
    client=translation_client,
)

repository.update_incident_translation(
    incident_id=incident["id"],
    headline_zh=translation.headline_zh,
    company_involved_zh=translation.company_involved_zh,
    reality_summary_zh=translation.reality_summary_zh,
    legitimacy_reasoning_zh=translation.legitimacy_reasoning_zh,
    source_validation_summary_zh=translation.source_validation_summary_zh,
    translation_status=translation.status,
    translated_at=_now_isoformat(),
)

incident["company_involved_zh"] = translation.company_involved_zh
```

- [ ] **Step 4: Update the in-memory repository helper used by the workflow tests**

```python
def update_incident_translation(
    self,
    *,
    incident_id: str,
    headline_zh: str,
    company_involved_zh: str,
    reality_summary_zh: str,
    legitimacy_reasoning_zh: str,
    source_validation_summary_zh: str,
    translation_status: str,
    translated_at: str,
) -> dict[str, Any] | None:
    incident = self.incidents.get(incident_id)
    if incident is None:
        return None
    incident.update(
        {
            "headline_zh": headline_zh,
            "company_involved_zh": company_involved_zh,
            "reality_summary_zh": reality_summary_zh,
            "legitimacy_reasoning_zh": legitimacy_reasoning_zh,
            "source_validation_summary_zh": source_validation_summary_zh,
            "translation_status": translation_status,
            "translated_at": translated_at,
        }
    )
    return self._serialize_admin_incident(incident)
```

- [ ] **Step 5: Re-run the workflow-focused tests to verify they pass**

Run: `cd /Users/leo/Desktop/AI_Oops/backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/services/test_incident_review.py tests/workflows/test_incident_csv_workflow.py -q`
Expected: PASS

- [ ] **Step 6: Commit the translation workflow change**

```bash
git add backend/tests/services/test_incident_review.py backend/tests/workflows/test_incident_csv_workflow.py backend/tests/support/fakes.py backend/app/services/incident_translation.py backend/app/services/incident_review.py
git commit -m "feat: translate company names in incident workflow"
```

### Task 3: Expose `company_involved_zh` through repository serialization and the public API

**Files:**
- Modify: `backend/tests/db/test_postgres_repository.py`
- Modify: `backend/tests/api/test_incidents_api.py`
- Modify: `backend/app/db/repository_protocol.py`
- Modify: `backend/app/db/postgres_repository.py`
- Modify: `backend/app/api/incidents.py`
- Modify: `backend/tests/support/fakes.py`
- Test: `backend/tests/db/test_postgres_repository.py`
- Test: `backend/tests/api/test_incidents_api.py`

- [ ] **Step 1: Write the failing repository and API assertions**

```python
def test_update_incident_translation_writes_company_translation(monkeypatch) -> None:
    repository.update_incident_translation(
        incident_id="incident-1",
        headline_zh="更新后的标题",
        company_involved_zh="开放人工智能",
        reality_summary_zh="更新后的摘要",
        legitimacy_reasoning_zh="已核实。",
        source_validation_summary_zh="来源充分。",
        translation_status="completed",
        translated_at="2026-05-01T12:00:00+00:00",
    )

    update_query, update_args = next(
        (query, args)
        for query, args in connection.calls
        if "update incident_logs" in query
    )
    params = update_args[0]
    assert "company_involved_zh = %s" in update_query
    assert params[1] == "开放人工智能"


assert payload["items"][1]["company_involved_zh"] == "开放人工智能"
assert detail_response.json()["company_involved_zh"] == "开放人工智能"
```

- [ ] **Step 2: Run the backend contract tests to verify they fail**

Run: `cd /Users/leo/Desktop/AI_Oops/backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/db/test_postgres_repository.py tests/api/test_incidents_api.py -q`
Expected: FAIL because the repository protocol, serializers, and response models do not include `company_involved_zh`.

- [ ] **Step 3: Add the repository and API field**

```python
class IncidentRepository(Protocol):
    def update_incident_translation(
        self,
        *,
        incident_id: str,
        headline_zh: str,
        company_involved_zh: str,
        reality_summary_zh: str,
        legitimacy_reasoning_zh: str,
        source_validation_summary_zh: str,
        translation_status: str,
        translated_at: str,
    ) -> dict[str, Any] | None:
        pass
```

```python
class PublicIncidentBaseResponse(BaseModel):
    id: str
    headline: str
    headline_en: str | None = None
    headline_zh: str | None = None
    date_logged: str
    company_involved: str
    company_involved_zh: str | None = None
    incident_topic: str | None = None
```

```python
return {
    "id": row["id"],
    "headline": row["headline"],
    "headline_en": row.get("headline_en") or row["headline"],
    "headline_zh": row.get("headline_zh"),
    "date_logged": row["date_logged"],
    "company_involved": row["company_involved"],
    "company_involved_zh": row.get("company_involved_zh"),
    "incident_topic": row.get("incident_topic"),
    "claimant_name": row["claimant_name"],
    "categories": json.loads(row["categories"]),
    "severity_score": row["severity_score"],
    "status": row["status"],
    "translation_status": row.get("translation_status"),
}
```

- [ ] **Step 4: Re-run the backend contract tests to verify they pass**

Run: `cd /Users/leo/Desktop/AI_Oops/backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/db/test_postgres_repository.py tests/api/test_incidents_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit the persistence and API change**

```bash
git add backend/tests/db/test_postgres_repository.py backend/tests/api/test_incidents_api.py backend/app/db/repository_protocol.py backend/app/db/postgres_repository.py backend/app/api/incidents.py backend/tests/support/fakes.py
git commit -m "feat: expose chinese company names in public incident api"
```

### Task 4: Render localized company names in the public dashboard

**Files:**
- Modify: `frontend/src/tests/PublicDashboardPage.test.tsx`
- Modify: `frontend/src/types/incident.ts`
- Modify: `frontend/src/pages/PublicDashboardPage.tsx`
- Test: `frontend/src/tests/PublicDashboardPage.test.tsx`

- [ ] **Step 1: Write the failing UI tests**

```tsx
function buildArchiveIncident(
  overrides: Partial<IncidentArchiveItem> = {},
): IncidentArchiveItem {
  return {
    id: overrides.id ?? "incident-1",
    headline: overrides.headline ?? "Customer support bot exposes private account notes",
    headline_en: overrides.headline_en ?? overrides.headline ?? "Customer support bot exposes private account notes",
    headline_zh: overrides.headline_zh ?? "客服机器人泄露了私密账户备注",
    date_logged: overrides.date_logged ?? "2026-04-29",
    company_involved: overrides.company_involved ?? "AssistCo",
    company_involved_zh: overrides.company_involved_zh ?? "助手公司",
    claimant_name: overrides.claimant_name ?? "AssistCo",
    incident_topic: overrides.incident_topic ?? "privacy",
    categories: overrides.categories ?? ["Privacy/Security"],
    severity_score: overrides.severity_score ?? 4,
    archive_summary:
      overrides.archive_summary ??
      "A support automation rollout leaked internal notes into user-facing replies.",
    archive_summary_en:
      overrides.archive_summary_en ??
      overrides.archive_summary ??
      "A support automation rollout leaked internal notes into user-facing replies.",
    archive_summary_zh:
      overrides.archive_summary_zh ??
      "一次支持自动化发布将内部备注泄露给了用户。",
    status: overrides.status ?? "approved",
    translation_status: overrides.translation_status ?? "completed",
  };
}

it("shows chinese company names when the reader locale is zh", async () => {
  mockedFetchIncidentFeed.mockResolvedValueOnce(
    buildFeedResponse([
      buildArchiveIncident({
        id: "incident-zh",
        company_involved: "OpenAI",
        company_involved_zh: "开放人工智能",
      }),
    ]),
  );
  mockedFetchIncidentDetail.mockResolvedValueOnce(
    buildIncidentDetail({
      id: "incident-zh",
      company_involved: "OpenAI",
      company_involved_zh: "开放人工智能",
    }),
  );

  render(<PublicDashboardPage />);
  fireEvent.click(await screen.findByRole("button", { name: "中文" }));

  expect(await screen.findAllByText("开放人工智能")).not.toHaveLength(0);
});

it("falls back to the canonical company name when no chinese company name exists", async () => {
  mockedFetchIncidentFeed.mockResolvedValueOnce(
    buildFeedResponse([
      buildArchiveIncident({
        id: "incident-fallback",
        company_involved: "RoboFleet",
        company_involved_zh: null,
      }),
    ]),
  );

  render(<PublicDashboardPage />);
  fireEvent.click(await screen.findByRole("button", { name: "中文" }));

  expect(await screen.findByText("RoboFleet")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run: `cd /Users/leo/Desktop/AI_Oops/frontend && npm run test -- src/tests/PublicDashboardPage.test.tsx`
Expected: FAIL because the incident types and locale helpers do not know about `company_involved_zh`.

- [ ] **Step 3: Add the frontend field and locale helper**

```ts
export type PublicIncidentBase = {
  id: string;
  headline: string;
  headline_en?: string | null;
  headline_zh?: string | null;
  date_logged: string;
  company_involved: string;
  company_involved_zh?: string | null;
  incident_topic?: string | null;
  claimant_name?: string;
  categories: string[];
  severity_score: number;
  status: string;
  translation_status?: string | null;
};
```

```tsx
function localizedCompany(incident: PublicIncidentBase, locale: ReaderLocale) {
  if (locale === "zh") {
    return incident.company_involved_zh ?? incident.company_involved;
  }

  return incident.company_involved;
}
```

```tsx
<span>{localizedCompany(incident, readerLocale)}</span>
<span>{localizedCompany(incidentDetail, readerLocale)}</span>
```

- [ ] **Step 4: Re-run the frontend test to verify it passes**

Run: `cd /Users/leo/Desktop/AI_Oops/frontend && npm run test -- src/tests/PublicDashboardPage.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit the public UI change**

```bash
git add frontend/src/tests/PublicDashboardPage.test.tsx frontend/src/types/incident.ts frontend/src/pages/PublicDashboardPage.tsx
git commit -m "feat: localize company names in chinese reader mode"
```

### Task 5: Update product docs and run final verification

**Files:**
- Modify: `docs/product/database-schema.md`
- Modify: `docs/product/daily-runner.md`
- Test: `backend/tests/db/test_schema_bootstrap.py`
- Test: `backend/tests/services/test_incident_review.py`
- Test: `backend/tests/workflows/test_incident_csv_workflow.py`
- Test: `backend/tests/db/test_postgres_repository.py`
- Test: `backend/tests/api/test_incidents_api.py`
- Test: `frontend/src/tests/PublicDashboardPage.test.tsx`

- [ ] **Step 1: Update the product docs to mention the new translated company field**

```md
| `company_involved` | Canonical source-language company name |
| `company_involved_zh` | Simplified Chinese company name for reader mode |
```

```md
Approved incidents that finish translation now persist:

- `headline_zh`
- `company_involved_zh`
- `reality_summary_zh`
- `legitimacy_reasoning_zh`
- `source_validation_summary_zh`
```

- [ ] **Step 2: Run the full focused verification suite**

Run: `cd /Users/leo/Desktop/AI_Oops/backend && UV_CACHE_DIR=../.uv-cache uv run pytest tests/db/test_schema_bootstrap.py tests/services/test_incident_review.py tests/workflows/test_incident_csv_workflow.py tests/db/test_postgres_repository.py tests/api/test_incidents_api.py -q`
Expected: PASS

Run: `cd /Users/leo/Desktop/AI_Oops/frontend && npm run test -- src/tests/PublicDashboardPage.test.tsx`
Expected: PASS

Run: `cd /Users/leo/Desktop/AI_Oops/frontend && npm run build`
Expected: PASS with Vite production build output

- [ ] **Step 3: Commit the docs and final verification pass**

```bash
git add docs/product/database-schema.md docs/product/daily-runner.md
git commit -m "docs: document chinese company translation support"
```

## Notes

- Keep the DeepSeek primary-review swap out of this implementation branch. It is a separate provider-integration change and should land in its own spec/plan pair after this field-level localization work ships.
