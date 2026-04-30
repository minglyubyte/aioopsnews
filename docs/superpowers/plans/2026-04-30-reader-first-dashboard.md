# Reader-First Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the live frontend into a demo-style public dashboard on `/` while moving staff review tools to a hidden `/internal` route.

**Architecture:** Keep the existing API layer and simple pathname-based entry switch in `frontend/src/main.tsx`. Split the current mixed `App.tsx` into a reader-first public page and a staff-only internal page, then restyle the public page by reusing the demo dashboard's visual language and layout patterns without changing backend behavior.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, existing fetch-based API helpers, existing demo CSS and data-driven frontend state.

---

## File Structure

- Create: `frontend/src/pages/PublicDashboardPage.tsx`
  - Reader-facing homepage using live incident/filter/detail data.
- Create: `frontend/src/pages/InternalReviewPage.tsx`
  - Staff-only review page using admin queue APIs and approval actions.
- Create: `frontend/src/pages/public-dashboard.css`
  - Public page styles derived from the demo dashboard tone and layout.
- Modify: `frontend/src/main.tsx`
  - Route switch for `/`, `/demo`, and `/internal`.
- Modify: `frontend/src/lib/api.ts`
  - Keep current API calls, optionally extract shared helpers only if needed by the split pages.
- Modify: `frontend/src/types/incident.ts`
  - Add duplicate/admin fields already returned by backend so `/internal` can display them.
- Modify: `frontend/src/index.css`
  - Remove obsolete mixed-page layout styles only after the new page stylesheet covers the public experience.
- Modify: `frontend/src/tests/App.test.tsx`
  - Keep route-level regression coverage if it is still the central integration test file.
- Create: `frontend/src/tests/PublicDashboardPage.test.tsx`
  - Public route behavior and rendering coverage.
- Create: `frontend/src/tests/InternalReviewPage.test.tsx`
  - Hidden internal route behavior and admin-only rendering coverage.

## Task 1: Split Route Entry And Type Surface

**Files:**
- Create: `frontend/src/pages/PublicDashboardPage.tsx`
- Create: `frontend/src/pages/InternalReviewPage.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/types/incident.ts`
- Test: `frontend/src/tests/PublicDashboardPage.test.tsx`

- [ ] **Step 1: Write the failing route/type test**

```tsx
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

vi.mock("../lib/api", () => ({
  fetchIncidentFeed: vi.fn().mockResolvedValue({ items: [] }),
  fetchIncidentFilters: vi.fn().mockResolvedValue({
    categories: [],
    claimants: [],
    companies: [],
    years: [],
    months_by_year: {},
  }),
  fetchIncidentDetail: vi.fn(),
  fetchAdminIncidentQueue: vi.fn(),
  updateAdminIncident: vi.fn(),
}));

it("renders the public dashboard on the root route and hides admin controls", async () => {
  window.history.pushState({}, "", "/");

  const { default: AppEntry } = await import("../main");
  render(<AppEntry />);

  expect(await screen.findByRole("heading", { name: "AI Reality Check" })).toBeInTheDocument();
  expect(screen.queryByText("Editor queue")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/tests/PublicDashboardPage.test.tsx`

Expected: FAIL because `main.tsx` does not export a renderable route entry component and the public/admin split does not exist yet.

- [ ] **Step 3: Write the minimal route split and type surface**

```tsx
// frontend/src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import DemoDashboard from "./demo/DemoDashboard";
import InternalReviewPage from "./pages/InternalReviewPage";
import PublicDashboardPage from "./pages/PublicDashboardPage";
import "./index.css";

export function AppEntry() {
  const path = window.location.pathname;

  if (path === "/demo") {
    return <DemoDashboard />;
  }

  if (path === "/internal") {
    return <InternalReviewPage />;
  }

  return <PublicDashboardPage />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppEntry />
  </React.StrictMode>,
);
```

