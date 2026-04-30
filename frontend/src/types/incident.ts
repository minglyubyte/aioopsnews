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

export type AdminIncident = Incident & {
  claimant_name?: string | null;
  matched_claim_id?: string | null;
  claim_match_confidence?: number | null;
  review_notes?: string | null;
};

export type AdminIncidentQueueResponse = {
  items: AdminIncident[];
};

export type AdminIncidentUpdateRequest = {
  status: "pending_review" | "approved" | "rejected" | "needs_rework";
  company_involved: string;
  claimant_name?: string | null;
  categories: string[];
  severity_score: number;
  reality_summary: string;
  matched_claim_id?: string | null;
  claim_match_confidence?: number | null;
  review_notes: string;
};
