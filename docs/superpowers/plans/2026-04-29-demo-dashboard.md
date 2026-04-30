# Demo Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a polished `/demo` route in the existing frontend that showcases an editorial mock dashboard backed by a typed local dataset without changing the live API-driven app.

**Architecture:** Introduce a lightweight pathname-based route switch at the app entry level, keep the existing `App` for the live product surface, and build the `/demo` experience from isolated demo components, local mock data, and dedicated CSS. The demo route will be presentation-first, with local selected-card state driving a featured incident detail spotlight.

**Tech Stack:** React, TypeScript, CSS, Vitest, Testing Library

---

## File Map

- Modify: `frontend/src/main.tsx`
  - Add a simple pathname-based route switch between the live app and the `/demo` dashboard.
- Add: `frontend/src/demo/demo-types.ts`
  - Typed shapes for mock incidents, spotlight content, and dashboard stats.
- Add: `frontend/src/demo/demo-data.ts`
  - Curated local mock dataset for the `/demo` route.
- Add: `frontend/src/demo/DemoDashboard.tsx`
  - Main presentation route with hero, rails, feed, spotlight, and local selection state.
- Add: `frontend/src/demo/demo.css`
  - Dedicated styles for the mock dashboard.
- Modify: `frontend/src/App.test.tsx`
  - Add `/demo` rendering coverage while preserving the live-route tests.

### Task 1: Route Switch and Demo Render Test

**Files:**
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/main.tsx`
- Add: `frontend/src/demo/DemoDashboard.tsx`

- [ ] **Step 1: Write the failing `/demo` route test**

```tsx
it("renders the demo dashboard route with hero copy and featured incident content", async () => {
  window.history.pushState({}, "", "/demo");

  renderApp();

  expect(
    screen.getByRole("heading", { name: "AI failures, without the hype cycle" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("AssistCo assistant exposes private billing notes"),
  ).toBeInTheDocument();
  expect(screen.getByText("Claim vs. reality")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Incident spotlight" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run: `npm test -- src/App.test.tsx`
Expected: FAIL because `/demo` does not exist yet.

- [ ] **Step 3: Write the minimal route switch and placeholder demo component**

```tsx
const path = window.location.pathname;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {path === "/demo" ? <DemoDashboard /> : <App />}
  </React.StrictMode>,
);
```

- [ ] **Step 4: Run the frontend test to verify it passes**

Run: `npm test -- src/App.test.tsx`
Expected: PASS

### Task 2: Typed Mock Dataset and Local Selection Flow

**Files:**
- Add: `frontend/src/demo/demo-types.ts`
- Add: `frontend/src/demo/demo-data.ts`
- Add: `frontend/src/demo/DemoDashboard.tsx`
- Modify: `frontend/src/App.test.tsx`

- [ ] **Step 1: Write the failing selection-state test**

```tsx
it("updates the incident spotlight when a different demo card is selected", async () => {
  window.history.pushState({}, "", "/demo");

  renderApp();
  fireEvent.click(
    screen.getByRole("button", {
      name: "Open incident detail for RoboFleet robot pilot rollback follows navigation failures",
    }),
  );

  expect(
    screen.getByRole("heading", {
      name: "RoboFleet robot pilot rollback follows navigation failures",
    }),
  ).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run: `npm test -- src/App.test.tsx`
Expected: FAIL because the demo dashboard has no typed dataset or card-selection behavior yet.

- [ ] **Step 3: Write the minimal typed mock data and selection logic**

```tsx
const [selectedIncidentId, setSelectedIncidentId] = useState(demoIncidents[0].id);
const selectedIncident =
  demoIncidents.find((incident) => incident.id === selectedIncidentId) ?? demoIncidents[0];
```

- [ ] **Step 4: Run the frontend test to verify it passes**

Run: `npm test -- src/App.test.tsx`
Expected: PASS

### Task 3: Visual Polish and Dedicated Demo CSS

**Files:**
- Add: `frontend/src/demo/demo.css`
- Modify: `frontend/src/demo/DemoDashboard.tsx`

- [ ] **Step 1: Build the final dashboard structure**

```tsx
<main className="demo-shell">
  <section className="demo-hero">...</section>
  <section className="demo-grid">
    <aside className="demo-rail">...</aside>
    <section className="demo-feed">...</section>
    <aside className="demo-sidebar">...</aside>
  </section>
  <section className="demo-spotlight">...</section>
</main>
```

- [ ] **Step 2: Add the dedicated visual system in `demo.css`**

```css
.demo-shell {
  background: radial-gradient(circle at top, #f5efe4 0%, #efe7d8 38%, #dfe4ea 100%);
}
```

- [ ] **Step 3: Run the focused frontend tests**

Run: `npm test -- src/App.test.tsx`
Expected: PASS

### Task 4: Full Verification

**Files:**
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/App.test.tsx`
- Add: `frontend/src/demo/demo-types.ts`
- Add: `frontend/src/demo/demo-data.ts`
- Add: `frontend/src/demo/DemoDashboard.tsx`
- Add: `frontend/src/demo/demo.css`

- [ ] **Step 1: Run frontend checks**

Run: `npm run format`
Expected: PASS

Run: `npm run lint`
Expected: PASS

Run: `npm test`
Expected: PASS

Run: `npm run build`
Expected: PASS

- [ ] **Step 2: Confirm branch state**

Run: `git status --short`
Expected: Only the intended frontend demo-route files are modified or added.
