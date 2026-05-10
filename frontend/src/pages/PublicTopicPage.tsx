import { useEffect, useState, type CSSProperties } from "react";

import { fetchIncidentFeed } from "../lib/api";
import { PUBLIC_COPY, type ReaderLocale, type ReaderTheme } from "../lib/locale";
import { buildIncidentPath, buildIncidentUrl } from "../lib/publicIncidentRoutes";
import {
  getTopicDefinition,
  topicDefinitions,
  topicDisplayLabel,
} from "../lib/publicTopicMetadata";
import {
  buildTopicPath,
  buildTopicUrl,
  type TopicKind,
} from "../lib/publicTopicRoutes";
import {
  READER_LOCALE_STORAGE_KEY,
  READER_THEME_STORAGE_KEY,
  readStoredReaderLocale,
  readStoredReaderTheme,
} from "../lib/publicReaderPreferences";
import type {
  IncidentArchiveItem,
  IncidentFeedResponse,
  IncidentSliceSummary,
} from "../types/incident";
import PublicSiteFooter from "./PublicSiteFooter";
import "./public-dashboard.css";

const TOPIC_PAGE_SIZE = 20;
const DETAIL_PAGE_BRAND = "AI Oops News";

type PublicTopicPageProps = {
  kind: TopicKind;
  slug: string;
};

const EMPTY_SLICE_SUMMARY: IncidentSliceSummary = {
  total_matches: 0,
  newest_logged: null,
  oldest_logged: null,
  highest_severity: null,
  top_categories: [],
  top_companies: [],
};

