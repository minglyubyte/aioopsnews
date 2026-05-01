# Internal Review Queue Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add queue collapse/expand controls and date/severity sorting to the internal review page while preserving the existing refresh-after-review behavior.

**Architecture:** Keep the feature local to the internal review page by introducing small UI state for queue visibility and sort mode, then derive queue ordering from a single helper that is reused for selection and refresh flows. Cover the new behavior with focused page tests first, then add only the CSS needed to support the new controls and collapsed state.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, existing global CSS in `frontend/src/index.css`

---

### Task 1: Document the expected queue interactions with tests

**Files:**
- Modify: `frontend/src/tests/InternalReviewPage.test.tsx`
- Test: `frontend/src/tests/InternalReviewPage.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
it("collapses and expands the review queue", async () => {
  render(<InternalReviewPage />);

  fireEvent.change(screen.getByLabelText("Admin token"), {
    target: { value: "editor-token" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Unlock admin" }));

  const queue = await screen.findByRole("region", { name: "Review queue" });
  expect(
    within(queue).getByRole("button", {
      name: /Open review for AssistCo exposed private account notes/i,
    }),
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Collapse queue" }));
  expect(
    within(queue).queryByRole("button", {
      name: /Open review for AssistCo exposed private account notes/i,
    }),
  ).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Expand queue" }));
  expect(
    within(queue).getByRole("button", {
      name: /Open review for AssistCo exposed private account notes/i,
    }),
  ).toBeInTheDocument();
});

it("sorts queue items by highest severity first when requested", async () => {
  mockedFetchAdminIncidentQueue.mockResolvedValueOnce({
    items: [
      buildAdminIncident({
        id: "incident-low",
        headline: "Lower severity incident",
        headline_en: "Lower severity incident",
        suggested_severity_score: 2,
        severity_score: 2,
        date_logged: "2026-06-02",
      }),
      buildAdminIncident({
        id: "incident-high",
        headline: "Higher severity incident",
        headline_en: "Higher severity incident",
        suggested_severity_score: 5,
        severity_score: 5,
        date_logged: "2026-05-01",
      }),
    ],
  });

  render(<InternalReviewPage />);

  fireEvent.change(screen.getByLabelText("Admin token"), {
    target: { value: "sort-token" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Unlock admin" }));

  const queue = await screen.findByRole("region", { name: "Review queue" });
  fireEvent.change(screen.getByLabelText("Sort queue"), {
    target: { value: "severity" },
  });

  const queueButtons = within(queue).getAllByRole("button");
  expect(within(queueButtons[0]).getByText("Higher severity incident")).toBeInTheDocument();
  expect(within(queueButtons[1]).getByText("Lower severity incident")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test -- src/tests/InternalReviewPage.test.tsx`
Expected: FAIL because the collapse/expand control and sort control do not exist yet.

- [ ] **Step 3: Commit the failing tests**

```bash
git add frontend/src/tests/InternalReviewPage.test.tsx
git commit -m "test: cover internal review queue controls"
```

### Task 2: Implement queue visibility and sort mode

**Files:**
- Modify: `frontend/src/pages/InternalReviewPage.tsx`
- Test: `frontend/src/tests/InternalReviewPage.test.tsx`

- [ ] **Step 1: Write the minimal implementation**

```tsx
const [isQueueCollapsed, setIsQueueCollapsed] = useState(false);
const [queueSortMode, setQueueSortMode] = useState<"date" | "severity">("date");

const sortedAdminIncidents = sortAdminIncidents(adminIncidents, queueSortMode);

<div className="internal-review-queue-controls">
  <label className="field internal-review-sort-field">
    <span>Sort queue</span>
    <select
      aria-label="Sort queue"
      value={queueSortMode}
      onChange={(event) => setQueueSortMode(event.target.value as "date" | "severity")}
    >
      <option value="date">Date (newest first)</option>
      <option value="severity">Severity (highest first)</option>
    </select>
  </label>
  <button
    className="secondary-action internal-review-queue-toggle"
    type="button"
    onClick={() => setIsQueueCollapsed((current) => !current)}
  >
    {isQueueCollapsed ? "Expand queue" : "Collapse queue"}
  </button>
</div>

{!isQueueCollapsed ? (
  <div className="public-archive-list internal-review-queue-list">
    {/* existing queue cards */}
  </div>
) : null}
```

- [ ] **Step 2: Update the sort helper**

```tsx
function sortAdminIncidents(
  incidents: AdminIncident[],
  sortMode: "date" | "severity" = "date",
): AdminIncident[] {
  return [...incidents].sort((left, right) => {
    if (sortMode === "severity") {
      const leftSeverity = left.suggested_severity_score ?? left.severity_score;
      const rightSeverity = right.suggested_severity_score ?? right.severity_score;

      if (rightSeverity !== leftSeverity) {
        return rightSeverity - leftSeverity;
      }
    }

    return right.date_logged.localeCompare(left.date_logged);
  });
}
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `npm run test -- src/tests/InternalReviewPage.test.tsx`
Expected: PASS with the new collapse/expand and severity sort tests green.

- [ ] **Step 4: Commit the implementation**

```bash
git add frontend/src/pages/InternalReviewPage.tsx frontend/src/tests/InternalReviewPage.test.tsx
git commit -m "feat: add internal review queue controls"
```

### Task 3: Style the new queue controls and collapsed state

**Files:**
- Modify: `frontend/src/index.css`
- Test: `frontend/src/tests/InternalReviewPage.test.tsx`

- [ ] **Step 1: Add minimal styles for the new controls**

```css
.internal-review-queue-toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: end;
  gap: 0.75rem 1rem;
  margin-bottom: 1rem;
}

.internal-review-sort-field {
  min-width: min(18rem, 100%);
}

.internal-review-sort-field span {
  font-size: 0.82rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.internal-review-queue-toggle {
  margin-top: 0;
}

.internal-review-queue-collapsed-note {
  margin: 0;
  color: #556c86;
}
```

- [ ] **Step 2: Run the focused tests again**

Run: `npm run test -- src/tests/InternalReviewPage.test.tsx`
Expected: PASS

- [ ] **Step 3: Run the frontend build**

Run: `npm run build`
Expected: PASS with Vite production build output

- [ ] **Step 4: Commit the styling and verification**

```bash
git add frontend/src/index.css
git commit -m "style: polish internal review queue controls"
```
