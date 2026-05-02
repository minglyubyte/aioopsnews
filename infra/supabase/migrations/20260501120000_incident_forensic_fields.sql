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
