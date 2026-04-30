export type IncidentSource = {
  id: string;
  source_url: string;
  source_type: string;
  publisher?: string;
  title?: string;
};

export type MatchedClaim = {
  id: string;
  claimant_name: string;
  company_involved: string;
  original_claim: string;
  claim_date: string;
  claim_topic: string;
  match_confidence: number;
};

export type Incident = {
  id: string;
  headline: string;
  headline_en?: string | null;
  headline_zh?: string | null;
  date_logged: string;
  company_involved: string;
  incident_topic?: string | null;
  claimant_name?: string;
  categories: string[];
  severity_score: number;
  reality_summary: string;
  reality_summary_en?: string | null;
  reality_summary_zh?: string | null;
  status: string;
  translation_status?: string | null;
  matched_claim?: MatchedClaim | null;
  sources: IncidentSource[];
};

export type IncidentFeedResponse = {
  items: Incident[];
};

export type IncidentFilters = {
  categories: string[];
  claimants: string[];
  companies: string[];
  years: number[];
  months_by_year: Record<string, number[]>;
};

export type IncidentFeedFilters = {
  category?: string;
  company?: string;
  claimant?: string;
  severityMin?: number;
  severityMax?: number;
  year?: number;
  month?: number;
  page?: number;
  pageSize?: number;
};

export type DuplicateCandidate = {
  candidate_incident_id: string;
  embedding_score: number;
  llm_verdict: string | null;
  confidence: number | null;
  reasoning: string | null;
  status: string | null;
};

export type AdminIncident = Incident & {
  claimant_name?: string | null;
  matched_claim_id?: string | null;
  claim_match_confidence?: number | null;
  review_notes?: string | null;
  legitimacy_score?: number | null;
  legitimacy_label?: string | null;
  legitimacy_reasoning?: string | null;
  source_validation_summary?: string | null;
  review_batch_id?: string | null;
  review_model?: string | null;
  duplicate_status: string | null;
  duplicate_of_incident_id: string | null;
  canonical_incident_id: string | null;
  duplicate_candidates: DuplicateCandidate[];
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
