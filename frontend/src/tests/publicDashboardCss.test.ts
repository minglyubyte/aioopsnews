import { readFileSync } from "node:fs";

const css = readFileSync("src/pages/public-dashboard.css", "utf8");

describe("public dashboard CSS", () => {
  it("keeps static public panels visible when they do not opt into in-view animation", () => {
    expect(css).toContain(".public-panel:not([data-inview])");
    expect(css).toMatch(
      /\.public-panel:not\(\[data-inview\]\)[\s\S]*?opacity:\s*1;/,
    );
    expect(css).toMatch(
      /\.public-panel:not\(\[data-inview\]\)[\s\S]*?transform:\s*translateY\(0\);/,
    );
  });

  it("constrains the archive list to a dedicated scroll area", () => {
    expect(css).toContain(".public-archive-scroll");
    expect(css).toMatch(
      /\.public-archive-scroll[\s\S]*?max-height:\s*min\(72rem,\s*82vh\);/,
    );
    expect(css).toMatch(
      /\.public-archive-scroll[\s\S]*?overflow-y:\s*auto;/,
    );
    expect(css).toMatch(
      /\.public-archive-scroll[\s\S]*?scrollbar-gutter:\s*stable;/,
    );
    expect(css).toMatch(
      /@media \(max-width:\s*759px\)[\s\S]*?\.public-archive-scroll[\s\S]*?max-height:\s*68vh;/,
    );
  });

  it("clamps archive card text and detail headings", () => {
    expect(css).toMatch(
      /\.public-archive-card h3[\s\S]*?-webkit-line-clamp:\s*2;/,
    );
    expect(css).toMatch(
      /\.public-archive-summary[\s\S]*?-webkit-line-clamp:\s*3;/,
    );
    expect(css).toMatch(
      /\.public-verification-summary[\s\S]*?-webkit-line-clamp:\s*2;/,
    );
    expect(css).toMatch(/\.case-hero h1[\s\S]*?-webkit-line-clamp:\s*3;/);
  });
});
