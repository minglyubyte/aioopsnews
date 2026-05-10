import {
  buildIncidentUrl,
  buildIncidentPath,
  MAX_INCIDENT_SLUG_LENGTH,
} from "../lib/publicIncidentRoutes";
import {
  buildRobotsTxt,
  buildSitemapXml,
  normalizeSiteUrl,
} from "../lib/seoFiles";
import type { PublicIncidentBase } from "../types/incident";

function buildIncident(
  overrides: Partial<PublicIncidentBase> = {},
): PublicIncidentBase {
  return {
    id: overrides.id ?? "incident-1",
    headline:
      overrides.headline ?? "Court sanctions brief with fake AI citations",
    headline_en:
      overrides.headline_en ??
      overrides.headline ??
      "Court sanctions brief with fake AI citations",
    headline_zh: overrides.headline_zh ?? null,
    date_logged: overrides.date_logged ?? "2026-05-06",
    company_involved: overrides.company_involved ?? "Court filing",
    company_involved_zh: overrides.company_involved_zh ?? null,
    incident_topic: overrides.incident_topic ?? "legal hallucination",
    claimant_name: overrides.claimant_name,
    categories: overrides.categories ?? ["Legal Hallucination"],
    severity_score: overrides.severity_score ?? 4,
    status: overrides.status ?? "approved",
    translation_status: overrides.translation_status ?? "completed",
    publication_track: overrides.publication_track ?? "verified_accident",
    evidence_tier: overrides.evidence_tier ?? "court_or_regulator",
    source_family: overrides.source_family ?? "legal_hallucination",
    verification_summary:
      overrides.verification_summary ??
      "A court record confirms the sanctions and fake citations.",
  };
}

describe("seo files", () => {
  it("normalizes site URLs without trailing slashes", () => {
    expect(normalizeSiteUrl("https://airealitycheck.example/")).toBe(
      "https://airealitycheck.example",
    );
  });

  it("builds a sitemap with incident URLs matching canonical route paths", () => {
    const incident = buildIncident();
    const sitemap = buildSitemapXml({
      incidents: [incident],
      siteUrl: "https://airealitycheck.example/",
    });

    expect(sitemap).toContain("<urlset");
    expect(sitemap).toContain(
      `<loc>${buildIncidentUrl(
        incident,
        "https://airealitycheck.example/",
      )}</loc>`,
    );
    expect(sitemap).toContain("<lastmod>2026-05-06</lastmod>");
  });

  it("limits generated incident slugs to 120 characters", () => {
    const path = buildIncidentPath(
      buildIncident({
        headline_en: Array.from({ length: 40 }, (_, index) => {
          return `Example${index}`;
        }).join(" "),
      }),
    );
    const slug = path.split("/").at(-1);

    expect(slug).toBeDefined();
    expect(slug?.length).toBeLessThanOrEqual(MAX_INCIDENT_SLUG_LENGTH);
  });

  it("escapes sitemap XML entities in generated locations", () => {
    const incident = buildIncident({
      id: "incident&1",
      headline_en: "Court sanctions brief with fake AI citations",
    });
    const sitemap = buildSitemapXml({
      incidents: [incident],
      siteUrl: "https://example.com",
    });

    expect(sitemap).toContain(
      "<loc>https://example.com/incidents/incident%261/court-sanctions-brief-with-fake-ai-citations</loc>",
    );
  });

  it("builds robots.txt that allows crawling and points at the sitemap", () => {
    expect(buildRobotsTxt("https://airealitycheck.example/")).toBe(
      [
        "User-agent: *",
        "Allow: /",
        "",
        "Sitemap: https://airealitycheck.example/sitemap.xml",
        "",
      ].join("\n"),
    );
  });
});
