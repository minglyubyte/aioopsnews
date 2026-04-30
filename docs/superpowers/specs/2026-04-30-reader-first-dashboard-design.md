# Reader-First Dashboard Design

## Summary

Redesign the live app so the public-facing experience becomes the primary product and adopts the existing demo dashboard's visual language. The live homepage should emphasize:

- latest incidents
- searchable archive discovery
- source-backed credibility

Editorial tools should move off the homepage into a separate hidden route for staff-only review operations.

This work is a frontend-first restructuring. It keeps the current backend APIs and workflow model, including:

- public incident feed and detail APIs
- admin review queue API
- legitimacy metadata
- duplicate metadata and canonical merge behavior
- localization fields for English and Chinese

## Goals

- Make the live `/` route feel like the demo dashboard instead of a mixed public/admin workspace.
- Prioritize latest incidents and archive exploration for readers.
- Preserve English-first rendering with the existing Chinese toggle.
- Keep source transparency and incident detail easy to inspect.
- Move admin review and deduplication operations out of the public page into a separate hidden route.

## Non-Goals

- No backend workflow redesign.
- No new ingestion, review, duplicate, or translation logic.
- No auth system redesign for staff access in this slice.
- No public user editing, submission, or annotation tools.
- No new source-preview crawler or rich preview system.

## Product Shape

### Public Route

The main route `/` becomes a reader-first dashboard built from real API data and visually aligned to the demo dashboard.

Primary use cases:

- see the newest approved incidents quickly
- browse incident patterns at a glance
- search and filter the archive
- open one incident and inspect sources

### Internal Route

A separate hidden route, recommended as `/internal`, hosts editorial operations.

Primary use cases:

- review pending incidents
- inspect legitimacy output
- inspect duplicate/canonical metadata
- approve items for publication

The internal route is intentionally operational and should not share the public homepage framing.

## Information Architecture

### `/`

Public homepage sections, top to bottom:

1. Hero
2. Incident signals
3. Featured/latest incident spotlight
4. Archive controls
5. Incident archive list
6. Incident detail and source trail

### `/internal`

Internal sections:

1. Staff header / route label
2. Review queue
3. Active review panel
4. Legitimacy metadata
5. Duplicate / canonical context
6. Approval controls

## Public Route Design

### Hero

Use the demo dashboard's tone and composition:

- brand label
- concise mission statement
- short explanation of what readers can do here
- English/Chinese toggle

The hero should feel editorial and trustworthy, not operational. It should avoid any admin token, queue, or staff wording.

### Incident Signals

Carry over the live data visualizations already present in the app, but style them like the demo dashboard:

- monthly incident count
- category distribution

These panels should function as orientation, not deep analytics. They establish that the archive is living and research-oriented.

### Featured / Latest Incident

Add a prominent spotlight card near the top of the page using the most recent approved incident from the current feed.

This block should show:

- company
- date
- severity
- localized headline
- localized summary
- category chips
- action to inspect more detail

This gives the homepage a clear center of gravity instead of sending readers straight into a flat list.

### Archive Controls

Keep the current filter power but integrate it visually into the dashboard instead of making it feel like a utility toolbar.

Keep:

- category filter
- year filter
- month filter
- company filter

Add:

- stronger visual grouping
- clearer archive framing

This section should support archive exploration without overtaking the spotlight content.

V1 keeps the existing archive filters as the discovery mechanism. A true text search box is explicitly deferred until there is matching API support.

### Incident Archive List

The archive list remains the main scrolling content area, but should adopt the demo dashboard's card design and spacing.

Each incident card should show:

- company
- severity
- date
- localized headline
- localized summary
- category chips
- claim-vs-reality block when present
- detail action

The archive should be visually denser than the spotlight section, reflecting its role as a research list rather than a headline module.

### Incident Detail

The selected incident detail block stays on the public route and should feel like a structured editorial fact sheet.

It should include:

- localized headline
- localized summary
- company / date / severity metadata
- claim-vs-reality panel when present
- sources panel

Source rendering should remain lightweight:

- publisher
- title when available
- plain outbound link

This slice does not add prerendered source previews or Open Graph cards.

## Internal Route Design

The internal route should be visually subordinate to the public product and optimized for operations.

It should rehome the current review functionality from the main page:

- admin token handling
- review queue loading
- active review form
- legitimacy score / label / reasoning
- source validation summary
- translation status

It should also expose duplicate metadata more clearly than the current mixed page allows:

- duplicate status
- canonical incident id
- duplicate target id
- candidate summary when available

The internal route does not need the public hero, spotlight, or archive storytelling layout.

## Data Mapping

This design intentionally reuses existing API contracts.

### Public Data

From the public feed and incident detail endpoints:

- incident list
- incident detail
- localized headline and summary
- claim match block
- sources
- filters

### Internal Data

From the admin queue endpoint:

- review queue items
- legitimacy metadata
- source validation summary
- translation status
- duplicate metadata now exposed by the backend

No new backend endpoint is required for the first implementation if current admin responses already contain the needed duplicate fields.

## Routing Strategy

Recommended routes:

- `/` for the public dashboard
- `/internal` for staff operations

This should be implemented in the frontend router or route-switching layer with minimal disruption to current data hooks.

If the app currently uses a single-page conditional rendering model, the implementation can still introduce route-based separation without changing backend APIs.

## Error Handling

### Public Route

- Feed load failure should show a calm fallback message.
- Detail load failure should stay localized to the detail panel.
- Filter load failure should degrade gracefully by hiding or disabling unavailable controls.

### Internal Route

- Missing or rejected admin token should remain isolated to `/internal`.
- Review queue failure should not affect the public route.
- Staff actions should keep current save/error affordances.

## Visual Direction

The live app should inherit the demo dashboard's:

- hierarchy
- spacing rhythm
- panel composition
- calm editorial tone
- spotlight/archive contrast

The design should not become a one-to-one copy if the real data needs denser archive treatment. The main adaptation is:

- keep the demo's identity
- make the real archive more useful

This is why the chosen direction is "option 1 with a little of option 2."

## Testing Plan

### Public Route

- renders incident signal panels with live data
- renders featured/latest spotlight
- renders archive cards from live feed
- preserves filter behavior
- preserves locale toggle behavior
- renders incident detail and sources correctly
- does not render admin queue or admin token UI on `/`

### Internal Route

- renders admin queue only on `/internal`
- preserves approval workflow
- shows legitimacy metadata
- shows duplicate metadata when present
- keeps translation status visible to staff

### Regression

- public API data still maps cleanly to incident cards and detail
- hidden duplicate rows do not appear in the public route
- approved canonical incidents still appear in the public route

## Implementation Notes

- Prefer reusing demo dashboard layout patterns rather than rebuilding from scratch.
- Extract shared presentation helpers where they improve clarity, but avoid broad refactors unrelated to the route split.
- Preserve current locale helpers and incident formatting behavior where possible.
- Keep internal operations isolated from public components to avoid future coupling.

## Risks

- Mixing demo-only structure too literally with live data could make archive workflows feel weak.
- Keeping everything in one large `App.tsx` file may slow future iteration if route separation is implemented without component extraction.
- Internal route hiddenness is a UI concern only in this slice; it is not a substitute for real access control.

## Recommendation

Proceed with a reader-first redesign that:

- turns `/` into a demo-style live dashboard
- introduces a dedicated `/internal` route for staff review
- preserves the current backend and workflow model
- keeps latest incidents first and archive discovery second

This gives the project a credible public-facing product without blocking on backend redesign or operational tooling changes.
