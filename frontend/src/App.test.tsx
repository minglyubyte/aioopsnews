import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import App from "./App";
import DemoDashboard from "./demo/DemoDashboard";

function renderPath(pathname: string) {
  window.history.pushState({}, "", pathname);

  if (pathname === "/demo") {
    return render(<DemoDashboard />);
  }

  return render(<App />);
}

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

function buildReaderFiltersResponse() {
  return {
    categories: ["Autonomous Systems", "Privacy/Security"],
    claimants: ["AssistCo", "RoboFleet"],
    companies: ["AssistCo", "RoboFleet"],
    years: [2026, 2025],
    months_by_year: {
      "2026": [5, 4],
      "2025": [12],
    },
  };
}

function buildIncident(
  overrides: Partial<{
    id: string;
    headline: string;
    headline_en: string;
    headline_zh: string | null;
    date_logged: string;
    company_involved: string;
    claimant_name: string;
    incident_topic: string | null;
    categories: string[];
    severity_score: number;
    reality_summary: string;
    reality_summary_en: string;
    reality_summary_zh: string | null;
    status: string;
    translation_status: string;
  }> = {},
) {
  return {
    id: overrides.id ?? "incident-1",
    headline:
      overrides.headline ?? "Customer support bot exposes private account notes",
    headline_en:
      overrides.headline_en ??
      overrides.headline ??
      "Customer support bot exposes private account notes",
    headline_zh:
      overrides.headline_zh ?? "中文：Customer support bot exposes private account notes",
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
    reality_summary_zh:
      overrides.reality_summary_zh ??
      "中文：A support automation rollout leaked internal notes into user-facing replies.",
    status: overrides.status ?? "approved",
    translation_status: overrides.translation_status ?? "completed",
    matched_claim: null,
    sources: [],
  };
}

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.pushState({}, "", "/");
    mockMatchMedia(false);
  });

  it("renders the demo dashboard route with hero copy and featured incident content", () => {
    renderPath("/demo");

    expect(
      screen.getByRole("heading", {
        name: "AI failures, without the hype cycle",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("AssistCo assistant exposes private billing notes")
        .length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole("heading", {
        name: "Spotlight",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Incident spotlight",
      }),
    ).toBeInTheDocument();
  });

  it("renders demo theme and language controls and defaults to light mode", () => {
    renderPath("/demo");

    expect(
      screen.getByRole("group", { name: "Demo language switch" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("group", { name: "Demo theme switch" }),
    ).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "English" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Light" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    expect(screen.getByRole("main")).toHaveAttribute("data-theme", "light");
  });

  it("defaults the demo route to dark mode when the system preference is dark", () => {
    mockMatchMedia(true);

    renderPath("/demo");

    expect(screen.getByRole("button", { name: "Dark" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("main")).toHaveAttribute("data-theme", "dark");
  });

  it("switches the demo route to Chinese copy and preserves spotlight selection", () => {
    renderPath("/demo");

    fireEvent.click(
      screen.getByRole("button", {
        name: /Open incident detail for RoboFleet robot pilot rollback follows navigation failures/i,
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "中文" }));

    expect(
      screen.getByRole("heading", {
        name: "AI 故障，不该被热潮掩盖",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText("RoboFleet 机器人试点因导航失误而回滚").length,
    ).toBeGreaterThan(0);
    expect(window.localStorage.getItem("ai-oops-demo-locale")).toBe("zh");

    const spotlight = screen
      .getByRole("heading", {
        name: "事件聚焦",
      })
      .closest("section");

    expect(spotlight).not.toBeNull();
    expect(
      within(spotlight as HTMLElement).getByRole("heading", {
        name: "RoboFleet 机器人试点因导航失误而回滚",
      }),
    ).toBeInTheDocument();
  });

  it("persists a manual dark theme choice on the demo route", () => {
    renderPath("/demo");

    fireEvent.click(screen.getByRole("button", { name: "Dark" }));

    expect(screen.getByRole("main")).toHaveAttribute("data-theme", "dark");
    expect(window.localStorage.getItem("ai-oops-demo-theme")).toBe("dark");
    expect(screen.getByRole("button", { name: "Dark" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("updates the incident spotlight when a different demo card is selected", () => {
    renderPath("/demo");

    fireEvent.click(
      screen.getByRole("button", {
        name: /Open incident detail for RoboFleet robot pilot rollback follows navigation failures/i,
      }),
    );

    const spotlight = screen
      .getByRole("heading", {
        name: "Incident spotlight",
      })
      .closest("section");

    expect(spotlight).not.toBeNull();
    expect(
      within(spotlight as HTMLElement).getByRole("heading", {
        name: "RoboFleet robot pilot rollback follows navigation failures",
      }),
    ).toBeInTheDocument();
  });

  it("renders demo incident signals with monthly counts and category distribution", () => {
    renderPath("/demo");

    expect(
      screen.getByRole("heading", {
        name: "Incident signals",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Apr 2026")).toBeInTheDocument();
    expect(screen.getByText("May 2026")).toBeInTheDocument();
    expect(
      screen.getByRole("img", {
        name: "Demo category distribution donut chart",
      }),
    ).toBeInTheDocument();
  });

  it("localizes demo incident signals when switching to Chinese", () => {
    renderPath("/demo");

    fireEvent.click(screen.getByRole("button", { name: "中文" }));

    expect(
      screen.getByRole("heading", {
        name: "事件信号",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("2026年4月")).toBeInTheDocument();
    expect(
      screen.getByRole("img", {
        name: "演示分类分布环形图",
      }),
    ).toBeInTheDocument();
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
        return new Response(JSON.stringify(buildReaderFiltersResponse()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
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

  it("renders tag and archive controls and preserves detail view with active archive filters", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();

      if (url.endsWith("/filters")) {
        return new Response(JSON.stringify(buildReaderFiltersResponse()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
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

      if (url.endsWith("/incidents/incident-robot-1")) {
        return new Response(
          JSON.stringify({
            id: "incident-robot-1",
            headline: "Warehouse robot rollback follows navigation failures",
            date_logged: "2026-04-24",
            company_involved: "RoboFleet",
            claimant_name: "RoboFleet",
            categories: ["Autonomous Systems"],
            severity_score: 3,
            reality_summary:
              "Operators paused a pilot after repeated pathing failures.",
            status: "approved",
            matched_claim: null,
            sources: [
              {
                id: "source-robot-1",
                source_url: "https://example.com/robotics",
                source_type: "primary",
                publisher: "City Ledger",
                title: "Warehouse robot rollback follows navigation failures",
              },
            ],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }

      if (
        url.includes("/incidents?category=Autonomous+Systems&year=2026&month=4")
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
              date_logged: "2025-12-18",
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

    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Customer support bot exposes private account notes",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Autonomous Systems" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Filter by year")).toBeInTheDocument();
    expect(screen.getByLabelText("Filter by month")).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Autonomous Systems" }));
    fireEvent.change(screen.getByLabelText("Filter by year"), {
      target: { value: "2026" },
    });
    fireEvent.change(screen.getByLabelText("Filter by month"), {
      target: { value: "4" },
    });

    expect(
      await screen.findByRole("heading", {
        name: "Warehouse robot rollback follows navigation failures",
      }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "View details" }));

    expect(
      await screen.findByRole("heading", {
        name: "Incident detail",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("City Ledger")).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/incidents?category=Autonomous+Systems&year=2026&month=4",
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
    expect(screen.getAllByText("Privacy/Security").length).toBeGreaterThan(1);
    expect(screen.getAllByText("AssistCo").length).toBeGreaterThan(0);
    expect(screen.getByText("Claim vs. reality")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Our assistant will eliminate repetitive support escalations.",
      ),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("defaults the public feed to English and switches incident copy to Chinese", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();

      if (url.endsWith("/filters")) {
        return new Response(JSON.stringify(buildReaderFiltersResponse()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      if (url.endsWith("/admin/incidents")) {
        return new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      return new Response(
        JSON.stringify({
          items: [
            buildIncident({
              headline: "Customer support bot exposes private account notes",
              headline_zh: "客服机器人泄露私人账户备注",
              reality_summary:
                "A support automation rollout leaked internal notes into user-facing replies.",
              reality_summary_zh:
                "支持自动化发布将内部备注泄露给用户可见的回复。",
            }),
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

    expect(
      await screen.findByRole("heading", {
        name: "Customer support bot exposes private account notes",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("group", { name: "Reader language switch" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Chinese" }));

    expect(
      await screen.findByRole("heading", {
        name: "客服机器人泄露私人账户备注",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("支持自动化发布将内部备注泄露给用户可见的回复。"),
    ).toBeInTheDocument();
    expect(window.localStorage.getItem("ai-reality-check-locale")).toBe("zh");
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

  it("shows legitimacy and translation metadata in the admin queue", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();

      if (url.endsWith("/filters")) {
        return new Response(JSON.stringify(buildReaderFiltersResponse()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      if (url.endsWith("/admin/incidents")) {
        return new Response(
          JSON.stringify({
            items: [
              {
                ...buildIncident({
                  id: "incident-admin-1",
                  headline: "AssistCo assistant exposes billing notes",
                  headline_zh: null,
                  translation_status: "not_requested",
                  status: "pending_review",
                }),
                matched_claim_id: null,
                claim_match_confidence: null,
                review_notes: "Awaiting editor review.",
                legitimacy_score: 0.87,
                legitimacy_label: "needs_review",
                legitimacy_reasoning:
                  "ACCEPT/medium editorial input with 3 validated sources for privacy.",
                source_validation_summary: "Validated 3 distinct sources.",
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

      return new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    vi.stubGlobal("fetch", fetchMock);
    window.localStorage.setItem("ai-reality-check-admin-token", "secret-token");

    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "AssistCo assistant exposes billing notes",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Legitimacy score 87%")).toBeInTheDocument();
    expect(screen.getByText("needs_review")).toBeInTheDocument();
    expect(screen.getByText("Validated 3 distinct sources.")).toBeInTheDocument();
    expect(screen.getByText("Translation not_requested")).toBeInTheDocument();
  });

  it("renders incident signals with chronological monthly counts and category distribution", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();

      if (url.endsWith("/filters")) {
        return new Response(JSON.stringify(buildReaderFiltersResponse()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      if (url.endsWith("/admin/incidents")) {
        return new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      return new Response(
        JSON.stringify({
          items: [
            buildIncident({
              id: "incident-march-1",
              headline: "Policy assistant invents a reimbursement rule",
              date_logged: "2026-03-07",
              categories: ["Policy"],
            }),
            buildIncident({
              id: "incident-april-1",
              headline: "Support bot exposes private account notes",
              date_logged: "2026-04-18",
              categories: ["Privacy/Security"],
            }),
            buildIncident({
              id: "incident-april-2",
              headline: "Pilot robot rollback follows route drift",
              date_logged: "2026-04-29",
              company_involved: "RoboFleet",
              claimant_name: "RoboFleet",
              categories: ["Autonomous Systems"],
            }),
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

    expect(
      await screen.findByRole("heading", {
        name: "Incident signals",
      }),
    ).toBeInTheDocument();

    expect(screen.getByText("Mar 2026")).toBeInTheDocument();
    expect(screen.getByText("Apr 2026")).toBeInTheDocument();
    expect(screen.getByText("1 incident")).toBeInTheDocument();
    expect(screen.getByText("2 incidents")).toBeInTheDocument();
    const categoryPanel = screen
      .getByRole("heading", {
        name: "Category distribution",
      })
      .closest("article");

    expect(categoryPanel).not.toBeNull();
    expect(
      within(categoryPanel as HTMLElement).getByRole("img", {
        name: "Category distribution donut chart",
      }),
    ).toBeInTheDocument();
    expect(
      within(categoryPanel as HTMLElement).getByText("Policy"),
    ).toBeInTheDocument();
    expect(
      within(categoryPanel as HTMLElement).getByText("Privacy/Security"),
    ).toBeInTheDocument();
    expect(
      within(categoryPanel as HTMLElement).getByText("Autonomous Systems"),
    ).toBeInTheDocument();
    expect(
      within(categoryPanel as HTMLElement).getAllByText("33%").length,
    ).toBeGreaterThan(0);
  });

  it("updates incident signals with reader filters and shows an empty summary state", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();

      if (url.endsWith("/filters")) {
        return new Response(JSON.stringify(buildReaderFiltersResponse()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      if (url.endsWith("/admin/incidents")) {
        return new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      if (url.includes("/incidents?category=Autonomous+Systems")) {
        return new Response(
          JSON.stringify({
            items: [
              buildIncident({
                id: "incident-robot-1",
                headline: "Warehouse robot rollback follows navigation failures",
                date_logged: "2026-04-24",
                company_involved: "RoboFleet",
                claimant_name: "RoboFleet",
                categories: ["Autonomous Systems"],
              }),
            ],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }

      if (url.includes("/incidents?company=RoboFleet")) {
        return new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }

      return new Response(
        JSON.stringify({
          items: [
            buildIncident({
              id: "incident-1",
              headline: "Customer support bot exposes private account notes",
              date_logged: "2026-04-29",
              categories: ["Privacy/Security"],
            }),
            buildIncident({
              id: "incident-2",
              headline: "Warehouse robot rollback follows navigation failures",
              date_logged: "2026-04-24",
              company_involved: "RoboFleet",
              claimant_name: "RoboFleet",
              categories: ["Autonomous Systems"],
            }),
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

    expect(
      await screen.findByRole("heading", {
        name: "Customer support bot exposes private account notes",
      }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Autonomous Systems" }));

    expect(
      await screen.findByRole("heading", {
        name: "Warehouse robot rollback follows navigation failures",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Apr 2026")).toBeInTheDocument();
    expect(screen.getByText("1 incident")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Autonomous Systems" }));
    fireEvent.change(screen.getByLabelText("Filter by company"), {
      target: { value: "RoboFleet" },
    });

    expect(
      await screen.findByText("No incidents match this slice yet."),
    ).toBeInTheDocument();
  });
});
