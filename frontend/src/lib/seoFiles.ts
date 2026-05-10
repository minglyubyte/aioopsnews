import { buildIncidentUrl, normalizeSiteUrl } from "./publicIncidentRoutes";
import { buildTopicUrl, type TopicKind } from "./publicTopicRoutes";
import type { PublicIncidentBase } from "../types/incident";

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

function escapeXml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}
