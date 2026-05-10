import {
  buildIncidentUrl,
  buildIncidentPath,
  MAX_INCIDENT_SLUG_LENGTH,
} from "../lib/publicIncidentRoutes";
import { buildTopicUrl, parseTopicRoute } from "../lib/publicTopicRoutes";
import {
  buildIncidentPrerenderHtml,
  buildRobotsTxt,
  buildSitemapXml,
  buildTopicPrerenderHtml,
  normalizeSiteUrl,
} from "../lib/seoFiles";
import type { IncidentDetail, PublicIncidentBase } from "../types/incident";

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

  it("builds and parses canonical topic URLs", () => {
    expect(buildTopicUrl("category", "Hallucinations", "https://example.com/")).toBe(
      "https://example.com/topics/category/hallucinations",
    );
    expect(
      buildTopicUrl("source", "legal_hallucination", "https://example.com/"),
    ).toBe("https://example.com/topics/source/legal-hallucination");
    expect(parseTopicRoute("/topics/category/hallucinations")).toEqual({
      kind: "category",
      slug: "hallucinations",
    });
  });

  it("adds topic URLs for categories and source families with public incidents", () => {
    const sitemap = buildSitemapXml({
      incidents: [
        buildIncident({
          categories: ["Hallucinations", "Model Governance"],
          source_family: "legal_hallucination",
        }),
        buildIncident({
          id: "incident-2",
          categories: ["Hallucinations"],
          source_family: "legal_hallucination",
        }),
      ],
      siteUrl: "https://airealitycheck.example/",
    });

    expect(sitemap).toContain(
      "<loc>https://airealitycheck.example/topics/category/hallucinations</loc>",
    );
    expect(sitemap).toContain(
      "<loc>https://airealitycheck.example/topics/category/model-governance</loc>",
    );
    expect(sitemap).toContain(
      "<loc>https://airealitycheck.example/topics/source/legal-hallucination</loc>",
    );
    expect(
      sitemap.match(/\/topics\/category\/hallucinations/g) ?? [],
    ).toHaveLength(1);
  });

  it("limits generated incident slugs to 80 characters", () => {
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
    expect(MAX_INCIDENT_SLUG_LENGTH).toBe(80);
  });

  it("uses short display titles in prerendered incident metadata", () => {
    const longHeadline =
      "Legal filing: Damien Charlotin's AI hallucination tracker records Amanda Adams v. Allen Butler Construction, Inc. in CA Texas with Pro Se Litigant linked to alleged or found AI legal hallucination. Nature: Fabricated: Case Law | Appellant cited several cases that do not exist.";
    const incident: IncidentDetail = {
      ...buildIncident({
        headline: longHeadline,
        headline_en: longHeadline,
        company_involved: "Legal filing",
        source_family: "legal_hallucination",
      }),
      reality_summary: "Court record confirms the issue.",
      reality_summary_en: "Court record confirms the issue.",
      reality_summary_zh: null,
      analysis: {},
      matched_claim: null,
      sources: [],
    };
    const html = buildIncidentPrerenderHtml({
      incident,
      siteUrl: "https://aioopsnews.com",
    });

    expect(html).toContain(
      "<title>AI legal hallucination: Amanda Adams v. Allen Butler Construction, Inc. | AI Oops News</title>",
    );
    expect(html).toContain(
      "<h1>AI legal hallucination: Amanda Adams v. Allen Butler Construction, Inc.</h1>",
    );
    expect(html).toContain(
      '"alternativeHeadline":"Legal filing: Damien Charlotin',
    );
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

  it("builds incident prerender HTML with canonical metadata and source links", () => {
    const incident: IncidentDetail = {
      ...buildIncident({
        headline_en: "Court <sanctions> & fake AI citations",
        company_involved: "Example & Co",
      }),
      reality_summary:
        "A court filing documented fabricated citations generated by AI.",
      reality_summary_en:
        "A court filing documented fabricated citations generated by AI.",
      reality_summary_zh: null,
      analysis: {},
      matched_claim: null,
      sources: [
        {
          id: "source-1",
          source_url: "https://example.com/court?case=1&view=pdf",
          source_type: "court",
          publisher: "Court Records",
          title: "Order & opinion",
        },
      ],
    };
    const html = buildIncidentPrerenderHtml({
      incident,
      siteUrl: "https://aioopsnews.com",
    });

    expect(html).toContain("<title>Court &lt;sanctions&gt; &amp; fake AI citations | AI Oops News</title>");
    expect(html).toContain(
      '<link rel="canonical" href="https://aioopsnews.com/incidents/incident-1/court-sanctions-fake-ai-citations" />',
    );
    expect(html).toContain("<h1>Court &lt;sanctions&gt; &amp; fake AI citations</h1>");
    expect(html).toContain("A court filing documented fabricated citations");
    expect(html).toContain("Example &amp; Co");
    expect(html).toContain(
      'href="https://example.com/court?case=1&amp;view=pdf"',
    );
    expect(html).toContain('"@type":"NewsArticle"');
    expect(html).toContain('<script type="module" src="/src/main.tsx"></script>');
  });

  it("builds topic prerender HTML with CollectionPage metadata and incident links", () => {
    const incident = buildIncident({
      headline_en: "Court sanctions brief with fake AI citations",
    });
    const html = buildTopicPrerenderHtml({
      kind: "category",
      value: "Hallucinations",
      incidents: [incident],
      siteUrl: "https://aioopsnews.com",
    });

    expect(html).toContain("<h1>Hallucinations AI Incidents</h1>");
    expect(html).toContain(
      '<link rel="canonical" href="https://aioopsnews.com/topics/category/hallucinations" />',
    );
    expect(html).toContain('"@type":"CollectionPage"');
    expect(html).toContain(
      'href="/incidents/incident-1/court-sanctions-brief-with-fake-ai-citations"',
    );
  });
});