```ts
// frontend/src/types/incident.ts
export type DuplicateCandidate = {
  candidate_incident_id: string;
  embedding_score: number;
  llm_verdict: string;
  confidence: number;
  reasoning?: string;
  status: string;
};

export type AdminIncident = Incident & {
  claimant_name?: string | null;
  matched_claim_id?: string | null;
  claim_match_confidence?: number | null;
  review_notes?: string | null;
  legitimacy_score?: number | null;
  legitimacy_label?: string | null;
  legitimacy_reasoning?: string | null;
  source_validation_summary?: string | null;
  review_batch_id?: string | null;
  review_model?: string | null;
  duplicate_status?: string | null;
  duplicate_of_incident_id?: string | null;
  canonical_incident_id?: string | null;
  duplicate_candidates?: DuplicateCandidate[];
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/tests/PublicDashboardPage.test.tsx`

Expected: PASS once the route entry exports a root-renderable component and `/` no longer depends on the mixed `App.tsx`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/main.tsx frontend/src/types/incident.ts frontend/src/pages/PublicDashboardPage.tsx frontend/src/pages/InternalReviewPage.tsx frontend/src/tests/PublicDashboardPage.test.tsx
git commit -m "feat: split public and internal frontend routes"
```

## Task 2: Build The Public Dashboard From Live Data

**Files:**
- Modify: `frontend/src/pages/PublicDashboardPage.tsx`
- Create: `frontend/src/pages/public-dashboard.css`
- Modify: `frontend/src/lib/api.ts`
- Test: `frontend/src/tests/PublicDashboardPage.test.tsx`

- [ ] **Step 1: Write the failing public dashboard behavior test**

```tsx
it("renders a featured incident, archive list, filters, and source-backed detail", async () => {
  fetchIncidentFeed.mockResolvedValue({
    items: [
      {
        id: "incident-1",
        headline: "Court filing included fake legal citations",
        headline_en: "Court filing included fake legal citations",
        headline_zh: "法院文件包含虚假法律引文",
        date_logged: "2023-05-03",
        company_involved: "OpenAI",
        categories: ["legal hallucination"],
        severity_score: 3,
        reality_summary: "Readers need the spotlight summary.",
        reality_summary_en: "Readers need the spotlight summary.",
        reality_summary_zh: "读者需要聚焦摘要。",
        status: "approved",
        sources: [],
      },
    ],
  });

  render(<PublicDashboardPage />);

  expect(await screen.findByText("Incident signals")).toBeInTheDocument();
  expect(screen.getByText("Latest entries")).toBeInTheDocument();
  expect(screen.getByText("Court filing included fake legal citations")).toBeInTheDocument();
  expect(screen.queryByText("Editor queue")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/tests/PublicDashboardPage.test.tsx`

Expected: FAIL because `PublicDashboardPage` is still empty or does not yet load live feed/filter/detail state.

- [ ] **Step 3: Write the minimal public page implementation**

```tsx
// frontend/src/pages/PublicDashboardPage.tsx
import { useEffect, useState } from "react";
import {
  fetchIncidentDetail,
  fetchIncidentFeed,
  fetchIncidentFilters,
} from "../lib/api";
import type { Incident, IncidentFeedFilters, IncidentFilters } from "../types/incident";
import "./public-dashboard.css";

export default function PublicDashboardPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [filters, setFilters] = useState<IncidentFilters | null>(null);
  const [readerFilters, setReaderFilters] = useState<IncidentFeedFilters>({});
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);
  const [incidentDetail, setIncidentDetail] = useState<Incident | null>(null);

  useEffect(() => {
    void fetchIncidentFilters().then(setFilters);
  }, []);

  useEffect(() => {
    void fetchIncidentFeed(readerFilters).then((response) => {
      setIncidents(response.items);
      setSelectedIncidentId((current) => current ?? response.items[0]?.id ?? null);
    });
  }, [readerFilters]);

  useEffect(() => {
    if (!selectedIncidentId) return;
    void fetchIncidentDetail(selectedIncidentId).then(setIncidentDetail);
  }, [selectedIncidentId]);

  const featuredIncident = incidents[0] ?? null;

  return (
    <main className="public-dashboard-shell">
      <section className="public-hero-card">
        <p className="demo-kicker">AI Reality Check</p>
        <h1>AI Reality Check</h1>
        <p className="public-hero-copy">
          A calm, source-backed archive of reviewed AI failures.
        </p>
      </section>

      <section className="public-signals-card">
        <h2>Incident signals</h2>
      </section>

      {featuredIncident ? (
        <section className="public-spotlight-card">
          <p className="demo-kicker">Incident spotlight</p>
          <h2>{featuredIncident.headline_en ?? featuredIncident.headline}</h2>
          <p>{featuredIncident.reality_summary_en ?? featuredIncident.reality_summary}</p>
        </section>
      ) : null}

      <section className="public-archive-card">
        <h2>Latest entries</h2>
        <div className="public-filter-grid">{filters ? "filters" : null}</div>
        <div className="public-incident-list">
          {incidents.map((incident) => (
            <button key={incident.id} type="button" onClick={() => setSelectedIncidentId(incident.id)}>
              {incident.headline_en ?? incident.headline}
            </button>
          ))}
        </div>
      </section>

      {incidentDetail ? (
        <section className="public-detail-card">
          <h2>Incident detail</h2>
          <h3>{incidentDetail.headline_en ?? incidentDetail.headline}</h3>
        </section>
      ) : null}
    </main>
  );
}
```

```css
/* frontend/src/pages/public-dashboard.css */
.public-dashboard-shell {
  min-height: 100vh;
  padding: 2rem;
  display: grid;
  gap: 1.5rem;
  background:
    radial-gradient(circle at top left, rgba(243, 229, 207, 0.92), transparent 28%),
    linear-gradient(180deg, #f5efe4 0%, #ece3d5 42%, #dfe5eb 100%);
  color: #17263a;
}

.public-hero-card,
.public-signals-card,
.public-spotlight-card,
.public-archive-card,
.public-detail-card {
  width: min(100%, 74rem);
  margin: 0 auto;
  padding: 2rem;
  border-radius: 1.5rem;
  background: rgba(255, 252, 247, 0.82);
  border: 1px solid rgba(23, 38, 58, 0.08);
  box-shadow: 0 18px 55px rgba(23, 38, 58, 0.1);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/tests/PublicDashboardPage.test.tsx`

Expected: PASS with the public page showing live-data sections and no admin controls on `/`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/PublicDashboardPage.tsx frontend/src/pages/public-dashboard.css frontend/src/tests/PublicDashboardPage.test.tsx
git commit -m "feat: build reader-first public dashboard"
```

## Task 3: Move Staff Review To `/internal`

**Files:**
- Modify: `frontend/src/pages/InternalReviewPage.tsx`
- Modify: `frontend/src/lib/api.ts`
- Test: `frontend/src/tests/InternalReviewPage.test.tsx`

- [ ] **Step 1: Write the failing internal route test**

```tsx
it("renders admin review data only on the internal route", async () => {
  fetchAdminIncidentQueue.mockResolvedValue({
    items: [
      {
        id: "incident-queue-1",
        headline: "Queued incident",
        date_logged: "2023-05-03",
        company_involved: "OpenAI",
        categories: [],
        severity_score: 3,
        reality_summary: "Needs review",
        status: "pending_review",
        sources: [],
        legitimacy_score: 0.74,
        legitimacy_label: "pending_review",
        legitimacy_reasoning: "Needs editor review",
        source_validation_summary: "Validated 3 distinct sources.",
        duplicate_status: null,
        duplicate_candidates: [],
      },
    ],
  });

  render(<InternalReviewPage />);

  expect(await screen.findByText("Editor queue")).toBeInTheDocument();
  expect(screen.getByText("Queued incident")).toBeInTheDocument();
  expect(screen.queryByText("Incident spotlight")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/tests/InternalReviewPage.test.tsx`

Expected: FAIL because the internal page has not yet been extracted from the old mixed app.

- [ ] **Step 3: Write the minimal internal page implementation**

```tsx
// frontend/src/pages/InternalReviewPage.tsx
import { useEffect, useState } from "react";
import {
  fetchAdminIncidentQueue,
  updateAdminIncident,
} from "../lib/api";
import type { AdminIncident } from "../types/incident";

const ADMIN_TOKEN_STORAGE_KEY = "ai-reality-check-admin-token";

export default function InternalReviewPage() {
  const [adminToken, setAdminToken] = useState<string | null>(
    () => window.localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY),
  );
  const [adminTokenInput, setAdminTokenInput] = useState(adminToken ?? "");
  const [adminIncidents, setAdminIncidents] = useState<AdminIncident[]>([]);

  useEffect(() => {
    if (!adminToken) return;
    void fetchAdminIncidentQueue(adminToken).then((response) => {
      setAdminIncidents(response.items);
    });
  }, [adminToken]);

  async function handleApprove(incident: AdminIncident) {
    if (!adminToken) return;
    const updated = await updateAdminIncident(adminToken, incident.id, {
      status: "approved",
      company_involved: incident.company_involved,
      claimant_name: incident.claimant_name ?? null,
      categories: incident.categories,
      severity_score: incident.severity_score,
      reality_summary: incident.reality_summary,
      matched_claim_id: incident.matched_claim_id ?? null,
      claim_match_confidence: incident.claim_match_confidence ?? null,
      review_notes: incident.review_notes ?? "",
    });
    setAdminIncidents((current) =>
      current.map((item) => (item.id === updated.id ? updated : item)),
    );
  }

  return (
    <main className="page-shell">
      <section className="feed-card">
        <p className="section-kicker">Internal review</p>
        <h1>Editor queue</h1>
        <form
          className="admin-auth-form"
          onSubmit={(event) => {
            event.preventDefault();
            window.localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, adminTokenInput.trim());
            setAdminToken(adminTokenInput.trim() || null);
          }}
        >
          <label className="field">
            <span>Admin token</span>
            <input value={adminTokenInput} onChange={(event) => setAdminTokenInput(event.target.value)} />
          </label>
          <button className="secondary-action" type="submit">Unlock admin</button>
        </form>
        <div className="review-grid">
          {adminIncidents.map((incident) => (
            <article className="incident-item" key={incident.id}>
              <h3>{incident.headline}</h3>
              <p>{incident.reality_summary}</p>
              <p>{incident.legitimacy_reasoning}</p>
              <p>{incident.source_validation_summary}</p>
              <p>{incident.duplicate_status ?? "no duplicate flag"}</p>
              <button className="primary-action" type="button" onClick={() => void handleApprove(incident)}>
                Approve Incident
              </button>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/tests/InternalReviewPage.test.tsx`

Expected: PASS with staff review appearing on `/internal` and absent from `/`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/InternalReviewPage.tsx frontend/src/tests/InternalReviewPage.test.tsx
git commit -m "feat: move staff review into internal route"
```

## Task 4: Bring The Public Styling In Line With The Demo

**Files:**
- Modify: `frontend/src/pages/PublicDashboardPage.tsx`
- Modify: `frontend/src/pages/public-dashboard.css`
- Modify: `frontend/src/index.css`
- Test: `frontend/src/tests/PublicDashboardPage.test.tsx`

- [ ] **Step 1: Write the failing visual-structure regression test**

```tsx
it("renders the featured spotlight, archive region, and source trail sections", async () => {
  render(<PublicDashboardPage />);

  expect(await screen.findByText("Incident spotlight")).toBeInTheDocument();
  expect(screen.getByText("Latest entries")).toBeInTheDocument();
  expect(screen.getByText("Incident detail")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- src/tests/PublicDashboardPage.test.tsx`

Expected: FAIL because the public page still uses a minimal scaffold and not the approved section hierarchy.

- [ ] **Step 3: Write the minimal style and layout adaptation**

```tsx
// frontend/src/pages/PublicDashboardPage.tsx
<main className="public-dashboard-shell">
  <div className="public-dashboard-frame">
    <section className="public-hero-card">...</section>
    <section className="public-signals-card">...</section>
    <section className="public-main-grid">
      <section className="public-feed-column">
        <article className="public-spotlight-card">
          <p className="demo-kicker">Incident spotlight</p>
          ...
        </article>
        <section className="public-archive-card">
          <p className="demo-kicker">Reviewed incidents</p>
          <h2>Latest entries</h2>
          ...
        </section>
      </section>
      <aside className="public-detail-column">
        <section className="public-detail-card">
          <p className="demo-kicker">Incident detail</p>
          ...
        </section>
      </aside>
    </section>
  </div>
</main>
```

```css
/* frontend/src/pages/public-dashboard.css */
.public-dashboard-frame {
  width: min(100%, 84rem);
  margin: 0 auto;
  display: grid;
  gap: 1.5rem;
}

.public-main-grid {
  display: grid;
  gap: 1.5rem;
}

.public-feed-column,
.public-detail-column {
  display: grid;
  gap: 1.5rem;
}

.public-incident-button {
  width: 100%;
  padding: 1.2rem 0;
  border: 0;
  border-top: 1px solid rgba(23, 38, 58, 0.08);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.public-source-link {
  color: #17263a;
  text-underline-offset: 0.16em;
}

@media (min-width: 1024px) {
  .public-main-grid {
    grid-template-columns: minmax(0, 1.4fr) minmax(20rem, 0.9fr);
    align-items: start;
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- src/tests/PublicDashboardPage.test.tsx`

Expected: PASS with the public page reflecting the approved demo-style hierarchy.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/PublicDashboardPage.tsx frontend/src/pages/public-dashboard.css frontend/src/index.css frontend/src/tests/PublicDashboardPage.test.tsx
git commit -m "feat: adapt public dashboard styling from demo"
```

## Task 5: Final Regression Coverage And Cleanup

**Files:**
- Modify: `frontend/src/tests/App.test.tsx`
- Modify: `frontend/src/tests/PublicDashboardPage.test.tsx`
- Modify: `frontend/src/tests/InternalReviewPage.test.tsx`

- [ ] **Step 1: Write the failing regression tests**

```tsx
it("does not render the admin token form on the public route", async () => {
  window.history.pushState({}, "", "/");
  render(<AppEntry />);

  expect(await screen.findByRole("heading", { name: "AI Reality Check" })).toBeInTheDocument();
  expect(screen.queryByLabelText("Admin token")).not.toBeInTheDocument();
});

it("renders duplicate metadata on the internal route when present", async () => {
  render(<InternalReviewPage />);

  expect(await screen.findByText("no duplicate flag")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- src/tests/App.test.tsx src/tests/PublicDashboardPage.test.tsx src/tests/InternalReviewPage.test.tsx`

Expected: FAIL until the route split, duplicate admin fields, and page-specific assertions are all aligned.

- [ ] **Step 3: Write the minimal regression fixes**

```tsx
// frontend/src/tests/App.test.tsx
window.history.pushState({}, "", "/internal");
render(<AppEntry />);
expect(await screen.findByText("Editor queue")).toBeInTheDocument();

window.history.pushState({}, "", "/");
render(<AppEntry />);
expect(screen.queryByText("Editor queue")).not.toBeInTheDocument();
```

```tsx
// frontend/src/tests/InternalReviewPage.test.tsx
expect(screen.getByText(/Translation/i)).toBeInTheDocument();
expect(screen.getByText(/duplicate/i)).toBeInTheDocument();
```

- [ ] **Step 4: Run the full frontend verification**

Run: `cd frontend && npm test`
Expected: PASS

Run: `cd frontend && npm run lint`
Expected: PASS

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/tests/App.test.tsx frontend/src/tests/PublicDashboardPage.test.tsx frontend/src/tests/InternalReviewPage.test.tsx
git commit -m "test: lock in public and internal dashboard split"
```

## Self-Review

- Spec coverage:
  - public demo-style homepage is covered by Tasks 2 and 4
  - hidden `/internal` route is covered by Tasks 1 and 3
  - latest incidents + archive behavior is covered by Tasks 2 and 4
  - source transparency and incident detail are covered by Task 2
  - duplicate metadata visibility for staff is covered by Tasks 1, 3, and 5
- Placeholder scan:
  - removed public text-search work from V1
  - all tasks include file paths, test commands, and concrete code snippets
- Type consistency:
  - route entry is `AppEntry`
  - public page is `PublicDashboardPage`
  - internal page is `InternalReviewPage`
  - admin duplicate fields use the same names as backend responses
