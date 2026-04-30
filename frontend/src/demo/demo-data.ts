import type { DemoIncident, DemoMetric, DemoSidebarCard } from "./demo-types";

export const demoMetrics: DemoMetric[] = [
  {
    label: "Reviewed incidents",
    value: "128",
    note: "documented, source-linked failures",
  },
  {
    label: "Claim precision",
    value: "100%",
    note: "seed gold-sample evaluation",
  },
  {
    label: "Manual review",
    value: "Always on",
    note: "public entries are never auto-published",
  },
];

export const demoIncidents: DemoIncident[] = [
  {
    id: "assistco",
    headline: "AssistCo assistant exposes private billing notes",
    company: "AssistCo",
    date: "May 1, 2026",
    severity: "Severity 4",
    categories: ["Privacy/Security", "Support automation"],
    summary:
      "A customer-support assistant leaked internal account notes into outward-facing replies before the workflow was halted.",
    sourceLabel: "Example News",
    sourceUrl: "https://example.com/articles/assistco-billing-notes",
    claimQuote: "Our assistant will eliminate repetitive support escalations.",
    claimMeta: "Claimed January 15, 2026 • Confidence 88%",
  },
  {
    id: "robofleet",
    headline: "RoboFleet robot pilot rollback follows navigation failures",
    company: "RoboFleet",
    date: "April 24, 2026",
    severity: "Severity 3",
    categories: ["Autonomous Systems", "Pilot rollback"],
    summary:
      "Operators paused a sidewalk robotics pilot after repeated navigation failures and escalating manual interventions.",
    sourceLabel: "City Transit Journal",
    sourceUrl: "https://example.com/articles/robofleet-pilot-rollback",
  },
  {
    id: "signalloop",
    headline: "SignalLoop misses another launch window after rollout delay",
    company: "SignalLoop",
    date: "April 20, 2026",
    severity: "Severity 2",
    categories: ["Missed Timelines", "Product rollout"],
    summary:
      "The company acknowledged another slipped release after publicly signaling a near-term product launch.",
    sourceLabel: "Product Ledger",
    sourceUrl: "https://example.com/articles/signalloop-delay",
  },
];

export const demoSidebarCards: DemoSidebarCard[] = [
  {
    title: "Editorial standard",
    body: "Every public entry is manually approved and must link to accountable reporting or primary-source material.",
  },
  {
    title: "Launch posture",
    body: "The current launch model favors fewer, better-documented incidents over broad automation coverage.",
  },
];
