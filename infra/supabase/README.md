# Supabase Schema

`migrations/20260429170000_initial_incident_schema.sql` is the fresh
PostgreSQL-native baseline for the app tables.

For local or development databases only, `reset_local_dev.sql` drops the app
tables and recreates them from that baseline. Do not run the reset script
against production.

After a reset, seed data through the backend import scripts so UUID primary keys,
PostgreSQL arrays, and JSONB payloads are written through the repository layer.
Claim CSV ids must be UUIDs when provided; incident CSV `incident_id` values are
external keys and do not need to be UUIDs.
