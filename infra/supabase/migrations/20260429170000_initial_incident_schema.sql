create extension if not exists pgcrypto;

create table if not exists claims (
    id uuid primary key default gen_random_uuid(),
    claimant_name text not null,
    company_involved text not null,
    original_claim text not null,
    claim_date date not null,
    claim_topic text not null,
    status text not null default 'seeded',
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists claim_sources (
    id uuid primary key default gen_random_uuid(),
    claim_id uuid not null references claims(id) on delete cascade,
    source_url text not null,
    source_kind text not null,
    display_order integer not null default 0,
    created_at timestamptz not null default now(),
    unique (claim_id, source_url)
);

create table if not exists incident_logs (
    id uuid primary key default gen_random_uuid(),
    external_id text unique,
    headline text not null,
    headline_en text,
    headline_zh text,
    date_logged date not null,
    company_involved text not null,
    incident_topic text,
    claimant_name text,
    categories text[] not null default '{}',
    severity_score integer not null,
    suggested_severity_score integer,
    reality_summary text not null,
    reality_summary_en text,
    reality_summary_zh text,
    status text not null default 'pending_review',
    ingestion_run_id text,
    confidence_score numeric(4, 3),
    severity_confidence numeric(4, 3),
    severity_reasoning text,
    severity_flags text,
    severity_model text,
    severity_decision_source text,
    review_notes text,
    matched_claim_id uuid references claims(id),
    claim_match_confidence numeric(4, 3),
    legitimacy_score numeric(4, 3),
    legitimacy_label text,
    legitimacy_reasoning text,
    source_validation_summary text,
    legitimacy_flag text,
    confidence_level text,
    import_notes text,
    translation_status text,
    review_batch_id text,
    review_model text,
    duplicate_status text,
    duplicate_of_incident_id uuid references incident_logs(id),
    canonical_incident_id uuid references incident_logs(id),
    embedding_model text,
    embedding_vector text,
    reviewed_at timestamptz,
    severity_suggested_at timestamptz,
    translated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (severity_score between 1 and 5),
    check (confidence_score is null or confidence_score between 0 and 1),
    check (
        claim_match_confidence is null
        or claim_match_confidence between 0 and 1
    )
);

create table if not exists incident_sources (
    id uuid primary key default gen_random_uuid(),
    incident_id uuid not null references incident_logs(id) on delete cascade,
    source_url text not null,
    canonical_url text,
    source_type text not null,
    publisher text,
    title text,
    published_at timestamptz,
    fetch_status text,
    http_status integer,
    evidence_text text,
    fetch_error text,
    fetched_at timestamptz,
    is_primary boolean not null default false,
    created_at timestamptz not null default now(),
    unique (incident_id, source_url)
);

create table if not exists incident_duplicate_candidates (
    id uuid primary key default gen_random_uuid(),
    incident_id uuid not null references incident_logs(id) on delete cascade,
    candidate_incident_id uuid not null references incident_logs(id) on delete cascade,
    embedding_score numeric(6, 5) not null,
    llm_verdict text not null,
    confidence numeric(4, 3) not null,
    reasoning text,
    status text not null,
    created_at timestamptz not null default now(),
    unique (incident_id, candidate_incident_id)
);

create index if not exists incident_logs_date_logged_idx
    on incident_logs (date_logged desc);

create index if not exists incident_logs_severity_score_idx
    on incident_logs (severity_score);

create index if not exists incident_logs_company_involved_idx
    on incident_logs (company_involved);

create index if not exists incident_logs_claimant_name_idx
    on incident_logs (claimant_name);

create index if not exists incident_logs_status_idx
    on incident_logs (status);

create index if not exists incident_logs_categories_idx
    on incident_logs using gin (categories);

create index if not exists claims_company_involved_idx
    on claims (company_involved);

create index if not exists claims_claim_date_idx
    on claims (claim_date desc);

create index if not exists claim_sources_claim_id_idx
    on claim_sources (claim_id);

create index if not exists claim_sources_source_kind_idx
    on claim_sources (source_kind);
