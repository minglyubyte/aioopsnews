# Vite Frontend Switch Design

**Date:** 2026-04-29
**Status:** Approved in chat, pending written-spec review
**Scope:** Replace the current Next.js frontend scaffold with a Vite + React + TypeScript scaffold while preserving the existing Task 1 backend, repo layout, and acceptance goals.

## Goal

Switch the frontend foundation from Next.js to plain React using Vite, while keeping the current TypeScript baseline and leaving the rest of the monorepo bootstrap intact.

## Why This Change

The user explicitly wants a plain React frontend rather than a framework with routing and server features like Next.js. Because the project is still at scaffold stage, replacing the frontend now is cheaper and cleaner than continuing to build additional tasks on top of the wrong stack.

## In Scope

- Replace the existing `frontend/` Next.js scaffold with `Vite + React + TypeScript`
- Keep the current placeholder landing page concept
- Keep frontend lint, test, and build tooling
- Update README setup and run commands for the new frontend stack
- Update CI so frontend checks run against the Vite app instead of Next.js
- Preserve the backend, infra placeholders, env template, and repo layout

## Out of Scope

- No product feature work beyond the existing placeholder UI
- No backend architecture changes
- No routing architecture beyond what Vite needs for the current placeholder app
- No styling redesign beyond the minimum changes needed to preserve the placeholder page
- No follow-on refactor of the overall implementation plan beyond noting that frontend references should now assume Vite/React instead of Next.js

## Recommended Approach

Replace the current `frontend/` app in-place on the `task-1-bootstrap` branch.

This is the best fit because:

- The current frontend is only a scaffold, so migration cost is still low
- It avoids carrying forward the wrong dependencies, config, and runtime assumptions
- It keeps the branch history focused on one bootstrap outcome instead of a bootstrap-plus-migration sequence

## Resulting Frontend Shape

The frontend should become a standard Vite React TypeScript app with focused bootstrap files:

- `frontend/index.html`
  - HTML entrypoint for Vite
- `frontend/src/main.tsx`
  - React mount entrypoint
- `frontend/src/App.tsx`
  - Placeholder page shell
- `frontend/src/index.css`
  - Global styles for the placeholder page
- `frontend/src/App.test.tsx` or equivalent
  - Minimal smoke test for the rendered placeholder UI
- `frontend/package.json`
  - Vite, React, TypeScript, lint, test, build, and dev scripts
- `frontend/vite.config.ts`
  - Vite configuration
- `frontend/tsconfig*.json`
  - TypeScript config for app and tooling

## Tooling Expectations

- Use React + TypeScript
- Use Vite for dev/build
- Keep linting and testing in place
- Prefer Vitest for frontend tests because it matches the Vite ecosystem cleanly
- Keep CI on a supported Node 22 baseline

## Acceptance Criteria

After the switch:

- `frontend` starts locally with Vite
- The placeholder page renders successfully
- Frontend lint passes
- Frontend tests pass
- Frontend build passes
- README commands match the new frontend workflow
- CI checks the Vite-based frontend rather than Next.js

## Risks

- Some Task 1 files and docs currently reference Next.js-specific commands and structure, so those references need to be updated consistently
- The frontend test setup will likely change from Jest to Vitest, which is a small tooling migration but should stay contained to `frontend/`
- Later plan references to Next.js should be interpreted as React/Vite unless the implementation plan is explicitly revised

## Implementation Notes

- Keep the backend untouched unless a shared doc or CI file needs a frontend command update
- Remove Next.js-specific config and generated assumptions from `frontend/`
- Do not broaden this into router setup or feature work
- Treat this as a correction to Task 1, not a new product feature
