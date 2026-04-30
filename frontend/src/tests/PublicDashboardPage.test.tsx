import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";

import PublicDashboardPage from "../pages/PublicDashboardPage";
import {
  fetchIncidentDetail,
  fetchIncidentFeed,
  fetchIncidentFilters,
} from "../lib/api";
import type { Incident } from "../types/incident";

vi.mock("../lib/api", () => ({
  fetchIncidentDetail: vi.fn(),
  fetchIncidentFeed: vi.fn(),
  fetchIncidentFilters: vi.fn(),
}));

const mockedFetchIncidentDetail = vi.mocked(fetchIncidentDetail);
const mockedFetchIncidentFeed = vi.mocked(fetchIncidentFeed);
const mockedFetchIncidentFilters = vi.mocked(fetchIncidentFilters);

function buildIncident(overrides: Partial<Incident> = {}): Incident {
  return {
    id: overrides.id ?? "incident-1",
    headline:
      overrides.headline ??
      "Customer support bot exposes private account notes",
    headline_en:
      overrides.headline_en ??
      overrides.headline ??
      "Customer support bot exposes private account notes",
    headline_zh: overrides.headline_zh ?? "客服机器人泄露了私密账户备注",
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
      "一次支持自动化发布将内部备注泄露给了用户。",
    status: overrides.status ?? "approved",
    translation_status: overrides.translation_status ?? "completed",
    matched_claim: overrides.matched_claim ?? null,
    sources: overrides.sources ?? [],
  };
}

