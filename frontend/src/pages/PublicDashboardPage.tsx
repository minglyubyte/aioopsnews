import { useEffect, useState } from "react";
import { useCountUp } from "../lib/useCountUp";
import { useInView } from "../lib/useInView";

import { fetchIncidentFeed, fetchIncidentFilters } from "../lib/api";
import { buildIncidentPath } from "../lib/publicIncidentRoutes";
import { localizePublicCategory } from "../lib/publicDashboardLocalization";
import {
  getTopicDefinition,
  topicDisplayLabel,
} from "../lib/publicTopicMetadata";
import { buildTopicPath, topicSlugFromValue } from "../lib/publicTopicRoutes";
import {
  READER_LOCALE_STORAGE_KEY,
  READER_THEME_STORAGE_KEY,
  readStoredReaderLocale,
  readStoredReaderTheme,
} from "../lib/publicReaderPreferences";
import type {
  IncidentArchiveItem,
  IncidentFeedFilters,
  IncidentFeedResponse,
  IncidentFilters,
  IncidentSliceSummary,
  PublicIncidentBase,
} from "../types/incident";
import "./public-dashboard.css";

const SIGNAL_COLORS = [
  "#8a3b26",
  "#274b63",
  "#8a6a2a",
  "#5e7041",
  "#6f4b7e",
  "#405061",
];
const ARCHIVE_PAGE_SIZE = 20;
const EMPTY_SLICE_SUMMARY: IncidentSliceSummary = {
  total_matches: 0,
  newest_logged: null,
  oldest_logged: null,
  highest_severity: null,
  top_categories: [],
  top_companies: [],
};

import {
  type CategorySignal,
  type HeroMetric,
  type HighlightInsight,
  type MonthlySignal,
  PUBLIC_COPY,
  type ReaderLocale,
  type ReaderTheme,
} from "../lib/locale";
import PublicSiteFooter from "./PublicSiteFooter";

