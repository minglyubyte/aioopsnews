import type { PublicIncidentBase } from "../types/incident";

export function buildIncidentPath(incident: PublicIncidentBase): string {
  return `/incidents/${encodeURIComponent(incident.id)}/${slugifyIncidentHeadline(
    incident.headline_en ?? incident.headline,
  )}`;
}

export function parseIncidentIdFromPath(pathname: string): string | null {
  const [, section, encodedIncidentId] = pathname.split("/");

  if (section !== "incidents" || !encodedIncidentId) {
    return null;
  }

  return decodeURIComponent(encodedIncidentId);
}

function slugifyIncidentHeadline(headline: string): string {
  const slug = headline
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-");

  return slug || "incident";
}
