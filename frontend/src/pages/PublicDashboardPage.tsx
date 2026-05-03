import { useEffect, useRef, useState } from "react";
import { useCountUp } from "../lib/useCountUp";
import { useInView } from "../lib/useInView";

import {
  fetchIncidentDetail,
  fetchIncidentFeed,
  fetchIncidentFilters,
} from "../lib/api";
import { localizePublicCategory } from "../lib/publicDashboardLocalization";
import type {
  IncidentAnalysis,
  IncidentArchiveItem,
  IncidentDetail,
  IncidentFeedFilters,
  IncidentFeedResponse,
  IncidentFilters,
  IncidentSliceSummary,
  PublicIncidentBase,
} from "../types/incident";
import "./public-dashboard.css";

const READER_LOCALE_STORAGE_KEY = "ai-reality-check-locale";
const READER_THEME_STORAGE_KEY = "ai-reality-check-theme";
const SIGNAL_COLORS = [
  "#8a3b26",
  "#274b63",
  "#8a6a2a",
  "#5e7041",
  "#6f4b7e",
  "#405061",
];
const ARCHIVE_PAGE_SIZE = 6;
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
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(
    null,
  );
  const [detailRequestNonce, setDetailRequestNonce] = useState(0);
  const [incidentDetail, setIncidentDetail] = useState<IncidentDetail | null>(null);
  const [isFiltersLoading, setIsFiltersLoading] = useState(true);
  const [isFeedLoading, setIsFeedLoading] = useState(true);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [feedError, setFeedError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const lastSliceFilterKeyRef = useRef(buildSliceFilterKey(readerFilters));

  // ── InView refs for entrance animations ──────────────────────────
  const [heroRef, heroInView] = useInView<HTMLElement>();
  const [metricsRef, metricsInView] = useInView<HTMLDivElement>();
  const [signalsRef, signalsInView] = useInView<HTMLElement>();
  const [monthlyCardRef, monthlyCardInView] = useInView<HTMLElement>();
  const [categoryCardRef, categoryCardInView] = useInView<HTMLElement>();
  const [archiveListRef, archiveListInView] = useInView<HTMLDivElement>();
  const [spotlightRef, spotlightInView] = useInView<HTMLElement>();
  const [insightsRef, insightsInView] = useInView<HTMLElement>();
  const [detailRef, detailInView] = useInView<HTMLElement>();
  const [sourceListRef, sourceListInView] = useInView<HTMLDivElement>();

  const incidents = feed.items;
  const selectedIncident =
    incidents.find((incident) => incident.id === selectedIncidentId) ?? null;
  const sliceSummary = feed.slice_summary;
  const availableMonths = readerFilters.year
    ? (filters?.months_by_year[String(readerFilters.year)] ?? [])
    : [];
  const copy = PUBLIC_COPY[readerLocale];
  const monthlySignals = buildMonthlySignals(incidents, readerLocale);
  const categorySignals = buildCategorySignals(incidents, readerLocale);
  const heroMetrics = buildHeroMetrics(
    feed,
    categorySignals,
    readerLocale,
  );
  const highlightInsights = buildHighlightInsights(sliceSummary, readerLocale);
  const maxMonthlyCount = Math.max(
    ...monthlySignals.map((signal) => signal.count),
    1,
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
    const nextSliceFilterKey = buildSliceFilterKey(readerFilters);
    const sliceFiltersChanged = lastSliceFilterKeyRef.current !== nextSliceFilterKey;

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
        setSelectedIncidentId((currentSelectedIncidentId) => {
          const incidentIsVisible = currentSelectedIncidentId
            ? response.items.some(
                (incident) => incident.id === currentSelectedIncidentId,
              )
            : false;

          if (currentSelectedIncidentId && incidentIsVisible) {
            return currentSelectedIncidentId;
          }

          if (currentSelectedIncidentId && !sliceFiltersChanged) {
            return currentSelectedIncidentId;
          }

          return response.items[0]?.id ?? null;
        });
        lastSliceFilterKeyRef.current = nextSliceFilterKey;
      } catch {
        if (!isCancelled) {
          setFeed(buildEmptyIncidentFeed());
          setSelectedIncidentId(null);
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

  useEffect(() => {
    let isCancelled = false;

    async function loadDetail() {
      if (!selectedIncidentId) {
        setIncidentDetail(null);
        setDetailError(null);
        setIsDetailLoading(false);
        return;
      }

      setIsDetailLoading(true);
      setDetailError(null);

      try {
        const detail = await fetchIncidentDetail(selectedIncidentId);

        if (!isCancelled) {
          setIncidentDetail(detail);
        }
      } catch {
        if (!isCancelled) {
          setIncidentDetail(null);
          setDetailError("Unable to load incident details right now.");
        }
      } finally {
        if (!isCancelled) {
          setIsDetailLoading(false);
        }
      }
    }

    void loadDetail();

    return () => {
      isCancelled = true;
    };
  }, [detailRequestNonce, selectedIncidentId]);

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

  function showIncidentDetail(incidentId: string) {
    setSelectedIncidentId((currentSelectedIncidentId) => {
      if (currentSelectedIncidentId === incidentId) {
        setDetailRequestNonce((currentNonce) => currentNonce + 1);
        return currentSelectedIncidentId;
      }

      return incidentId;
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
                          style={{
                            width: `${Math.max((signal.count / maxMonthlyCount) * 100, 18)}%`,
                            "--bar-index": barIdx,
                          } as React.CSSProperties}
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
                    style={{ backgroundImage: buildCategoryDonut(categorySignals) }}
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
                      event.target.value ? Number(event.target.value) : undefined,
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
                    <div className="public-skeleton-card" key={i} style={{ marginBottom: "1rem" }}>
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
                  {incidents.map((incident, cardIdx) => {
                    const isSelected = incident.id === selectedIncident?.id;

                    return (
                      <article
                        className={`public-archive-card${isSelected ? " is-selected" : ""}`}
                        key={incident.id}
                        style={{ "--card-index": cardIdx } as React.CSSProperties}
                      >
                        <div className="incident-meta">
                          <span>{localizedCompanyName(incident, readerLocale)}</span>
                          <span>{severityLabel(incident.severity_score, readerLocale)}</span>
                          <span>{formatDate(incident.date_logged, readerLocale)}</span>
                        </div>
                        <h3>{localizedHeadline(incident, readerLocale)}</h3>
                        <p className="body-copy public-archive-summary">
                          {buildSnippet(
                            localizedArchiveSummary(incident, readerLocale),
                          )}
                        </p>
                        <div className="tag-row">
                          {incident.categories.map((category) => (
                            <span className="tag" key={category}>
                              {localizePublicCategory(category, readerLocale)}
                            </span>
                          ))}
                        </div>
                        <button
                          aria-pressed={isSelected}
                          className="secondary-action public-detail-button"
                          type="button"
                          onClick={() => showIncidentDetail(incident.id)}
                        >
                          {copy.detailActionLabel(
                            localizedHeadline(incident, readerLocale),
                          )}
                        </button>
                      </article>
                    );
                  })}
                </div>
              ) : null}
              {!isFeedLoading && !feedError && incidents.length === 0 ? (
                <p className="body-copy">{copy.noIncidentsForSlice}</p>
              ) : null}
              {!isFeedLoading && !feedError && incidents.length > 0 ? (
                <div className="public-archive-pagination">
                  <span className="body-copy public-pagination-summary">
                    {copy.paginationSummary(incidents.length, feed.total_count)}
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
              {!isFeedLoading && !feedError && sliceSummary.total_matches > 0 ? (
                <article
                  className="public-panel-compact public-spotlight-insights"
                  data-inview={insightsInView ? "true" : "false"}
                  ref={insightsRef}
                >
                  <p className="public-claim-kicker">{copy.highlightInsightsTitle}</p>
                  <p className="body-copy public-spotlight-copy">
                    {copy.highlightInsightsBody}
                  </p>
                  <div className="public-highlight-list">
                    {highlightInsights.map((insight, insightIdx) => (
                      <section
                        className="public-highlight-item"
                        key={insight.label}
                        style={{ "--insight-index": insightIdx } as React.CSSProperties}
                      >
                        <span className="public-highlight-label">{insight.label}</span>
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
              {!isFeedLoading && !feedError && sliceSummary.total_matches === 0 ? (
                <p className="body-copy">{copy.highlightsEmpty}</p>
              ) : null}
            </section>
          </aside>
        </section>

        <section
          className="public-panel public-detail-section"
          aria-live="polite"
          data-inview={detailInView ? "true" : "false"}
          ref={detailRef}
        >
          <div className="section-header">
            <p className="public-kicker">{copy.detailKicker}</p>
            <h2>{copy.detailTitle}</h2>
          </div>
          {isDetailLoading ? (
            <div aria-busy="true" style={{ display: "grid", gap: "1rem" }}>
              <div className="public-skeleton public-skeleton-block is-medium" />
              <div className="public-skeleton public-skeleton-block is-tall" />
              <div className="public-skeleton public-skeleton-block" />
              <div className="public-skeleton public-skeleton-block is-medium" />
            </div>
          ) : null}
          {detailError ? <p>{copy.detailError}</p> : null}
          {!isDetailLoading && !detailError && incidentDetail ? (
            <div className="public-detail-grid">
              <article className="public-incident-card public-detail-card">
                <div className="incident-meta">
                  <span>{localizedCompanyName(incidentDetail, readerLocale)}</span>
                  <span>{severityLabel(incidentDetail.severity_score, readerLocale)}</span>
                  <span>{formatDate(incidentDetail.date_logged, readerLocale)}</span>
                </div>
                <h3>{localizedHeadline(incidentDetail, readerLocale)}</h3>
                <p className="body-copy">
                  {localizedDetailSummary(incidentDetail, readerLocale)}
                </p>
                <div className="tag-row">
                  {incidentDetail.categories.map((category) => (
                    <span className="tag" key={category}>
                      {localizePublicCategory(category, readerLocale)}
                    </span>
                  ))}
                </div>
                <div className="public-detail-analysis">
                  {localizedAnalysisText(
                    incidentDetail.analysis,
                    "what_happened",
                    readerLocale,
                  ) ? (
                    <section className="public-detail-block">
                      <p className="public-claim-kicker">{copy.whatHappenedTitle}</p>
                      <p className="body-copy">
                        {localizedAnalysisText(
                          incidentDetail.analysis,
                          "what_happened",
                          readerLocale,
                        )}
                      </p>
                    </section>
                  ) : null}
                  <section className="public-detail-block">
                    <p className="public-claim-kicker">
                      {copy.aiFailurePointTitle}
                    </p>
                    <p className="body-copy">
                      {localizedAnalysisText(
                        incidentDetail.analysis,
                        "ai_failure_point",
                        readerLocale,
                      ) ?? copy.aiFailurePointUnavailable}
                    </p>
                  </section>
                  {localizedAnalysisText(
                    incidentDetail.analysis,
                    "why_it_matters",
                    readerLocale,
                  ) ? (
                    <section className="public-detail-block">
                      <p className="public-claim-kicker">{copy.whyItMattersTitle}</p>
                      <p className="body-copy">
                        {localizedAnalysisText(
                          incidentDetail.analysis,
                          "why_it_matters",
                          readerLocale,
                        )}
                      </p>
                    </section>
                  ) : null}
                  {localizedAnalysisText(
                    incidentDetail.analysis,
                    "evidence_summary",
                    readerLocale,
                  ) ? (
                    <section className="public-detail-block">
                      <p className="public-claim-kicker">
                        {copy.evidenceSummaryTitle}
                      </p>
                      <p className="body-copy">
                        {localizedAnalysisText(
                          incidentDetail.analysis,
                          "evidence_summary",
                          readerLocale,
                        )}
                      </p>
                    </section>
                  ) : null}
                </div>
                {incidentDetail.matched_claim ? (
                  <section
                    className="public-claim-block"
                    aria-label={copy.claimVsReality}
                  >
                    <p className="public-claim-kicker">{copy.claimVsReality}</p>
                    <p className="public-claim-quote">
                      {incidentDetail.matched_claim.original_claim}
                    </p>
                    <div className="incident-meta">
                      <span>{incidentDetail.matched_claim.claimant_name}</span>
                      <span>{incidentDetail.matched_claim.claim_date}</span>
                      <span>
                        {copy.confidenceLabel}{" "}
                        {Math.round(
                          incidentDetail.matched_claim.match_confidence * 100,
                        )}
                        %
                      </span>
                    </div>
                  </section>
                ) : null}
              </article>

              <aside 
                className="public-panel public-source-panel"
                data-inview={sourceListInView ? "true" : "false"}
                ref={sourceListRef}
              >
                <p className="public-kicker">{copy.reportingTrailKicker}</p>
                <h3>{copy.sourcesTitle}</h3>
                <div
                  className="public-source-list"
                  data-inview={sourceListInView ? "true" : "false"}
                  ref={sourceListRef}
                >
                  {incidentDetail.sources.length === 0 ? (
                    <p className="body-copy">{copy.noSources}</p>
                  ) : (
                    incidentDetail.sources.map((source, srcIdx) => (
                      <article
                        className="public-source-item"
                        key={source.id}
                        style={{ "--source-index": srcIdx } as React.CSSProperties}
                      >
                        <p className="public-source-publisher">
                          {source.publisher ?? source.source_type}
                        </p>
                        <a href={source.source_url}>
                          {source.title ?? source.source_url}
                        </a>
                      </article>
                    ))
                  )}
                </div>
              </aside>
            </div>
          ) : null}
          {!isDetailLoading && !detailError && !incidentDetail ? (
            <p className="body-copy">{copy.selectIncident}</p>
          ) : null}
        </section>
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

function localizedDetailSummary(incident: IncidentDetail, locale: ReaderLocale) {
  const incidentSummary = localizedAnalysisText(
    incident.analysis,
    "incident_summary",
    locale,
  );
  if (incidentSummary) {
    return incidentSummary;
  }

  if (locale === "zh") {
    return (
      incident.reality_summary_zh ??
      incident.reality_summary_en ??
      incident.reality_summary
    );
  }

  return incident.reality_summary_en ?? incident.reality_summary;
}

function localizedAnalysisText(
  analysis: IncidentAnalysis,
  key:
    | "incident_summary"
    | "what_happened"
    | "ai_failure_point"
    | "why_it_matters"
    | "evidence_summary",
  locale: ReaderLocale,
) {
  const englishKey = `${key}_en` as keyof IncidentAnalysis;
  const chineseKey = `${key}_zh` as keyof IncidentAnalysis;
  const baseKey = key as keyof IncidentAnalysis;

  if (locale === "zh") {
    return (
      analysis[chineseKey] ??
      analysis[baseKey] ??
      analysis[englishKey] ??
      null
    );
  }

  return analysis[englishKey] ?? analysis[baseKey] ?? null;
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
        locale === "zh" ? "当前筛选结果中的已审阅事件数" : "Reviewed incidents in this slice",
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
                    `${locale === "zh" ? entry.company_zh ?? entry.company : entry.company} (${entry.count})`,
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

function buildSliceFilterKey(filters: IncidentFeedFilters) {
  const { page: _page, pageSize: _pageSize, ...sliceFilters } = filters;
  return JSON.stringify(sliceFilters);
}

function readStoredReaderLocale(): ReaderLocale {
  const storedLocale = window.localStorage.getItem(READER_LOCALE_STORAGE_KEY);
  return storedLocale === "zh" ? "zh" : "en";
}

function readStoredReaderTheme(): ReaderTheme {
  const storedTheme = window.localStorage.getItem(READER_THEME_STORAGE_KEY);
  return storedTheme === "dark" ? "dark" : "light";
}
