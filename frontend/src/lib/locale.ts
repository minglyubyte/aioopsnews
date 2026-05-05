/**
 * Bilingual copy and locale types for the public dashboard.
 * Extracted from PublicDashboardPage to keep the component focused on rendering.
 */

export type ReaderLocale = "en" | "zh";
export type ReaderTheme = "light" | "dark";

export type MonthlySignal = {
  monthKey: string;
  label: string;
  count: number;
};

export type CategorySignal = {
  category: string;
  count: number;
  share: number;
};

export type HeroMetric = {
  label: string;
  value: string;
  note: string;
};

export type HighlightInsight = {
  label: string;
  value: string;
  note: string;
};

export const PUBLIC_COPY = {
  en: {
    brand: "AI Reality Check",
    positioning: "A readable watchlist of AI failures and verified accidents",
    lede: "Are you tired of headlines like these?",
    heroExamples: [
      '"AGI is HERE? This Mind-Blowing AI Just Made Humans OBSOLETE 🤯"',
      '"GAME OVER. I Watched AI Replace an Entire Company in 60 Seconds 🚨"',
      '"TERRIFYING: This New AI Feature Will Take Your Job by 2027 🥶"',
      '"Stop Learning to Code! AI is Now 100x Smarter Than Senior Engineers 📉"',
      `"The 'Human Replacement' Update: Why You Need to Panic (And How to Survive) 🧟‍♂️"`,
    ],
    heroCopy:
      "We are here to remind you that AI is not perfect, so relax and do not panic.",
    languageSwitchLabel: "Reader language switch",
    themeSwitchLabel: "Reader theme switch",
    lightTheme: "Light",
    darkTheme: "Dark",
    filtersLoading: "Loading filters...",
    filtersError: "Unable to load archive filters right now.",
    signalsKicker: "Signals",
    signalsTitle: "Incident signals",
    signalsNote:
      "Live patterns update as the archive narrows, so the dashboard stays useful for quick scans and deeper research.",
    currentFeedSizeKicker: "Current feed size",
    currentFeedSizeTitle: (count: number) =>
      `${count} incident${count === 1 ? "" : "s"} in current feed`,
    monthlySignalAria: "Monthly incident signal",
    incidentCountLabel: (count: number) =>
      `${count} incident${count === 1 ? "" : "s"}`,
    signalNoData:
      "Incident counts will appear here once the current slice has data.",
    categoryDistributionKicker: "Category distribution",
    categoryDistributionTitle: "What the current feed is surfacing",
    donutIncidentLabel: (count: number) =>
      count === 1 ? "incident" : "incidents",
    categoryDistributionAria: "Category distribution summary",
    categoryShareLabel: (share: number) => `${share}% of current feed`,
    categoryNoData:
      "Category distribution will appear once incidents are available.",
    archiveControlsRegion: "Archive controls",
    archiveControlsKicker: "Archive controls",
    archiveControlsTitle: "Archive controls",
    archiveControlsBody:
      "Narrow the public archive by category, company, and timeframe.",
    filterByCategory: "Filter by category",
    allCategories: "All categories",
    filterByCompany: "Filter by company",
    allCompanies: "All companies",
    filterByTrack: "Filter by track",
    allTracks: "All tracks",
    filterBySourceFamily: "Filter by source family",
    allSourceFamilies: "All source families",
    filterByYear: "Filter by year",
    allYears: "All years",
    filterByMonth: "Filter by month",
    allMonths: "All months",
    archiveRegion: "Browse incidents",
    archiveKicker: "Browse",
    archiveTitle: "Browse incidents",
    archiveLoading: "Loading incident archive...",
    spotlightKicker: "Highlights",
    spotlightTitle: "Quick takeaway",
    spotlightLoading: "Loading incident feed...",
    highlightsEmpty: "Highlights will appear once this slice has enough signal.",
    highlightInsightsTitle: "Slice-level view",
    highlightInsightsBody:
      "This panel summarizes the filtered archive so readers can scan the shape of the slice before opening any incident.",
    verifiedSectionTitle: "Verified AI Accidents",
    verifiedSectionBody:
      "Source-backed case files from official, court, regulator, company, or fixed high-provenance records.",
    verifiedSectionEmpty:
      "No verified accident case files in this slice yet.",
    watchSectionTitle: "AI Accident Watch",
    watchSectionBody:
      "Developing reports and credible signals that are readable, useful, and clearly not fully confirmed.",
    watchSectionEmpty: "No watch items in this slice yet.",
    noIncidentsForSlice: "No incidents match this slice yet.",
    detailActionLabel: (headline: string) => `Open full context for ${headline}`,
    sourceBackedDetailActionLabel: (headline: string) =>
      `Open full context for ${headline}`,
    detailKicker: "Evidence",
    detailTitle: "Full context",
    detailLoading: "Loading incident details...",
    aiFailurePointTitle: "AI failure point",
    aiFailurePointUnavailable: "Not yet structured for this incident.",
    whatHappenedTitle: "What happened",
    whyItMattersTitle: "Why it matters",
    evidenceSummaryTitle: "Evidence summary",
    whatIsConfirmedTitle: "What is confirmed",
    whatRemainsUncertainTitle: "What remains uncertain",
    primarySourceTrailTitle: "Primary source trail",
    claimVsReality: "Claim vs. reality",
    confidenceLabel: "Confidence",
    reportingTrailKicker: "Reporting trail",
    sourcesTitle: "Sources",
    noSources: "Source links are not available for this incident yet.",
    selectIncident:
      "Select an incident from the archive to inspect the full context and sources.",
    feedError: "Unable to load the incident feed right now.",
    detailError: "Unable to load incident details right now.",
    paginationPrevious: "Previous",
    paginationNext: "Next",
    paginationStatus: (page: number, totalPages: number) =>
      `Page ${page} of ${totalPages}`,
    paginationSummary: (visibleCount: number, totalCount: number) =>
      `Showing ${visibleCount} of ${totalCount} incidents`,
    metrics: {
      currentFeed: "Current feed",
      currentFeedNote: (count: number) =>
        count === 1 ? "reviewed incident" : "reviewed incidents",
      companiesInView: "Companies in view",
      companiesInViewNote: (count: number) =>
        count === 1 ? "organization surfaced" : "organizations surfaced",
      latestLogged: "Latest logged",
      latestLoggedNote: "anchoring the spotlight card",
      categorySpread: "Category spread",
      categorySpreadNote: (count: number) =>
        count === 1 ? "category in the slice" : "categories in the slice",
      awaitingData: "Awaiting data",
    },
    highlights: {
      totalMatches: "Matches",
      timeWindow: "Time window",
      highestSeverity: "Highest severity",
      topCategories: "Top categories",
      topCompanies: "Top companies",
      noTimeWindow: "No dates in this slice yet",
      noTopCategories: "No categories yet",
      noTopCompanies: "No companies yet",
      severityValue: (severity: number) => `Severity ${severity}`,
      timeWindowValue: (newest: string, oldest: string) =>
        newest === oldest ? newest : `${newest} to ${oldest}`,
      topListValue: (items: string[]) => items.join(", "),
    },
    dateLocale: "en-US",
  },
  zh: {
    brand: "AI 现实校验",
    positioning: "一个可读的 AI 失败观察站与已验证事故档案",
    lede: "你是否也受够了这样的标题？",
    heroExamples: [
      '"太炸裂了！刚刚AI史诗级更新，这几个行业的饭碗彻底被砸碎！😱"',
      '"全人类失业倒计时？这个新出炉的AI强到离谱，看完惊出冷汗... 🥶"',
      '"降维打击！AI已经能100%替代人工，现在转行还来得及吗？🚨"',
      '"别再无脑干活了！我亲眼看着AI在5分钟内干掉了一个团队 🤯"',
      '"彻底觉醒！当AI学会自己写代码，打工人的末日真的来了！🔥"',
    ],
    heroCopy:
      "我们想提醒你，AI 并不完美，所以放轻松，不要恐慌。",
    languageSwitchLabel: "读者语言切换",
    themeSwitchLabel: "读者主题切换",
    lightTheme: "浅色",
    darkTheme: "深色",
    filtersLoading: "正在加载筛选项...",
    filtersError: "当前无法加载档案筛选项。",
    signalsKicker: "信号",
    signalsTitle: "事件信号",
    signalsNote:
      "随着档案范围缩小，实时模式也会同步更新，方便快速浏览和深入研究。",
    currentFeedSizeKicker: "当前条目规模",
    currentFeedSizeTitle: (count: number) => `当前结果中有 ${count} 起事件`,
    monthlySignalAria: "每月事件信号",
    incidentCountLabel: (count: number) => `${count} 起事件`,
    signalNoData: "当前筛选结果出现后，这里会显示事件数量趋势。",
    categoryDistributionKicker: "类别分布",
    categoryDistributionTitle: "当前结果正在浮现什么",
    donutIncidentLabel: () => "事件",
    categoryDistributionAria: "类别分布摘要",
    categoryShareLabel: (share: number) => `占当前结果的 ${share}%`,
    categoryNoData: "有事件数据后，这里会显示类别分布。",
    archiveControlsRegion: "档案筛选",
    archiveControlsKicker: "档案筛选",
    archiveControlsTitle: "档案筛选",
    archiveControlsBody: "按类别、公司和时间范围缩小公开档案。",
    filterByCategory: "按类别筛选",
    allCategories: "全部类别",
    filterByCompany: "按公司筛选",
    allCompanies: "全部公司",
    filterByTrack: "按轨道筛选",
    allTracks: "全部轨道",
    filterBySourceFamily: "按来源领域筛选",
    allSourceFamilies: "全部来源领域",
    filterByYear: "按年份筛选",
    allYears: "全部年份",
    filterByMonth: "按月份筛选",
    allMonths: "全部月份",
    archiveRegion: "浏览事件",
    archiveKicker: "浏览",
    archiveTitle: "浏览事件",
    archiveLoading: "正在加载事件档案...",
    spotlightKicker: "亮点",
    spotlightTitle: "快速了解",
    spotlightLoading: "正在加载事件流...",
    highlightsEmpty: "当这个筛选范围积累到足够信号后，这里会显示摘要。",
    verifiedSectionTitle: "已验证 AI 事故",
    verifiedSectionBody:
      "来自官方、法院、监管、公司或固定高可信记录的来源支撑档案。",
    verifiedSectionEmpty: "这个筛选范围里还没有已验证事故档案。",
    watchSectionTitle: "AI 事故观察",
    watchSectionBody:
      "仍在发展中的报道和可信信号，保持可读，同时清楚标注尚未完全确认。",
    watchSectionEmpty: "这个筛选范围里还没有观察条目。",
    highlightInsightsTitle: "筛选摘要",
    highlightInsightsBody:
      "这个面板总结当前筛选后的公开档案，让读者先看清整体轮廓，再决定打开哪一条事件。",
    noIncidentsForSlice: "当前筛选结果下还没有匹配事件。",
    detailActionLabel: (headline: string) => `打开 ${headline} 的完整背景`,
    sourceBackedDetailActionLabel: (headline: string) =>
      `打开${headline}的完整背景`,
    detailKicker: "证据",
    detailTitle: "完整背景",
    detailLoading: "正在加载事件详情...",
    aiFailurePointTitle: "AI 失效点",
    aiFailurePointUnavailable: "这起事件的 AI 失效点尚未整理出来。",
    whatHappenedTitle: "发生了什么",
    whyItMattersTitle: "为什么重要",
    evidenceSummaryTitle: "证据摘要",
    whatIsConfirmedTitle: "已确认内容",
    whatRemainsUncertainTitle: "仍不确定内容",
    primarySourceTrailTitle: "主要来源链",
    claimVsReality: "声明 vs. 现实",
    confidenceLabel: "置信度",
    reportingTrailKicker: "报道轨迹",
    sourcesTitle: "来源",
    noSources: "这起事件暂时还没有可用的来源链接。",
    selectIncident: "从档案中选择一条事件以查看完整背景和来源。",
    feedError: "当前无法加载事件流。",
    detailError: "当前无法加载事件详情。",
    paginationPrevious: "上一页",
    paginationNext: "下一页",
    paginationStatus: (page: number, totalPages: number) =>
      `第 ${page} 页，共 ${totalPages} 页`,
    paginationSummary: (visibleCount: number, totalCount: number) =>
      `当前显示 ${visibleCount} / ${totalCount} 起事件`,
    metrics: {
      currentFeed: "当前结果",
      currentFeedNote: (count: number) =>
        count === 1 ? "已审阅事件" : "已审阅事件",
      companiesInView: "涉及组织",
      companiesInViewNote: (count: number) =>
        count === 1 ? "家组织被呈现" : "家组织被呈现",
      latestLogged: "最新记录",
      latestLoggedNote: "用于锚定聚焦卡片",
      categorySpread: "类别范围",
      categorySpreadNote: (count: number) =>
        count === 1 ? "个类别出现在当前结果中" : "个类别出现在当前结果中",
      awaitingData: "等待数据",
    },
    highlights: {
      totalMatches: "匹配数量",
      timeWindow: "时间范围",
      highestSeverity: "最高严重级别",
      topCategories: "主要类别",
      topCompanies: "主要公司",
      noTimeWindow: "当前筛选范围还没有日期",
      noTopCategories: "当前还没有类别",
      noTopCompanies: "当前还没有公司",
      severityValue: (severity: number) => `严重级别 ${severity}`,
      timeWindowValue: (newest: string, oldest: string) =>
        newest === oldest ? newest : `${newest} 至 ${oldest}`,
      topListValue: (items: string[]) => items.join("、"),
    },
    dateLocale: "zh-CN",
  },
} satisfies Record<
  ReaderLocale,
  {
    brand: string;
    positioning: string;
    lede: string;
    heroExamples: string[];
    heroCopy: string;
    languageSwitchLabel: string;
    themeSwitchLabel: string;
    lightTheme: string;
    darkTheme: string;
    filtersLoading: string;
    filtersError: string;
    signalsKicker: string;
    signalsTitle: string;
    signalsNote: string;
    currentFeedSizeKicker: string;
    currentFeedSizeTitle: (count: number) => string;
    monthlySignalAria: string;
    incidentCountLabel: (count: number) => string;
    signalNoData: string;
    categoryDistributionKicker: string;
    categoryDistributionTitle: string;
    donutIncidentLabel: (count: number) => string;
    categoryDistributionAria: string;
    categoryShareLabel: (share: number) => string;
    categoryNoData: string;
    archiveControlsRegion: string;
    archiveControlsKicker: string;
    archiveControlsTitle: string;
    archiveControlsBody: string;
    filterByCategory: string;
    allCategories: string;
    filterByCompany: string;
    allCompanies: string;
    filterByTrack: string;
    allTracks: string;
    filterBySourceFamily: string;
    allSourceFamilies: string;
    filterByYear: string;
    allYears: string;
    filterByMonth: string;
    allMonths: string;
    archiveRegion: string;
    archiveKicker: string;
    archiveTitle: string;
    archiveLoading: string;
    spotlightKicker: string;
    spotlightTitle: string;
    spotlightLoading: string;
    highlightsEmpty: string;
    highlightInsightsTitle: string;
    highlightInsightsBody: string;
    verifiedSectionTitle: string;
    verifiedSectionBody: string;
    verifiedSectionEmpty: string;
    watchSectionTitle: string;
    watchSectionBody: string;
    watchSectionEmpty: string;
    noIncidentsForSlice: string;
    detailActionLabel: (headline: string) => string;
    sourceBackedDetailActionLabel: (headline: string) => string;
    detailKicker: string;
    detailTitle: string;
    detailLoading: string;
    aiFailurePointTitle: string;
    aiFailurePointUnavailable: string;
    whatHappenedTitle: string;
    whyItMattersTitle: string;
    evidenceSummaryTitle: string;
    whatIsConfirmedTitle: string;
    whatRemainsUncertainTitle: string;
    primarySourceTrailTitle: string;
    claimVsReality: string;
    confidenceLabel: string;
    reportingTrailKicker: string;
    sourcesTitle: string;
    noSources: string;
    selectIncident: string;
    feedError: string;
    detailError: string;
    paginationPrevious: string;
    paginationNext: string;
    paginationStatus: (page: number, totalPages: number) => string;
    paginationSummary: (visibleCount: number, totalCount: number) => string;
    metrics: {
      currentFeed: string;
      currentFeedNote: (count: number) => string;
      companiesInView: string;
      companiesInViewNote: (count: number) => string;
      latestLogged: string;
      latestLoggedNote: string;
      categorySpread: string;
      categorySpreadNote: (count: number) => string;
      awaitingData: string;
    };
    highlights: {
      totalMatches: string;
      timeWindow: string;
      highestSeverity: string;
      topCategories: string;
      topCompanies: string;
      noTimeWindow: string;
      noTopCategories: string;
      noTopCompanies: string;
      severityValue: (severity: number) => string;
      timeWindowValue: (newest: string, oldest: string) => string;
      topListValue: (items: string[]) => string;
    };
    dateLocale: string;
  }
>;
