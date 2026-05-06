-- Destructive local/dev reset. Do not run against production.

drop table if exists incident_duplicate_candidates cascade;
drop table if exists incident_sources cascade;
drop table if exists incident_logs cascade;
drop table if exists claim_sources cascade;
drop table if exists claims cascade;

\ir migrations/20260429170000_initial_incident_schema.sql
