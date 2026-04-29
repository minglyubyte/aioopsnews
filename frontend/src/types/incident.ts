export type IncidentSource = {
  id: string;
  source_url: string;
  source_type: string;
  publisher?: string;
  title?: string;
};

export type Incident = {
  id: string;
  headline: string;
  date_logged: string;
  company_involved: string;
  claimant_name?: string;
  categories: string[];
  severity_score: number;
  reality_summary: string;
  status: string;
  sources: IncidentSource[];
};

export type IncidentFeedResponse = {
  items: Incident[];
};

export type IncidentFilters = {
  categories: string[];
  claimants: string[];
  companies: string[];
};