export default function PublicTopicPage({ kind, slug }: PublicTopicPageProps) {
  const [readerLocale, setReaderLocale] = useState<ReaderLocale>(() =>
    readStoredReaderLocale(),
  );
  const [readerTheme, setReaderTheme] = useState<ReaderTheme>(() =>
    readStoredReaderTheme(),
  );
  const [feed, setFeed] = useState<IncidentFeedResponse>(() =>
    buildEmptyIncidentFeed(),
  );
  const [isLoading, setIsLoading] = useState(true);
  const [feedError, setFeedError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const topic = getTopicDefinition(kind, slug);
  const copy = PUBLIC_COPY[readerLocale];

  useEffect(() => {
    window.localStorage.setItem(READER_LOCALE_STORAGE_KEY, readerLocale);
  }, [readerLocale]);

  useEffect(() => {
    window.localStorage.setItem(READER_THEME_STORAGE_KEY, readerTheme);
  }, [readerTheme]);

  useEffect(() => {
    setPage(1);
  }, [kind, slug]);

  useEffect(() => {
    if (!topic) {
      setIsLoading(false);
      setFeed(buildEmptyIncidentFeed());
      setFeedError(null);
      setTopicMetadata({
        canonicalUrl: window.location.href,
        description: "Topic not found.",
        incidents: [],
        isIndexable: false,
        title: "Topic not found",
      });
      return;
    }

    const resolvedTopic = topic;
    let isCancelled = false;

    async function loadTopicFeed() {
      setIsLoading(true);
      setFeedError(null);

      try {
        const response = normalizeIncidentFeed(
          await fetchIncidentFeed({
            ...(kind === "category"
              ? { category: resolvedTopic.value }
              : { sourceFamily: resolvedTopic.value }),
            page,
            pageSize: TOPIC_PAGE_SIZE,
          }),
        );

        if (!isCancelled) {
          setFeed(response);
        }
      } catch {
        if (!isCancelled) {
          setFeed(buildEmptyIncidentFeed());
          setFeedError(copy.feedError);
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadTopicFeed();

    return () => {
      isCancelled = true;
    };
  }, [copy.feedError, kind, page, topic]);

  useEffect(() => {
    if (!topic) {
      return;
    }

    const title = topic.title[readerLocale];
    const description = topic.description[readerLocale];
    const canonicalUrl = buildTopicUrl(topicKindForUrl(kind), topic.value, getSiteUrl());
    const isIndexable = !isLoading && !feedError && feed.total_count > 0;

    setTopicMetadata({
      canonicalUrl,
      description,
      incidents: feed.items,
      isIndexable,
      title,
    });
  }, [feed.items, feed.total_count, feedError, isLoading, kind, readerLocale, topic]);

  if (!topic) {
    return (
      <main className="public-dashboard public-case-page" data-theme={readerTheme}>
        <div className="case-shell">
          <TopicHeader
            copy={copy}
            readerLocale={readerLocale}
            readerTheme={readerTheme}
            setReaderLocale={setReaderLocale}
            setReaderTheme={setReaderTheme}
          />
          <section className="public-panel public-topic-hero">
            <p className="public-kicker">Topic</p>
            <h1>Topic not found</h1>
            <p className="body-copy">
              This topic is not available in the public incident archive.
            </p>
            <a className="secondary-action" href="/">
              {copy.detailBackToFeed}
            </a>
          </section>
          <PublicSiteFooter copy={copy} />
        </div>
      </main>
    );
  }

  const title = topic.title[readerLocale];
  const description = topic.description[readerLocale];
  const paginationRange = buildPaginationRange(
    feed.page,
    TOPIC_PAGE_SIZE,
    feed.items.length,
    feed.total_count,
  );

  return (
    <main className="public-dashboard public-case-page" data-theme={readerTheme}>
      <div className="case-shell">
        <TopicHeader
          copy={copy}
          readerLocale={readerLocale}
          readerTheme={readerTheme}
          setReaderLocale={setReaderLocale}
          setReaderTheme={setReaderTheme}
        />

        <section className="public-panel public-topic-hero">
          <p className="public-kicker">Topic archive</p>
          <h1>{title}</h1>
          <p className="case-dek">{description}</p>
          <div className="public-topic-stats">
            <TopicStat label="Incidents" value={`${feed.total_count} incidents`} />
            <TopicStat
              label="Latest logged"
              value={formatTopicDate(feed.slice_summary.newest_logged, readerLocale)}
            />
            <TopicStat
              label="Highest severity"
              value={
                feed.slice_summary.highest_severity
                  ? `Severity ${feed.slice_summary.highest_severity}`
                  : "Awaiting data"
              }
            />
            <TopicStat
              label="Top companies"
              value={
                feed.slice_summary.top_companies
                  .slice(0, 3)
                  .map((company) =>
                    readerLocale === "zh"
                      ? (company.company_zh ?? company.company)
                      : company.company,
                  )
                  .join(", ") || "Awaiting data"
              }
            />
          </div>
        </section>

        <section className="public-panel public-feed-panel">
          <div className="section-header">
            <p className="public-kicker">Cases</p>
            <h2>{copy.archiveTitle}</h2>
          </div>
          {isLoading ? (
            <p className="body-copy" aria-busy="true">
              {copy.archiveLoading}
            </p>
          ) : null}
          {feedError ? <p className="body-copy">{feedError}</p> : null}
          {!isLoading && !feedError && feed.items.length === 0 ? (
            <p className="body-copy">{copy.noIncidentsForSlice}</p>
          ) : null}
          {!isLoading && !feedError && feed.items.length > 0 ? (
            <>
              <div className="public-archive-list" data-inview="true">
                {feed.items.map((incident, cardIndex) => (
                  <TopicIncidentCard
                    incident={incident}
                    key={incident.id}
                    readerLocale={readerLocale}
                    styleIndex={cardIndex}
                  />
                ))}
              </div>
              <div className="public-archive-pagination">
                <span className="body-copy public-pagination-summary">
                  {copy.paginationSummary(
                    paginationRange.start,
                    paginationRange.end,
                    feed.total_count,
                  )}
                </span>
                <div className="public-pagination-controls">
                  <button
                    className="secondary-action"
                    disabled={!feed.has_previous_page}
                    onClick={() => setPage((currentPage) => Math.max(currentPage - 1, 1))}
                    type="button"
                  >
                    {copy.paginationPrevious}
                  </button>
                  <span className="public-pagination-status">
                    {copy.paginationStatus(feed.page, feed.total_pages)}
                  </span>
                  <button
                    className="secondary-action"
                    disabled={!feed.has_next_page}
                    onClick={() => setPage((currentPage) => currentPage + 1)}
                    type="button"
                  >
                    {copy.paginationNext}
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </section>

        <section className="case-continue-panel" data-inview="true">
          <p className="public-kicker">Explore</p>
          <h2>{readerLocale === "zh" ? "继续浏览专题" : "Explore topics"}</h2>
          <div className="public-related-actions">
            <a className="secondary-action" href="/">
              {copy.detailBackToFeed}
            </a>
            {topicDefinitions(kind)
              .filter((candidate) => candidate.value !== topic.value)
              .slice(0, 4)
              .map((candidate) => (
                <a
                  className="tag"
                  href={buildTopicPath(kind, candidate.value)}
                  key={candidate.value}
                >
                  {topicDisplayLabel(kind, candidate.value, readerLocale)}
                </a>
              ))}
          </div>
        </section>

        <PublicSiteFooter copy={copy} />
      </div>
    </main>
  );
}

function TopicHeader({
  copy,
  readerLocale,
  readerTheme,
  setReaderLocale,
  setReaderTheme,
}: {
  copy: (typeof PUBLIC_COPY)[ReaderLocale];
  readerLocale: ReaderLocale;
  readerTheme: ReaderTheme;
  setReaderLocale: (locale: ReaderLocale) => void;
  setReaderTheme: (theme: ReaderTheme) => void;
}) {
  return (
    <header className="case-site-header">
      <a className="case-brand-link" href="/">
        {copy.brand}
      </a>
      <div className="case-header-actions">
        <div
          aria-label={copy.languageSwitchLabel}
          className="public-toggle-group"
          role="group"
        >
          <button
            aria-pressed={readerLocale === "en"}
            className={`public-toggle-button${readerLocale === "en" ? " is-active" : ""}`}
            onClick={() => setReaderLocale("en")}
            type="button"
          >
            English
          </button>
          <button
            aria-pressed={readerLocale === "zh"}
            className={`public-toggle-button${readerLocale === "zh" ? " is-active" : ""}`}
            onClick={() => setReaderLocale("zh")}
            type="button"
          >
            中文
          </button>
        </div>
        <div
          aria-label={copy.themeSwitchLabel}
          className="public-toggle-group"
          role="group"
        >
          <button
            aria-pressed={readerTheme === "light"}
            className={`public-toggle-button${readerTheme === "light" ? " is-active" : ""}`}
            onClick={() => setReaderTheme("light")}
            type="button"
          >
            {copy.lightTheme}
          </button>
          <button
            aria-pressed={readerTheme === "dark"}
            className={`public-toggle-button${readerTheme === "dark" ? " is-active" : ""}`}
            onClick={() => setReaderTheme("dark")}
            type="button"
          >
            {copy.darkTheme}
          </button>
        </div>
        <a className="case-back-link" href="/">
          {copy.detailBackToFeed}
        </a>
      </div>
    </header>
  );
}

function TopicStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="case-meta-item">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function TopicIncidentCard({
  incident,
  readerLocale,
  styleIndex,
}: {
  incident: IncidentArchiveItem;
  readerLocale: ReaderLocale;
  styleIndex: number;
}) {
  const headline =
    readerLocale === "zh"
      ? (incident.headline_zh ?? incident.headline_en ?? incident.headline)
      : (incident.headline_en ?? incident.headline);
  const summary =
    readerLocale === "zh"
      ? (incident.archive_summary_zh ??
        incident.archive_summary_en ??
        incident.archive_summary)
      : (incident.archive_summary_en ?? incident.archive_summary);

  return (
    <article
      className="public-archive-card"
      style={{ "--card-index": styleIndex } as CSSProperties}
    >
      <div className="incident-meta">
        <span>{incident.company_involved}</span>
        <span>{formatTopicDate(incident.date_logged, readerLocale)}</span>
      </div>
      <h3>{headline}</h3>
      <p className="body-copy">{summary}</p>
      <a
        className="secondary-action"
        href={buildIncidentPath(incident)}
      >{`Open full context for ${headline}`}</a>
    </article>
  );
}

function buildEmptyIncidentFeed(): IncidentFeedResponse {
  return {
    items: [],
    page: 1,
    page_size: TOPIC_PAGE_SIZE,
    total_count: 0,
    total_pages: 1,
    has_next_page: false,
    has_previous_page: false,
    slice_summary: EMPTY_SLICE_SUMMARY,
  };
}

function normalizeIncidentFeed(
  response: Partial<IncidentFeedResponse> & { items?: IncidentArchiveItem[] },
): IncidentFeedResponse {
  const items = response.items ?? [];

  return {
    items,
    page: response.page ?? 1,
    page_size: response.page_size ?? TOPIC_PAGE_SIZE,
    total_count: response.total_count ?? items.length,
    total_pages: response.total_pages ?? 1,
    has_next_page: response.has_next_page ?? false,
    has_previous_page: response.has_previous_page ?? false,
    slice_summary: response.slice_summary ?? EMPTY_SLICE_SUMMARY,
  };
}

function buildPaginationRange(
  page: number,
  pageSize: number,
  visibleCount: number,
  totalCount: number,
) {
  if (visibleCount === 0 || totalCount === 0) {
    return { start: 0, end: 0 };
  }

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(start + visibleCount - 1, totalCount);

  return { start, end };
}

function formatTopicDate(dateValue: string | null | undefined, locale: ReaderLocale) {
  if (!dateValue) {
    return locale === "zh" ? "等待数据" : "Awaiting data";
  }

  return new Intl.DateTimeFormat(PUBLIC_COPY[locale].dateLocale, {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(`${dateValue}T00:00:00Z`));
}

function getSiteUrl() {
  const configuredSiteUrl = import.meta.env.VITE_PUBLIC_SITE_URL;

  if (configuredSiteUrl?.trim()) {
    return configuredSiteUrl;
  }

  return window.location.origin;
}

function topicKindForUrl(kind: TopicKind) {
  return kind;
}

function setTopicMetadata({
  canonicalUrl,
  description,
  incidents,
  isIndexable,
  title,
}: {
  canonicalUrl: string;
  description: string;
  incidents: IncidentArchiveItem[];
  isIndexable: boolean;
  title: string;
}) {
  document.title = `${title} | ${DETAIL_PAGE_BRAND}`;
  setMetaDescription(description);
  setCanonicalLink(canonicalUrl);
  setRobotsMeta(isIndexable ? "index,follow" : "noindex,follow");
  setStructuredData({
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: title,
    description,
    mainEntityOfPage: canonicalUrl,
    mainEntity: incidents.map((incident) => ({
      "@type": "NewsArticle",
      headline: incident.headline_en ?? incident.headline,
      url: buildIncidentUrl(incident, getSiteUrl()),
    })),
  });
}

function setMetaDescription(content: string) {
  let metaDescription = document.querySelector<HTMLMetaElement>(
    'meta[name="description"]',
  );

  if (!metaDescription) {
    metaDescription = document.createElement("meta");
    metaDescription.name = "description";
    document.head.append(metaDescription);
  }

  metaDescription.content = content;
}

function setCanonicalLink(href: string) {
  let canonicalLink = document.querySelector<HTMLLinkElement>(
    'link[rel="canonical"]',
  );

  if (!canonicalLink) {
    canonicalLink = document.createElement("link");
    canonicalLink.rel = "canonical";
    document.head.append(canonicalLink);
  }

  canonicalLink.href = href;
}

function setRobotsMeta(content: string) {
  let robotsMeta = document.querySelector<HTMLMetaElement>(
    'meta[name="robots"]',
  );

  if (!robotsMeta) {
    robotsMeta = document.createElement("meta");
    robotsMeta.name = "robots";
    document.head.append(robotsMeta);
  }

  robotsMeta.content = content;
}

function setStructuredData(data: Record<string, unknown>) {
  let structuredData = document.querySelector<HTMLScriptElement>(
    'script[type="application/ld+json"]',
  );

  if (!structuredData) {
    structuredData = document.createElement("script");
    structuredData.type = "application/ld+json";
    document.head.append(structuredData);
  }

  structuredData.textContent = JSON.stringify(data);
}
