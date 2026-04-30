# Demo Dashboard Design

## Goal

Create a separate `/demo` route in the existing frontend that presents a polished, editorial-style mock dashboard for AI Reality Check without changing the live product surface.

## Recommended Approach

Build the route from a typed local mock dataset rather than live API calls.

This keeps the demo stable, visually controlled, and easy to iterate on while preserving the existing API-driven screen for real usage.

## Route Strategy

- Keep the current app behavior intact.
- Add a dedicated `/demo` route inside the existing frontend.
- Treat `/demo` as a presentation-first surface, not a second production read path.

## Data Strategy

- Store a local typed mock dataset in the frontend.
- Include:
  - featured incidents
  - claim-vs-reality spotlight content
  - source credibility notes
  - launch-readiness and operations summary numbers
- Keep the dataset small, curated, and deliberately presentation-quality.

## Page Structure

### Hero

- Editorial headline and short framing copy
- Compact metrics strip for launch-readiness and editorial status
- A visible distinction between “documented failures” and “public hype”

### Left Rail

- Mock filter chips or sections for category, company, and severity
- Short editorial standards panel
- Taxonomy or source-policy callout

### Main Feed

- Rich incident cards with:
  - headline
  - date
  - company
  - summary
  - severity
  - categories
  - source references
- Stronger visual hierarchy than the current live screen

### Right Rail

- Claim-vs-reality spotlight
- Source credibility explainer
- Queue or operations summary panel

### Detail Spotlight

- One featured incident expanded below the feed
- Include richer summary, source list, and claim context

## Visual Direction

- Keep the existing editorial/serif identity, but make it more intentional
- Use a newspaper-meets-control-room feel
- Prefer warm paper surfaces, slate ink tones, restrained alert colors, and structured dashboard blocks
- Avoid generic SaaS visual language

## Interaction Model

- Mostly presentational interactions
- Mock filters and cards can change local selected state for feel
- No backend requests required
- One selected incident can drive the lower detail spotlight

## Technical Direction

- Stay with React + TypeScript + CSS for this slice
- Do not migrate the app to Tailwind in the same change
- Split the demo route into focused files instead of growing `App.tsx` further

## Suggested Frontend Units

- `frontend/src/demo/DemoDashboard.tsx`
- `frontend/src/demo/demo-data.ts`
- `frontend/src/demo/demo-types.ts`
- `frontend/src/demo/demo.css`
- lightweight route switch in the app entry path

## Testing

- Add a focused frontend test that proves `/demo` renders:
  - hero copy
  - at least one incident card
  - claim-vs-reality spotlight
  - detail spotlight
- Keep tests shallow and presentation-oriented

## Scope Boundaries

- No Tailwind migration
- No backend changes
- No replacement of the live feed
- No requirement for the demo route to share behavior with the live route beyond basic app shell compatibility