describe("PublicDashboardPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.resetAllMocks();

    mockedFetchIncidentFilters.mockResolvedValue({
      categories: ["Privacy/Security", "Autonomous Systems"],
      claimants: ["AssistCo", "RoboFleet"],
      companies: ["AssistCo", "RoboFleet"],
      years: [2026, 2025],
      months_by_year: {
        "2026": [4, 3],
        "2025": [12],
      },
    });
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it("renders live reader-facing sections and keeps the spotlight pinned to the latest incident", async () => {
    const latestIncident = buildIncident({
      id: "incident-1",
      headline: "AssistCo assistant exposes private billing notes",
      headline_en: "AssistCo assistant exposes private billing notes",
      headline_zh: "AssistCo 助手泄露了私密账单备注",
      date_logged: "2026-04-29",
      company_involved: "AssistCo",
      categories: ["Privacy/Security"],
      severity_score: 4,
      reality_summary:
        "A support automation rollout leaked internal notes into user-facing replies.",
      reality_summary_en:
        "A support automation rollout leaked internal notes into user-facing replies.",
      reality_summary_zh: "一次支持自动化发布将内部备注泄露给了用户。",
      matched_claim: {
        id: "claim-1",
        claimant_name: "AssistCo",
        company_involved: "AssistCo",
        original_claim: "Our assistant never exposes internal account notes.",
        claim_date: "2026-04-20",
        claim_topic: "privacy",
        match_confidence: 0.93,
      },
      sources: [
        {
          id: "source-latest",
          publisher: "Ledger News",
          source_type: "article",
          source_url: "https://example.com/assistco",
          title: "AssistCo assistant exposes private billing notes",
        },
      ],
    });

    const archiveIncident = buildIncident({
      id: "incident-2",
      headline: "RoboFleet robot pilot rollback follows navigation failures",
      headline_en: "RoboFleet robot pilot rollback follows navigation failures",
      headline_zh: "RoboFleet 机器人试点因导航失误而回滚",
      company_involved: "RoboFleet",
      claimant_name: "RoboFleet",
      incident_topic: "autonomy",
      categories: ["Autonomous Systems"],
      severity_score: 3,
      reality_summary:
        "An urban robot pilot paused after repeated routing mistakes.",
      reality_summary_en:
        "An urban robot pilot paused after repeated routing mistakes.",
      reality_summary_zh: "城市机器人试点在多次路线错误后被暂停。",
      date_logged: "2026-03-15",
      sources: [
        {
          id: "source-robot",
          publisher: "City Desk",
          source_type: "article",
          source_url: "https://example.com/robot-pilot",
          title: "Robot pilot paused after navigation failures",
        },
      ],
    });

    mockedFetchIncidentFeed.mockResolvedValue({
      items: [latestIncident, archiveIncident],
    });
    mockedFetchIncidentDetail.mockImplementation(async (incidentId: string) => {
      if (incidentId === "incident-1") {
        return latestIncident;
      }

      if (incidentId === "incident-2") {
        return archiveIncident;
      }

      throw new Error(`Unexpected incident detail request for ${incidentId}`);
    });

    render(<PublicDashboardPage />);

    expect(
      await screen.findByRole("heading", { name: "Incident spotlight" }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("group", { name: "Reader language switch" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "English" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    expect(screen.getByText("2 incidents in current feed")).toBeInTheDocument();
    const monthlySignal = screen.getByLabelText("Monthly incident signal");
    expect(within(monthlySignal).getByText("Apr 2026")).toBeInTheDocument();
    expect(within(monthlySignal).getByText("Mar 2026")).toBeInTheDocument();
    expect(within(monthlySignal).getAllByText("1 incident")).toHaveLength(2);

    const categorySignal = screen.getByLabelText(
      "Category distribution summary",
    );
    expect(
      within(categorySignal).getAllByText("50% of current feed"),
    ).toHaveLength(2);

    const spotlight = screen
      .getByRole("heading", { name: "Incident spotlight" })
      .closest("section");
    expect(spotlight).not.toBeNull();
    expect(
      within(spotlight as HTMLElement).getByRole("heading", {
        name: "AssistCo assistant exposes private billing notes",
      }),
    ).toBeInTheDocument();
    expect(
      within(spotlight as HTMLElement).getByRole("button", {
        name: /Open source-backed detail for AssistCo assistant exposes private billing notes/i,
      }),
    ).toBeInTheDocument();

    const archive = screen.getByRole("region", { name: "Incident archive" });
    expect(
      within(archive).getByText(
        "An urban robot pilot paused after repeated routing mistakes.",
      ),
    ).toBeInTheDocument();
    expect(within(archive).getByText("Severity 3")).toBeInTheDocument();
    expect(within(archive).getByText("Autonomous Systems")).toBeInTheDocument();

    await waitFor(() => {
      expect(mockedFetchIncidentDetail).toHaveBeenCalledWith("incident-1");
    });

    fireEvent.click(
      within(archive).getByRole("button", {
        name: /Open incident detail for RoboFleet robot pilot rollback follows navigation failures/i,
      }),
    );

    await waitFor(() => {
      expect(mockedFetchIncidentDetail).toHaveBeenLastCalledWith("incident-2");
    });

    expect(
      within(spotlight as HTMLElement).getByRole("heading", {
        name: "AssistCo assistant exposes private billing notes",
      }),
    ).toBeInTheDocument();

    const detail = screen
      .getByRole("heading", { name: "Incident detail" })
      .closest("section");
    expect(detail).not.toBeNull();
    expect(
      within(detail as HTMLElement).getByRole("heading", {
        name: "RoboFleet robot pilot rollback follows navigation failures",
      }),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByRole("link", {
        name: "Robot pilot paused after navigation failures",
      }),
    ).toHaveAttribute("href", "https://example.com/robot-pilot");

    fireEvent.click(screen.getByRole("button", { name: "中文" }));

    expect(
      within(spotlight as HTMLElement).getByRole("heading", {
        name: "AssistCo 助手泄露了私密账单备注",
      }),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByRole("heading", {
        name: "RoboFleet 机器人试点因导航失误而回滚",
      }),
    ).toBeInTheDocument();

    fireEvent.click(
      within(spotlight as HTMLElement).getByRole("button", {
        name: /Open source-backed detail for AssistCo 助手泄露了私密账单备注/i,
      }),
    );

    await waitFor(() => {
      expect(mockedFetchIncidentDetail).toHaveBeenLastCalledWith("incident-1");
    });

    expect(
      within(detail as HTMLElement).getByText("Claim vs. reality"),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByText(
        "Our assistant never exposes internal account notes.",
      ),
    ).toBeInTheDocument();
  });

  it("shows filter bootstrap failure and empty-state detail copy when no incidents are available", async () => {
    mockedFetchIncidentFilters.mockRejectedValue(new Error("filters failed"));
    mockedFetchIncidentFeed.mockResolvedValue({ items: [] });

    render(<PublicDashboardPage />);

    expect(
      await screen.findByText("Unable to load archive filters right now."),
    ).toBeInTheDocument();
    expect(screen.getByText("0 incidents in current feed")).toBeInTheDocument();
    expect(
      screen.getByText("No incidents match this slice yet."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Select an incident from the archive to inspect its sources.",
      ),
    ).toBeInTheDocument();
    expect(mockedFetchIncidentDetail).not.toHaveBeenCalled();
  });
});