export default function PublicDashboardPage() {
  const [filters, setFilters] = useState<IncidentFilters | null>(null);
  const [filtersError, setFiltersError] = useState<string | null>(null);
  const [readerFilters, setReaderFilters] = useState<IncidentFeedFilters>({
    page: 1,
    pageSize: ARCHIVE_PAGE_SIZE,
  });
  const [readerLocale, setReaderLocale] = useState<ReaderLocale>(() =>
    readStoredReaderLocale(),
  );
  const [readerTheme, setReaderTheme] = useState<ReaderTheme>(() =>
    readStoredReaderTheme(),
  );
  const [feed, setFeed] = useState<IncidentFeedResponse>(() =>
    buildEmptyIncidentFeed(),
  );
  const [isFiltersLoading, setIsFiltersLoading] = useState(true);
  const [isFeedLoading, setIsFeedLoading] = useState(true);
  const [feedError, setFeedError] = useState<string | null>(null);

  // ── InView refs for entrance animations ──────────────────────────
  const [heroRef, heroInView] = useInView<HTMLElement>();
  const [metricsRef, metricsInView] = useInView<HTMLDivElement>();
  const [signalsRef, signalsInView] = useInView<HTMLElement>();
  const [monthlyCardRef, monthlyCardInView] = useInView<HTMLElement>();
  const [categoryCardRef, categoryCardInView] = useInView<HTMLElement>();
  const [archiveListRef, archiveListInView] = useInView<HTMLDivElement>();
  const [spotlightRef, spotlightInView] = useInView<HTMLElement>();
  const [insightsRef, insightsInView] = useInView<HTMLElement>();

  const incidents = feed.items;
  const verifiedIncidents = incidents.filter(
    (incident) => incident.publication_track === "verified_accident",
  );
  const watchIncidents = incidents.filter(
    (incident) => incident.publication_track !== "verified_accident",
  );
  const sliceSummary = feed.slice_summary;
  const availableMonths = readerFilters.year
    ? (filters?.months_by_year[String(readerFilters.year)] ?? [])
    : [];
  const copy = PUBLIC_COPY[readerLocale];
  const monthlySignals = buildMonthlySignals(incidents, readerLocale);
  const categorySignals = buildCategorySignals(incidents, readerLocale);
  const heroMetrics = buildHeroMetrics(feed, categorySignals, readerLocale);
  const highlightInsights = buildHighlightInsights(sliceSummary, readerLocale);
  const maxMonthlyCount = Math.max(
    ...monthlySignals.map((signal) => signal.count),
    1,
  );
  const paginationRange = buildPaginationRange(
    feed.page,
    ARCHIVE_PAGE_SIZE,
    incidents.length,
    feed.total_count,
  );

  useEffect(() => {
    window.localStorage.setItem(READER_LOCALE_STORAGE_KEY, readerLocale);
  }, [readerLocale]);

  useEffect(() => {
    window.localStorage.setItem(READER_THEME_STORAGE_KEY, readerTheme);
  }, [readerTheme]);

  useEffect(() => {
    let isCancelled = false;

    async function loadFilters() {
      setIsFiltersLoading(true);
      setFiltersError(null);

      try {
        const nextFilters = await fetchIncidentFilters();

        if (!isCancelled) {
          setFilters(nextFilters);
        }
      } catch {
        if (!isCancelled) {
          setFilters(null);
          setFiltersError("Unable to load archive filters right now.");
        }
      } finally {
        if (!isCancelled) {
          setIsFiltersLoading(false);
        }
      }
    }

    void loadFilters();

    return () => {
      isCancelled = true;
    };
  }, []);

  useEffect(() => {
    let isCancelled = false;

    async function loadFeed() {
      setIsFeedLoading(true);
      setFeedError(null);

      try {
        const response = normalizeIncidentFeed(
          await fetchIncidentFeed(readerFilters),
        );

        if (isCancelled) {
          return;
        }

        setFeed(response);
      } catch {
        if (!isCancelled) {
          setFeed(buildEmptyIncidentFeed());
          setFeedError("Unable to load the incident feed right now.");
        }
      } finally {
        if (!isCancelled) {
          setIsFeedLoading(false);
        }
      }
    }

    void loadFeed();

    return () => {
      isCancelled = true;
    };
  }, [readerFilters]);

  function updateFilter<K extends keyof IncidentFeedFilters>(
    key: K,
    value: IncidentFeedFilters[K],
  ) {
    setReaderFilters((currentFilters) => ({
      ...currentFilters,
      [key]: value,
      page: 1,
    }));
  }

  function renderArchiveCard(incident: IncidentArchiveItem, cardIdx: number) {
    return (
      <article
        className="public-archive-card"
        key={incident.id}
        style={{ "--card-index": cardIdx } as React.CSSProperties}
      >
        <div className="incident-meta">
          <span>{localizedCompanyName(incident, readerLocale)}</span>
          <span>{severityLabel(incident.severity_score, readerLocale)}</span>
          <span>{formatDate(incident.date_logged, readerLocale)}</span>
        </div>
        <div className="public-evidence-badges">
          <span className="tag">
            {trackLabel(incident.publication_track, readerLocale)}
          </span>
          <span className="tag">
            {evidenceTierLabel(incident.evidence_tier, readerLocale)}
          </span>
          <span className="tag">
            {sourceFamilyLabel(incident.source_family, readerLocale)}
          </span>
        </div>
        <h3>{localizedHeadline(incident, readerLocale)}</h3>
        <p className="body-copy public-archive-summary">
          {buildSnippet(localizedArchiveSummary(incident, readerLocale))}
        </p>
        <p className="body-copy public-verification-summary">
          {localizedVerificationSummary(incident, readerLocale)}
        </p>
        <div className="tag-row">
          {incident.categories.map((category) => (
            <span className="tag" key={category}>
              {localizePublicCategory(category, readerLocale)}
            </span>
          ))}
        </div>
        <a
          className="secondary-action public-detail-button"
          href={buildIncidentPath(incident)}
        >
          {copy.detailActionLabel(localizedHeadline(incident, readerLocale))}
        </a>
      </article>
    );
  }

  function handleYearChange(value: string) {
    const year = value ? Number(value) : undefined;

    setReaderFilters((currentFilters) => {
      const validMonths = year
        ? (filters?.months_by_year[String(year)] ?? [])
        : [];
      const month =
        currentFilters.month && validMonths.includes(currentFilters.month)
          ? currentFilters.month
          : undefined;

      return {
        ...currentFilters,
        year,
        month,
        page: 1,
      };
    });
  }

  return (
    <main className="public-dashboard" data-theme={readerTheme}>
      <div className="public-frame">
        <section
          className="public-panel public-hero"
          data-inview={heroInView ? "true" : "false"}
          ref={heroRef}
        >
          <div className="public-hero-header">
            <div>
              <p className="eyebrow public-kicker">{copy.brand}</p>
              <h1>{copy.brand}</h1>
              <p className="body-copy public-positioning">{copy.positioning}</p>
            </div>
            <div className="public-utility-cluster">
              <div
                aria-label={copy.languageSwitchLabel}
                className="public-toggle-group"
                role="group"
              >
                <button
                  aria-pressed={readerLocale === "en"}
                  className={`public-toggle-button${readerLocale === "en" ? " is-active" : ""}`}
                  type="button"
                  onClick={() => setReaderLocale("en")}
                >
                  English
                </button>
                <button
                  aria-pressed={readerLocale === "zh"}
                  className={`public-toggle-button${readerLocale === "zh" ? " is-active" : ""}`}
                  type="button"
                  onClick={() => setReaderLocale("zh")}
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
                  type="button"
                  onClick={() => setReaderTheme("light")}
                >
                  {copy.lightTheme}
                </button>
                <button
                  aria-pressed={readerTheme === "dark"}
                  className={`public-toggle-button${readerTheme === "dark" ? " is-active" : ""}`}
                  type="button"
                  onClick={() => setReaderTheme("dark")}
                >
                  {copy.darkTheme}
                </button>
              </div>
            </div>
          </div>
          <p className="lede">{copy.lede}</p>
          <ul className="public-hero-list">
            {copy.heroExamples.map((example, idx) => (
              <li
                className="body-copy public-hero-list-item"
                key={example}
                style={{ "--hero-item-index": idx } as React.CSSProperties}
              >
                {example}
              </li>
            ))}
          </ul>
          <p className="body-copy public-hero-copy">{copy.heroCopy}</p>

          <div
            className="public-metrics"
            data-inview={metricsInView ? "true" : "false"}
            ref={metricsRef}
          >
            {heroMetrics.map((metric, idx) => (
              <MetricCard
                inView={metricsInView}
                index={idx}
                key={metric.label}
                metric={metric}
              />
            ))}
          </div>

          {isFiltersLoading ? (
            <div className="public-status" aria-busy="true">
              <div className="public-skeleton public-skeleton-block is-medium" />
              <div className="public-skeleton public-skeleton-block is-short" />
            </div>
          ) : null}
          {filtersError ? (
            <p className="public-error" role="status">
              {copy.filtersError}
            </p>
          ) : null}
        </section>

        <section
          className="public-panel public-signals"
          aria-live="polite"
          data-inview={signalsInView ? "true" : "false"}
          ref={signalsRef}
        >
          <div className="public-signals-header">
            <div>
              <p className="public-kicker">{copy.signalsKicker}</p>
              <h2>{copy.signalsTitle}</h2>
            </div>
            <p className="body-copy public-signals-note">{copy.signalsNote}</p>
          </div>

          <div className="public-signals-grid">
            <article
              className="public-signal-card"
              data-inview={monthlyCardInView ? "true" : "false"}
              ref={monthlyCardRef}
            >
              <p className="public-kicker">{copy.currentFeedSizeKicker}</p>
              <h3>{copy.currentFeedSizeTitle(incidents.length)}</h3>
              {monthlySignals.length > 0 ? (
                <ol
                  className="public-signal-list"
                  aria-label={copy.monthlySignalAria}
                >
                  {monthlySignals.map((signal, barIdx) => (
                    <li className="public-signal-row" key={signal.monthKey}>
                      <div className="public-signal-meta">
                        <span>{signal.label}</span>
                        <span>{copy.incidentCountLabel(signal.count)}</span>
                      </div>
                      <div aria-hidden="true" className="public-signal-track">
                        <div
                          className="public-signal-bar"
                          style={
                            {
                              width: `${Math.max((signal.count / maxMonthlyCount) * 100, 18)}%`,
                              "--bar-index": barIdx,
                            } as React.CSSProperties
                          }
                        />
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="body-copy">{copy.signalNoData}</p>
              )}
            </article>

            <article
              className="public-signal-card"
              data-inview={categoryCardInView ? "true" : "false"}
              ref={categoryCardRef}
            >
              <p className="public-kicker">{copy.categoryDistributionKicker}</p>
              <h3>{copy.categoryDistributionTitle}</h3>
              {categorySignals.length > 0 ? (
                <div className="public-signal-distribution">
                  <div
                    aria-hidden="true"
                    className="public-donut"
                    style={{
                      backgroundImage: buildCategoryDonut(categorySignals),
                    }}
                  >
                    <div className="public-donut-core">
                      <strong>{incidents.length}</strong>
                      <span>{copy.donutIncidentLabel(incidents.length)}</span>
                    </div>
                  </div>

                  <ul
                    className="public-signal-list public-distribution-list"
                    aria-label={copy.categoryDistributionAria}
                  >
                    {categorySignals.map((signal, index) => (
                      <li className="public-signal-row" key={signal.category}>
                        <div className="public-distribution-item">
                          <span
                            aria-hidden="true"
                            className="public-distribution-swatch"
                            style={{
                              backgroundColor:
                                SIGNAL_COLORS[index % SIGNAL_COLORS.length],
                            }}
                          />
                          <span>{signal.category}</span>
                          <span>{signal.count}</span>
                          <span>{copy.categoryShareLabel(signal.share)}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="body-copy">{copy.categoryNoData}</p>
              )}
            </article>
          </div>

          <section
            aria-label={copy.archiveControlsRegion}
            className="public-archive-toolbar"
          >
            <div className="public-archive-toolbar-header">
              <p className="public-kicker">{copy.archiveControlsKicker}</p>
              <h3>{copy.archiveControlsTitle}</h3>
            </div>
            <p className="body-copy public-archive-toolbar-copy">
              {copy.archiveControlsBody}
            </p>
            <div className="public-archive-toolbar-grid">
              <label className="field public-toolbar-field">
                <span>{copy.filterByCategory}</span>
                <select
                  aria-label={copy.filterByCategory}
                  disabled={isFiltersLoading}
                  value={readerFilters.category ?? ""}
                  onChange={(event) =>
                    updateFilter("category", event.target.value || undefined)
                  }
                >
                  <option value="">{copy.allCategories}</option>
                  {(filters?.categories ?? []).map((category) => (
                    <option key={category} value={category}>
                      {localizePublicCategory(category, readerLocale)}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field public-toolbar-field">
                <span>{copy.filterByCompany}</span>
                <select
                  aria-label={copy.filterByCompany}
                  disabled={isFiltersLoading}
                  value={readerFilters.company ?? ""}
                  onChange={(event) =>
                    updateFilter("company", event.target.value || undefined)
                  }
                >
                  <option value="">{copy.allCompanies}</option>
                  {(filters?.companies ?? []).map((company) => (
                    <option key={company} value={company}>
                      {localizedCompanyFilterLabel(
                        company,
                        filters?.company_labels_zh,
                        readerLocale,
                      )}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field public-toolbar-field">
                <span>{copy.filterByTrack}</span>
                <select
                  aria-label={copy.filterByTrack}
                  disabled={isFiltersLoading}
                  value={readerFilters.publicationTrack ?? ""}
                  onChange={(event) =>
                    updateFilter(
                      "publicationTrack",
                      event.target.value || undefined,
                    )
                  }
                >
                  <option value="">{copy.allTracks}</option>
                  {(filters?.publication_tracks ?? []).map((track) => (
                    <option key={track} value={track}>
                      {trackLabel(track, readerLocale)}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field public-toolbar-field">
                <span>{copy.filterBySourceFamily}</span>
                <select
                  aria-label={copy.filterBySourceFamily}
                  disabled={isFiltersLoading}
                  value={readerFilters.sourceFamily ?? ""}
                  onChange={(event) =>
                    updateFilter(
                      "sourceFamily",
                      event.target.value || undefined,
                    )
                  }
                >
                  <option value="">{copy.allSourceFamilies}</option>
                  {(filters?.source_families ?? []).map((sourceFamily) => (
                    <option key={sourceFamily} value={sourceFamily}>
                      {sourceFamilyLabel(sourceFamily, readerLocale)}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field public-toolbar-field">
                <span>{copy.filterByYear}</span>
                <select
                  aria-label={copy.filterByYear}
                  disabled={isFiltersLoading}
                  value={readerFilters.year?.toString() ?? ""}
                  onChange={(event) => handleYearChange(event.target.value)}
                >
                  <option value="">{copy.allYears}</option>
                  {(filters?.years ?? []).map((year) => (
                    <option key={year} value={year}>
                      {year}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field public-toolbar-field">
                <span>{copy.filterByMonth}</span>
                <select
                  aria-label={copy.filterByMonth}
                  disabled={isFiltersLoading || !readerFilters.year}
                  value={readerFilters.month?.toString() ?? ""}
                  onChange={(event) =>
                    updateFilter(
                      "month",
                      event.target.value
                        ? Number(event.target.value)
                        : undefined,
                    )
                  }
                >
                  <option value="">{copy.allMonths}</option>
                  {availableMonths.map((month) => (
                    <option key={month} value={month}>
                      {monthLabelForNumber(month, readerLocale)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="public-topic-links" aria-label="Topic pages">
              {(filters?.categories ?? []).map((category) => (
                <a
                  className="tag"
                  href={buildTopicPath("category", category)}
                  key={`category-${category}`}
                >
                  {localizePublicCategory(category, readerLocale)}
                </a>
              ))}
              {(filters?.source_families ?? [])
                .filter((sourceFamily) =>
                  getTopicDefinition("source", topicSlugFromValue(sourceFamily)),
                )
                .map((sourceFamily) => (
                  <a
                    className="tag"
                    href={buildTopicPath("source", sourceFamily)}
                    key={`source-${sourceFamily}`}
                  >
                    {topicDisplayLabel("source", sourceFamily, readerLocale)}
                  </a>
                ))}
            </div>
          </section>
        </section>

        <section className="public-content-grid">
          <section className="public-feed-column">
            <section
              aria-label={copy.archiveRegion}
              className="public-panel public-feed-panel"
              role="region"
              data-inview={archiveListInView ? "true" : "false"}
              ref={archiveListRef}
            >
              <div className="section-header">
                <p className="public-kicker">{copy.archiveKicker}</p>
                <h2>{copy.archiveTitle}</h2>
              </div>
              {isFeedLoading ? (
                <div aria-busy="true" aria-label={copy.archiveLoading}>
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div
                      className="public-skeleton-card"
                      key={i}
                      style={{ marginBottom: "1rem" }}
                    >
                      <div className="public-skeleton public-skeleton-block is-short" />
                      <div className="public-skeleton public-skeleton-block is-tall" />
                      <div className="public-skeleton public-skeleton-block is-medium" />
                    </div>
                  ))}
                </div>
              ) : null}
              {!isFeedLoading && !feedError ? (
                <div
                  className="public-archive-list"
                  data-inview={archiveListInView ? "true" : "false"}
                  ref={archiveListRef}
                >
                  <section className="public-track-section">
                    <div className="public-track-header">
                      <h3>{copy.verifiedSectionTitle}</h3>
                      <p className="body-copy">{copy.verifiedSectionBody}</p>
                    </div>
                    {verifiedIncidents.length > 0 ? (
                      verifiedIncidents.map((incident, cardIdx) =>
                        renderArchiveCard(incident, cardIdx),
                      )
                    ) : (
                      <p className="public-track-empty">
                        {copy.verifiedSectionEmpty}
                      </p>
                    )}
                  </section>
                  <section className="public-track-section">
                    <div className="public-track-header">
                      <h3>{copy.watchSectionTitle}</h3>
                      <p className="body-copy">{copy.watchSectionBody}</p>
                    </div>
                    {watchIncidents.length > 0 ? (
                      watchIncidents.map((incident, cardIdx) =>
                        renderArchiveCard(
                          incident,
                          verifiedIncidents.length + cardIdx,
                        ),
                      )
                    ) : (
                      <p className="public-track-empty">
                        {copy.watchSectionEmpty}
                      </p>
                    )}
                  </section>
                </div>
              ) : null}
              {!isFeedLoading && !feedError && incidents.length === 0 ? (
                <p className="body-copy">{copy.noIncidentsForSlice}</p>
              ) : null}
              {!isFeedLoading && !feedError && incidents.length > 0 ? (
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
                      type="button"
                      onClick={() =>
                        setReaderFilters((currentFilters) => ({
                          ...currentFilters,
                          page: Math.max((currentFilters.page ?? 1) - 1, 1),
                          pageSize: ARCHIVE_PAGE_SIZE,
                        }))
                      }
                    >
                      {copy.paginationPrevious}
                    </button>
                    <span className="public-pagination-status">
                      {copy.paginationStatus(feed.page, feed.total_pages)}
                    </span>
                    <button
                      className="secondary-action"
                      disabled={!feed.has_next_page}
                      type="button"
                      onClick={() =>
                        setReaderFilters((currentFilters) => ({
                          ...currentFilters,
                          page: (currentFilters.page ?? 1) + 1,
                          pageSize: ARCHIVE_PAGE_SIZE,
                        }))
                      }
                    >
                      {copy.paginationNext}
                    </button>
                  </div>
                </div>
              ) : null}
            </section>
          </section>

          <aside className="public-sidebar">
            <section
              className="public-panel public-spotlight"
              aria-live="polite"
              data-inview={spotlightInView ? "true" : "false"}
              ref={spotlightRef}
            >
              <div className="section-header">
                <p className="public-kicker">{copy.spotlightKicker}</p>
                <h2>{copy.spotlightTitle}</h2>
              </div>
              {isFeedLoading ? (
                <div aria-busy="true">
                  <div className="public-skeleton public-skeleton-block is-medium" />
                  <div className="public-skeleton public-skeleton-block" />
                  <div className="public-skeleton public-skeleton-block is-short" />
                </div>
              ) : null}
              {feedError ? <p>{copy.feedError}</p> : null}
              {!isFeedLoading &&
              !feedError &&
              sliceSummary.total_matches > 0 ? (
                <article
                  className="public-panel-compact public-spotlight-insights"
                  data-inview={insightsInView ? "true" : "false"}
                  ref={insightsRef}
                >
                  <p className="public-claim-kicker">
                    {copy.highlightInsightsTitle}
                  </p>
                  <p className="body-copy public-spotlight-copy">
                    {copy.highlightInsightsBody}
                  </p>
                  <div className="public-highlight-list">
                    {highlightInsights.map((insight, insightIdx) => (
                      <section
                        className="public-highlight-item"
                        key={insight.label}
                        style={
                          {
                            "--insight-index": insightIdx,
                          } as React.CSSProperties
                        }
                      >
                        <span className="public-highlight-label">
                          {insight.label}
                        </span>
                        <strong className="public-highlight-value">
                          {insight.value}
                        </strong>
                        <span className="body-copy public-highlight-note">
                          {insight.note}
                        </span>
                      </section>
                    ))}
                  </div>
                </article>
              ) : null}
              {!isFeedLoading &&
              !feedError &&
              sliceSummary.total_matches === 0 ? (
                <p className="body-copy">{copy.highlightsEmpty}</p>
              ) : null}
            </section>
          </aside>
        </section>

        <PublicSiteFooter copy={copy} />
      </div>
    </main>
  );
}

// ── MetricCard: animated counter sub-component ─────────────────────

function MetricCard({
  metric,
  inView,
  index,
}: {
  metric: { label: string; value: string; note: string };
  inView: boolean;
  index: number;
}) {
  const animatedValue = useCountUp(metric.value, inView);

  return (
    <article
      className="public-metric"
      style={{ "--metric-index": index } as React.CSSProperties}
    >
      <span className="public-metric-label">{metric.label}</span>
      <strong className="public-metric-value">{animatedValue}</strong>
      <span className="public-metric-note">{metric.note}</span>
    </article>
  );
}

function localizedHeadline(incident: PublicIncidentBase, locale: ReaderLocale) {
  if (locale === "zh") {
    return incident.headline_zh ?? incident.headline_en ?? incident.headline;
  }

  return incident.headline_en ?? incident.headline;
}

function localizedCompanyName(
  incident: PublicIncidentBase,
  locale: ReaderLocale,
) {
  if (locale === "zh") {
    return incident.company_involved_zh ?? incident.company_involved;
  }

  return incident.company_involved;
}

function localizedCompanyFilterLabel(
  company: string,
  companyLabelsZh: Record<string, string | null> | undefined,
  locale: ReaderLocale,
) {
  if (locale === "zh") {
    return companyLabelsZh?.[company] ?? company;
  }

  return company;
}

function localizedArchiveSummary(
  incident: PublicIncidentBase & {
    archive_summary?: string | null;
    archive_summary_en?: string | null;
    archive_summary_zh?: string | null;
    reality_summary?: string | null;
    reality_summary_en?: string | null;
    reality_summary_zh?: string | null;
  },
  locale: ReaderLocale,
) {
  const archiveSummary =
    incident.archive_summary ??
    incident.reality_summary ??
    incident.headline_en ??
    incident.headline;
  const archiveSummaryEn =
    incident.archive_summary_en ??
    incident.reality_summary_en ??
    archiveSummary;
  const archiveSummaryZh =
    incident.archive_summary_zh ?? incident.reality_summary_zh;

  if (locale === "zh") {
    return archiveSummaryZh ?? archiveSummaryEn ?? archiveSummary;
  }

  return archiveSummaryEn ?? archiveSummary;
}

const TRACK_LABELS_ZH: Record<string, string> = {
  accident_watch: "事故观察",
  verified_accident: "已验证事故",
};

const EVIDENCE_TIER_LABELS_ZH: Record<string, string> = {
  court_or_regulator: "法院或监管记录",
  official_documented: "官方已记录",
  reported_unconfirmed: "报道未确认",
};

const SOURCE_FAMILY_LABELS_ZH: Record<string, string> = {
  autonomous_vehicle: "自主车辆",
  coding_failure: "代码生成故障",
  customer_support: "客户支持",
  legal_hallucination: "法律幻觉",
  model_governance: "模型治理",
};

function trackLabel(track: string, locale: ReaderLocale) {
  if (locale === "zh") {
    return TRACK_LABELS_ZH[track] ?? humanizeSnakeCase(track);
  }

  if (track === "verified_accident") {
    return "Verified accident";
  }
  if (track === "accident_watch") {
    return "Accident watch";
  }
  return humanizeSnakeCase(track);
}

function evidenceTierLabel(evidenceTier: string, locale: ReaderLocale) {
  if (locale === "zh") {
    return (
      EVIDENCE_TIER_LABELS_ZH[evidenceTier] ?? humanizeSnakeCase(evidenceTier)
    );
  }

  return humanizeSnakeCase(evidenceTier);
}

function sourceFamilyLabel(sourceFamily: string, locale: ReaderLocale) {
  if (locale === "zh") {
    return (
      SOURCE_FAMILY_LABELS_ZH[sourceFamily] ?? humanizeSnakeCase(sourceFamily)
    );
  }

  return humanizeSnakeCase(sourceFamily);
}

function localizedVerificationSummary(
  incident: PublicIncidentBase,
  locale: ReaderLocale,
) {
  if (locale !== "zh") {
    return incident.verification_summary;
  }

  if (incident.publication_track === "verified_accident") {
    return (
      `固定高可信来源记录了这起${sourceFamilyLabel(incident.source_family, locale)}` +
      "事故；编辑审核仍会检查 AI 相关性、重复风险和严重程度。"
    );
  }

  return (
    "这是一条自动发现的观察信号；需要官方、法院、监管、公司或固定高可信来源" +
    "确认后，才会进入已验证事故档案。"
  );
}

function humanizeSnakeCase(value: string) {
  const spaced = value.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function buildSnippet(summary: string | null | undefined) {
  const safeSummary = summary ?? "";

  if (safeSummary.length <= 140) {
    return safeSummary;
  }

  return `${safeSummary.slice(0, 137).trimEnd()}...`;
}

function buildMonthlySignals(
  incidents: PublicIncidentBase[],
  locale: ReaderLocale,
): MonthlySignal[] {
  const counts = new Map<string, number>();

  for (const incident of incidents) {
    const date = new Date(`${incident.date_logged}T00:00:00Z`);
    const monthKey = `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
    counts.set(monthKey, (counts.get(monthKey) ?? 0) + 1);
  }

  return [...counts.entries()]
    .sort(([leftKey], [rightKey]) => (leftKey < rightKey ? 1 : -1))
    .map(([monthKey, count]) => {
      const [year, month] = monthKey.split("-").map(Number);
      const label = monthYearFormatter(locale).format(
        new Date(Date.UTC(year, month - 1, 1)),
      );

      return { monthKey, label, count };
    });
}

function buildCategorySignals(
  incidents: PublicIncidentBase[],
  locale: ReaderLocale,
): CategorySignal[] {
  const counts = new Map<string, number>();

  for (const incident of incidents) {
    for (const category of incident.categories) {
      const localizedCategory = localizePublicCategory(category, locale);
      counts.set(localizedCategory, (counts.get(localizedCategory) ?? 0) + 1);
    }
  }

  return [...counts.entries()]
    .sort(
      (left, right) => right[1] - left[1] || left[0].localeCompare(right[0]),
    )
    .map(([category, count]) => ({
      category,
      count,
      share: Math.round((count / incidents.length) * 100),
    }));
}

function buildCategoryDonut(signals: CategorySignal[]) {
  if (signals.length === 0) {
    return "conic-gradient(rgba(23, 38, 58, 0.12) 0deg 360deg)";
  }

  const totalCount = signals.reduce(
    (runningTotal, signal) => runningTotal + signal.count,
    0,
  );

  let currentAngle = 0;
  const stops = signals.map((signal, index) => {
    const start = currentAngle;
    const next =
      totalCount === 0
        ? currentAngle
        : currentAngle + (signal.count / totalCount) * 360;
    currentAngle = next;
    return `${SIGNAL_COLORS[index % SIGNAL_COLORS.length]} ${start}deg ${next}deg`;
  });

  if (currentAngle < 360) {
    stops.push(
      `${SIGNAL_COLORS[(signals.length - 1) % SIGNAL_COLORS.length]} ${currentAngle}deg 360deg`,
    );
  }

  return `conic-gradient(${stops.join(", ")})`;
}

function buildHeroMetrics(
  feed: IncidentFeedResponse,
  categorySignals: CategorySignal[],
  locale: ReaderLocale,
): HeroMetric[] {
  const copy = PUBLIC_COPY[locale];
  const companies = new Set(
    feed.slice_summary.top_companies.map((company) => company.company),
  );

  return [
    {
      label: copy.metrics.currentFeed,
      value: `${feed.slice_summary.total_matches}`,
      note: copy.metrics.currentFeedNote(feed.slice_summary.total_matches),
    },
    {
      label: copy.metrics.companiesInView,
      value: `${companies.size}`,
      note: copy.metrics.companiesInViewNote(companies.size),
    },
    {
      label: copy.metrics.latestLogged,
      value: feed.slice_summary.newest_logged
        ? formatDate(feed.slice_summary.newest_logged, locale)
        : copy.metrics.awaitingData,
      note: copy.metrics.latestLoggedNote,
    },
    {
      label: copy.metrics.categorySpread,
      value: `${categorySignals.length}`,
      note: copy.metrics.categorySpreadNote(categorySignals.length),
    },
  ];
}

function buildHighlightInsights(
  sliceSummary: IncidentSliceSummary,
  locale: ReaderLocale,
): HighlightInsight[] {
  const copy = PUBLIC_COPY[locale];

  return [
    {
      label: copy.highlights.totalMatches,
      value: `${sliceSummary.total_matches}`,
      note:
        locale === "zh"
          ? "当前筛选结果中的已审阅事件数"
          : "Reviewed incidents in this slice",
    },
    {
      label: copy.highlights.timeWindow,
      value:
        sliceSummary.newest_logged && sliceSummary.oldest_logged
          ? copy.highlights.timeWindowValue(
              formatDate(sliceSummary.newest_logged, locale),
              formatDate(sliceSummary.oldest_logged, locale),
            )
          : copy.highlights.noTimeWindow,
      note:
        locale === "zh"
          ? "这个筛选范围覆盖的公开记录时间段"
          : "Range covered by the current filtered archive",
    },
    {
      label: copy.highlights.highestSeverity,
      value:
        sliceSummary.highest_severity !== null &&
        sliceSummary.highest_severity !== undefined
          ? copy.highlights.severityValue(sliceSummary.highest_severity)
          : copy.metrics.awaitingData,
      note:
        locale === "zh"
          ? "当前筛选结果中的最高严重级别"
          : "Highest severity present in the current slice",
    },
    {
      label: copy.highlights.topCategories,
      value:
        sliceSummary.top_categories.length > 0
          ? copy.highlights.topListValue(
              sliceSummary.top_categories
                .slice(0, 3)
                .map(
                  (entry) =>
                    `${localizePublicCategory(entry.category, locale)} (${entry.count})`,
                ),
            )
          : copy.highlights.noTopCategories,
      note:
        locale === "zh"
          ? "按出现频次排列的主要类别"
          : "Most frequent categories in the filtered archive",
    },
    {
      label: copy.highlights.topCompanies,
      value:
        sliceSummary.top_companies.length > 0
          ? copy.highlights.topListValue(
              sliceSummary.top_companies
                .slice(0, 3)
                .map(
                  (entry) =>
                    `${locale === "zh" ? (entry.company_zh ?? entry.company) : entry.company} (${entry.count})`,
                ),
            )
          : copy.highlights.noTopCompanies,
      note:
        locale === "zh"
          ? "当前筛选结果中最常出现的公司"
          : "Companies appearing most often in this slice",
    },
  ];
}

function monthLabelForNumber(month: number, locale: ReaderLocale) {
  return new Intl.DateTimeFormat(PUBLIC_COPY[locale].dateLocale, {
    month: "long",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(2026, month - 1, 1)));
}

function formatDate(dateString: string, locale: ReaderLocale) {
  return new Intl.DateTimeFormat(PUBLIC_COPY[locale].dateLocale, {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${dateString}T00:00:00Z`));
}

function monthYearFormatter(locale: ReaderLocale) {
  return new Intl.DateTimeFormat(PUBLIC_COPY[locale].dateLocale, {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

function severityLabel(severityScore: number, locale: ReaderLocale) {
  if (locale === "zh") {
    return `严重级别 ${severityScore}`;
  }

  return `Severity ${severityScore}`;
}

function buildEmptyIncidentFeed(): IncidentFeedResponse {
  return {
    items: [],
    page: 1,
    page_size: ARCHIVE_PAGE_SIZE,
    total_count: 0,
    total_pages: 1,
    has_next_page: false,
    has_previous_page: false,
    slice_summary: EMPTY_SLICE_SUMMARY,
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

function normalizeIncidentFeed(
  response: Partial<IncidentFeedResponse> & {
    items?: IncidentArchiveItem[];
  },
): IncidentFeedResponse {
  const items = response.items ?? [];

  return {
    items,
    page: response.page ?? 1,
    page_size: response.page_size ?? ARCHIVE_PAGE_SIZE,
    total_count: response.total_count ?? items.length,
    total_pages: response.total_pages ?? 1,
    has_next_page: response.has_next_page ?? false,
    has_previous_page: response.has_previous_page ?? false,
    slice_summary: response.slice_summary ?? {
      total_matches: items.length,
      newest_logged: items[0]?.date_logged ?? null,
      oldest_logged: items[items.length - 1]?.date_logged ?? null,
      highest_severity:
        items.length > 0
          ? Math.max(...items.map((item) => item.severity_score))
          : null,
      top_categories: [],
      top_companies: [],
    },
  };
}
