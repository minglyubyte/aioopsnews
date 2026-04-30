export type DemoMetric = {
  label: string;
  value: string;
  note: string;
};

export type DemoIncident = {
  id: string;
  headline: string;
  company: string;
  date: string;
  severity: string;
  categories: string[];
  summary: string;
  sourceLabel: string;
  sourceUrl: string;
  claimQuote?: string;
  claimMeta?: string;
};

export type DemoSidebarCard = {
  title: string;
  body: string;
};
