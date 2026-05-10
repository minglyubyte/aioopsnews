import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { parseEnv } from "node:util";
import {
  buildIncidentPath,
  buildIncidentUrl,
  normalizeSiteUrl,
} from "../src/lib/publicIncidentRouteCore.js";
import {
  buildIncidentDisplayTitle,
  buildOriginalIncidentTitle,
} from "../src/lib/publicIncidentTitleCore.js";
import {
  buildTopicPath,
  buildTopicUrl,
} from "../src/lib/publicTopicRouteCore.js";

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

export async function fetchPublicIncidentDetails({
  apiBaseUrl = DEFAULT_API_BASE_URL,
  fetchImpl = fetch,
  incidents,
} = {}) {
  const details = [];

  for (const incident of incidents) {
    const url = new URL(
      `incidents/${encodeURIComponent(incident.id)}`,
      ensureTrailingSlash(apiBaseUrl),
    );
    const response = await fetchImpl(url.toString());
    if (!response.ok) {
      throw new Error(
        `Failed to fetch incident detail ${incident.id}: ${response.status}`,
      );
    }

    details.push(await response.json());
  }

  return details;
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
  const incidentDetails = await fetchPublicIncidentDetails({
    apiBaseUrl: resolvedApiBaseUrl,
    fetchImpl,
    incidents,
  });
  const { sitemapXml, robotsTxt } = buildSeoFileContents({
    incidents,
    siteUrl: resolvedSiteUrl,
  });

  await mkdir(outputDir, { recursive: true });
  await writeFile(new URL("sitemap.xml", outputDir), sitemapXml);
  await writeFile(new URL("robots.txt", outputDir), robotsTxt);
  const { incidentHtmlCount, topicHtmlCount } = await writePrerenderHtmlFiles({
    incidents,
    incidentDetails,
    outputDir,
    siteUrl: resolvedSiteUrl,
  });

  return {
    incidentCount: incidents.length,
    incidentHtmlCount,
    topicHtmlCount,
  };
}

