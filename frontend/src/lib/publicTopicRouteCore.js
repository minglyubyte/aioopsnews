export const TOPIC_KINDS = ["category", "source"];

export function buildTopicPath(kind, value) {
  return `/topics/${encodeURIComponent(kind)}/${topicSlugFromValue(value)}`;
}

export function buildTopicUrl(kind, value, siteUrl) {
  return `${normalizeSiteUrl(siteUrl)}${buildTopicPath(kind, value)}`;
}

export function parseTopicRoute(pathname) {
  const [, section, kind, slug] = pathname.split("/");

  if (section !== "topics" || !TOPIC_KINDS.includes(kind) || !slug) {
    return null;
  }

  return {
    kind,
    slug: decodeURIComponent(slug),
  };
}

export function topicSlugFromValue(value) {
  const slug = String(value ?? "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-");

  return slug || "topic";
}

export function normalizeSiteUrl(siteUrl) {
  return siteUrl.replace(/\/+$/, "");
}
