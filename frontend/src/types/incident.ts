export type IncidentSource = {
  id: string;
  source_url: string;
  source_type: string;
  source_origin?: string | null;
  source_registry_key?: string | null;
  raw_source_payload?: Record<string, unknown> | null;
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

export type PublicIncidentBase = {
  id: string;
  headline: string;
  headline_en?: string | null;
  headline_zh?: string | null;
  date_logged: string;
  company_involved: string;
  company_involved_zh?: string | null;
  incident_topic?: string | null;
  claimant_name?: string;
  categories: string[];
  severity_score: number;
  status: string;
  translation_status?: string | null;
  publication_track: string;
  evidence_tier: string;
  source_family: string;
  verification_summary: string;
};

export type IncidentArchiveItem = PublicIncidentBase & {
  archive_summary: string;
  archive_summary_en?: string | null;
  archive_summary_zh?: string | null;
};

export type IncidentAnalysis = {
  incident_summary_en?: string | null;
  incident_summary_zh?: string | null;
  what_happened_en?: string | null;
  what_happened_zh?: string | null;
  ai_failure_point_en?: string | null;
  ai_failure_point_zh?: string | null;
  why_it_matters_en?: string | null;
  why_it_matters_zh?: string | null;
  evidence_summary_en?: string | null;
  evidence_summary_zh?: string | null;
  incident_summary?: string | null;
  what_happened?: string | null;
  ai_failure_point?: string | null;
  why_it_matters?: string | null;
  evidence_summary?: string | null;
};

export type FeedSummaryCount = {
  count: number;
};

export type FeedCategorySummary = FeedSummaryCount & {
  category: string;
};

export type FeedCompanySummary = FeedSummaryCount & {
  company: string;
  company_zh?: string | null;
};

export type IncidentSliceSummary = {
  total_matches: number;
  newest_logged?: string | null;
  oldest_logged?: string | null;
  highest_severity?: number | null;
  top_categories: FeedCategorySummary[];
  top_companies: FeedCompanySummary[];
};

export type IncidentDetail = PublicIncidentBase & {
  reality_summary: string;
  reality_summary_en?: string | null;
  reality_summary_zh?: string | null;
  analysis: IncidentAnalysis;
  matched_claim?: MatchedClaim | null;
  sources: IncidentSource[];
};

export type Incident = PublicIncidentBase & {
  archive_summary?: string | null;
  archive_summary_en?: string | null;
  archive_summary_zh?: string | null;
  reality_summary?: string | null;
  reality_summary_en?: string | null;
  reality_summary_zh?: string | null;
  analysis?: IncidentAnalysis | null;
  matched_claim?: MatchedClaim | null;
  sources?: IncidentSource[];
};

export type IncidentFeedResponse = {
  items: IncidentArchiveItem[];
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
  has_next_page: boolean;
  has_previous_page: boolean;
  slice_summary: IncidentSliceSummary;
};

export type IncidentFilters = {
  categories: string[];
  claimants: string[];
  companies: string[];
  company_labels_zh: Record<string, string | null>;
  publication_tracks: string[];
  source_families: string[];
  years: number[];
  months_by_year: Record<string, number[]>;
};

export type IncidentFeedFilters = {
  category?: string;
  company?: string;
  claimant?: string;
  severityMin?: number;
  severityMax?: number;
  publicationTrack?: string;
  sourceFamily?: string;
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

export type AdminIncident = PublicIncidentBase & {
  reality_summary: string;
  reality_summary_en?: string | null;
  reality_summary_zh?: string | null;
  analysis?: IncidentAnalysis | null;
  matched_claim?: MatchedClaim | null;
  sources: IncidentSource[];
  claimant_name?: string | null;
  matched_claim_id?: string | null;
  claim_match_confidence?: number | null;
  review_notes?: string | null;
  legitimacy_score?: number | null;
  legitimacy_label?: string | null;
  suggested_severity_score?: number | null;
  severity_confidence?: number | null;
  severity_reasoning?: string | null;
  severity_flags?: string[];
  severity_model?: string | null;
  severity_decision_source?: string | null;
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
  status:
    | "pending_review"
    | "pending_editor_review"
    | "approved"
    | "rejected"
    | "needs_rework";
  company_involved: string;
  claimant_name?: string | null;
  categories: string[];
  severity_score: number;
  reality_summary: string;
  matched_claim_id?: string | null;
  claim_match_confidence?: number | null;
  review_notes: string;
};
