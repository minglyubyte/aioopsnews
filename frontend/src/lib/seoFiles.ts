import { buildIncidentPath } from "./publicIncidentRoutes";
import type { PublicIncidentBase } from "../types/incident";

type SitemapOptions = {
  incidents: PublicIncidentBase[];
  siteUrl: string;
};

export function buildSitemapXml({ incidents, siteUrl }: SitemapOptions) {
  const normalizedSiteUrl = normalizeSiteUrl(siteUrl);
  const urls = incidents
    .map(
      (incident) => `  <url>
    <loc>${escapeXml(`${normalizedSiteUrl}${buildIncidentPath(incident)}`)}</loc>
    <lastmod>${escapeXml(incident.date_logged)}</lastmod>
  </url>`,
    )
    .join("\n");

  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    urls,
    "</urlset>",
    "",
  ].join("\n");
}

export function buildRobotsTxt(siteUrl: string) {
  const normalizedSiteUrl = normalizeSiteUrl(siteUrl);

  return [
    "User-agent: *",
    "Allow: /",
    "",
    `Sitemap: ${normalizedSiteUrl}/sitemap.xml`,
    "",
  ].join("\n");
}

export function normalizeSiteUrl(siteUrl: string) {
  return siteUrl.replace(/\/+$/, "");
}

function escapeXml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}
