import { buildIncidentUrl } from "../lib/publicIncidentRoutes";

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

  it("generates sitemap URLs that match frontend incident route paths", async () => {
    const { buildSeoFileContents } = await import(
      "../../scripts/generate-seo-files.mjs"
    );
    const incident = {
      id: "incident-1",
      headline: "Court sanctions brief with fake AI citations",
      headline_en: "Court sanctions brief with fake AI citations",
      date_logged: "2026-05-06",
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
    expect(robotsTxt).toContain(
      "Sitemap: https://airealitycheck.example/sitemap.xml",
    );
  });
});
