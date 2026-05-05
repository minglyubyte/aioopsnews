-- Database schema and migrations for AI Reality Check.
-- Loaded at repository startup via _initialize_database().

create table if not exists claims (
    id text primary key,
    claimant_name text not null,
    company_involved text not null,
    original_claim text not null,
    claim_date text not null,
    claim_topic text not null,
    status text not null,
    notes text,
    created_at timestamptz default current_timestamp,
    updated_at timestamptz default current_timestamp
);

alter table claims
    add column if not exists notes text;

create table if not exists claim_sources (
    id text primary key,
    claim_id text not null references claims(id) on delete cascade,
    source_url text not null,
    source_kind text not null,
    display_order integer not null default 0,
    created_at timestamptz default current_timestamp
);

create table if not exists incident_logs (
    id text primary key,
    external_id text,
    headline text not null,
    headline_en text,
    headline_zh text,
    date_logged text not null,
    company_involved text not null,
    company_involved_zh text,
    incident_topic text,
    claimant_name text,
    categories text not null,
    severity_score integer not null,
    suggested_severity_score integer,
    reality_summary text not null,
    reality_summary_en text,
    reality_summary_zh text,
    status text not null,
    ingestion_run_id text,
    confidence_score double precision,
    severity_confidence double precision,
    severity_reasoning text,
    severity_flags text,
    severity_model text,
    severity_decision_source text,
    review_notes text,
    matched_claim_id text references claims(id),
    claim_match_confidence double precision,
    legitimacy_score double precision,
    legitimacy_label text,
    legitimacy_reasoning text,
    legitimacy_reasoning_zh text,
    source_validation_summary text,
    source_validation_summary_zh text,
    incident_summary_en text,
    incident_summary_zh text,
    what_happened_en text,
    what_happened_zh text,
    ai_failure_point_en text,
    ai_failure_point_zh text,
    why_it_matters_en text,
    why_it_matters_zh text,
    evidence_summary_en text,
    evidence_summary_zh text,
    publication_track text,
    evidence_tier text,
    source_family text,
    verification_summary text,
    legitimacy_flag text,
    confidence_level text,
    import_notes text,
    translation_status text,
    review_batch_id text,
    review_model text,
    duplicate_status text,
    duplicate_of_incident_id text references incident_logs(id),
    canonical_incident_id text references incident_logs(id),
    embedding_model text,
    embedding_vector text,
    reviewed_at timestamptz,
    severity_suggested_at timestamptz,
    translated_at timestamptz,
    created_at timestamptz default current_timestamp,
    updated_at timestamptz default current_timestamp
);

alter table incident_logs
    add column if not exists external_id text;

alter table incident_logs
    add column if not exists suggested_severity_score integer;

alter table incident_logs
    add column if not exists severity_confidence double precision;

alter table incident_logs
    add column if not exists severity_reasoning text;

alter table incident_logs
    add column if not exists severity_flags text;

alter table incident_logs
    add column if not exists severity_model text;

alter table incident_logs
    add column if not exists severity_decision_source text;

alter table incident_logs
    add column if not exists headline_en text;

alter table incident_logs
    add column if not exists headline_zh text;

alter table incident_logs
    add column if not exists company_involved_zh text;

alter table incident_logs
    add column if not exists incident_topic text;

alter table incident_logs
    add column if not exists reality_summary_en text;

alter table incident_logs
    add column if not exists reality_summary_zh text;

alter table incident_logs
    add column if not exists legitimacy_score double precision;

alter table incident_logs
    add column if not exists legitimacy_label text;

alter table incident_logs
    add column if not exists legitimacy_reasoning text;

alter table incident_logs
    add column if not exists legitimacy_reasoning_zh text;

alter table incident_logs
    add column if not exists source_validation_summary text;

alter table incident_logs
    add column if not exists source_validation_summary_zh text;

alter table incident_logs
    add column if not exists incident_summary_en text;

alter table incident_logs
    add column if not exists incident_summary_zh text;

alter table incident_logs
    add column if not exists what_happened_en text;

alter table incident_logs
    add column if not exists what_happened_zh text;

alter table incident_logs
    add column if not exists ai_failure_point_en text;

alter table incident_logs
    add column if not exists ai_failure_point_zh text;

alter table incident_logs
    add column if not exists why_it_matters_en text;

alter table incident_logs
    add column if not exists why_it_matters_zh text;

alter table incident_logs
    add column if not exists evidence_summary_en text;

alter table incident_logs
    add column if not exists evidence_summary_zh text;

alter table incident_logs
    add column if not exists publication_track text;

alter table incident_logs
    add column if not exists evidence_tier text;

alter table incident_logs
    add column if not exists source_family text;

alter table incident_logs
    add column if not exists verification_summary text;

alter table incident_logs
    add column if not exists legitimacy_flag text;

alter table incident_logs
    add column if not exists confidence_level text;

alter table incident_logs
    add column if not exists import_notes text;

alter table incident_logs
    add column if not exists translation_status text;

alter table incident_logs
    add column if not exists review_batch_id text;

alter table incident_logs
    add column if not exists review_model text;

alter table incident_logs
    add column if not exists duplicate_status text;

alter table incident_logs
    add column if not exists duplicate_of_incident_id text references incident_logs(id);

alter table incident_logs
    add column if not exists canonical_incident_id text references incident_logs(id);

alter table incident_logs
    add column if not exists embedding_model text;

alter table incident_logs
    add column if not exists embedding_vector text;

alter table incident_logs
    add column if not exists reviewed_at timestamptz;

alter table incident_logs
    add column if not exists severity_suggested_at timestamptz;

alter table incident_logs
    add column if not exists translated_at timestamptz;

create table if not exists incident_sources (
    id text primary key,
    incident_id text not null references incident_logs(id) on delete cascade,
    source_url text not null,
    canonical_url text,
    source_type text not null,
    publisher text,
    title text,
    published_at text,
    fetch_status text,
    http_status integer,
    evidence_text text,
    fetch_error text,
    source_origin text,
    source_registry_key text,
    raw_source_payload text,
    fetched_at timestamptz,
    is_primary integer not null default 0,
    created_at timestamptz default current_timestamp
);

alter table incident_sources
    add column if not exists canonical_url text;

alter table incident_sources
    add column if not exists fetch_status text;

alter table incident_sources
    add column if not exists http_status integer;

alter table incident_sources
    add column if not exists evidence_text text;

alter table incident_sources
    add column if not exists fetch_error text;

alter table incident_sources
    add column if not exists source_origin text;

alter table incident_sources
    add column if not exists source_registry_key text;

alter table incident_sources
    add column if not exists raw_source_payload text;

alter table incident_sources
    add column if not exists fetched_at timestamptz;

create table if not exists incident_duplicate_candidates (
    id text primary key,
    incident_id text not null references incident_logs(id) on delete cascade,
    candidate_incident_id text not null references incident_logs(id) on delete cascade,
    embedding_score double precision not null,
    llm_verdict text not null,
    confidence double precision not null,
    reasoning text,
    status text not null,
    created_at timestamptz default current_timestamp
);

create unique index if not exists claim_sources_claim_url_unique_idx
    on claim_sources (claim_id, source_url);

create index if not exists claim_sources_claim_id_idx
    on claim_sources (claim_id);

create index if not exists claim_sources_source_kind_idx
    on claim_sources (source_kind);

create unique index if not exists incident_logs_external_id_unique_idx
    on incident_logs (external_id)
    where external_id is not null;

create unique index if not exists incident_duplicate_candidates_unique_idx
    on incident_duplicate_candidates (incident_id, candidate_incident_id);
