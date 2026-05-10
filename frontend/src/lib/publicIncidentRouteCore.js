import { buildIncidentDisplayTitle } from "./publicIncidentTitleCore.js";

export const MAX_INCIDENT_SLUG_LENGTH = 80;

export function buildIncidentPath(incident) {
  return `/incidents/${encodeURIComponent(incident.id)}/${slugifyIncidentHeadline(
    buildIncidentDisplayTitle(incident, "en"),
  )}`;
}

export function buildIncidentUrl(incident, siteUrl) {
  return `${normalizeSiteUrl(siteUrl)}${buildIncidentPath(incident)}`;
}

export function parseIncidentIdFromPath(pathname) {
  const [, section, encodedIncidentId] = pathname.split("/");

  if (section !== "incidents" || !encodedIncidentId) {
    return null;
  }

  return decodeURIComponent(encodedIncidentId);
}

export function normalizeSiteUrl(siteUrl) {
  return siteUrl.replace(/\/+$/, "");
}

function slugifyIncidentHeadline(headline) {
  const slug = String(headline ?? "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-");

  if (!slug) {
    return "incident";
  }

  return (
    slug.slice(0, MAX_INCIDENT_SLUG_LENGTH).replace(/-+$/g, "") || "incident"
  );
}