async function loadProjectEnv() {
  try {
    const envUrl = new URL("../../.env", import.meta.url);
    if (envUrl.protocol !== "file:") {
      return;
    }

    const envText = await readFile(envUrl, {
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

export async function writePrerenderHtmlFiles({
  incidents,
  incidentDetails,
  outputDir,
  siteUrl,
}) {
  await rm(new URL("incidents/", outputDir), { recursive: true, force: true });
  await rm(new URL("topics/", outputDir), { recursive: true, force: true });

  let incidentHtmlCount = 0;
  for (const incident of incidentDetails) {
    const html = buildIncidentPrerenderHtml({ incident, siteUrl });
    await writeGeneratedHtml(outputDir, buildIncidentPath(incident), html);
    incidentHtmlCount += 1;
  }

  let topicHtmlCount = 0;
  for (const topic of collectPublicTopics(incidents)) {
    const topicIncidents = incidents.filter((incident) => {
      if (topic.kind === "category") {
        return (incident.categories ?? []).includes(topic.value);
      }
      return incident.source_family === topic.value;
    });
    if (!topicIncidents.length) {
      continue;
    }

    const html = buildTopicPrerenderHtml({
      kind: topic.kind,
      value: topic.value,
      incidents: topicIncidents,
      siteUrl,
    });
    await writeGeneratedHtml(outputDir, buildTopicPath(topic.kind, topic.value), html);
    topicHtmlCount += 1;
  }

  return { incidentHtmlCount, topicHtmlCount };
}

async function writeGeneratedHtml(outputDir, routePath, html) {
  const relativePath = `${routePath.replace(/^\/+/, "")}/index.html`;
  const fileUrl = new URL(relativePath, outputDir);
  await mkdir(new URL("./", fileUrl), { recursive: true });
  await writeFile(fileUrl, html);
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

export function buildIncidentPrerenderHtml({ incident, siteUrl }) {
  const headline = buildIncidentDisplayTitle(incident);
  const originalHeadline = buildOriginalIncidentTitle(incident);
  const description = incident.reality_summary_en ?? incident.reality_summary;
  const canonicalUrl = buildIncidentUrl(incident, siteUrl);
  const sourceItems = (incident.sources ?? [])
    .map((source) => {
      const label = source.title || source.publisher || source.source_url;
      return `<li><a href="${escapeHtmlAttribute(
        source.source_url,
      )}">${escapeHtml(label)}</a></li>`;
    })
    .join("");

  return buildPrerenderDocument({
    title: `${headline} | AI Oops News`,
    description,
    canonicalUrl,
    structuredData: {
      "@context": "https://schema.org",
      "@type": "NewsArticle",
      headline,
      alternativeHeadline: originalHeadline,
      description,
      datePublished: incident.date_logged,
      dateModified: incident.date_logged,
      mainEntityOfPage: canonicalUrl,
      isAccessibleForFree: true,
      author: {
        "@type": "Organization",
        name: "AI Oops News",
      },
      publisher: {
        "@type": "Organization",
        name: "AI Oops News",
      },
    },
    bodyHtml: [
      `<p class="seo-kicker">Case file</p>`,
      `<h1>${escapeHtml(headline)}</h1>`,
      `<p>${escapeHtml(description)}</p>`,
      `<dl>`,
      `<dt>Company</dt><dd>${escapeHtml(incident.company_involved)}</dd>`,
      `<dt>Date</dt><dd>${escapeHtml(incident.date_logged)}</dd>`,
      `<dt>Severity</dt><dd>${escapeHtml(String(incident.severity_score))}</dd>`,
      `<dt>Evidence tier</dt><dd>${escapeHtml(incident.evidence_tier)}</dd>`,
      `</dl>`,
      `<h2>Sources</h2>`,
      sourceItems ? `<ul>${sourceItems}</ul>` : `<p>No source links listed.</p>`,
      `<p>AI Oops News summarizes cited public sources for informational and research purposes only. Verify important facts from original sources.</p>`,
    ].join("\n"),
  });
}

export function buildTopicPrerenderHtml({ kind, value, incidents, siteUrl }) {
  const title = `${topicTitle(value)} AI Incidents`;
  const description = `Browse ${incidents.length} public AI incident records related to ${topicTitle(
    value,
  )}.`;
  const canonicalUrl = buildTopicUrl(kind, value, siteUrl);
  const incidentItems = incidents
    .slice(0, 20)
    .map((incident) => {
      const headline = buildIncidentDisplayTitle(incident);
      return `<li><a href="${escapeHtmlAttribute(
        buildIncidentPath(incident),
      )}">${escapeHtml(headline)}</a></li>`;
    })
    .join("");

  return buildPrerenderDocument({
    title: `${title} | AI Oops News`,
    description,
    canonicalUrl,
    structuredData: {
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      name: title,
      description,
      mainEntityOfPage: canonicalUrl,
      mainEntity: incidents.slice(0, 20).map((incident) => ({
        "@type": "NewsArticle",
        headline: buildIncidentDisplayTitle(incident),
        url: buildIncidentUrl(incident, siteUrl),
      })),
    },
    bodyHtml: [
      `<p class="seo-kicker">Topic archive</p>`,
      `<h1>${escapeHtml(title)}</h1>`,
      `<p>${escapeHtml(description)}</p>`,
      `<p>${incidents.length} incidents</p>`,
      incidentItems ? `<ul>${incidentItems}</ul>` : `<p>No incidents listed.</p>`,
    ].join("\n"),
  });
}

function buildPrerenderDocument({
  bodyHtml,
  canonicalUrl,
  description,
  structuredData,
  title,
}) {
  return [
    "<!doctype html>",
    '<html lang="en">',
    "  <head>",
    '    <meta charset="UTF-8" />',
    '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />',
    `    <title>${escapeHtml(title)}</title>`,
    `    <meta name="description" content="${escapeHtmlAttribute(description)}" />`,
    `    <link rel="canonical" href="${escapeHtmlAttribute(canonicalUrl)}" />`,
    '    <script type="application/ld+json">',
    `      ${JSON.stringify(structuredData)}`,
    "    </script>",
    "  </head>",
    "  <body>",
    `    <div id="root">${bodyHtml}</div>`,
    '    <script type="module" src="/src/main.tsx"></script>',
    "  </body>",
    "</html>",
    "",
  ].join("\n");
}

function topicTitle(value) {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
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

function escapeHtml(value) {
  return escapeXml(value);
}

function escapeHtmlAttribute(value) {
  return escapeXml(value);
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const result = await generateSeoFiles();
  console.log(
    `Generated SEO files for ${result.incidentCount} incidents, ${result.incidentHtmlCount} incident pages, and ${result.topicHtmlCount} topic pages.`,
  );
}
