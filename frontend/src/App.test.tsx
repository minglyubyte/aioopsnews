import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";

describe("App", () => {
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

    render(<App />);

    expect(screen.getByText("Loading incident feed...")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", {
        name: "Customer support bot exposes private account notes",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Privacy/Security")).toHaveLength(2);
    expect(screen.getByText("AssistCo")).toBeInTheDocument();
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
