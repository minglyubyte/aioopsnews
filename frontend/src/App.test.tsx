import { render, screen } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  it("renders incidents from the API feed", async () => {
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
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
