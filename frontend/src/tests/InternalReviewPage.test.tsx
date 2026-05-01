import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import InternalReviewPage from "../pages/InternalReviewPage";
import { fetchAdminIncidentQueue, updateAdminIncident } from "../lib/api";
import type { AdminIncident } from "../types/incident";

vi.mock("../lib/api", () => ({
  fetchAdminIncidentQueue: vi.fn(),
  updateAdminIncident: vi.fn(),
}));

const mockedFetchAdminIncidentQueue = vi.mocked(fetchAdminIncidentQueue);
const mockedUpdateAdminIncident = vi.mocked(updateAdminIncident);

function mockMatchMedia(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

function buildAdminIncident(
  overrides: Partial<AdminIncident> = {},
): AdminIncident {
  return {
    id: overrides.id ?? "incident-1",
    headline: overrides.headline ?? "AssistCo exposed private account notes",
    headline_en:
      overrides.headline_en ??
      overrides.headline ??
      "AssistCo exposed private account notes",
    headline_zh: overrides.headline_zh ?? null,
    date_logged: overrides.date_logged ?? "2026-04-29",
    company_involved: overrides.company_involved ?? "AssistCo",
    claimant_name: overrides.claimant_name ?? "AssistCo",
    incident_topic: overrides.incident_topic ?? "privacy",
    categories: overrides.categories ?? ["Privacy/Security"],
    severity_score: overrides.severity_score ?? 4,
    reality_summary:
      overrides.reality_summary ??
      "A support automation rollout leaked internal notes into user-facing replies.",
    reality_summary_en:
      overrides.reality_summary_en ??
      overrides.reality_summary ??
      "A support automation rollout leaked internal notes into user-facing replies.",
    reality_summary_zh: overrides.reality_summary_zh ?? null,
    status: overrides.status ?? "pending_editor_review",
    translation_status: overrides.translation_status ?? "pending",
    matched_claim: overrides.matched_claim ?? null,
    sources: overrides.sources ?? [],
    matched_claim_id: overrides.matched_claim_id ?? null,
    claim_match_confidence: overrides.claim_match_confidence ?? null,
    review_notes: overrides.review_notes ?? "Needs editor decision.",
    legitimacy_score: overrides.legitimacy_score ?? 0.92,
    legitimacy_label: overrides.legitimacy_label ?? "high_confidence",
    suggested_severity_score: overrides.suggested_severity_score ?? 3,
    severity_confidence: overrides.severity_confidence ?? 0.88,
    severity_reasoning:
      overrides.severity_reasoning ??
      "The incident caused meaningful operational disruption that required staff intervention.",
    severity_flags: overrides.severity_flags ?? ["core_system_outage"],
    severity_model: overrides.severity_model ?? "gpt-5.4-mini",
    severity_decision_source: overrides.severity_decision_source ?? null,
    legitimacy_reasoning:
      overrides.legitimacy_reasoning ??
      "Three credible sources agree on the same event and date.",
    source_validation_summary:
      overrides.source_validation_summary ??
      "3 valid sources fetched successfully.",
    review_batch_id: overrides.review_batch_id ?? "batch-1",
    review_model: overrides.review_model ?? "gpt-5.4-mini",
    duplicate_status: overrides.duplicate_status ?? "suspected",
    duplicate_of_incident_id: overrides.duplicate_of_incident_id ?? null,
    canonical_incident_id: overrides.canonical_incident_id ?? null,
    duplicate_candidates: overrides.duplicate_candidates ?? [
      {
        candidate_incident_id: "incident-9",
        embedding_score: 0.88,
        llm_verdict: "needs_review",
        confidence: 0.71,
        reasoning: "Same company and highly similar event summary.",
        status: "pending_review",
      },
    ],
  };
}

describe("InternalReviewPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    mockMatchMedia(false);
    mockedFetchAdminIncidentQueue.mockResolvedValue({
      items: [
        buildAdminIncident({
          date_logged: "2026-06-01",
          canonical_incident_id: "incident-1-canonical",
          duplicate_of_incident_id: "incident-1-parent",
          sources: [
            {
              id: "source-1",
              source_url: "https://example.com/assistco-incident",
              source_type: "primary",
              publisher: "Example News",
              title: "AssistCo incident coverage",
            },
            {
              id: "source-2",
              source_url: "https://example.com/assistco-follow-up",
              source_type: "secondary",
              publisher: "Follow Up Desk",
              title: "AssistCo follow-up analysis",
            },
          ],
        }),
        buildAdminIncident({
          id: "incident-2",
          date_logged: "2026-04-20",
          headline: "RoboFleet rollback followed navigation failures",
          headline_en: "RoboFleet rollback followed navigation failures",
          company_involved: "RoboFleet",
          claimant_name: "RoboFleet",
          legitimacy_score: 0.83,
          legitimacy_label: "needs_review",
          duplicate_status: null,
          duplicate_candidates: [],
        }),
      ],
    });
    mockedUpdateAdminIncident.mockImplementation(async (_token, incidentId) =>
      buildAdminIncident({
        id: incidentId,
        status: "approved",
        translation_status: "completed",
      }),
    );
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("keeps the internal route staff-only and supports queue approval", async () => {
    render(<InternalReviewPage />);

    expect(
      screen.getByRole("heading", { name: "Internal review" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Incident spotlight" }),
    ).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Admin token"), {
      target: { value: "secret-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Unlock admin" }));

    await waitFor(() => {
      expect(mockedFetchAdminIncidentQueue).toHaveBeenCalledWith("secret-token");
    });

    expect(window.localStorage.getItem("ai-reality-check-admin-token")).toBe(
      "secret-token",
    );

    const queue = screen.getByRole("region", { name: "Review queue" });
    expect(
      within(queue).getByText(/Choose an incident waiting for editorial review/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Review and approve the selected incident/i),
    ).toBeInTheDocument();

    expect(
      within(queue).getByRole("button", {
        name: /Open review for AssistCo exposed private account notes/i,
      }),
    ).toBeInTheDocument();
    const selectedQueueCard = within(queue).getByRole("button", {
      name: /Open review for AssistCo exposed private account notes/i,
    });
    expect(
      within(selectedQueueCard).getByText("AssistCo exposed private account notes"),
    ).toBeInTheDocument();
    expect(
      within(selectedQueueCard).getByText("Status: pending_editor_review"),
    ).toBeInTheDocument();
    expect(within(selectedQueueCard).getByText("AssistCo")).toBeInTheDocument();
    expect(within(selectedQueueCard).getByText("Severity 3")).toBeInTheDocument();
    expect(within(selectedQueueCard).getByText("2026-06-01")).toBeInTheDocument();

    expect(screen.getByText("high_confidence")).toBeInTheDocument();
    expect(screen.getByText(/Suggested severity 3/i)).toBeInTheDocument();
    expect(screen.getByText(/Confidence 88%/i)).toBeInTheDocument();
    expect(
      screen.getByText(
        "The incident caused meaningful operational disruption that required staff intervention.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/Flags: core_system_outage/i)).toBeInTheDocument();
    expect(
      screen.getByText("Three credible sources agree on the same event and date."),
    ).toBeInTheDocument();
    expect(screen.getByText("Example News")).toBeInTheDocument();
    expect(screen.getByText("Primary source")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "AssistCo incident coverage" }),
    ).toHaveAttribute("href", "https://example.com/assistco-incident");
    expect(screen.getByText("https://example.com/assistco-incident")).toBeInTheDocument();
    expect(screen.getByText("Follow Up Desk")).toBeInTheDocument();
    expect(screen.getByText("Secondary source")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "AssistCo follow-up analysis" }),
    ).toHaveAttribute("href", "https://example.com/assistco-follow-up");
    expect(screen.getByText(/Canonical incident incident-1-parent/i)).toBeInTheDocument();
    expect(screen.getByText(/Canonical record incident-1-canonical/i)).toBeInTheDocument();
    expect(screen.getByText(/Potential duplicate: incident-9/i)).toBeInTheDocument();

    fireEvent.click(
      within(queue).getByRole("button", {
        name: /Open review for RoboFleet rollback followed navigation failures/i,
      }),
    );

    expect(
      within(queue).getByRole("button", {
        name: /Open review for RoboFleet rollback followed navigation failures/i,
      }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getAllByRole("heading", {
        name: "RoboFleet rollback followed navigation failures",
      }).length,
    ).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Approve incident" }));

    await waitFor(() => {
      expect(mockedUpdateAdminIncident).toHaveBeenCalledWith(
        "secret-token",
        "incident-2",
        expect.objectContaining({
          status: "approved",
          company_involved: "RoboFleet",
          categories: ["Privacy/Security"],
          severity_score: 3,
        }),
      );
    });
  });

  it("shows the locked state and surfaces a rejected admin token", async () => {
    mockedFetchAdminIncidentQueue.mockRejectedValueOnce(
      new Error("Request failed: 401"),
    );

    render(<InternalReviewPage />);

    expect(screen.getByText("Admin access required")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Admin token"), {
      target: { value: "bad-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Unlock admin" }));

    expect(
      await screen.findByText("Admin token was rejected."),
    ).toBeInTheDocument();
    expect(mockedFetchAdminIncidentQueue).toHaveBeenCalledWith("bad-token");
  });

  it("surfaces a generic queue failure after unlock", async () => {
    mockedFetchAdminIncidentQueue.mockRejectedValueOnce(
      new Error("network down"),
    );

    render(<InternalReviewPage />);

    fireEvent.change(screen.getByLabelText("Admin token"), {
      target: { value: "ops-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Unlock admin" }));

    expect(
      await screen.findByText("Unable to load the review queue right now."),
    ).toBeInTheDocument();
  });

  it("shows an empty queue for staff review", async () => {
    mockedFetchAdminIncidentQueue.mockResolvedValueOnce({ items: [] });

    render(<InternalReviewPage />);

    fireEvent.change(screen.getByLabelText("Admin token"), {
      target: { value: "editor-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Unlock admin" }));

    expect(
      await screen.findByText("No incidents are waiting for review right now."),
    ).toBeInTheDocument();
  });

  it("surfaces save failure during approval", async () => {
    mockedUpdateAdminIncident.mockRejectedValueOnce(new Error("save failed"));

    render(<InternalReviewPage />);

    fireEvent.change(screen.getByLabelText("Admin token"), {
      target: { value: "editor-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Unlock admin" }));

    await screen.findByRole("heading", { name: "Incident review" });

    fireEvent.click(screen.getByRole("button", { name: "Approve incident" }));

    expect(
      await screen.findByText("Unable to save the review decision right now."),
    ).toBeInTheDocument();
  });

  it("supports rejecting an incident from the review form", async () => {
    mockedUpdateAdminIncident.mockImplementationOnce(async (_token, incidentId) =>
      buildAdminIncident({
        id: incidentId,
        status: "rejected",
      }),
    );

    render(<InternalReviewPage />);

    fireEvent.change(screen.getByLabelText("Admin token"), {
      target: { value: "editor-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Unlock admin" }));

    await screen.findByRole("heading", { name: "Incident review" });

    fireEvent.click(screen.getByRole("button", { name: "Reject incident" }));

    await waitFor(() => {
      expect(mockedUpdateAdminIncident).toHaveBeenCalledWith(
        "editor-token",
        "incident-1",
        expect.objectContaining({
          status: "rejected",
        }),
      );
    });
  });

  it("reveals the review panel after a mobile queue selection", async () => {
    mockMatchMedia(true);

    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });

    render(<InternalReviewPage />);

    fireEvent.change(screen.getByLabelText("Admin token"), {
      target: { value: "mobile-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Unlock admin" }));

    const queue = await screen.findByRole("region", { name: "Review queue" });

    fireEvent.click(
      within(queue).getByRole("button", {
        name: /Open review for RoboFleet rollback followed navigation failures/i,
      }),
    );

    await waitFor(() => {
      expect(scrollIntoView).toHaveBeenCalled();
    });
  });

  it("sorts queue items by newest date first", async () => {
    mockedFetchAdminIncidentQueue.mockResolvedValueOnce({
      items: [
        buildAdminIncident({
          id: "incident-older",
          date_logged: "2026-04-20",
          headline: "Older incident in queue",
          headline_en: "Older incident in queue",
          company_involved: "OlderCo",
        }),
        buildAdminIncident({
          id: "incident-newer",
          date_logged: "2026-06-01",
          headline: "Newer incident in queue",
          headline_en: "Newer incident in queue",
          company_involved: "NewerCo",
        }),
      ],
    });

    render(<InternalReviewPage />);

    fireEvent.change(screen.getByLabelText("Admin token"), {
      target: { value: "sort-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Unlock admin" }));

    const queue = await screen.findByRole("region", { name: "Review queue" });
    const queueButtons = within(queue).getAllByRole("button");

    expect(
      within(queueButtons[0]).getByText("Newer incident in queue"),
    ).toBeInTheDocument();
    expect(within(queueButtons[0]).getByText("2026-06-01")).toBeInTheDocument();
    expect(
      within(queueButtons[1]).getByText("Older incident in queue"),
    ).toBeInTheDocument();
    expect(within(queueButtons[1]).getByText("2026-04-20")).toBeInTheDocument();
  });
});
