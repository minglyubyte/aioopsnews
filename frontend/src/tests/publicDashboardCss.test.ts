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
});
