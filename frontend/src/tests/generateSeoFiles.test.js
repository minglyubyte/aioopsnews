import { buildIncidentUrl } from "../lib/publicIncidentRoutes";
import { buildTopicUrl } from "../lib/publicTopicRoutes";

describe("generate SEO files script helpers", () => {
  it("fetches all public incident feed pages", async () => {
    const { fetchPublicIncidents } = await import(
      "../../scripts/generate-seo-files.mjs"
    );
    const fetchCalls = [];
    const fetchImpl = vi.fn(async (url) => {
      fetchCalls.push(String(url));
      const parsedUrl = new URL(String(url));
      const page = parsedUrl.searchParams.get("page");

      return {
        ok: true,
        status: 200,
        async json() {
          return {
            items:
              page === "1"
                ? [
                    {
                      id: "incident-1",
                      headline: "First incident",
                      headline_en: "First incident",
                      date_logged: "2026-05-06",
                    },
                  ]
                : [
                    {
                      id: "incident-2",
                      headline: "Second incident",
                      headline_en: "Second incident",
                      date_logged: "2026-05-05",
                    },
                  ],
            has_next_page: page === "1",
          };
        },
      };
    });

    const incidents = await fetchPublicIncidents({
      apiBaseUrl: "https://api.example.com/",
      fetchImpl,
    });

    expect(fetchCalls).toEqual([
      "https://api.example.com/incidents?page=1&page_size=100",
      "https://api.example.com/incidents?page=2&page_size=100",
    ]);
    expect(incidents).toHaveLength(2);
  });

  it("generates sitemap URLs that match frontend incident and topic route paths", async () => {
    const { buildSeoFileContents } = await import(
      "../../scripts/generate-seo-files.mjs"
    );
    const incident = {
      id: "incident-1",
      headline: "Court sanctions brief with fake AI citations",
      headline_en: "Court sanctions brief with fake AI citations",
      date_logged: "2026-05-06",
      categories: ["Hallucinations"],
      source_family: "legal_hallucination",
    };
    const { sitemapXml, robotsTxt } = buildSeoFileContents({
      incidents: [incident],
      siteUrl: "https://airealitycheck.example/",
    });

    expect(sitemapXml).toContain(
      `<loc>${buildIncidentUrl(
        incident,
        "https://airealitycheck.example/",
      )}</loc>`,
    );
    expect(sitemapXml).toContain("<lastmod>2026-05-06</lastmod>");
    expect(sitemapXml).toContain(
      `<loc>${buildTopicUrl(
        "category",
        "Hallucinations",
        "https://airealitycheck.example/",
      )}</loc>`,
    );
    expect(sitemapXml).toContain(
      `<loc>${buildTopicUrl(
        "source",
        "legal_hallucination",
        "https://airealitycheck.example/",
      )}</loc>`,
    );
    expect(robotsTxt).toContain(
      "Sitemap: https://airealitycheck.example/sitemap.xml",
    );
  });

  it("fetches incident details and writes prerender HTML files", async () => {
    const { generateSeoFiles } = await import(
      "../../scripts/generate-seo-files.mjs"
    );
    const { mkdtemp, readFile } = await import("node:fs/promises");
    const { tmpdir } = await import("node:os");
    const { join } = await import("node:path");
    const { pathToFileURL } = await import("node:url");
    const outputDir = pathToFileURL(
      `${await mkdtemp(join(tmpdir(), "seo-prerender-"))}/`,
    );
    const incident = {
      id: "incident-1",
      headline: "Court sanctions brief with fake AI citations",
      headline_en: "Court sanctions brief with fake AI citations",
      date_logged: "2026-05-06",
      company_involved: "Court filing",
      categories: ["Hallucinations"],
      severity_score: 4,
      status: "approved",
      publication_track: "verified_accident",
      evidence_tier: "court_or_regulator",
      source_family: "legal_hallucination",
      verification_summary: "Court record confirms the issue.",
      archive_summary: "Court record confirms the issue.",
    };
    const detail = {
      ...incident,
      reality_summary: "Court record confirms fake citations.",
      reality_summary_en: "Court record confirms fake citations.",
      analysis: {},
      matched_claim: null,
      sources: [
        {
          id: "source-1",
          source_url: "https://example.com/order.pdf",
          source_type: "court",
          publisher: "Court",
          title: "Order",
        },
      ],
    };
    const fetchImpl = vi.fn(async (url) => {
      const parsedUrl = new URL(String(url));
      if (parsedUrl.pathname === "/incidents/incident-1") {
        return {
          ok: true,
          status: 200,
          async json() {
            return detail;
          },
        };
      }

      return {
        ok: true,
        status: 200,
        async json() {
          return {
            items: [incident],
            has_next_page: false,
          };
        },
      };
    });

    const result = await generateSeoFiles({
      apiBaseUrl: "https://api.example.com/",
      siteUrl: "https://aioopsnews.com",
      outputDir,
      fetchImpl,
    });

    expect(result).toEqual({
      incidentCount: 1,
      incidentHtmlCount: 1,
      topicHtmlCount: 2,
    });
    const incidentHtml = await readFile(
      new URL(
        "incidents/incident-1/court-sanctions-brief-with-fake-ai-citations/index.html",
        outputDir,
      ),
      "utf8",
    );
    const topicHtml = await readFile(
      new URL("topics/category/hallucinations/index.html", outputDir),
      "utf8",
    );

    expect(incidentHtml).toContain("<h1>Court sanctions brief with fake AI citations</h1>");
    expect(incidentHtml).toContain("https://example.com/order.pdf");
    expect(topicHtml).toContain("<h1>Hallucinations AI Incidents</h1>");
  });
});
