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

update incident_logs
set
    publication_track = coalesce(publication_track, 'verified_accident'),
    evidence_tier = coalesce(evidence_tier, 'official_documented'),
    source_family = coalesce(source_family, 'autonomous_vehicle'),
    verification_summary = coalesce(
        nullif(verification_summary, ''),
        'California DMV collision-report metadata documents this autonomous-vehicle incident; editorial review still checks AI relevance, severity, and exact causal claims.'
    )
where lower(company_involved) = 'waymo'
  and (
      headline ilike '%california dmv%'
      or headline ilike '%dmv collision%'
      or reality_summary ilike '%california dmv%'
      or reality_summary ilike '%dmv collision%'
      or categories::text ilike '%autonomous systems%'
  );

update incident_sources
set
    source_origin = coalesce(source_origin, 'fixed_verified_source'),
    source_registry_key = coalesce(source_registry_key, 'ca_dmv_av_collisions')
where incident_id in (
    select id
    from incident_logs
    where publication_track = 'verified_accident'
      and source_family = 'autonomous_vehicle'
      and lower(company_involved) = 'waymo'
)
  and (
      publisher ilike '%dmv%'
      or source_url ilike '%dmv.ca.gov%'
  );
