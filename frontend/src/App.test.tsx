import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("keeps the admin queue locked until an admin token is entered", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();

      if (url.endsWith("/filters")) {
        return new Response(
          JSON.stringify({
            categories: ["Autonomous Systems", "Privacy/Security"],
            claimants: ["AssistCo", "RoboFleet"],
            companies: ["AssistCo", "RoboFleet"],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }

      return new Response(
        JSON.stringify({
          items: [],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    });

    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(
      await screen.findByText("Admin access required"),
    ).toBeInTheDocument();

    expect(fetchMock).not.toHaveBeenCalledWith(
      "http://127.0.0.1:8000/admin/incidents",
    );
  });

  it("loads the admin queue after a valid token is submitted", async () => {
    const fetchMock = vi.fn(
      async (input: string | URL | Request, init?: RequestInit) => {
        const url = input.toString();

        if (url.endsWith("/filters")) {
          return new Response(
            JSON.stringify({
              categories: ["Autonomous Systems", "Privacy/Security"],
              claimants: ["AssistCo", "RoboFleet"],
              companies: ["AssistCo", "RoboFleet"],
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          );
        }

        if (url.endsWith("/admin/incidents")) {
          expect(init?.headers).toMatchObject({
            "X-Admin-Token": "secret-token",
          });

          return new Response(
            JSON.stringify({
              items: [
                {
                  id: "incident-admin-1",
                  headline: "AssistCo assistant exposes billing notes",
                  date_logged: "2026-05-01",
                  company_involved: "Pending classification",
                  claimant_name: null,
                  categories: [],
                  severity_score: 1,
                  reality_summary:
                    "A support assistant exposed private billing notes in customer-facing replies.",
                  status: "pending_review",
                  matched_claim_id: null,
                  claim_match_confidence: null,
                  review_notes: "Awaiting editor review.",
                  sources: [
                    {
                      id: "source-admin-1",
                      source_url:
                        "https://example.com/articles/assistco-billing-notes",
                      source_type: "secondary",
                      publisher: "Example News",
                    },
                  ],
                },
              ],
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          );
        }

        return new Response(
          JSON.stringify({
            items: [],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );

    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    fireEvent.change(screen.getByLabelText("Admin token"), {
      target: { value: "secret-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Unlock admin" }));

    expect(
      await screen.findByRole("heading", {
        name: "AssistCo assistant exposes billing notes",
      }),
    ).toBeInTheDocument();
  });

  it("shows a specific admin auth error when the token is rejected", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();

      if (url.endsWith("/filters")) {
        return new Response(
          JSON.stringify({
            categories: ["Autonomous Systems", "Privacy/Security"],
            claimants: ["AssistCo", "RoboFleet"],
            companies: ["AssistCo", "RoboFleet"],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }

      if (url.endsWith("/admin/incidents")) {
        return new Response(
          JSON.stringify({
            detail: "Admin access required",
          }),
          {
            status: 401,
            headers: { "Content-Type": "application/json" },
          },
        );
      }

      return new Response(
        JSON.stringify({
          items: [],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    });

    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    fireEvent.change(screen.getByLabelText("Admin token"), {
      target: { value: "wrong-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Unlock admin" }));

    expect(
      await screen.findByText("Admin token was rejected."),
    ).toBeInTheDocument();
  });

  it("opens a detail panel for a selected public incident", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();

      if (url.endsWith("/filters")) {
        return new Response(
          JSON.stringify({
            categories: ["Autonomous Systems", "Privacy/Security"],
            claimants: ["AssistCo", "RoboFleet"],
            companies: ["AssistCo", "RoboFleet"],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }

      if (url.endsWith("/admin/incidents")) {
        return new Response(
          JSON.stringify({
            items: [],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }

      if (url.endsWith("/incidents/incident-1")) {
        return new Response(
          JSON.stringify({
            id: "incident-1",
            headline: "Customer support bot exposes private account notes",
            date_logged: "2026-04-29",
            company_involved: "AssistCo",
            claimant_name: "AssistCo",
            categories: ["Privacy/Security"],
            severity_score: 4,
            reality_summary:
              "A support automation rollout leaked internal notes into user-facing replies.",
            status: "approved",
            matched_claim: {
              id: "claim-1",
              claimant_name: "AssistCo",
              company_involved: "AssistCo",
              original_claim:
                "Our assistant will eliminate repetitive support escalations.",
              claim_date: "2026-01-15",
              claim_topic: "job automation",
              match_confidence: 0.88,
            },
            sources: [
              {
                id: "source-1",
                source_url: "https://example.com/privacy-story",
                source_type: "primary",
                publisher: "Example News",
                title: "Customer support bot exposes private account notes",
              },
            ],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }

      return new Response(
        JSON.stringify({
          items: [
            {
              id: "incident-1",
              headline: "Customer support bot exposes private account notes",
              date_logged: "2026-04-29",
              company_involved: "AssistCo",
              claimant_name: "AssistCo",
              categories: ["Privacy/Security"],
              severity_score: 4,
              reality_summary:
                "A support automation rollout leaked internal notes into user-facing replies.",
              status: "approved",
              matched_claim: {
                id: "claim-1",
                claimant_name: "AssistCo",
                company_involved: "AssistCo",
                original_claim:
                  "Our assistant will eliminate repetitive support escalations.",
                claim_date: "2026-01-15",
                claim_topic: "job automation",
                match_confidence: 0.88,
              },
              sources: [],
            },
          ],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    });

    vi.stubGlobal("fetch", fetchMock);

    window.localStorage.setItem("ai-reality-check-admin-token", "secret-token");

    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Customer support bot exposes private account notes",
      }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "View details" }));

    expect(
      await screen.findByRole("heading", {
        name: "Incident detail",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Example News")).toBeInTheDocument();
    expect(
      screen.getByText("https://example.com/privacy-story"),
    ).toBeInTheDocument();
  });

  it("refetches the public feed when a reader applies filters", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();

      if (url.endsWith("/filters")) {
        return new Response(
          JSON.stringify({
            categories: ["Autonomous Systems", "Privacy/Security"],
            claimants: ["AssistCo", "RoboFleet"],
            companies: ["AssistCo", "RoboFleet"],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }

      if (url.includes("/admin/incidents")) {
        return new Response(
          JSON.stringify({
            items: [],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }

      if (
        url.includes("/incidents?category=Autonomous+Systems&company=RoboFleet")
      ) {
        return new Response(
          JSON.stringify({
            items: [
              {
                id: "incident-robot-1",
                headline:
                  "Warehouse robot rollback follows navigation failures",
                date_logged: "2026-04-24",
                company_involved: "RoboFleet",
                claimant_name: "RoboFleet",
                categories: ["Autonomous Systems"],
                severity_score: 3,
                reality_summary:
                  "Operators paused a pilot after repeated pathing failures.",
                status: "approved",
                matched_claim: null,
                sources: [],
              },
            ],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }

      return new Response(
        JSON.stringify({
          items: [
            {
              id: "incident-1",
              headline: "Customer support bot exposes private account notes",
              date_logged: "2026-04-29",
              company_involved: "AssistCo",
              claimant_name: "AssistCo",
              categories: ["Privacy/Security"],
              severity_score: 4,
              reality_summary:
                "A support automation rollout leaked internal notes into user-facing replies.",
              status: "approved",
              matched_claim: null,
              sources: [],
            },
          ],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    });

    vi.stubGlobal("fetch", fetchMock);

    window.localStorage.setItem("ai-reality-check-admin-token", "secret-token");

    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Customer support bot exposes private account notes",
      }),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Filter by category"), {
      target: { value: "Autonomous Systems" },
    });
    fireEvent.change(screen.getByLabelText("Filter by company"), {
      target: { value: "RoboFleet" },
    });

    expect(
      await screen.findByRole("heading", {
        name: "Warehouse robot rollback follows navigation failures",
      }),
    ).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/incidents?category=Autonomous+Systems&company=RoboFleet",
      {
        headers: undefined,
      },
    );
  });

  it("renders the public incident feed from the API", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();

      if (url.endsWith("/filters")) {
        return new Response(
          JSON.stringify({
            categories: ["Autonomous Systems", "Privacy/Security"],
            claimants: ["AssistCo", "RoboFleet"],
            companies: ["AssistCo", "RoboFleet"],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }

      if (url.endsWith("/admin/incidents")) {
        return new Response(
          JSON.stringify({
            items: [
              {
                id: "incident-admin-1",
                headline: "AssistCo assistant exposes billing notes",
                date_logged: "2026-05-01",
                company_involved: "Pending classification",
                claimant_name: null,
                categories: [],
                severity_score: 1,
                reality_summary:
                  "A support assistant exposed private billing notes in customer-facing replies.",
                status: "pending_review",
                matched_claim_id: null,
                claim_match_confidence: null,
                review_notes: "Awaiting editor review.",
                sources: [
                  {
                    id: "source-admin-1",
                    source_url:
                      "https://example.com/articles/assistco-billing-notes",
                    source_type: "secondary",
                    publisher: "Example News",
                  },
                ],
              },
            ],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }

      return new Response(
        JSON.stringify({
          items: [
            {
              id: "incident-1",
              headline: "Customer support bot exposes private account notes",
              date_logged: "2026-04-29",
              company_involved: "AssistCo",
              claimant_name: "AssistCo",
              categories: ["Privacy/Security"],
              severity_score: 4,
              reality_summary:
                "A support automation rollout leaked internal notes into user-facing replies.",
              status: "approved",
              matched_claim: {
                id: "claim-1",
                claimant_name: "AssistCo",
                company_involved: "AssistCo",
                original_claim:
                  "Our assistant will eliminate repetitive support escalations.",
                claim_date: "2026-01-15",
                claim_topic: "job automation",
                match_confidence: 0.88,
              },
              sources: [
                {
                  id: "source-1",
                  source_url: "https://example.com/privacy-story",
                  source_type: "primary",
                  publisher: "Example News",
                },
              ],
            },
          ],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    });

    vi.stubGlobal("fetch", fetchMock);

    window.localStorage.setItem("ai-reality-check-admin-token", "secret-token");

    render(<App />);

    expect(screen.getByText("Loading incident feed...")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", {
        name: "Customer support bot exposes private account notes",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Privacy/Security")).toHaveLength(2);
    expect(screen.getAllByText("AssistCo").length).toBeGreaterThan(0);
    expect(screen.getByText("Claim vs. reality")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Our assistant will eliminate repetitive support escalations.",
      ),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("lets an editor approve a pending incident from the admin queue", async () => {
    const fetchMock = vi.fn(
      async (input: string | URL | Request, init?: RequestInit) => {
        const url = input.toString();

        if (url.endsWith("/filters")) {
          return new Response(
            JSON.stringify({
              categories: ["Autonomous Systems", "Privacy/Security"],
              claimants: ["AssistCo", "RoboFleet"],
              companies: ["AssistCo", "RoboFleet"],
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          );
        }

        if (url.endsWith("/admin/incidents/incident-admin-1")) {
          const body = JSON.parse(String(init?.body));

          return new Response(
            JSON.stringify({
              id: "incident-admin-1",
              headline: "AssistCo assistant exposes billing notes",
              date_logged: "2026-05-01",
              company_involved: body.company_involved,
              claimant_name: body.claimant_name,
              categories: body.categories,
              severity_score: body.severity_score,
              reality_summary: body.reality_summary,
              status: body.status,
              matched_claim_id: body.matched_claim_id,
              claim_match_confidence: body.claim_match_confidence,
              review_notes: body.review_notes,
              sources: [
                {
                  id: "source-admin-1",
                  source_url:
                    "https://example.com/articles/assistco-billing-notes",
                  source_type: "secondary",
                  publisher: "Example News",
                },
              ],
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          );
        }

        if (url.endsWith("/admin/incidents")) {
          return new Response(
            JSON.stringify({
              items: [
                {
                  id: "incident-admin-1",
                  headline: "AssistCo assistant exposes billing notes",
                  date_logged: "2026-05-01",
                  company_involved: "Pending classification",
                  claimant_name: null,
                  categories: [],
                  severity_score: 1,
                  reality_summary:
                    "A support assistant exposed private billing notes in customer-facing replies.",
                  status: "pending_review",
                  matched_claim_id: null,
                  claim_match_confidence: null,
                  review_notes: "Awaiting editor review.",
                  sources: [
                    {
                      id: "source-admin-1",
                      source_url:
                        "https://example.com/articles/assistco-billing-notes",
                      source_type: "secondary",
                      publisher: "Example News",
                    },
                  ],
                },
              ],
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          );
        }

        return new Response(
          JSON.stringify({
            items: [
              {
                id: "incident-1",
                headline: "Customer support bot exposes private account notes",
                date_logged: "2026-04-29",
                company_involved: "AssistCo",
                claimant_name: "AssistCo",
                categories: ["Privacy/Security"],
                severity_score: 4,
                reality_summary:
                  "A support automation rollout leaked internal notes into user-facing replies.",
                status: "approved",
                matched_claim: {
                  id: "claim-1",
                  claimant_name: "AssistCo",
                  company_involved: "AssistCo",
                  original_claim:
                    "Our assistant will eliminate repetitive support escalations.",
                  claim_date: "2026-01-15",
                  claim_topic: "job automation",
                  match_confidence: 0.88,
                },
                sources: [],
              },
            ],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );

    vi.stubGlobal("fetch", fetchMock);

    window.localStorage.setItem("ai-reality-check-admin-token", "secret-token");

    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "AssistCo assistant exposes billing notes",
      }),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Company"), {
      target: { value: "AssistCo" },
    });
    fireEvent.change(screen.getByLabelText("Category"), {
      target: { value: "Privacy/Security" },
    });
    fireEvent.change(screen.getByLabelText("Severity"), {
      target: { value: "5" },
    });
    fireEvent.change(screen.getByLabelText("Review Notes"), {
      target: { value: "Approved after editor verification." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve Incident" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:8000/admin/incidents/incident-admin-1",
        expect.objectContaining({
          method: "PATCH",
        }),
      );
    });

    expect(await screen.findByText("approved")).toBeInTheDocument();
    expect(
      screen.getByText("Approved after editor verification."),
    ).toBeInTheDocument();
  });
});
