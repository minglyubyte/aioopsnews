import { readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const PRERENDER_ROUTE_ROOTS = ["incidents", "topics"];

export function extractAppAssetTags(indexHtml) {
  const headTags = [
    ...indexHtml.matchAll(/<link\b[^>]+rel=["']modulepreload["'][^>]*>/gi),
    ...indexHtml.matchAll(/<link\b[^>]+rel=["']stylesheet["'][^>]*>/gi),
  ].map((match) => match[0]);
  const bodyTags = [
    ...indexHtml.matchAll(
      /<script\b[^>]+type=["']module["'][^>]+src=["'][^"']+["'][^>]*><\/script>/gi,
    ),
  ].map((match) => match[0]);

  return {
    head: dedupeTags(headTags).join("\n    "),
    body: dedupeTags(bodyTags).join("\n    "),
  };
}

export function injectAppAssetsIntoPrerenderHtml(html, assetTags) {
  const withoutDevEntry = html.replace(
    /\s*<script\b[^>]+src=["']\/src\/main\.tsx["'][^>]*><\/script>\s*/i,
    "\n",
  );
  const withHeadAssets = assetTags.head
    ? withoutDevEntry.replace("</head>", `    ${assetTags.head}\n  </head>`)
    : withoutDevEntry;

  return assetTags.body
    ? withHeadAssets.replace("</body>", `    ${assetTags.body}\n  </body>`)
    : withHeadAssets;
}

export async function postprocessPrerenderHtml({ distDir = getDefaultDistDir() } = {}) {
  if (!distDir) {
    throw new Error("distDir is required outside file-based execution");
  }
  const indexHtml = await readFile(join(distDir, "index.html"), "utf8");
  const assetTags = extractAppAssetTags(indexHtml);
  let processedCount = 0;

  for (const routeRoot of PRERENDER_ROUTE_ROOTS) {
    const routeDirectory = join(distDir, routeRoot);
    for (const htmlFile of await findIndexHtmlFiles(routeDirectory)) {
      const html = await readFile(htmlFile, "utf8");
      await writeFile(
        htmlFile,
        injectAppAssetsIntoPrerenderHtml(html, assetTags),
        "utf8",
      );
      processedCount += 1;
    }
  }

  return { processedCount };
}

async function findIndexHtmlFiles(directory) {
  let entries;
  try {
    entries = await readdir(directory, { withFileTypes: true });
  } catch (error) {
    if (error?.code === "ENOENT") {
      return [];
    }
    throw error;
  }

  const htmlFiles = [];
  for (const entry of entries) {
    const entryPath = join(directory, entry.name);
    if (entry.isDirectory()) {
      htmlFiles.push(...(await findIndexHtmlFiles(entryPath)));
    } else if (entry.name === "index.html") {
      htmlFiles.push(entryPath);
    }
  }
  return htmlFiles;
}

function dedupeTags(tags) {
  return [...new Set(tags)];
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { processedCount } = await postprocessPrerenderHtml();
  console.log(`Postprocessed ${processedCount} prerender HTML files.`);
}

function getDefaultDistDir() {
  try {
    const scriptUrl = new URL(import.meta.url);
    if (scriptUrl.protocol !== "file:") {
      return null;
    }
    return fileURLToPath(new URL("../dist", scriptUrl));
  } catch {
    return null;
  }
}
