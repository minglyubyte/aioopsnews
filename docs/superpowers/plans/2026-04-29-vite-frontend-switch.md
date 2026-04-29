# Vite Frontend Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current Next.js frontend scaffold with a Vite + React + TypeScript scaffold while keeping the existing backend bootstrap and repo layout intact.

**Architecture:** Rewrite only `frontend/` and the shared files that reference frontend tooling. The backend, env template, and overall monorepo shape stay the same, but the frontend moves from a file-system-routed Next.js app to a client-rendered Vite entrypoint with a small React app shell and Vitest-based smoke coverage.

**Tech Stack:** Vite, React, TypeScript, Vitest, Testing Library, ESLint, Prettier, GitHub Actions, FastAPI.

---

## File Structure

### Files to Remove

- `frontend/app/page.tsx`
- `frontend/app/layout.tsx`
- `frontend/app/globals.css`
- `frontend/jest.config.js`
- `frontend/jest.setup.ts`
- `frontend/next-env.d.ts`
- `frontend/next.config.ts`
- `frontend/.eslintrc.json`

### Files to Create

- `frontend/index.html`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/index.css`
- `frontend/src/App.test.tsx`
- `frontend/vite.config.ts`
- `frontend/vitest.config.ts`
- `frontend/vitest.setup.ts`
- `frontend/eslint.config.js`
- `frontend/tsconfig.app.json`
- `frontend/tsconfig.node.json`

### Files to Modify

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/tsconfig.json`
- `README.md`
- `.github/workflows/ci.yml`

## Target Frontend Shape

The final frontend should look like this:

```text
frontend/
  index.html
  package.json
  package-lock.json
  tsconfig.json
  tsconfig.app.json
  tsconfig.node.json
  vite.config.ts
  vitest.config.ts
  vitest.setup.ts
  eslint.config.js
  .prettierignore
  src/
    App.tsx
    App.test.tsx
    index.css
    main.tsx
```

### Task 1: Replace the Next.js App With a Vite React App

**Files:**
- Delete: `frontend/app/page.tsx`
- Delete: `frontend/app/layout.tsx`
- Delete: `frontend/app/globals.css`
- Delete: `frontend/next-env.d.ts`
- Delete: `frontend/next.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/index.css`
- Modify: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.app.json`
- Create: `frontend/tsconfig.node.json`

- [ ] **Step 1: Write the failing frontend smoke test**

Create `frontend/src/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  it("renders the AI Reality Check placeholder page", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "AI Reality Check" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("MVP scaffold for the accountability platform."),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails before implementation**

Run:

```bash
cd /Users/leo/Desktop/AI_Oops/.worktrees/task-1-bootstrap/frontend
npm test -- --runInBand
```

Expected: FAIL because `src/App.tsx` and the Vitest-based test runner are not set up yet.

- [ ] **Step 3: Create the Vite entrypoint and placeholder app**

Create `frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AI Reality Check</title>
    <meta
      name="description"
      content="Bootstrap scaffold for the AI Reality Check MVP."
    />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

Create `frontend/src/App.tsx`:

```tsx
export default function App() {
  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">AI Reality Check</p>
        <h1>AI Reality Check</h1>
        <p className="lede">MVP scaffold for the accountability platform.</p>
        <p className="body-copy">
          This bootstrap establishes the Vite React frontend, FastAPI backend,
          and shared developer workflow for future product work.
        </p>
      </section>
    </main>
  );
}
```

Create `frontend/src/index.css`:

```css
:root {
  color: #10233f;
  background: linear-gradient(180deg, #f4f8fb 0%, #e9eef5 100%);
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  line-height: 1.5;
  font-weight: 400;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
}

#root {
  min-height: 100vh;
}

.page-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 2rem;
}

.hero-card {
  width: min(100%, 44rem);
  padding: 3rem;
  border-radius: 1.5rem;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 24px 80px rgba(16, 35, 63, 0.12);
}

.eyebrow {
  margin: 0 0 0.75rem;
  font-size: 0.875rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #46607d;
}

.lede {
  font-size: 1.125rem;
}

.body-copy {
  color: #304760;
}
```

Create `frontend/tsconfig.json`:

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

Create `frontend/tsconfig.app.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "Bundler",
    "allowImportingTsExtensions": false,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
```

Create `frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts", "vitest.config.ts", "eslint.config.js"]
}
```

- [ ] **Step 4: Run the frontend test again**

Run:

```bash
cd /Users/leo/Desktop/AI_Oops/.worktrees/task-1-bootstrap/frontend
npm test -- --runInBand
```

Expected: still FAIL, but now because the test runner/tooling still points at the old Next.js/Jest setup. The React app files should exist.

- [ ] **Step 5: Commit the app-structure replacement**

```bash
git -C /Users/leo/Desktop/AI_Oops/.worktrees/task-1-bootstrap add \
  frontend/index.html \
  frontend/src/main.tsx \
  frontend/src/App.tsx \
  frontend/src/index.css \
  frontend/src/App.test.tsx \
  frontend/tsconfig.json \
  frontend/tsconfig.app.json \
  frontend/tsconfig.node.json \
  frontend/app \
  frontend/next-env.d.ts \
  frontend/next.config.ts
git -C /Users/leo/Desktop/AI_Oops/.worktrees/task-1-bootstrap commit -m "refactor: replace next app shell with vite react structure"
```

### Task 2: Replace Next.js Tooling With Vite, Vitest, and Flat ESLint

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Delete: `frontend/jest.config.js`
- Delete: `frontend/jest.setup.ts`
- Delete: `frontend/.eslintrc.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Create: `frontend/eslint.config.js`

