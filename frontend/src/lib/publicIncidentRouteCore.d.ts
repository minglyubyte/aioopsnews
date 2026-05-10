import type { PublicIncidentBase } from "../types/incident";

export const MAX_INCIDENT_SLUG_LENGTH: 120;

export function buildIncidentPath(incident: PublicIncidentBase): string;

export function buildIncidentUrl(
  incident: PublicIncidentBase,
  siteUrl: string,
): string;

export function parseIncidentIdFromPath(pathname: string): string | null;

export function normalizeSiteUrl(siteUrl: string): string;
