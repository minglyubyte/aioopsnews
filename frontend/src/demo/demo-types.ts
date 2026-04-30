export type DemoLocale = "en" | "zh";

export type LocalizedText = Record<DemoLocale, string>;

export type DemoMetric = {
  label: LocalizedText;
  value: LocalizedText;
  note: LocalizedText;
};

export type DemoIncident = {
  id: string;
  headline: LocalizedText;
  company: string;
  dateLogged: string;
  date: LocalizedText;
  severity: LocalizedText;
  categories: LocalizedText[];
  summary: LocalizedText;
  sourceLabel: LocalizedText;
  sourceUrl: string;
  claimQuote?: LocalizedText;
  claimMeta?: LocalizedText;
};

export type DemoSidebarCard = {
  title: LocalizedText;
  body: LocalizedText;
};

export type DemoPageCopy = {
  heroKicker: LocalizedText;
  heroTitle: LocalizedText;
  heroCopy: LocalizedText;
  filterKicker: LocalizedText;
  filterTitle: LocalizedText;
  filterChips: LocalizedText[];
  latestKicker: LocalizedText;
  latestTitle: LocalizedText;
  claimKicker: LocalizedText;
  claimTitle: LocalizedText;
  claimLabel: LocalizedText;
  sourceCredibilityKicker: LocalizedText;
  sourceCredibilityTitle: LocalizedText;
  sourceCredibilityBody: LocalizedText;
  spotlightKicker: LocalizedText;
  spotlightTitle: LocalizedText;
  spotlightSourcesKicker: LocalizedText;
  spotlightSourcesTitle: LocalizedText;
  signalsKicker: LocalizedText;
  signalsTitle: LocalizedText;
  signalsMonthlyKicker: LocalizedText;
  signalsMonthlyTitle: LocalizedText;
  signalsMonthlyNote: LocalizedText;
  signalsMonthlyFallback: LocalizedText;
  signalsCategoryKicker: LocalizedText;
  signalsCategoryTitle: LocalizedText;
  signalsCategoryNote: LocalizedText;
  signalsDonutLabel: LocalizedText;
};
