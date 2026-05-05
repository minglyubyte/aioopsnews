import {
  act,
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
import type {
  IncidentArchiveItem,
  IncidentDetail,
  IncidentFeedResponse,
} from "../types/incident";

vi.mock("../lib/api", () => ({
  fetchIncidentDetail: vi.fn(),
  fetchIncidentFeed: vi.fn(),
  fetchIncidentFilters: vi.fn(),
}));

const mockedFetchIncidentDetail = vi.mocked(fetchIncidentDetail);
const mockedFetchIncidentFeed = vi.mocked(fetchIncidentFeed);
const mockedFetchIncidentFilters = vi.mocked(fetchIncidentFilters);

function buildArchiveIncident(
  overrides: Partial<IncidentArchiveItem> = {},
): IncidentArchiveItem {
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
    company_involved_zh:
      "company_involved_zh" in overrides
        ? overrides.company_involved_zh ?? null
        : "助理公司",
    claimant_name: overrides.claimant_name ?? "AssistCo",
    incident_topic: overrides.incident_topic ?? "privacy",
    categories: overrides.categories ?? ["Privacy/Security"],
    severity_score: overrides.severity_score ?? 4,
    publication_track: overrides.publication_track ?? "accident_watch",
    evidence_tier: overrides.evidence_tier ?? "reported_unconfirmed",
    source_family: overrides.source_family ?? "customer_support",
    verification_summary:
      overrides.verification_summary ??
      "Reported by credible sources; official confirmation remains pending.",
    archive_summary:
      overrides.archive_summary ??
      "A support automation rollout leaked internal notes into user-facing replies.",
    archive_summary_en:
      overrides.archive_summary_en ??
      overrides.archive_summary ??
      "A support automation rollout leaked internal notes into user-facing replies.",
    archive_summary_zh:
      overrides.archive_summary_zh ??
      "一次支持自动化发布将内部备注泄露给了用户。",
    status: overrides.status ?? "approved",
    translation_status: overrides.translation_status ?? "completed",
  };
}

function buildIncidentDetail(
  overrides: Partial<IncidentDetail> = {},
): IncidentDetail {
  const archiveIncident = buildArchiveIncident(overrides);

  return {
    ...archiveIncident,
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
    analysis: overrides.analysis ?? {
      incident_summary_en:
        "A support automation rollout exposed private notes in customer replies.",
      incident_summary_zh: "一次支持自动化发布在客户回复中暴露了私密备注。",
      what_happened_en:
        "A support automation rollout leaked internal notes into user-facing replies.",
      what_happened_zh: "一次支持自动化发布将内部备注泄露给了用户。",
      ai_failure_point_en:
        "The assistant failed to keep internal support context out of generated replies.",
      ai_failure_point_zh: "该助手未能阻止内部支持上下文进入生成的回复。",
      why_it_matters_en:
        "Private account context escaped the support workflow and reached customers directly.",
      why_it_matters_zh: "私密账户背景信息离开了支持工作流，并直接出现在客户对话中。",
      evidence_summary_en:
        "The incident was validated through a primary report and corroborating coverage.",
      evidence_summary_zh: "这起事件已通过一手报告和补充报道完成核实。",
    },
    matched_claim: overrides.matched_claim ?? null,
    sources: overrides.sources ?? [],
  };
}

