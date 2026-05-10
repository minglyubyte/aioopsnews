import { mkdir, readFile, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { parseEnv } from "node:util";
import {
  buildIncidentUrl,
  normalizeSiteUrl,
} from "../src/lib/publicIncidentRouteCore.js";
import { buildTopicUrl } from "../src/lib/publicTopicRouteCore.js";

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
  apiBaseUrl,
  siteUrl,
  outputDir = new URL("../public/", import.meta.url),
  fetchImpl = fetch,
} = {}) {
  await loadProjectEnv();
  const resolvedApiBaseUrl =
    apiBaseUrl ?? process.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;
  const resolvedSiteUrl =
    siteUrl ??
    process.env.SITE_URL ??
    process.env.VITE_PUBLIC_SITE_URL ??
    DEFAULT_SITE_URL;
  const incidents = await fetchPublicIncidents({
    apiBaseUrl: resolvedApiBaseUrl,
    fetchImpl,
  });
  const { sitemapXml, robotsTxt } = buildSeoFileContents({
    incidents,
    siteUrl: resolvedSiteUrl,
  });

  await mkdir(outputDir, { recursive: true });
  await writeFile(new URL("sitemap.xml", outputDir), sitemapXml);
  await writeFile(new URL("robots.txt", outputDir), robotsTxt);

  return {
    incidentCount: incidents.length,
  };
}

async function loadProjectEnv() {
  try {
    const envText = await readFile(new URL("../../.env", import.meta.url), {
      encoding: "utf8",
    });
    const parsedEnv = parseEnv(envText);

    for (const [key, value] of Object.entries(parsedEnv)) {
      process.env[key] ??= value;
    }
  } catch (error) {
    if (error && typeof error === "object" && "code" in error) {
      if (error.code === "ENOENT") {
        return;
      }
    }

    throw error;
  }
}

function buildSitemapXml({ incidents, siteUrl }) {
  const incidentUrls = incidents
    .map(
      (incident) => `  <url>
    <loc>${escapeXml(buildIncidentUrl(incident, siteUrl))}</loc>
    <lastmod>${escapeXml(incident.date_logged)}</lastmod>
  </url>`,
    )
    .join("\n");
  const newestLastmod = incidents[0]?.date_logged ?? "";
  const topicUrls = collectPublicTopics(incidents)
    .map(
      (topic) => `  <url>
    <loc>${escapeXml(buildTopicUrl(topic.kind, topic.value, siteUrl))}</loc>${
      newestLastmod ? `\n    <lastmod>${escapeXml(newestLastmod)}</lastmod>` : ""
    }
  </url>`,
    )
    .join("\n");
  const urls = [incidentUrls, topicUrls].filter(Boolean).join("\n");

  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    urls,
    "</urlset>",
    "",
  ].join("\n");
}

function collectPublicTopics(incidents) {
  const topicKeys = new Set();
  const topics = [];

  for (const incident of incidents) {
    for (const category of incident.categories ?? []) {
      addTopic(topics, topicKeys, "category", category);
    }
    if (incident.source_family) {
      addTopic(topics, topicKeys, "source", incident.source_family);
    }
  }

  return topics;
}

function addTopic(topics, topicKeys, kind, value) {
  const key = `${kind}:${value}`;
  if (topicKeys.has(key)) {
    return;
  }

  topicKeys.add(key);
  topics.push({ kind, value });
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

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const result = await generateSeoFiles();
  console.log(`Generated SEO files for ${result.incidentCount} incidents.`);
}
