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
    headline text not null,
    date_logged date not null,
    company_involved text not null,
    claimant_name text,
    categories text[] not null default '{}',
    severity_score integer not null,
    reality_summary text not null,
    status text not null default 'pending_review',
    ingestion_run_id text,
    confidence_score numeric(4, 3),
    review_notes text,
    matched_claim_id uuid references claims(id),
    claim_match_confidence numeric(4, 3),
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
    source_type text not null,
    publisher text,
    title text,
    published_at timestamptz,
    is_primary boolean not null default false,
    created_at timestamptz not null default now(),
    unique (incident_id, source_url)
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
