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
import { buildIncidentUrl } from "../lib/publicIncidentRoutes";
import { buildTopicUrl } from "../lib/publicTopicRoutes";
import { RouteEntry } from "../main";
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
        ? (overrides.company_involved_zh ?? null)
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
      why_it_matters_zh:
        "私密账户背景信息离开了支持工作流，并直接出现在客户对话中。",
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
    page_size: overrides.page_size ?? 20,
    total_count: overrides.total_count ?? items.length,
    total_pages: overrides.total_pages ?? 1,
    has_next_page: overrides.has_next_page ?? false,
    has_previous_page: overrides.has_previous_page ?? false,
    slice_summary: overrides.slice_summary ?? {
      total_matches: items.length,
      newest_logged: items[0]?.date_logged ?? null,
      oldest_logged: items.at(-1)?.date_logged ?? null,
      highest_severity: Math.max(
        ...items.map((item) => item.severity_score),
        0,
      ),
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
              (candidate) =>
                candidate.company_involved === item.company_involved,
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
    vi.unstubAllEnvs();
    document
      .querySelector<HTMLMetaElement>('meta[name="robots"]')
      ?.remove();
    window.history.pushState({}, "", "/");
  });

  it("renders dual-track sections, evidence metadata, filters, and case file links without loading inline detail", async () => {
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

    render(<PublicDashboardPage />);

    expect(
      await screen.findByText(
        "A readable watchlist of AI failures and verified accidents",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/AI Oops News is for informational and research purposes only/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Read full disclaimer" }),
    ).toHaveAttribute("href", "/disclaimer");

    const verifiedSection = screen
      .getByRole("heading", { name: "Verified AI Accidents" })
      .closest("section");
    const watchSection = screen
      .getByRole("heading", { name: "AI News" })
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
    expect(
      within(verifiedSection as HTMLElement).getByRole("link", {
        name: /Open case file/i,
      }),
    ).toHaveAttribute(
      "href",
      "/incidents/incident-verified/dmv-collision-report-documents-autonomous-vehicle-crash",
    );

    expect(screen.getByLabelText("Filter by track")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Filter by source family"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Full context" }),
    ).not.toBeInTheDocument();
    expect(mockedFetchIncidentDetail).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Filter by track"), {
      target: { value: "verified_accident" },
    });

    await waitFor(() => {
      expect(mockedFetchIncidentFeed).toHaveBeenLastCalledWith(
        expect.objectContaining({ publicationTrack: "verified_accident" }),
      );
    });
    expect(mockedFetchIncidentDetail).not.toHaveBeenCalled();
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
      await screen.findByRole("heading", { name: "AI News" })
    ).closest("section");

    expect(watchSection).not.toBeNull();
    expect(
      within(watchSection as HTMLElement).getByText(
        "No AI news items in this slice yet.",
      ),
    ).toBeInTheDocument();
  });

  it("renders an incident detail page from a shareable incident URL", async () => {
    const boundingClientRectSpy = vi
      .spyOn(HTMLElement.prototype, "getBoundingClientRect")
      .mockReturnValue({
        bottom: 100,
        height: 100,
        left: 0,
        right: 100,
        top: 0,
        width: 100,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      });
    const originalHeadline =
      "Legal filing: Damien Charlotin's AI hallucination tracker records Amanda Adams v. Allen Butler Construction, Inc. in CA Texas with Pro Se Litigant linked to alleged or found AI legal hallucination. Nature: Fabricated: Case Law | Appellant cited several cases that do not exist.";
    const incident = buildIncidentDetail({
      id: "incident-routed",
      headline: originalHeadline,
      headline_en: originalHeadline,
      date_logged: "2026-05-06",
      company_involved: "Court filing",
      categories: ["Legal Hallucination"],
      severity_score: 4,
      publication_track: "verified_accident",
      evidence_tier: "court_or_regulator",
      source_family: "legal_hallucination",
      reality_summary:
        "A court sanctioned a filing after it included fake AI-generated citations.",
      reality_summary_en:
        "A court sanctioned a filing after it included fake AI-generated citations.",
      verification_summary:
        "A court record confirms the sanctions and fake citations.",
      analysis: {
        incident_summary_en:
          "A court sanctioned a filing after it included fake AI-generated citations.",
        what_happened_en:
          "The brief included cases the court could not verify.",
        ai_failure_point_en:
          "The AI-assisted workflow produced fake legal citations.",
        why_it_matters_en:
          "The incident shows why legal AI output needs source verification.",
        evidence_summary_en:
          "The court order documents the sanctions and citation failures.",
      },
      sources: [
        {
          id: "source-court",
          source_url: "https://example.com/court-order.pdf",
          source_type: "court",
          publisher: "Court order",
          title: "Sanctions order",
        },
        {
          id: "source-empty-labels",
          source_url:
            "https://www.damiencharlotin.com/documents/2078/Butler_v._Fidelity_USA_30_April_2026.pdf",
          source_type: "imported",
          publisher: "",
          title: "",
        },
      ],
    });

    mockedFetchIncidentDetail.mockResolvedValue(incident);
    window.history.pushState(
      {},
      "",
      "/incidents/incident-routed/court-sanctions-brief-with-fake-ai-citations",
    );

    render(<RouteEntry />);

    await waitFor(() => {
      expect(mockedFetchIncidentDetail).toHaveBeenCalledWith("incident-routed");
    });
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "AI legal hallucination: Amanda Adams v. Allen Butler Construction, Inc.",
      }),
    ).toBeInTheDocument();
    expect(document.title).toBe(
      "AI legal hallucination: Amanda Adams v. Allen Butler Construction, Inc. | AI Oops News",
    );
    expect(
      document.querySelector<HTMLMetaElement>('meta[name="description"]')
        ?.content,
    ).toBe(
      "A court sanctioned a filing after it included fake AI-generated citations.",
    );
    expect(screen.getByText("Court filing")).toBeInTheDocument();
    expect(screen.getByText("Severity 4")).toBeInTheDocument();
    expect(screen.getByText("May 6, 2026")).toBeInTheDocument();
    expect(screen.getAllByText("Verified accident").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Court or regulator").length).toBeGreaterThan(0);
    expect(screen.getByText("At a glance")).toBeInTheDocument();
    expect(screen.getByText("Source count")).toBeInTheDocument();
    expect(screen.getByText("2 sources")).toBeInTheDocument();
    expect(screen.getByText("What happened")).toBeInTheDocument();
    expect(screen.getByText("Primary source trail")).toBeInTheDocument();
    expect(
      screen.getByText(
        "This case file summarizes cited sources. It is not legal advice. Verify against the original documents.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Court source")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Sanctions order" }),
    ).toHaveAttribute("href", "https://example.com/court-order.pdf");
    expect(screen.getByText("damiencharlotin.com")).toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: "damiencharlotin.com/documents/2078/Butler_v._Fidelity_USA_30_April_2026.pdf",
      }),
    ).toHaveAttribute(
      "href",
      "https://www.damiencharlotin.com/documents/2078/Butler_v._Fidelity_USA_30_April_2026.pdf",
    );
    expect(
      screen
        .getByRole("link", {
          name: "damiencharlotin.com/documents/2078/Butler_v._Fidelity_USA_30_April_2026.pdf",
        })
        .closest(".public-source-list"),
    ).toHaveAttribute("data-inview", "true");
    expect(
      screen
        .getAllByRole("link", { name: "Back to feed" })
        .every((link) => link.getAttribute("href") === "/"),
    ).toBe(true);
    expect(screen.getByText("Continue reading")).toBeInTheDocument();
    expect(screen.getByText("Original record title")).toBeInTheDocument();
    expect(screen.getByText(originalHeadline)).toBeInTheDocument();
    expect(screen.getAllByText("Legal Hallucination").length).toBeGreaterThan(
      0,
    );
    expect(
      document.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.href,
    ).toBe(buildIncidentUrl(incident, window.location.origin));
    const structuredData = JSON.parse(
      document.querySelector<HTMLScriptElement>(
        'script[type="application/ld+json"]',
      )?.textContent ?? "{}",
    ) as Record<string, unknown>;
    expect(structuredData).toMatchObject({
      "@context": "https://schema.org",
      "@type": "NewsArticle",
      headline:
        "AI legal hallucination: Amanda Adams v. Allen Butler Construction, Inc.",
      alternativeHeadline: originalHeadline,
      datePublished: "2026-05-06",
      dateModified: "2026-05-06",
      mainEntityOfPage: buildIncidentUrl(incident, window.location.origin),
    });
    boundingClientRectSpy.mockRestore();
  });

  it("inherits the Chinese reader preference on the incident detail page", async () => {
    window.localStorage.setItem("ai-reality-check-locale", "zh");
    const incident = buildIncidentDetail({
      id: "incident-routed-zh",
      headline: "Court sanctions brief with fake AI citations",
      headline_en: "Court sanctions brief with fake AI citations",
      headline_zh: "法院因虚假 AI 引文制裁法律文件",
      date_logged: "2026-05-06",
      company_involved: "Court filing",
      company_involved_zh: "法院文件",
      categories: ["Legal Hallucination"],
      severity_score: 4,
      publication_track: "verified_accident",
      evidence_tier: "court_or_regulator",
      source_family: "legal_hallucination",
      reality_summary:
        "A court sanctioned a filing after it included fake AI-generated citations.",
      reality_summary_en:
        "A court sanctioned a filing after it included fake AI-generated citations.",
      reality_summary_zh: "法院因文件包含 AI 生成的虚假引文而作出处罚。",
      analysis: {
        incident_summary_en:
          "A court sanctioned a filing after it included fake AI-generated citations.",
        incident_summary_zh: "法院因文件包含 AI 生成的虚假引文而作出处罚。",
        what_happened_en:
          "The brief included cases the court could not verify.",
        what_happened_zh: "该法律文件包含法院无法核实的案例。",
        ai_failure_point_en:
          "The AI-assisted workflow produced fake legal citations.",
        ai_failure_point_zh: "AI 辅助流程生成了虚假的法律引文。",
        why_it_matters_en:
          "The incident shows why legal AI output needs source verification.",
        why_it_matters_zh: "这起事件说明法律 AI 输出必须经过来源核验。",
        evidence_summary_en:
          "The court order documents the sanctions and citation failures.",
        evidence_summary_zh: "法院命令记录了处罚和引文失败。",
      },
      sources: [
        {
          id: "source-court-zh",
          source_url: "https://example.com/court-order.pdf",
          source_type: "court",
          publisher: "Court order",
          title: "Sanctions order",
        },
      ],
    });

    mockedFetchIncidentDetail.mockResolvedValue(incident);
    window.history.pushState(
      {},
      "",
      "/incidents/incident-routed-zh/court-sanctions-brief-with-fake-ai-citations",
    );

    render(<RouteEntry />);

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "法院因虚假 AI 引文制裁法律文件",
      }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(document.title).toBe(
        "法院因虚假 AI 引文制裁法律文件 | AI Oops News",
      );
      expect(
        document.querySelector<HTMLMetaElement>('meta[name="description"]')
          ?.content,
      ).toBe("法院因文件包含 AI 生成的虚假引文而作出处罚。");
    });
    expect(screen.getByText("案件档案")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "中文" })).toHaveClass(
      "is-active",
    );
    expect(screen.getByRole("button", { name: "浅色" })).toHaveClass(
      "is-active",
    );
    expect(screen.getByText("一眼看清")).toBeInTheDocument();
    expect(screen.getByText("法院文件")).toBeInTheDocument();
    expect(screen.getByText("严重级别 4")).toBeInTheDocument();
    expect(screen.getAllByText("已验证事故").length).toBeGreaterThan(0);
    expect(screen.getAllByText("法院或监管记录").length).toBeGreaterThan(0);
    expect(screen.getByText("来源数量")).toBeInTheDocument();
    expect(screen.getByText("1 个来源")).toBeInTheDocument();
    expect(screen.getByText("发生了什么")).toBeInTheDocument();
    expect(
      screen.getByText("该法律文件包含法院无法核实的案例。"),
    ).toBeInTheDocument();
    expect(screen.getByText("主要来源链")).toBeInTheDocument();
    expect(
      screen.getByText(
        "本案件档案基于已列明来源整理，不构成法律建议。请以原始文件核验。",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/AI Oops News 仅供信息参考与研究使用。/),
    ).toBeInTheDocument();
    expect(
      screen
        .getAllByRole("link", { name: "返回事件流" })
        .every((link) => link.getAttribute("href") === "/"),
    ).toBe(true);
    expect(screen.getByText("继续阅读")).toBeInTheDocument();

    expect(
      document.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.href,
    ).toBe(buildIncidentUrl(incident, window.location.origin));
    const structuredData = JSON.parse(
      document.querySelector<HTMLScriptElement>(
        'script[type="application/ld+json"]',
      )?.textContent ?? "{}",
    ) as Record<string, unknown>;
    expect(structuredData).toMatchObject({
      headline: "法院因虚假 AI 引文制裁法律文件",
      description: "法院因文件包含 AI 生成的虚假引文而作出处罚。",
      mainEntityOfPage: buildIncidentUrl(incident, window.location.origin),
    });
  });

  it("uses VITE_PUBLIC_SITE_URL for incident canonical URLs when configured", async () => {
    vi.stubEnv("VITE_PUBLIC_SITE_URL", "https://airealitycheck.example/");
    const incident = buildIncidentDetail({
      id: "incident-prod",
      headline: "Court sanctions brief with fake AI citations",
      headline_en: "Court sanctions brief with fake AI citations",
      date_logged: "2026-05-06",
    });

    mockedFetchIncidentDetail.mockResolvedValue(incident);
    window.history.pushState(
      {},
      "",
      "/incidents/incident-prod/court-sanctions-brief-with-fake-ai-citations",
    );

    render(<RouteEntry />);

    await waitFor(() => {
      expect(mockedFetchIncidentDetail).toHaveBeenCalledWith("incident-prod");
    });

    const canonicalUrl = buildIncidentUrl(
      incident,
      "https://airealitycheck.example/",
    );
    await waitFor(() => {
      expect(
        document.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.href,
      ).toBe(canonicalUrl);
    });
    expect(
      JSON.parse(
        document.querySelector<HTMLScriptElement>(
          'script[type="application/ld+json"]',
        )?.textContent ?? "{}",
      ),
    ).toMatchObject({
      mainEntityOfPage: canonicalUrl,
    });
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
        incident_summary_zh:
          "一次支持自动化发布在客户回复中暴露了私密账单备注。",
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
        evidence_summary_zh:
          "Ledger News 记录了这次暴露，随后公司关闭了该功能。",
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
      reality_summary_zh: "城市机器人试点在多次路线错误和人工干预后被暂停。",
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
    expect(latestIncidentDetail.sources).toHaveLength(1);
    expect(archiveIncidentDetail.sources).toHaveLength(1);

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

    const spotlight = screen
      .getByRole("heading", { name: "Quick takeaway" })
      .closest("section");
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
      within(
        screen
          .getByRole("heading", { name: "Incident signals" })
          .closest("section") as HTMLElement,
      ).getByRole("heading", { name: "Archive controls" }),
    ).toBeInTheDocument();

    const archive = screen.getByRole("region", { name: "Browse incidents" });
    expect(
      archive.querySelector(".public-archive-scroll"),
    ).toBeInTheDocument();
    expect(
      within(archive).getByText(
        "An urban robot pilot paused after repeated routing mistakes.",
      ),
    ).toBeInTheDocument();
    expect(within(archive).getByText("Severity 3")).toBeInTheDocument();
    expect(within(archive).getByText("Autonomous Systems")).toBeInTheDocument();
    expect(
      within(archive).queryByText("Claim vs. reality"),
    ).not.toBeInTheDocument();
    expect(within(archive).getByText("Page 1 of 2")).toBeInTheDocument();
    expect(
      within(archive).getByText("Showing 1-2 of 8 incidents"),
    ).toBeInTheDocument();
    expect(within(archive).getByText("AssistCo")).toBeInTheDocument();
    expect(latestIncident.company_involved_zh).toBe("助理公司");

    expect(
      within(archive).getByRole("link", {
        name: /Open case file: AssistCo assistant exposes private billing notes/i,
      }),
    ).toHaveAttribute(
      "href",
      "/incidents/incident-1/assistco-assistant-exposes-private-billing-notes",
    );
    expect(mockedFetchIncidentDetail).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "中文" }));

    expect(
      screen.getByRole("heading", { name: "AI 现实校验" }),
    ).toBeInTheDocument();
    expect(
      within(spotlight as HTMLElement).getByText("筛选摘要"),
    ).toBeInTheDocument();
    expect(
      within(spotlight as HTMLElement).getByText(
        "隐私 / 安全 (5)、自主系统 (3)",
      ),
    ).toBeInTheDocument();
    expect(
      within(spotlight as HTMLElement).getByText(
        "助理公司 (5)、机器人舰队 (3)",
      ),
    ).toBeInTheDocument();
    expect(within(archive).getByText("隐私 / 安全")).toBeInTheDocument();
    expect(within(archive).getByText("自主系统")).toBeInTheDocument();
    expect(within(archive).getAllByText("事故观察")).toHaveLength(2);
    expect(within(archive).getAllByText("报道未确认")).toHaveLength(2);
    expect(within(archive).getAllByText("客户支持")).toHaveLength(2);
    expect(
      within(archive).getAllByText(
        "这是一条自动发现的观察信号；需要官方、法院、监管、公司或固定高可信来源确认后，才会进入已验证事故档案。",
      ),
    ).toHaveLength(2);
    expect(
      screen.getByRole("heading", { name: "事件信号" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "档案筛选" }),
    ).toBeInTheDocument();
    expect(screen.getByText("你是否也受够了这样的标题？")).toBeInTheDocument();
    expect(
      screen.getByText("我们想提醒你，AI 并不完美，所以放轻松，不要恐慌。"),
    ).toBeInTheDocument();

    expect(within(archive).getByText("助理公司")).toBeInTheDocument();
    expect(
      within(archive).getByRole("link", {
        name: /打开完整背景: AssistCo 助手泄露了私密账单备注/i,
      }),
    ).toHaveAttribute(
      "href",
      "/incidents/incident-1/assistco-assistant-exposes-private-billing-notes",
    );
    expect(within(archive).getByText("RoboFleet")).toBeInTheDocument();
    expect(mockedFetchIncidentDetail).not.toHaveBeenCalled();
  });

  it("renders a category topic page with canonical CollectionPage metadata", async () => {
    vi.stubEnv("VITE_PUBLIC_SITE_URL", "https://aioopsnews.com");
    const incident = buildArchiveIncident({
      id: "incident-hallucination",
      headline: "Court warns litigant about fake AI citations",
      headline_en: "Court warns litigant about fake AI citations",
      categories: ["Hallucinations"],
      source_family: "legal_hallucination",
      company_involved: "Court filing",
      date_logged: "2026-05-06",
    });
    mockedFetchIncidentFeed.mockResolvedValue(
      buildFeedResponse([incident], {
        total_count: 42,
        total_pages: 3,
        slice_summary: {
          total_matches: 42,
          newest_logged: "2026-05-06",
          oldest_logged: "2024-01-10",
          highest_severity: 5,
          top_categories: [{ category: "Hallucinations", count: 42 }],
          top_companies: [{ company: "Court filing", count: 8 }],
        },
      }),
    );
    window.history.pushState({}, "", "/topics/category/hallucinations");

    render(<RouteEntry />);

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "AI Hallucination Incidents",
      }),
    ).toBeInTheDocument();
    expect(mockedFetchIncidentFeed).toHaveBeenCalledWith(
      expect.objectContaining({
        category: "Hallucinations",
        page: 1,
        pageSize: 20,
      }),
    );
    expect(screen.getByText("42 incidents")).toBeInTheDocument();
    expect(screen.getByText("Showing 1-1 of 42 incidents")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Read full disclaimer" }),
    ).toHaveAttribute("href", "/disclaimer");
    expect(
      screen.getByRole("link", {
        name: /Open case file/i,
      }),
    ).toHaveAttribute(
      "href",
      "/incidents/incident-hallucination/court-warns-litigant-about-fake-ai-citations",
    );

    const canonicalUrl = buildTopicUrl(
      "category",
      "Hallucinations",
      "https://aioopsnews.com",
    );
    expect(document.title).toBe("AI Hallucination Incidents | AI Oops News");
    expect(
      document.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.href,
    ).toBe(canonicalUrl);
    expect(
      document.querySelector<HTMLMetaElement>('meta[name="description"]')
        ?.content,
    ).toContain("Browse verified and source-backed AI hallucination incidents");
    await waitFor(() => {
      expect(
        document.querySelector<HTMLMetaElement>('meta[name="robots"]')?.content,
      ).toBe("index,follow");
    });
    expect(
      JSON.parse(
        document.querySelector<HTMLScriptElement>(
          'script[type="application/ld+json"]',
        )?.textContent ?? "{}",
      ),
    ).toMatchObject({
      "@type": "CollectionPage",
      name: "AI Hallucination Incidents",
      mainEntityOfPage: canonicalUrl,
    });
  });

  it("renders a source-family topic page and noindexes unknown topics", async () => {
    const incident = buildArchiveIncident({
      id: "incident-legal-source",
      headline: "Legal AI citation failure reaches court",
      headline_en: "Legal AI citation failure reaches court",
      categories: ["Hallucinations"],
      source_family: "legal_hallucination",
    });
    mockedFetchIncidentFeed.mockResolvedValueOnce(
      buildFeedResponse([incident], {
        total_count: 3,
        slice_summary: {
          total_matches: 3,
          newest_logged: "2026-04-29",
          oldest_logged: "2026-01-01",
          highest_severity: 4,
          top_categories: [{ category: "Hallucinations", count: 3 }],
          top_companies: [{ company: "AssistCo", count: 2 }],
        },
      }),
    );
    window.history.pushState({}, "", "/topics/source/legal-hallucination");

    const { unmount } = render(<RouteEntry />);

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "AI Legal Hallucination Cases",
      }),
    ).toBeInTheDocument();
    expect(mockedFetchIncidentFeed).toHaveBeenCalledWith(
      expect.objectContaining({
        sourceFamily: "legal_hallucination",
        pageSize: 20,
      }),
    );
    await waitFor(() => {
      expect(
        document.querySelector<HTMLMetaElement>('meta[name="robots"]')?.content,
      ).toBe("index,follow");
    });

    unmount();
    mockedFetchIncidentFeed.mockClear();
    window.history.pushState({}, "", "/topics/category/not-real");
    render(<RouteEntry />);

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Topic not found",
      }),
    ).toBeInTheDocument();
    expect(mockedFetchIncidentFeed).not.toHaveBeenCalled();
    expect(
      document.querySelector<HTMLMetaElement>('meta[name="robots"]')?.content,
    ).toBe("noindex,follow");
  });

  it("renders a bilingual disclaimer page with noindex metadata", async () => {
    vi.stubEnv("VITE_PUBLIC_SITE_URL", "https://aioopsnews.com/");
    window.history.pushState({}, "", "/disclaimer");

    render(<RouteEntry />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Disclaimer" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/AI Oops News is provided for informational and research purposes only/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Read full disclaimer" }),
    ).not.toBeInTheDocument();
    expect(mockedFetchIncidentFeed).not.toHaveBeenCalled();
    expect(mockedFetchIncidentDetail).not.toHaveBeenCalled();
    expect(document.title).toBe("Disclaimer | AI Oops News");
    expect(
      document.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.href,
    ).toBe("https://aioopsnews.com/disclaimer");
    expect(
      document.querySelector<HTMLMetaElement>('meta[name="robots"]')?.content,
    ).toBe("noindex,follow");
    expect(
      document.querySelector<HTMLScriptElement>(
        'script[type="application/ld+json"]',
      ),
    ).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "中文" }));

    expect(
      screen.getByRole("heading", { level: 1, name: "免责声明" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/AI Oops News 仅供信息参考与研究使用。本站基于公开报道/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "查看完整免责声明" }),
    ).not.toBeInTheDocument();
    expect(document.title).toBe("免责声明 | AI Oops News");
  });

  it("uses Chinese company labels for filter options while keeping canonical company values", async () => {
    mockedFetchIncidentFeed.mockResolvedValue(
      buildFeedResponse([buildArchiveIncident()]),
    );

    render(<PublicDashboardPage />);

    await screen.findByRole("heading", { name: "Quick takeaway" });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "中文" }));
    });

    const companyFilter = screen.getByLabelText(
      "按公司筛选",
    ) as HTMLSelectElement;
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
      screen.queryByRole("heading", { name: "Full context" }),
    ).not.toBeInTheDocument();
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

  it("falls back to English detail analysis text when localized fields are empty strings", async () => {
    const incident = buildArchiveIncident({
      id: "incident-waymo",
      headline_zh: "Waymo 事故",
      archive_summary_zh: "一份官方事故报告。",
    });
    mockedFetchIncidentDetail.mockResolvedValue(
      buildIncidentDetail({
        ...incident,
        analysis: {
          what_happened_en: "English incident context remains available.",
          what_happened_zh: "",
          ai_failure_point_en: "English failure point remains available.",
          ai_failure_point_zh: "",
          evidence_summary_en: "Official DMV report confirms the incident.",
          evidence_summary_zh: "",
        },
      }),
    );
    window.history.pushState(
      {},
      "",
      "/incidents/incident-waymo/waymo-incident",
    );

    render(<RouteEntry />);

    expect(
      await screen.findByText("English incident context remains available."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("English failure point remains available."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Official DMV report confirms the incident."),
    ).toBeInTheDocument();
  });

  it("shows a detail-route failure without loading the feed", async () => {
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
    expect(incident.archive_summary).toContain("warehouse classifier");
    mockedFetchIncidentDetail.mockRejectedValue(new Error("detail failed"));
    window.history.pushState(
      {},
      "",
      "/incidents/incident-3/warehouse-classifier-reroutes-medical-inventory",
    );

    render(<RouteEntry />);

    expect(
      await screen.findByText("Unable to load incident details right now."),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(mockedFetchIncidentDetail).toHaveBeenCalledWith("incident-3");
    });
    expect(mockedFetchIncidentFeed).not.toHaveBeenCalled();
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
    window.history.pushState(
      {},
      "",
      "/incidents/incident-legacy/mercedes-benz-autonomous-testing-vehicle-collision",
    );

    render(<RouteEntry />);

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: /Mercedes Benz: An autonomous testing vehicle/,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("AI failure point")).toBeInTheDocument();
    expect(
      screen.getByText("Not yet structured for this incident."),
    ).toBeInTheDocument();
    expect(screen.queryByText("What happened")).not.toBeInTheDocument();
    expect(
      screen.getAllByText(
        "An autonomous testing vehicle was involved in a collision requiring formal documentation submission to the California Department of Motor Vehicles.",
      ),
    ).toHaveLength(1);
  });

  it("shows official-detail-pending copy for thin autonomous vehicle records", async () => {
    const thinIncident = buildArchiveIncident({
      id: "incident-thin-av",
      headline: "California DMV published Waymo collision report",
      headline_en: "California DMV published Waymo collision report",
      company_involved: "Waymo",
      categories: ["Autonomous Systems"],
      publication_track: "verified_accident",
      evidence_tier: "official_documented",
      source_family: "autonomous_vehicle",
      archive_summary:
        "California DMV published an autonomous vehicle collision report.",
    });

    mockedFetchIncidentDetail.mockResolvedValue(
      buildIncidentDetail({
        ...thinIncident,
        reality_summary:
          "California DMV published an autonomous vehicle collision report.",
        analysis: {
          incident_summary_en:
            "California DMV published an autonomous vehicle collision report.",
          ai_failure_point_en: null,
          evidence_summary_en: "Official DMV collision report.",
          detail_quality: "insufficient",
          detail_quality_reasons: [
            "missing_evidence_text",
            "missing_ai_failure_point",
          ],
          source_fact_summary: null,
        },
        sources: [
          {
            id: "source-thin-av",
            source_url: "https://www.dmv.ca.gov/report.pdf",
            source_type: "official",
            publisher: "California DMV",
            title: "Waymo collision report",
          },
        ],
      }),
    );
    window.history.pushState(
      {},
      "",
      "/incidents/incident-thin-av/california-dmv-published-waymo-collision-report",
    );

    render(<RouteEntry />);

    expect(
      await screen.findByText("Official report, detail pending"),
    ).toBeInTheDocument();
    expect(screen.queryByText("AI failure point")).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: "Waymo collision report",
      }),
    ).toBeInTheDocument();
  });

  it("keeps existing autonomous vehicle case detail visible when source evidence is incomplete", async () => {
    const autonomousIncident = buildArchiveIncident({
      id: "incident-av-rich",
      headline: "California DMV published Waymo collision report",
      headline_en: "California DMV published Waymo collision report",
      company_involved: "Waymo",
      categories: ["Autonomous Systems"],
      publication_track: "verified_accident",
      evidence_tier: "official_documented",
      source_family: "autonomous_vehicle",
      archive_summary:
        "California DMV published an autonomous vehicle collision report.",
    });

    mockedFetchIncidentDetail.mockResolvedValue(
      buildIncidentDetail({
        ...autonomousIncident,
        reality_summary:
          "California DMV published an autonomous vehicle collision report.",
        analysis: {
          incident_summary_en:
            "The DMV report documents a Waymo collision in autonomous mode.",
          what_happened_en:
            "The Waymo vehicle stopped on a narrow street before another vehicle passed closely and made contact with its rear left side.",
          ai_failure_point_en:
            "The autonomous driving system did not preserve enough clearance or negotiate the tight passing scenario before contact occurred.",
          why_it_matters_en:
            "The incident matters because low-speed urban conflicts still test autonomous vehicle prediction and planning behavior.",
          evidence_summary_en: "Official DMV collision report.",
          detail_quality: "insufficient",
          detail_quality_reasons: ["missing_evidence_text"],
          source_fact_summary: null,
        },
        sources: [
          {
            id: "source-pdf",
            source_url: "https://www.dmv.ca.gov/portal/file/waymo_031826-pdf/",
            source_type: "official",
            publisher: "California DMV",
            title: "Waymo collision report",
          },
          {
            id: "source-index",
            source_url:
              "https://www.dmv.ca.gov/portal/vehicle-industry-services/autonomous-vehicles/autonomous-vehicle-collision-reports/",
            source_type: "official",
            publisher: "California DMV",
            title: "Autonomous Vehicle Collision Reports",
          },
          {
            id: "source-nhtsa",
            source_url:
              "https://www.nhtsa.gov/laws-regulations/standing-general-order-crash-reporting",
            source_type: "official",
            publisher: "NHTSA",
            title: "Standing General Order Crash Reporting",
          },
        ],
      }),
    );
    window.history.pushState(
      {},
      "",
      "/incidents/incident-av-rich/california-dmv-published-waymo-collision-report",
    );

    render(<RouteEntry />);

    expect(
      await screen.findByText("Official report, detail pending"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "The Waymo vehicle stopped on a narrow street before another vehicle passed closely and made contact with its rear left side.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "The autonomous driving system did not preserve enough clearance or negotiate the tight passing scenario before contact occurred.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "The incident matters because low-speed urban conflicts still test autonomous vehicle prediction and planning behavior.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Waymo collision report" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", {
        name: "Autonomous Vehicle Collision Reports",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", {
        name: "Standing General Order Crash Reporting",
      }),
    ).not.toBeInTheDocument();
  });

  it("paginates archive results without loading incident details", async () => {
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
          total_count: 25,
          total_pages: 2,
          has_next_page: true,
        }),
      )
      .mockResolvedValueOnce(
        buildFeedResponse([secondPageIncident], {
          page: 2,
          total_count: 25,
          total_pages: 2,
          has_next_page: false,
          has_previous_page: true,
        }),
      );

    render(<PublicDashboardPage />);

    await screen.findByText("Page 1 of 2");
    expect(screen.getByText("Showing 1-1 of 25 incidents")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    await screen.findByText("Page 2 of 2");
    expect(screen.getByText("Second page incident")).toBeInTheDocument();
    expect(screen.getByText("Showing 21-21 of 25 incidents")).toBeInTheDocument();
    expect(mockedFetchIncidentFeed.mock.calls[0]?.[0]).toMatchObject({
      page: 1,
      pageSize: 20,
    });
    expect(mockedFetchIncidentFeed.mock.calls[1]?.[0]).toMatchObject({
      page: 2,
      pageSize: 20,
    });
    expect(
      screen.queryByRole("heading", { name: "First page incident" }),
    ).not.toBeInTheDocument();
    expect(mockedFetchIncidentDetail).not.toHaveBeenCalled();
  });

  it("renders a public theme switch, defaults to light, and persists dark mode after toggle", async () => {
    mockedFetchIncidentFeed.mockResolvedValue(
      buildFeedResponse([buildArchiveIncident()]),
    );

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
