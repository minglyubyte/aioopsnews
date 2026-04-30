import { useEffect, useState } from "react";

import {
  fetchIncidentDetail,
  fetchIncidentFeed,
  fetchIncidentFilters,
} from "../lib/api";
import type {
  Incident,
  IncidentFeedFilters,
  IncidentFilters,
} from "../types/incident";
import "./public-dashboard.css";

const READER_LOCALE_STORAGE_KEY = "ai-reality-check-locale";
const MONTH_LABEL_FORMATTER = new Intl.DateTimeFormat("en-US", {
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});
const SIGNAL_COLORS = [
  "#8a3b26",
  "#274b63",
  "#8a6a2a",
  "#5e7041",
  "#6f4b7e",
  "#405061",
];

type ReaderLocale = "en" | "zh";

type MonthlySignal = {
  monthKey: string;
  label: string;
  count: number;
};

type CategorySignal = {
  category: string;
  count: number;
  share: number;
};

type HeroMetric = {
  label: string;
  value: string;
  note: string;
};

export default function PublicDashboardPage() {
  const [filters, setFilters] = useState<IncidentFilters | null>(null);
  const [filtersError, setFiltersError] = useState<string | null>(null);
  const [readerFilters, setReaderFilters] = useState<IncidentFeedFilters>({});
  const [readerLocale, setReaderLocale] = useState<ReaderLocale>(() =>
    readStoredReaderLocale(),
  );
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(
    null,
  );
  const [detailRequestNonce, setDetailRequestNonce] = useState(0);
  const [incidentDetail, setIncidentDetail] = useState<Incident | null>(null);
  const [isFiltersLoading, setIsFiltersLoading] = useState(true);
  const [isFeedLoading, setIsFeedLoading] = useState(true);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [feedError, setFeedError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  const featuredIncident = incidents[0] ?? null;
  const selectedIncident =
    incidents.find((incident) => incident.id === selectedIncidentId) ?? null;
  const availableMonths = readerFilters.year
    ? (filters?.months_by_year[String(readerFilters.year)] ?? [])
    : [];
  const monthlySignals = buildMonthlySignals(incidents);
  const categorySignals = buildCategorySignals(incidents);
  const heroMetrics = buildHeroMetrics(
    incidents,
    categorySignals,
    featuredIncident,
  );
  const maxMonthlyCount = Math.max(
    ...monthlySignals.map((signal) => signal.count),
    1,
  );

  useEffect(() => {
    window.localStorage.setItem(READER_LOCALE_STORAGE_KEY, readerLocale);
  }, [readerLocale]);

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
        const response = await fetchIncidentFeed(readerFilters);

        if (isCancelled) {
          return;
        }

        setIncidents(response.items);
        setSelectedIncidentId((currentSelectedIncidentId) => {
          if (
            currentSelectedIncidentId &&
            response.items.some(
              (incident) => incident.id === currentSelectedIncidentId,
            )
          ) {
            return currentSelectedIncidentId;
          }

          return response.items[0]?.id ?? null;
        });
      } catch {
        if (!isCancelled) {
          setIncidents([]);
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
    <main className="public-dashboard">
      <div className="public-frame">
        <section className="public-panel public-hero">
          <div className="public-hero-header">
            <div>
              <p className="eyebrow public-kicker">AI Reality Check</p>
              <h1>AI Reality Check</h1>
            </div>
            <div className="public-utility-cluster">
              <div
                aria-label="Reader language switch"
                className="public-locale-toggle"
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
            </div>
          </div>
          <p className="lede">
            A calm feed of reviewed AI failures, grounded in credible reporting.
          </p>
          <p className="body-copy public-hero-copy">
            Follow the latest verified incidents, browse by signal, and inspect
            the reporting behind each entry.
          </p>

          <div className="public-metrics">
            {heroMetrics.map((metric) => (
              <article className="public-metric" key={metric.label}>
                <span className="public-metric-label">{metric.label}</span>
                <strong className="public-metric-value">{metric.value}</strong>
                <span className="public-metric-note">{metric.note}</span>
              </article>
            ))}
          </div>

          {isFiltersLoading ? (
            <p className="body-copy public-status">Loading filters...</p>
          ) : null}
          {filtersError ? (
            <p className="public-error" role="status">
              {filtersError}
            </p>
          ) : null}
        </section>

        <section className="public-panel public-signals" aria-live="polite">
          <div className="public-signals-header">
            <div>
              <p className="public-kicker">Signals</p>
              <h2>Incident signals</h2>
            </div>
            <p className="body-copy public-signals-note">
              Live patterns update as the archive narrows, so the dashboard
              stays useful for quick scans and deeper research.
            </p>
          </div>

          <div className="public-signals-grid">
            <article className="public-signal-card">
              <p className="public-kicker">Current feed size</p>
              <h3>{`${incidents.length} incident${incidents.length === 1 ? "" : "s"} in current feed`}</h3>
              {monthlySignals.length > 0 ? (
                <ol
                  className="public-signal-list"
                  aria-label="Monthly incident signal"
                >
                  {monthlySignals.map((signal) => (
                    <li className="public-signal-row" key={signal.monthKey}>
                      <div className="public-signal-meta">
                        <span>{signal.label}</span>
                        <span>
                          {signal.count} incident{signal.count === 1 ? "" : "s"}
                        </span>
                      </div>
                      <div aria-hidden="true" className="public-signal-track">
                        <div
                          className="public-signal-bar"
                          style={{
                            width: `${Math.max((signal.count / maxMonthlyCount) * 100, 18)}%`,
                          }}
                        />
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="body-copy">
                  Incident counts will appear here once the current slice has
                  data.
                </p>
              )}
            </article>

            <article className="public-signal-card">
              <p className="public-kicker">Category distribution</p>
              <h3>What the current feed is surfacing</h3>
              {categorySignals.length > 0 ? (
                <div className="public-signal-distribution">
                  <div
                    aria-hidden="true"
                    className="public-donut"
                    style={{ backgroundImage: buildCategoryDonut(categorySignals) }}
                  >
                    <div className="public-donut-core">
                      <strong>{incidents.length}</strong>
                      <span>
                        {incidents.length === 1 ? "incident" : "incidents"}
                      </span>
                    </div>
                  </div>

                  <ul
                    className="public-signal-list public-distribution-list"
                    aria-label="Category distribution summary"
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
                          <span>{`${signal.share}% of current feed`}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="body-copy">
                  Category distribution will appear once incidents are available.
                </p>
              )}
            </article>
          </div>
        </section>

        <section className="public-content-grid">
          <aside className="public-rail">
            <section
              aria-label="Archive controls"
              className="public-panel public-panel-compact"
              role="region"
            >
              <div className="section-header">
                <p className="public-kicker">Archive controls</p>
                <h2>Archive controls</h2>
              </div>
              <p className="body-copy">
                Narrow the public archive by category, company, and timeframe.
              </p>
              <div className="public-filter-grid">
                <label className="field">
                  <span>Filter by category</span>
                  <select
                    aria-label="Filter by category"
                    disabled={isFiltersLoading}
                    value={readerFilters.category ?? ""}
                    onChange={(event) =>
                      updateFilter("category", event.target.value || undefined)
                    }
                  >
                    <option value="">All categories</option>
                    {(filters?.categories ?? []).map((category) => (
                      <option key={category} value={category}>
                        {category}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span>Filter by company</span>
                  <select
                    aria-label="Filter by company"
                    disabled={isFiltersLoading}
                    value={readerFilters.company ?? ""}
                    onChange={(event) =>
                      updateFilter("company", event.target.value || undefined)
                    }
                  >
                    <option value="">All companies</option>
                    {(filters?.companies ?? []).map((company) => (
                      <option key={company} value={company}>
                        {company}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span>Filter by year</span>
                  <select
                    aria-label="Filter by year"
                    disabled={isFiltersLoading}
                    value={readerFilters.year?.toString() ?? ""}
                    onChange={(event) => handleYearChange(event.target.value)}
                  >
                    <option value="">All years</option>
                    {(filters?.years ?? []).map((year) => (
                      <option key={year} value={year}>
                        {year}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="field">
                  <span>Filter by month</span>
                  <select
                    aria-label="Filter by month"
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
                    <option value="">All months</option>
                    {availableMonths.map((month) => (
                      <option key={month} value={month}>
                        {monthLabelForNumber(month)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </section>

            <section className="public-panel public-panel-compact">
              <p className="public-kicker">Source trail</p>
              <h3>Every public card should open into evidence</h3>
              <p className="body-copy">
                The archive stays reader-first, but each incident still points
                back to the reporting and source trail behind it.
              </p>
            </section>
          </aside>

          <section className="public-feed-column">
            <section
              aria-label="Incident archive"
              className="public-panel public-feed-panel"
              role="region"
            >
              <div className="section-header">
                <p className="public-kicker">Archive</p>
                <h2>Incident archive</h2>
              </div>
              {isFeedLoading ? <p>Loading incident archive...</p> : null}
              {!isFeedLoading && !feedError ? (
                <div className="public-archive-list">
                  {incidents.map((incident) => {
                    const isSelected = incident.id === selectedIncident?.id;

                    return (
                      <article
                        className={`public-archive-card${isSelected ? " is-selected" : ""}`}
                        key={incident.id}
                      >
                        <div className="incident-meta">
                          <span>{incident.company_involved}</span>
                          <span>Severity {incident.severity_score}</span>
                          <span>{formatDate(incident.date_logged)}</span>
                        </div>
                        <h3>{localizedHeadline(incident, readerLocale)}</h3>
                        <p className="body-copy public-archive-summary">
                          {buildSnippet(localizedSummary(incident, readerLocale))}
                        </p>
                        {incident.matched_claim ? (
                          <section
                            className="public-claim-block"
                            aria-label="Claim vs. reality"
                          >
                            <p className="public-claim-kicker">
                              Claim vs. reality
                            </p>
                            <p className="public-claim-quote">
                              {incident.matched_claim.original_claim}
                            </p>
                          </section>
                        ) : null}
                        <div className="tag-row">
                          {incident.categories.map((category) => (
                            <span className="tag" key={category}>
                              {category}
                            </span>
                          ))}
                        </div>
                        <button
                          aria-pressed={isSelected}
                          className="secondary-action public-detail-button"
                          type="button"
                          onClick={() => showIncidentDetail(incident.id)}
                        >
                          Open incident detail for{" "}
                          {localizedHeadline(incident, readerLocale)}
                        </button>
                      </article>
                    );
                  })}
                </div>
              ) : null}
            </section>
          </section>

          <aside className="public-sidebar">
            <section className="public-panel public-spotlight" aria-live="polite">
              <div className="section-header">
                <p className="public-kicker">Spotlight</p>
                <h2>Incident spotlight</h2>
              </div>
              {isFeedLoading ? <p>Loading incident feed...</p> : null}
              {feedError ? <p>{feedError}</p> : null}
              {!isFeedLoading && !feedError && featuredIncident ? (
                <article className="public-incident-card public-spotlight-card">
                  <div className="incident-meta">
                    <span>{featuredIncident.company_involved}</span>
                    <span>Severity {featuredIncident.severity_score}</span>
                    <span>{formatDate(featuredIncident.date_logged)}</span>
                  </div>
                  <h3>{localizedHeadline(featuredIncident, readerLocale)}</h3>
                  <p className="body-copy">
                    {localizedSummary(featuredIncident, readerLocale)}
                  </p>
                  <div className="tag-row">
                    {featuredIncident.categories.map((category) => (
                      <span className="tag" key={category}>
                        {category}
                      </span>
                    ))}
                  </div>
                  <button
                    className="secondary-action public-detail-button"
                    type="button"
                    onClick={() => showIncidentDetail(featuredIncident.id)}
                  >
                    Open source-backed detail for{" "}
                    {localizedHeadline(featuredIncident, readerLocale)}
                  </button>
                </article>
              ) : null}
              {!isFeedLoading && !feedError && !featuredIncident ? (
                <p className="body-copy">No incidents match this slice yet.</p>
              ) : null}
            </section>
          </aside>
        </section>

        <section className="public-panel public-detail-section" aria-live="polite">
          <div className="section-header">
            <p className="public-kicker">Source-backed detail</p>
            <h2>Incident detail</h2>
          </div>
          {isDetailLoading ? <p>Loading incident details...</p> : null}
          {detailError ? <p>{detailError}</p> : null}
          {!isDetailLoading && !detailError && incidentDetail ? (
            <div className="public-detail-grid">
              <article className="public-incident-card public-detail-card">
                <div className="incident-meta">
                  <span>{incidentDetail.company_involved}</span>
                  <span>Severity {incidentDetail.severity_score}</span>
                  <span>{formatDate(incidentDetail.date_logged)}</span>
                </div>
                <h3>{localizedHeadline(incidentDetail, readerLocale)}</h3>
                <p className="body-copy">
                  {localizedSummary(incidentDetail, readerLocale)}
                </p>
                <div className="tag-row">
                  {incidentDetail.categories.map((category) => (
                    <span className="tag" key={category}>
                      {category}
                    </span>
                  ))}
                </div>
                {incidentDetail.matched_claim ? (
                  <section
                    className="public-claim-block"
                    aria-label="Claim vs. reality"
                  >
                    <p className="public-claim-kicker">Claim vs. reality</p>
                    <p className="public-claim-quote">
                      {incidentDetail.matched_claim.original_claim}
                    </p>
                    <div className="incident-meta">
                      <span>{incidentDetail.matched_claim.claimant_name}</span>
                      <span>{incidentDetail.matched_claim.claim_date}</span>
                      <span>
                        Confidence{" "}
                        {Math.round(
                          incidentDetail.matched_claim.match_confidence * 100,
                        )}
                        %
                      </span>
                    </div>
                  </section>
                ) : null}
              </article>

              <aside className="public-panel public-source-panel">
                <p className="public-kicker">Reporting trail</p>
                <h3>Sources</h3>
                <div className="public-source-list">
                  {incidentDetail.sources.length === 0 ? (
                    <p className="body-copy">
                      Source links are not available for this incident yet.
                    </p>
                  ) : (
                    incidentDetail.sources.map((source) => (
                      <article className="public-source-item" key={source.id}>
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
            <p className="body-copy">
              Select an incident from the archive to inspect its sources.
            </p>
          ) : null}
        </section>
      </div>
    </main>
  );
}

function localizedHeadline(incident: Incident, locale: ReaderLocale) {
  if (locale === "zh") {
    return incident.headline_zh ?? incident.headline_en ?? incident.headline;
  }

  return incident.headline_en ?? incident.headline;
}

function localizedSummary(incident: Incident, locale: ReaderLocale) {
  if (locale === "zh") {
    return (
      incident.reality_summary_zh ??
      incident.reality_summary_en ??
      incident.reality_summary
    );
  }

  return incident.reality_summary_en ?? incident.reality_summary;
}

function buildSnippet(summary: string) {
  if (summary.length <= 140) {
    return summary;
  }

  return `${summary.slice(0, 137).trimEnd()}...`;
}

function buildMonthlySignals(incidents: Incident[]): MonthlySignal[] {
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
      const label = MONTH_LABEL_FORMATTER.format(
        new Date(Date.UTC(year, month - 1, 1)),
      );

      return { monthKey, label, count };
    });
}

function buildCategorySignals(incidents: Incident[]): CategorySignal[] {
  const counts = new Map<string, number>();

  for (const incident of incidents) {
    for (const category of incident.categories) {
      counts.set(category, (counts.get(category) ?? 0) + 1);
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
  incidents: Incident[],
  categorySignals: CategorySignal[],
  featuredIncident: Incident | null,
): HeroMetric[] {
  const companies = new Set(
    incidents.map((incident) => incident.company_involved),
  );

  return [
    {
      label: "Current feed",
      value: `${incidents.length}`,
      note:
        incidents.length === 1 ? "reviewed incident" : "reviewed incidents",
    },
    {
      label: "Companies in view",
      value: `${companies.size}`,
      note:
        companies.size === 1
          ? "organization surfaced"
          : "organizations surfaced",
    },
    {
      label: "Latest logged",
      value: featuredIncident
        ? formatDate(featuredIncident.date_logged)
        : "Awaiting data",
      note: "anchoring the spotlight card",
    },
    {
      label: "Category spread",
      value: `${categorySignals.length}`,
      note:
        categorySignals.length === 1
          ? "category in the slice"
          : "categories in the slice",
    },
  ];
}

function monthLabelForNumber(month: number) {
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(2026, month - 1, 1)));
}

function formatDate(dateString: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${dateString}T00:00:00Z`));
}

function readStoredReaderLocale(): ReaderLocale {
  const storedLocale = window.localStorage.getItem(READER_LOCALE_STORAGE_KEY);
  return storedLocale === "zh" ? "zh" : "en";
}
