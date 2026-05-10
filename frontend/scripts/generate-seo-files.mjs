import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const DEFAULT_SITE_URL = "http://localhost:5173";
const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const INCIDENT_PAGE_SIZE = 100;

export async function fetchPublicIncidents({
  apiBaseUrl = DEFAULT_API_BASE_URL,
  fetchImpl = fetch,
} = {}) {
  const incidents = [];
  let page = 1;
  let hasNextPage = true;

  while (hasNextPage) {
    const url = new URL("incidents", ensureTrailingSlash(apiBaseUrl));
    url.searchParams.set("page", String(page));
    url.searchParams.set("page_size", String(INCIDENT_PAGE_SIZE));

    const response = await fetchImpl(url.toString());
    if (!response.ok) {
      throw new Error(`Failed to fetch incidents: ${response.status}`);
    }

    const payload = await response.json();
    incidents.push(...payload.items);
    hasNextPage = Boolean(payload.has_next_page);
    page += 1;
  }

  return incidents;
}

export function buildSeoFileContents({ incidents, siteUrl }) {
  return {
    sitemapXml: buildSitemapXml({ incidents, siteUrl }),
    robotsTxt: buildRobotsTxt(siteUrl),
  };
}

export async function generateSeoFiles({
  apiBaseUrl = process.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL,
  siteUrl = process.env.SITE_URL ??
    process.env.VITE_PUBLIC_SITE_URL ??
    DEFAULT_SITE_URL,
  outputDir = new URL("../public/", import.meta.url),
  fetchImpl = fetch,
} = {}) {
  const incidents = await fetchPublicIncidents({ apiBaseUrl, fetchImpl });
  const { sitemapXml, robotsTxt } = buildSeoFileContents({
    incidents,
    siteUrl,
  });

  await mkdir(outputDir, { recursive: true });
  await writeFile(new URL("sitemap.xml", outputDir), sitemapXml);
  await writeFile(new URL("robots.txt", outputDir), robotsTxt);

  return {
    incidentCount: incidents.length,
  };
}

function buildSitemapXml({ incidents, siteUrl }) {
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

function buildRobotsTxt(siteUrl) {
  const normalizedSiteUrl = normalizeSiteUrl(siteUrl);

  return [
    "User-agent: *",
    "Allow: /",
    "",
    `Sitemap: ${normalizedSiteUrl}/sitemap.xml`,
    "",
  ].join("\n");
}

function buildIncidentPath(incident) {
  return `/incidents/${encodeURIComponent(incident.id)}/${slugifyIncidentHeadline(
    incident.headline_en ?? incident.headline,
  )}`;
}

function slugifyIncidentHeadline(headline) {
  const slug = headline
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-");

  return slug || "incident";
}

function normalizeSiteUrl(siteUrl) {
  return siteUrl.replace(/\/+$/, "");
}

function ensureTrailingSlash(url) {
  return url.endsWith("/") ? url : `${url}/`;
}

function escapeXml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const result = await generateSeoFiles();
  console.log(`Generated SEO files for ${result.incidentCount} incidents.`);
}
