const CATEGORY_LABELS = {
  "Autonomous Systems": {
    en: "Autonomous Systems",
    zh: "自主系统",
  },
  Hallucinations: {
    en: "Hallucinations",
    zh: "幻觉输出",
  },
  "Job Automation Fails": {
    en: "Job Automation Fails",
    zh: "岗位自动化失灵",
  },
  "Missed Timelines": {
    en: "Missed Timelines",
    zh: "延期失约",
  },
  "Model Governance": {
    en: "Model Governance",
    zh: "模型治理",
  },
  "Privacy/Security": {
    en: "Privacy/Security",
    zh: "隐私 / 安全",
  },
} as const;

export type PublicDashboardLocale = "en" | "zh";

export function localizePublicCategory(
  category: string,
  locale: PublicDashboardLocale,
) {
  return CATEGORY_LABELS[category as keyof typeof CATEGORY_LABELS]?.[locale] ?? category;
}
