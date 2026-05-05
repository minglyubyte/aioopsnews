alter table incident_logs
    add column if not exists publication_track text;

alter table incident_logs
    add column if not exists evidence_tier text;

alter table incident_logs
    add column if not exists source_family text;

alter table incident_logs
    add column if not exists verification_summary text;

alter table incident_sources
    add column if not exists source_origin text;

alter table incident_sources
    add column if not exists source_registry_key text;

alter table incident_sources
    add column if not exists raw_source_payload text;
