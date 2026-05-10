export type TopicKind = "category" | "source";

export const TOPIC_KINDS: TopicKind[];

export function buildTopicPath(kind: TopicKind, value: string): string;

export function buildTopicUrl(
  kind: TopicKind,
  value: string,
  siteUrl: string,
): string;

export function parseTopicRoute(
  pathname: string,
): { kind: TopicKind; slug: string } | null;

export function topicSlugFromValue(value: string): string;

export function normalizeSiteUrl(siteUrl: string): string;