- [ ] **Step 1: Update the package manifest for Vite**

Replace `frontend/package.json` with:

```json
{
  "name": "ai-reality-check-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "format": "prettier --check .",
    "lint": "eslint .",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "19.1.0",
    "react-dom": "19.1.0"
  },
  "devDependencies": {
    "@eslint/js": "9.25.1",
    "@testing-library/jest-dom": "6.6.3",
    "@testing-library/react": "16.3.0",
    "@types/node": "22.15.17",
    "@types/react": "19.1.4",
    "@types/react-dom": "19.1.5",
    "@vitejs/plugin-react": "4.4.1",
    "eslint": "9.25.1",
    "eslint-plugin-react-hooks": "5.2.0",
    "eslint-plugin-react-refresh": "0.4.19",
    "globals": "16.0.0",
    "jsdom": "26.1.0",
    "prettier": "3.5.3",
    "typescript": "5.8.3",
    "typescript-eslint": "8.31.1",
    "vite": "6.3.5",
    "vitest": "3.1.2"
  }
}
```

- [ ] **Step 2: Create the Vite/Vitest/ESLint config files**

Create `frontend/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
});
```

Create `frontend/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./vitest.setup.ts",
  },
});
```

Create `frontend/vitest.setup.ts`:

```ts
import "@testing-library/jest-dom";
```

Create `frontend/eslint.config.js`:

```js
import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
    },
  },
);
```

- [ ] **Step 3: Reinstall frontend dependencies and update the lockfile**

Run:

```bash
cd /Users/leo/Desktop/AI_Oops/.worktrees/task-1-bootstrap/frontend
npm install
```

Expected: `package-lock.json` updates to the Vite/Vitest dependency graph, with Next.js removed.

- [ ] **Step 4: Run the frontend quality checks**

Run:

```bash
cd /Users/leo/Desktop/AI_Oops/.worktrees/task-1-bootstrap/frontend
npm run format
npm run lint
npm test
npm run build
```

Expected: all commands PASS.

- [ ] **Step 5: Commit the tooling migration**

```bash
git -C /Users/leo/Desktop/AI_Oops/.worktrees/task-1-bootstrap add \
  frontend/package.json \
  frontend/package-lock.json \
  frontend/vite.config.ts \
  frontend/vitest.config.ts \
  frontend/vitest.setup.ts \
  frontend/eslint.config.js \
  frontend/jest.config.js \
  frontend/jest.setup.ts \
  frontend/.eslintrc.json
git -C /Users/leo/Desktop/AI_Oops/.worktrees/task-1-bootstrap commit -m "build: switch frontend tooling from next to vite"
```

### Task 3: Update Shared Docs and CI for the New Frontend Workflow

**Files:**
- Modify: `README.md`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Update the README to describe Vite and Node 22**

Update `README.md` so these sections read as follows:

```md
# AI Reality Check

AI Reality Check is an MVP accountability platform for tracking AI failures and reality-checking public claims against reported outcomes. This bootstrap task sets up the initial monorepo structure, a placeholder Vite React frontend, and a minimal FastAPI backend.

## Repository Layout

- `frontend/` - Vite React TypeScript app with lint, test, and build commands.
- `backend/` - FastAPI service with pytest and Ruff configuration.
- `infra/` - Placeholder infrastructure docs for Supabase and scheduled jobs.
- `.env.example` - Shared environment template for local development.

## Prerequisites

- Node.js 22+
- npm 11+
- Python 3.13+
- `uv` 0.9+

## Local Setup

1. Copy environment variables:

   ```bash
   cp .env.example .env
   ```

2. Install frontend dependencies:

   ```bash
   cd frontend
   npm ci
   ```

3. Install backend dependencies:

   ```bash
   cd backend
   UV_CACHE_DIR=../.uv-cache uv sync --all-groups
   ```

## Run Locally

### Frontend

```bash
cd frontend
npm run dev
```

The placeholder UI is available at `http://localhost:5173`.
```

- [ ] **Step 2: Update CI to use Node 22 and the Vite frontend**

Update `.github/workflows/ci.yml` so the frontend job contains:

```yaml
  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run format
      - run: npm run lint
      - run: npm test
      - run: npm run build
```

- [ ] **Step 3: Verify runtime acceptance**

Run:

```bash
cd /Users/leo/Desktop/AI_Oops/.worktrees/task-1-bootstrap/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Then verify:

```bash
curl -i http://127.0.0.1:5173
```

Expected:
- Vite dev server starts successfully
- `curl` returns `HTTP/1.1 200 OK`
- The HTML contains `AI Reality Check`

- [ ] **Step 4: Commit the shared-file updates**

```bash
git -C /Users/leo/Desktop/AI_Oops/.worktrees/task-1-bootstrap add \
  README.md \
  .github/workflows/ci.yml
git -C /Users/leo/Desktop/AI_Oops/.worktrees/task-1-bootstrap commit -m "docs: update bootstrap workflow for vite frontend"
```

## Self-Review

- **Spec coverage:** The plan updates the frontend scaffold, tooling, tests, docs, and CI exactly as required by the approved spec.
- **Placeholder scan:** No TBD or implicit “do the rest” instructions remain; each task includes file targets, concrete content, and explicit commands.
- **Type consistency:** All frontend references consistently use `src/`, Vite, React, TypeScript, and Vitest rather than mixing in Next.js-era files.