function buildFeedResponse(
  items: IncidentArchiveItem[],
  overrides: Partial<IncidentFeedResponse> = {},
): IncidentFeedResponse {
  return {
    items,
    page: overrides.page ?? 1,
    page_size: overrides.page_size ?? 6,
    total_count: overrides.total_count ?? items.length,
    total_pages: overrides.total_pages ?? 1,
    has_next_page: overrides.has_next_page ?? false,
    has_previous_page: overrides.has_previous_page ?? false,
    slice_summary:
      overrides.slice_summary ?? {
        total_matches: items.length,
        newest_logged: items[0]?.date_logged ?? null,
        oldest_logged: items.at(-1)?.date_logged ?? null,
        highest_severity: Math.max(...items.map((item) => item.severity_score), 0),
        top_categories: [
          ...new Map(
            items.flatMap((item) =>
              item.categories.map((category) => [
                category,
                items.filter((candidate) =>
                  candidate.categories.includes(category),
                ).length,
              ]),
            ),
          ).entries(),
        ].map(([category, count]) => ({ category, count })),
        top_companies: [
          ...new Map(
            items.map((item) => [
              item.company_involved,
              items.filter(
                (candidate) => candidate.company_involved === item.company_involved,
              ).length,
            ]),
          ).entries(),
        ].map(([company, count]) => ({ company, count })),
      },
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
      company_labels_zh: {
        AssistCo: "助理公司",
        RoboFleet: "机器人舰队",
      },
      publication_tracks: ["accident_watch", "verified_accident"],
      source_families: ["customer_support", "autonomous_vehicle"],
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

  it("renders dual-track sections, evidence metadata, filters, and detail evidence block", async () => {
    const verifiedIncident = buildArchiveIncident({
      id: "incident-verified",
      headline: "DMV collision report documents autonomous vehicle crash",
      headline_en: "DMV collision report documents autonomous vehicle crash",
      date_logged: "2026-05-02",
      company_involved: "RoboFleet",
      company_involved_zh: "机器人舰队",
      categories: ["Autonomous Systems"],
      publication_track: "verified_accident",
      evidence_tier: "official_documented",
      source_family: "autonomous_vehicle",
      verification_summary:
        "California DMV documents the collision; editorial review still checks AI relevance and severity.",
      archive_summary:
        "A fixed verified source documents an autonomous vehicle collision.",
    });
    const watchIncident = buildArchiveIncident({
      id: "incident-watch",
      headline: "AI coding assistant blamed for migration outage",
      headline_en: "AI coding assistant blamed for migration outage",
      company_involved: "DeployAI",
      company_involved_zh: null,
      categories: ["Model Governance"],
      publication_track: "accident_watch",
      evidence_tier: "reported_unconfirmed",
      source_family: "coding_failure",
      verification_summary:
        "Search discovery found reporting, but no official source has verified the incident yet.",
      archive_summary:
        "Reporting says a coding assistant produced a broken migration.",
    });

    mockedFetchIncidentFeed.mockResolvedValue(
      buildFeedResponse([verifiedIncident, watchIncident]),
    );
    mockedFetchIncidentDetail.mockResolvedValue(
      buildIncidentDetail({
        ...verifiedIncident,
        sources: [
          {
            id: "source-dmv",
            source_url: "https://www.dmv.ca.gov/report.pdf",
            source_type: "official",
            source_origin: "fixed_verified_source",
            source_registry_key: "ca_dmv_av_collisions",
            raw_source_payload: { report_number: "OL 316" },
            publisher: "California DMV",
            title: "Autonomous vehicle collision report",
          },
        ],
      }),
    );

    render(<PublicDashboardPage />);

    expect(
      await screen.findByText(
        "A readable watchlist of AI failures and verified accidents",
      ),
    ).toBeInTheDocument();

    const verifiedSection = screen
      .getByRole("heading", { name: "Verified AI Accidents" })
      .closest("section");
    const watchSection = screen
      .getByRole("heading", { name: "AI Accident Watch" })
      .closest("section");

    expect(verifiedSection).not.toBeNull();
    expect(watchSection).not.toBeNull();
    expect(
      within(verifiedSection as HTMLElement).getByText(
        "DMV collision report documents autonomous vehicle crash",
      ),
    ).toBeInTheDocument();
    expect(
      within(verifiedSection as HTMLElement).getByText("Official documented"),
    ).toBeInTheDocument();
    expect(
      within(verifiedSection as HTMLElement).getByText("Autonomous vehicle"),
    ).toBeInTheDocument();
    expect(
      within(watchSection as HTMLElement).getByText(
        "AI coding assistant blamed for migration outage",
      ),
    ).toBeInTheDocument();
    expect(
      within(watchSection as HTMLElement).getByText("Reported unconfirmed"),
    ).toBeInTheDocument();
    expect(
      within(watchSection as HTMLElement).getByText("Coding failure"),
    ).toBeInTheDocument();

    expect(screen.getByLabelText("Filter by track")).toBeInTheDocument();
    expect(screen.getByLabelText("Filter by source family")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Filter by track"), {
      target: { value: "verified_accident" },
    });

    await waitFor(() => {
      expect(mockedFetchIncidentFeed).toHaveBeenLastCalledWith(
        expect.objectContaining({ publicationTrack: "verified_accident" }),
      );
    });

    expect(
      screen.getByRole("heading", { name: "What is confirmed" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "What remains uncertain" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Primary source trail" }),
    ).toBeInTheDocument();
    const confirmedBlock = screen
      .getByRole("heading", { name: "What is confirmed" })
      .closest("div");
    expect(confirmedBlock).not.toBeNull();
    expect(
      within(confirmedBlock as HTMLElement).getByText(
        "California DMV documents the collision; editorial review still checks AI relevance and severity.",
      ),
    ).toBeInTheDocument();
  });

  it("keeps empty track sections visible", async () => {
    const verifiedIncident = buildArchiveIncident({
      id: "incident-verified-only",
      headline: "DMV collision report documents autonomous vehicle crash",
      headline_en: "DMV collision report documents autonomous vehicle crash",
      publication_track: "verified_accident",
      evidence_tier: "official_documented",
      source_family: "autonomous_vehicle",
    });

    mockedFetchIncidentFeed.mockResolvedValue(
      buildFeedResponse([verifiedIncident]),
    );
    mockedFetchIncidentDetail.mockResolvedValue(
      buildIncidentDetail(verifiedIncident),
    );

    render(<PublicDashboardPage />);

    const watchSection = (
      await screen.findByRole("heading", { name: "AI Accident Watch" })
    ).closest("section");

    expect(watchSection).not.toBeNull();
    expect(
      within(watchSection as HTMLElement).getByText(
        "No watch items in this slice yet.",
      ),
    ).toBeInTheDocument();
  });

  it("renders slice-level highlights, localized archive cards, and source-backed detail", async () => {
    const latestIncident = buildArchiveIncident({
      id: "incident-1",
      headline: "AssistCo assistant exposes private billing notes",
      headline_en: "AssistCo assistant exposes private billing notes",
      headline_zh: "AssistCo 助手泄露了私密账单备注",
      date_logged: "2026-12-29",
      company_involved: "AssistCo",
      company_involved_zh: "助理公司",
      categories: ["Privacy/Security"],
      severity_score: 4,
      archive_summary:
        "A support automation rollout leaked internal notes into user-facing replies.",
      archive_summary_en:
        "A support automation rollout leaked internal notes into user-facing replies.",
      archive_summary_zh: "一次支持自动化发布将内部备注泄露给了用户。",
    });

    const latestIncidentDetail = buildIncidentDetail({
      ...latestIncident,
      reality_summary:
        "A support automation rollout leaked internal notes into user-facing replies.",
      reality_summary_en:
        "A support automation rollout leaked internal notes into user-facing replies.",
      reality_summary_zh: "一次支持自动化发布将内部备注泄露给了用户。",
      analysis: {
        incident_summary_en:
          "A support automation release exposed private billing notes in customer replies.",
        incident_summary_zh: "一次支持自动化发布在客户回复中暴露了私密账单备注。",
        what_happened_en:
          "A support automation rollout leaked internal notes into user-facing replies.",
        what_happened_zh: "一次支持自动化发布将内部备注泄露给了用户。",
        ai_failure_point_en:
          "The reply composer mixed internal billing annotations into customer-facing output.",
        ai_failure_point_zh: "回复生成器将内部账单注释混入了面向客户的输出。",
        why_it_matters_en:
          "Sensitive billing context appeared in customer conversations instead of staying inside the support workflow.",
        why_it_matters_zh:
          "敏感的账单背景信息出现在客户对话中，而不是留在支持工作流内部。",
        evidence_summary_en:
          "Ledger News documented the exposure and the company later disabled the feature.",
        evidence_summary_zh: "Ledger News 记录了这次暴露，随后公司关闭了该功能。",
      },
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

    const archiveIncident = buildArchiveIncident({
      id: "incident-2",
      headline: "RoboFleet robot pilot rollback follows navigation failures",
      headline_en: "RoboFleet robot pilot rollback follows navigation failures",
      headline_zh: "RoboFleet 机器人试点因导航失误而回滚",
      company_involved: "RoboFleet",
      company_involved_zh: null,
      claimant_name: "RoboFleet",
      incident_topic: "autonomy",
      categories: ["Autonomous Systems"],
      severity_score: 3,
      archive_summary:
        "An urban robot pilot paused after repeated routing mistakes.",
      archive_summary_en:
        "An urban robot pilot paused after repeated routing mistakes.",
      archive_summary_zh: "城市机器人试点在多次路线错误后被暂停。",
      date_logged: "2026-10-15",
    });

    const archiveIncidentDetail = buildIncidentDetail({
      ...archiveIncident,
      reality_summary:
        "An urban robot pilot paused after repeated routing mistakes and multiple manual interventions.",
      reality_summary_en:
        "An urban robot pilot paused after repeated routing mistakes and multiple manual interventions.",
      reality_summary_zh:
        "城市机器人试点在多次路线错误和人工干预后被暂停。",
      analysis: {
        incident_summary_en:
          "An urban robot pilot paused after repeated navigation failures.",
        incident_summary_zh: "一次城市机器人试点在反复的导航失误后被暂停。",
        what_happened_en:
          "Repeated navigation failures forced operators to pause the urban robot pilot.",
        what_happened_zh: "反复的导航失误迫使运营人员暂停了城市机器人试点。",
        ai_failure_point_en:
          "The autonomy stack could not reliably interpret dense downtown routing constraints.",
        ai_failure_point_zh: "自动驾驶栈无法稳定理解高密度市中心路线约束。",
        why_it_matters_en:
          "The rollback shows the system still could not handle dense downtown routing without human supervision.",
        why_it_matters_zh:
          "这次回滚说明系统仍然无法在没有人工监督的情况下处理高密度市中心路线。",
        evidence_summary_en:
          "City Desk reported the pause and linked it to repeated routing mistakes during the pilot.",
        evidence_summary_zh:
          "City Desk 报道了这次暂停，并将其与试点期间反复出现的路线错误联系起来。",
      },
      matched_claim: {
        id: "claim-2",
        claimant_name: "RoboFleet",
        company_involved: "RoboFleet",
        original_claim: "The pilot can already handle dense downtown routing.",
        claim_date: "2026-10-01",
        claim_topic: "autonomy",
        match_confidence: 0.82,
      },
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

    mockedFetchIncidentFeed.mockResolvedValue(
      buildFeedResponse([latestIncident, archiveIncident], {
        total_count: 8,
        total_pages: 2,
        has_next_page: true,
        slice_summary: {
          total_matches: 8,
          newest_logged: "2026-12-29",
          oldest_logged: "2026-10-15",
          highest_severity: 4,
          top_categories: [
            { category: "Privacy/Security", count: 5 },
            { category: "Autonomous Systems", count: 3 },
          ],
          top_companies: [
            { company: "AssistCo", company_zh: "助理公司", count: 5 },
            { company: "RoboFleet", company_zh: "机器人舰队", count: 3 },
          ],
        },
      }),
    );
    mockedFetchIncidentDetail.mockImplementation(async (incidentId: string) => {
      if (incidentId === "incident-1") {
        return latestIncidentDetail;
      }

      if (incidentId === "incident-2") {
        return archiveIncidentDetail;
      }

      throw new Error(`Unexpected incident detail request for ${incidentId}`);
    });

    render(<PublicDashboardPage />);

    expect(
      await screen.findByRole("heading", { name: "Quick takeaway" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Editor queue" }),
    ).not.toBeInTheDocument();

    expect(
      screen.getByRole("group", { name: "Reader language switch" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "English" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    expect(screen.getByText("2 incidents in current feed")).toBeInTheDocument();
    const monthlySignal = screen.getByLabelText("Monthly incident signal");
    const monthlyItems = within(monthlySignal).getAllByRole("listitem");
    expect(
      within(monthlyItems[0] as HTMLElement).getByText("Dec 2026"),
    ).toBeInTheDocument();
    expect(
      within(monthlyItems[1] as HTMLElement).getByText("Oct 2026"),
    ).toBeInTheDocument();
    expect(within(monthlySignal).getAllByText("1 incident")).toHaveLength(2);

    const categorySignal = screen.getByLabelText(
      "Category distribution summary",
    );
    expect(
      within(categorySignal).getAllByText("50% of current feed"),
    ).toHaveLength(2);

    const spotlight = screen.getByRole("heading", { name: "Quick takeaway" }).closest(
      "section",
    );
    expect(spotlight).not.toBeNull();
    expect(
      within(spotlight as HTMLElement).getByText("Slice-level view"),
    ).toBeInTheDocument();
    expect(
      within(spotlight as HTMLElement).getByText("Matches"),
    ).toBeInTheDocument();
    expect(within(spotlight as HTMLElement).getByText("8")).toBeInTheDocument();
    expect(
      within(spotlight as HTMLElement).getByText(
        "Privacy/Security (5), Autonomous Systems (3)",
      ),
    ).toBeInTheDocument();
    expect(
      within(spotlight as HTMLElement).queryByRole("button", {
        name: /Open full context/i,
      }),
    ).not.toBeInTheDocument();
    expect(
      within(spotlight as HTMLElement).queryByText("Claim vs. reality"),
    ).not.toBeInTheDocument();

    const archiveControls = screen.getByRole("region", {
      name: "Archive controls",
    });
    expect(
      within(archiveControls).getByLabelText("Filter by category"),
    ).toBeInTheDocument();
    expect(
      within(archiveControls).getByLabelText("Filter by company"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("heading", { name: "Incident signals" }).closest("section") as HTMLElement).getByRole(
        "heading",
        { name: "Archive controls" },
      ),
    ).toBeInTheDocument();

    const archive = screen.getByRole("region", { name: "Browse incidents" });
    expect(
      within(archive).getByText(
        "An urban robot pilot paused after repeated routing mistakes.",
      ),
    ).toBeInTheDocument();
    expect(within(archive).getByText("Severity 3")).toBeInTheDocument();
    expect(within(archive).getByText("Autonomous Systems")).toBeInTheDocument();
    expect(within(archive).queryByText("Claim vs. reality")).not.toBeInTheDocument();
    expect(within(archive).getByText("Page 1 of 2")).toBeInTheDocument();
    expect(within(archive).getByText("Showing 2 of 8 incidents")).toBeInTheDocument();
    expect(within(archive).getByText("AssistCo")).toBeInTheDocument();
    expect(latestIncident.company_involved_zh).toBe("助理公司");

    await waitFor(() => {
      expect(mockedFetchIncidentDetail).toHaveBeenCalledWith("incident-1");
    });

    const detail = screen
      .getByRole("heading", { name: "Full context" })
      .closest("section");
    expect(detail).not.toBeNull();
    expect(
      within(detail as HTMLElement).getByRole("heading", {
        name: "AssistCo assistant exposes private billing notes",
      }),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByText("What happened"),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByText(
        "A support automation release exposed private billing notes in customer replies.",
      ),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByText("AI failure point"),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByText(
        "The reply composer mixed internal billing annotations into customer-facing output.",
      ),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByText("Why it matters"),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByText("Evidence summary"),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByText("Claim vs. reality"),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByRole("link", {
        name: "AssistCo assistant exposes private billing notes",
      }),
    ).toHaveAttribute("href", "https://example.com/assistco");

    fireEvent.click(screen.getByRole("button", { name: "中文" }));

    expect(
      screen.getByRole("heading", { name: "AI 现实校验" }),
    ).toBeInTheDocument();
    expect(
      within(spotlight as HTMLElement).getByText("筛选摘要"),
    ).toBeInTheDocument();
    expect(
      within(spotlight as HTMLElement).getByText("隐私 / 安全 (5)、自主系统 (3)"),
    ).toBeInTheDocument();
    expect(
      within(spotlight as HTMLElement).getByText("助理公司 (5)、机器人舰队 (3)"),
    ).toBeInTheDocument();
    expect(
      await within(detail as HTMLElement).findByRole("heading", {
        name: "AssistCo 助手泄露了私密账单备注",
      }),
    ).toBeInTheDocument();
    expect(within(archive).getByText("隐私 / 安全")).toBeInTheDocument();
    expect(within(archive).getByText("自主系统")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "事件信号" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "档案筛选" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("你是否也受够了这样的标题？"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "我们想提醒你，AI 并不完美，所以放轻松，不要恐慌。",
      ),
    ).toBeInTheDocument();

    expect(
      within(detail as HTMLElement).getByRole("heading", {
        name: "AssistCo 助手泄露了私密账单备注",
      }),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByText("声明 vs. 现实"),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByText(
        "Our assistant never exposes internal account notes.",
      ),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByText(
        "一次支持自动化发布在客户回复中暴露了私密账单备注。",
      ),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByText("AI 失效点"),
    ).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByText(
        "回复生成器将内部账单注释混入了面向客户的输出。",
      ),
    ).toBeInTheDocument();
    expect(within(archive).getByText("助理公司")).toBeInTheDocument();
    expect(within(detail as HTMLElement).getByText("助理公司")).toBeInTheDocument();

    fireEvent.click(
      within(archive).getByRole("button", {
        name: /打开 RoboFleet 机器人试点因导航失误而回滚 的完整背景/i,
      }),
    );

    await waitFor(() => {
      expect(mockedFetchIncidentDetail).toHaveBeenLastCalledWith("incident-2");
    });
    await waitFor(() => {
      expect(
        within(detail as HTMLElement).getByRole("heading", {
          name: "RoboFleet 机器人试点因导航失误而回滚",
        }),
      ).toBeInTheDocument();
    });
    expect(within(archive).getByText("RoboFleet")).toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getAllByText("RoboFleet"),
    ).toHaveLength(2);
  });

  it("uses Chinese company labels for filter options while keeping canonical company values", async () => {
    mockedFetchIncidentFeed.mockResolvedValue(
      buildFeedResponse([buildArchiveIncident()]),
    );
    mockedFetchIncidentDetail.mockResolvedValue(buildIncidentDetail());

    render(<PublicDashboardPage />);

    await screen.findByRole("heading", { name: "Quick takeaway" });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "中文" }));
    });

    const companyFilter = screen.getByLabelText("按公司筛选") as HTMLSelectElement;
    const option = within(companyFilter).getByRole("option", {
      name: "助理公司",
    }) as HTMLOptionElement;

    expect(option.value).toBe("AssistCo");

    await act(async () => {
      fireEvent.change(companyFilter, { target: { value: "AssistCo" } });
    });

    expect(companyFilter.value).toBe("AssistCo");
    await waitFor(() => {
      expect(mockedFetchIncidentFeed).toHaveBeenLastCalledWith(
        expect.objectContaining({ company: "AssistCo" }),
      );
    });
  });

  it("shows filter bootstrap failure and empty-state detail copy when no incidents are available", async () => {
    mockedFetchIncidentFilters.mockRejectedValue(new Error("filters failed"));
    mockedFetchIncidentFeed.mockResolvedValue(buildFeedResponse([]));

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
        "Select an incident from the archive to inspect the full context and sources.",
      ),
    ).toBeInTheDocument();
    expect(mockedFetchIncidentDetail).not.toHaveBeenCalled();
  });

  it("shows a public feed failure without exposing editor controls", async () => {
    mockedFetchIncidentFeed.mockRejectedValue(new Error("feed failed"));
    mockedFetchIncidentDetail.mockImplementation(async () => {
      throw new Error("detail should not load");
    });

    render(<PublicDashboardPage />);

    expect(
      await screen.findByText("Unable to load the incident feed right now."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Editor queue" }),
    ).not.toBeInTheDocument();
    expect(mockedFetchIncidentDetail).not.toHaveBeenCalled();
  });

  it("shows a localized detail failure and lets readers retry the same incident", async () => {
    const incident = buildArchiveIncident({
      id: "incident-3",
      headline: "Warehouse classifier reroutes medical inventory",
      headline_en: "Warehouse classifier reroutes medical inventory",
      date_logged: "2026-11-05",
      company_involved: "SortGrid",
      categories: ["Operations"],
      severity_score: 5,
      archive_summary:
        "A warehouse classifier repeatedly misrouted urgent medical stock.",
      archive_summary_en:
        "A warehouse classifier repeatedly misrouted urgent medical stock.",
    });

    const incidentDetail = buildIncidentDetail({
      ...incident,
      reality_summary:
        "A warehouse classifier repeatedly misrouted urgent medical stock.",
      reality_summary_en:
        "A warehouse classifier repeatedly misrouted urgent medical stock.",
      analysis: {
        what_happened_en:
          "A warehouse classifier repeatedly misrouted urgent medical stock.",
        why_it_matters_en:
          "Critical supplies were delayed because the model kept sending them to the wrong handling lane.",
        evidence_summary_en:
          "Operations logs and staff review confirmed repeated misrouting during the rollout.",
      },
    });

    mockedFetchIncidentFeed.mockResolvedValue(buildFeedResponse([incident]));
    mockedFetchIncidentDetail
      .mockRejectedValueOnce(new Error("detail failed"))
      .mockResolvedValueOnce(incidentDetail);

    render(<PublicDashboardPage />);

    await waitFor(() => {
      expect(mockedFetchIncidentDetail).toHaveBeenCalledWith("incident-3");
    });

    expect(
      await screen.findByText("Unable to load incident details right now."),
    ).toBeInTheDocument();

    fireEvent.click(
      within(screen.getByRole("region", { name: "Browse incidents" })).getByRole(
        "button",
        {
        name: /Open full context for Warehouse classifier reroutes medical inventory/i,
        },
      ),
    );

    await waitFor(() => {
      expect(mockedFetchIncidentDetail).toHaveBeenCalledTimes(2);
    });
    const detail = screen
      .getByRole("heading", { name: "Full context" })
      .closest("section");
    expect(detail).not.toBeNull();
    expect(
      screen.queryByText("Unable to load incident details right now."),
    ).not.toBeInTheDocument();
    expect(
      within(detail as HTMLElement).getByRole("heading", {
        name: "Warehouse classifier reroutes medical inventory",
      }),
    ).toBeInTheDocument();
  });

  it("renders the forensic detail structure for legacy incidents without structured ai failure data", async () => {
    const legacyIncident = buildArchiveIncident({
      id: "incident-legacy",
      headline:
        "Mercedes Benz: An autonomous testing vehicle was involved in a collision requiring formal documentation submission to the California Department of Motor Vehicles.",
      company_involved: "Mercedes Benz",
      categories: ["Autonomous Systems"],
      severity_score: 2,
      archive_summary:
        "An autonomous testing vehicle was involved in a collision requiring formal documentation submission to the California Department of Motor Vehicles.",
      archive_summary_en:
        "An autonomous testing vehicle was involved in a collision requiring formal documentation submission to the California Department of Motor Vehicles.",
      date_logged: "2023-11-29",
    });

    mockedFetchIncidentFeed.mockResolvedValue(buildFeedResponse([legacyIncident]));
    mockedFetchIncidentDetail.mockResolvedValue(
      buildIncidentDetail({
        ...legacyIncident,
        reality_summary:
          "An autonomous testing vehicle was involved in a collision requiring formal documentation submission to the California Department of Motor Vehicles.",
        reality_summary_en:
          "An autonomous testing vehicle was involved in a collision requiring formal documentation submission to the California Department of Motor Vehicles.",
        analysis: {
          what_happened_en: null,
          what_happened_zh: null,
          ai_failure_point_en: null,
          ai_failure_point_zh: null,
          why_it_matters_en:
            "Incident involves a Mercedes Benz autonomous testing vehicle collision with official DMV documentation.",
          why_it_matters_zh: null,
          evidence_summary_en:
            "High quality, official DMV collision report and academic dashboard.",
          evidence_summary_zh: null,
        },
      }),
    );

    render(<PublicDashboardPage />);

    fireEvent.click(
      await screen.findByRole("button", {
        name: /Open full context for Mercedes Benz: An autonomous testing vehicle was involved in a collision requiring formal documentation submission to the California Department of Motor Vehicles./i,
      }),
    );

    const detail = await screen.findByRole("heading", { name: "Full context" });
    const detailSection = detail.closest("section");
    expect(detailSection).not.toBeNull();
    expect(
      within(detailSection as HTMLElement).getByText("AI failure point"),
    ).toBeInTheDocument();
    expect(
      within(detailSection as HTMLElement).getByText(
        "Not yet structured for this incident.",
      ),
    ).toBeInTheDocument();
    expect(
      within(detailSection as HTMLElement).queryByText("What happened"),
    ).not.toBeInTheDocument();
    expect(
      within(detailSection as HTMLElement).getAllByText(
        "An autonomous testing vehicle was involved in a collision requiring formal documentation submission to the California Department of Motor Vehicles.",
      ),
    ).toHaveLength(1);
  });

  it("paginates archive results and keeps the selected detail visible across page changes", async () => {
    const firstPageIncident = buildArchiveIncident({
      id: "incident-page-1",
      headline: "First page incident",
      date_logged: "2026-11-20",
    });
    const secondPageIncident = buildArchiveIncident({
      id: "incident-page-2",
      headline: "Second page incident",
      date_logged: "2026-11-12",
      company_involved: "PageCo",
    });

    mockedFetchIncidentFeed
      .mockResolvedValueOnce(
        buildFeedResponse([firstPageIncident], {
          total_count: 7,
          total_pages: 2,
          has_next_page: true,
        }),
      )
      .mockResolvedValueOnce(
        buildFeedResponse([secondPageIncident], {
          page: 2,
          total_count: 7,
          total_pages: 2,
          has_next_page: false,
          has_previous_page: true,
        }),
      );
    mockedFetchIncidentDetail.mockResolvedValue(
      buildIncidentDetail({
        ...firstPageIncident,
        analysis: {
          what_happened_en: "First page incident detail",
        },
      }),
    );

    render(<PublicDashboardPage />);

    await screen.findByText("Page 1 of 2");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    await screen.findByText("Page 2 of 2");
    expect(screen.getByText("Second page incident")).toBeInTheDocument();
    expect(
      mockedFetchIncidentFeed.mock.calls[0]?.[0],
    ).toMatchObject({ page: 1, pageSize: 6 });
    expect(
      mockedFetchIncidentFeed.mock.calls[1]?.[0],
    ).toMatchObject({ page: 2, pageSize: 6 });
    expect(
      screen.getByRole("heading", { name: "First page incident" }),
    ).toBeInTheDocument();
  });

  it("renders a public theme switch, defaults to light, and persists dark mode after toggle", async () => {
    mockedFetchIncidentFeed.mockResolvedValue(
      buildFeedResponse([buildArchiveIncident()]),
    );
    mockedFetchIncidentDetail.mockResolvedValue(buildIncidentDetail());

    render(<PublicDashboardPage />);

    expect(
      await screen.findByRole("group", { name: "Reader theme switch" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Light" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("main")).toHaveAttribute("data-theme", "light");

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Dark" }));
    });

    expect(screen.getByRole("button", { name: "Dark" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("main")).toHaveAttribute("data-theme", "dark");
    expect(window.localStorage.getItem("ai-reality-check-theme")).toBe("dark");
  });
});
