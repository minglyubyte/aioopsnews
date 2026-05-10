describe("postprocess prerender HTML helpers", () => {
  it("injects production app assets and removes the dev entry", async () => {
    const { extractAppAssetTags, injectAppAssetsIntoPrerenderHtml } =
      await import("../../scripts/postprocess-prerender-html.mjs");

    const indexHtml = `
      <!doctype html>
      <html>
        <head>
          <link rel="stylesheet" crossorigin href="/assets/main-test.css">
        </head>
        <body>
          <div id="root"></div>
          <script type="module" crossorigin src="/assets/main-test.js"></script>
        </body>
      </html>
    `;
    const prerenderHtml = `
      <!doctype html>
      <html>
        <head><title>Incident</title></head>
        <body>
          <div id="root"></div>
          <script type="module" src="/src/main.tsx"></script>
        </body>
      </html>
    `;

    const assetTags = extractAppAssetTags(indexHtml);
    const processedHtml = injectAppAssetsIntoPrerenderHtml(
      prerenderHtml,
      assetTags,
    );

    expect(processedHtml).toContain("/assets/main-test.css");
    expect(processedHtml).toContain("/assets/main-test.js");
    expect(processedHtml).not.toContain("/src/main.tsx");
  });
});
