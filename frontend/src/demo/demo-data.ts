import type {
  DemoIncident,
  DemoMetric,
  DemoPageCopy,
  LocalizedText,
} from "./demo-types";

function localized(en: string, zh: string): LocalizedText {
  return { en, zh };
}

export const demoPageCopy: DemoPageCopy = {
  heroKicker: localized("AI Reality Check Demo", "AI Reality Check 演示"),
  heroTitle: localized(
    "AI failures, without the hype cycle",
    "AI 故障，不该被热潮掩盖",
  ),
  heroCopy: localized(
    "A reader-facing mock dashboard for calmly tracking documented AI failures, the public promises around them, and the operational standards required to publish responsibly.",
    "一个面向读者的模拟仪表盘，用更克制的方式追踪已被记录的 AI 故障、围绕它们的公开承诺，以及负责任发布所需遵循的运营标准。",
  ),
  filterKicker: localized("Reader filters", "读者筛选"),
  filterTitle: localized("Mock taxonomy", "模拟分类法"),
  filterChips: [
    localized("Privacy/Security", "隐私 / 安全"),
    localized("Autonomous Systems", "自主系统"),
    localized("Missed Timelines", "延期失约"),
    localized("Severity 3+", "三级及以上"),
  ],
  latestKicker: localized("Latest incidents", "最新事件"),
  latestTitle: localized("Documented breakdowns", "已记录的失效案例"),
  detailKicker: localized("Source-backed detail", "来源支撑详情"),
  detailTitle: localized("Incident detail", "事件详情"),
  claimKicker: localized("Claim vs. reality", "承诺与现实"),
  claimTitle: localized("Spotlight", "聚焦"),
  claimLabel: localized("Claim vs. reality", "承诺与现实"),
  sourceCredibilityKicker: localized("Source credibility", "来源可信度"),
  sourceCredibilityTitle: localized("Publishing rule", "发布规则"),
  sourceCredibilityBody: localized(
    "Entries must link to accountable reporting or primary-source material. The feed favors fewer, better-documented incidents over broad automated coverage.",
    "每条记录都必须链接到可追责的报道或一手材料。该信息流优先收录数量更少但证据更扎实的事件，而不是追求大范围自动化覆盖。",
  ),
  spotlightKicker: localized("Incident spotlight", "事件聚焦"),
  spotlightTitle: localized("Incident spotlight", "事件聚焦"),
  spotlightSourcesKicker: localized("Sources", "来源"),
  spotlightSourcesTitle: localized("Reference trail", "参考链路"),
  signalsKicker: localized("Incident signals", "事件信号"),
  signalsTitle: localized("Incident signals", "事件信号"),
  signalsMonthlyKicker: localized("Monthly count", "月度数量"),
  signalsMonthlyTitle: localized("Monthly incident count", "月度事件数量"),
  signalsMonthlyNote: localized(
    "A compact read on the demo incident cadence.",
    "用简洁方式查看演示事件的月度节奏。",
  ),
  signalsMonthlyFallback: localized(
    "Only one month is represented here, so the chart stays intentionally spare.",
    "当前只覆盖一个月份，因此图形会保持克制而简洁。",
  ),
  signalsCategoryKicker: localized("Category mix", "分类构成"),
  signalsCategoryTitle: localized("Category distribution", "分类分布"),
  signalsCategoryNote: localized(
    "Distribution across the mock incidents in this demo set.",
    "展示这组演示事件中的分类分布。",
  ),
  signalsDonutLabel: localized(
    "Demo category distribution donut chart",
    "演示分类分布环形图",
  ),
};

export const demoMetrics: DemoMetric[] = [
  {
    label: localized("Reviewed incidents", "已审核事件"),
    value: localized("128", "128"),
    note: localized(
      "documented, source-linked failures",
      "已记录并附来源链接的故障案例",
    ),
  },
  {
    label: localized("Claim precision", "承诺匹配准确率"),
    value: localized("100%", "100%"),
    note: localized("seed gold-sample evaluation", "来自种子金标样本评估"),
  },
  {
    label: localized("Manual review", "人工审核"),
    value: localized("Always on", "始终开启"),
    note: localized(
      "public entries are never auto-published",
      "公开条目绝不自动发布",
    ),
  },
];

export const demoIncidents: DemoIncident[] = [
  {
    id: "assistco",
    headline: localized(
      "AssistCo assistant exposes private billing notes",
      "AssistCo 助手泄露了私密账单备注",
    ),
    company: "AssistCo",
    dateLogged: "2026-05-01",
    date: localized("May 1, 2026", "2026 年 5 月 1 日"),
    severity: localized("Severity 4", "四级事件"),
    categories: [
      localized("Privacy/Security", "隐私 / 安全"),
      localized("Support automation", "客服自动化"),
    ],
    summary: localized(
      "A customer-support assistant leaked internal account notes into outward-facing replies before the workflow was halted.",
      "一款客服助手在工作流被叫停前，将内部账户备注泄露到了面向客户的回复中。",
    ),
    sourceLabel: localized("Example News", "示例新闻"),
    sourceUrl: "https://example.com/articles/assistco-billing-notes",
    claimQuote: localized(
      "Our assistant will eliminate repetitive support escalations.",
      "我们的助手将消除重复性的客服升级流程。",
    ),
    claimMeta: localized(
      "Claimed January 15, 2026 • Confidence 88%",
      "宣称于 2026 年 1 月 15 日 • 置信度 88%",
    ),
  },
  {
    id: "robofleet",
    headline: localized(
      "RoboFleet robot pilot rollback follows navigation failures",
      "RoboFleet 机器人试点因导航失误而回滚",
    ),
    company: "RoboFleet",
    dateLogged: "2026-04-24",
    date: localized("April 24, 2026", "2026 年 4 月 24 日"),
    severity: localized("Severity 3", "三级事件"),
    categories: [
      localized("Autonomous Systems", "自主系统"),
      localized("Pilot rollback", "试点回滚"),
    ],
    summary: localized(
      "Operators paused a sidewalk robotics pilot after repeated navigation failures and escalating manual interventions.",
      "在连续出现导航失误且人工干预不断升级后，运营方暂停了一项人行道机器人试点。",
    ),
    sourceLabel: localized("City Transit Journal", "城市交通期刊"),
    sourceUrl: "https://example.com/articles/robofleet-pilot-rollback",
  },
  {
    id: "signalloop",
    headline: localized(
      "SignalLoop misses another launch window after rollout delay",
      "SignalLoop 再次错过上线窗口，发布继续延后",
    ),
    company: "SignalLoop",
    dateLogged: "2026-04-20",
    date: localized("April 20, 2026", "2026 年 4 月 20 日"),
    severity: localized("Severity 2", "二级事件"),
    categories: [
      localized("Missed Timelines", "延期失约"),
      localized("Product rollout", "产品发布"),
    ],
    summary: localized(
      "The company acknowledged another slipped release after publicly signaling a near-term product launch.",
      "在公开暗示产品即将上线后，这家公司又承认了一次发布时间跳票。",
    ),
    sourceLabel: localized("Product Ledger", "产品纪事"),
    sourceUrl: "https://example.com/articles/signalloop-delay",
  },
];
