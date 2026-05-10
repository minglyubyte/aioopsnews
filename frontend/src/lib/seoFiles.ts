import {
  buildIncidentPath,
  buildIncidentUrl,
  normalizeSiteUrl,
} from "./publicIncidentRoutes";
import { buildTopicUrl, type TopicKind } from "./publicTopicRoutes";
import type { IncidentDetail, PublicIncidentBase } from "../types/incident";

export { normalizeSiteUrl } from "./publicIncidentRoutes";

type SitemapOptions = {
  incidents: PublicIncidentBase[];
  siteUrl: string;
};

export function buildSitemapXml({ incidents, siteUrl }: SitemapOptions) {
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

function collectPublicTopics(incidents: PublicIncidentBase[]) {
  const topicKeys = new Set<string>();
  const topics: Array<{ kind: TopicKind; value: string }> = [];

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

function addTopic(
  topics: Array<{ kind: TopicKind; value: string }>,
  topicKeys: Set<string>,
  kind: TopicKind,
  value: string,
) {
  const key = `${kind}:${value}`;
  if (topicKeys.has(key)) {
    return;
  }

  topicKeys.add(key);
  topics.push({ kind, value });
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

export function buildIncidentPrerenderHtml({
  incident,
  siteUrl,
}: {
  incident: IncidentDetail;
  siteUrl: string;
}) {
  const headline = incident.headline_en ?? incident.headline;
  const description = incident.reality_summary_en ?? incident.reality_summary;
  const canonicalUrl = buildIncidentUrl(incident, siteUrl);
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline,
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
  };
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
    structuredData,
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

export function buildTopicPrerenderHtml({
  kind,
  value,
  incidents,
  siteUrl,
}: {
  kind: TopicKind;
  value: string;
  incidents: PublicIncidentBase[];
  siteUrl: string;
}) {
  const title = `${topicTitle(value)} AI Incidents`;
  const description = `Browse ${incidents.length} public AI incident records related to ${topicTitle(
    value,
  )}.`;
  const canonicalUrl = buildTopicUrl(kind, value, siteUrl);
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: title,
    description,
    mainEntityOfPage: canonicalUrl,
    mainEntity: incidents.slice(0, 20).map((incident) => ({
      "@type": "NewsArticle",
      headline: incident.headline_en ?? incident.headline,
      url: buildIncidentUrl(incident, siteUrl),
    })),
  };
  const incidentItems = incidents
    .slice(0, 20)
    .map((incident) => {
      const headline = incident.headline_en ?? incident.headline;
      return `<li><a href="${escapeHtmlAttribute(
        buildIncidentPath(incident),
      )}">${escapeHtml(headline)}</a></li>`;
    })
    .join("");

  return buildPrerenderDocument({
    title: `${title} | AI Oops News`,
    description,
    canonicalUrl,
    structuredData,
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
}: {
  bodyHtml: string;
  canonicalUrl: string;
  description: string;
  structuredData: Record<string, unknown>;
  title: string;
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

function topicTitle(value: string) {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function escapeXml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function escapeHtml(value: string) {
  return escapeXml(value);
}

function escapeHtmlAttribute(value: string) {
  return escapeXml(value);
}
