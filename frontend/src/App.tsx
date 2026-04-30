import type { CSSProperties, FormEvent } from "react";
import { useEffect, useState } from "react";

import {
  fetchAdminIncidentQueue,
  fetchIncidentDetail,
  fetchIncidentFeed,
  fetchIncidentFilters,
  updateAdminIncident,
} from "./lib/api";
import type {
  AdminIncident,
  Incident,
  IncidentFeedFilters,
  IncidentFilters,
} from "./types/incident";

const ADMIN_TOKEN_STORAGE_KEY = "ai-reality-check-admin-token";

type FeedState = {
  incidents: Incident[];
  adminIncidents: AdminIncident[];
  filters: IncidentFilters | null;
  isLoading: boolean;
  error: string | null;
  isAdminLoading: boolean;
  adminError: string | null;
};

const initialState: FeedState = {
  incidents: [],
  adminIncidents: [],
  filters: null,
  isLoading: true,
  error: null,
  isAdminLoading: false,
  adminError: null,
};

const MONTH_LABEL_FORMATTER = new Intl.DateTimeFormat("en-US", {
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

const SIGNAL_COLORS = [
  "#1d4763",
  "#c0672d",
  "#8f3441",
  "#597b53",
  "#9c8453",
  "#5a5f8f",
];

type MonthlyIncidentPoint = {
  monthKey: string;
  label: string;
  count: number;
};

type CategoryDistributionSegment = {
  category: string;
  count: number;
  percentage: number;
  color: string;
};

export default function App() {
  const [
    {
      incidents,
      adminIncidents,
      filters,
      isLoading,
      error,
      isAdminLoading,
      adminError,
    },
    setFeedState,
  ] = useState<FeedState>(initialState);
  const [drafts, setDrafts] = useState<Record<string, ReviewDraft>>({});
  const [activeReviewId, setActiveReviewId] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [readerFilters, setReaderFilters] = useState<IncidentFeedFilters>({});
  const [adminTokenInput, setAdminTokenInput] = useState(
    () => readStoredAdminToken() ?? "",
  );
  const [adminToken, setAdminToken] = useState<string | null>(() =>
    readStoredAdminToken(),
  );
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(
    null,
  );
  const [incidentDetail, setIncidentDetail] = useState<Incident | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const activeIncident =
    adminIncidents.find((incident) => incident.id === activeReviewId) ??
    adminIncidents[0] ??
    null;
  const activeDraft = activeIncident
    ? (drafts[activeIncident.id] ?? createReviewDraft(activeIncident))
    : null;
  const availableYears = filters?.years ?? [];
  const availableMonths = readerFilters.year
    ? (filters?.months_by_year?.[String(readerFilters.year)] ?? [])
    : [];
  const monthlyIncidentPoints = buildMonthlyIncidentPoints(incidents);
  const categorySegments = buildCategoryDistributionSegments(incidents);
  const donutChartStyle = buildDonutChartStyle(categorySegments);
  const maxMonthlyCount = Math.max(
    ...monthlyIncidentPoints.map((point) => point.count),
    1,
  );

  useEffect(() => {
    let isCancelled = false;

    async function loadFilters() {
      try {
        const filterResponse = await fetchIncidentFilters();

        if (!isCancelled) {
          setFeedState((currentState) => ({
            ...currentState,
            filters: filterResponse,
          }));
        }
      } catch {
        if (!isCancelled) {
          setFeedState((currentState) => ({
            ...currentState,
            filters: null,
          }));
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
    const resolvedAdminToken = adminToken;

    if (resolvedAdminToken === null) {
      setFeedState((currentState) => ({
        ...currentState,
        adminIncidents: [],
        isAdminLoading: false,
        adminError: "Admin access required",
      }));
      setDrafts({});
      setActiveReviewId(null);
      return () => {
        isCancelled = true;
      };
    }

    async function loadAdminQueue() {
      if (resolvedAdminToken === null) {
        return;
      }

      setFeedState((currentState) => ({
        ...currentState,
        isAdminLoading: true,
        adminError: null,
      }));

      try {
        const adminQueueResponse =
          await fetchAdminIncidentQueue(resolvedAdminToken);

        if (!isCancelled) {
          const nextActiveIncident = adminQueueResponse.items[0] ?? null;
          setFeedState((currentState) => ({
            ...currentState,
            adminIncidents: adminQueueResponse.items,
            isAdminLoading: false,
            adminError: null,
          }));
          setDrafts(
            Object.fromEntries(
              adminQueueResponse.items.map((incident) => [
                incident.id,
                createReviewDraft(incident),
              ]),
            ),
          );
          setActiveReviewId(nextActiveIncident?.id ?? null);
        }
      } catch (loadError) {
        if (!isCancelled) {
          setFeedState((currentState) => ({
            ...currentState,
            adminIncidents: [],
            isAdminLoading: false,
            adminError:
              loadError instanceof Error &&
              loadError.message === "Request failed: 401"
                ? "Admin token was rejected."
                : "Unable to load the review queue right now.",
          }));
          setDrafts({});
          setActiveReviewId(null);
        }
      }
    }

    void loadAdminQueue();

    return () => {
      isCancelled = true;
    };
  }, [adminToken]);

  useEffect(() => {
    let isCancelled = false;

    async function loadIncidents() {
      setFeedState((currentState) => ({
        ...currentState,
        isLoading: true,
        error: null,
      }));

      try {
        const feedResponse = await fetchIncidentFeed(readerFilters);

        if (!isCancelled) {
          setFeedState((currentState) => ({
            ...currentState,
            incidents: feedResponse.items,
            isLoading: false,
            error: null,
          }));
        }
      } catch {
        if (!isCancelled) {
          setFeedState((currentState) => ({
            ...currentState,
            incidents: [],
            isLoading: false,
            error: "Unable to load the incident feed right now.",
          }));
        }
      }
    }

    void loadIncidents();

    return () => {
      isCancelled = true;
    };
  }, [readerFilters]);

  async function handleApproveIncident() {
    if (!activeIncident || !activeDraft || !adminToken) {
      return;
    }

    setIsSaving(true);

    try {
      const updatedIncident = await updateAdminIncident(
        adminToken,
        activeIncident.id,
        {
          status: "approved",
          company_involved: activeDraft.company,
          claimant_name: activeIncident.claimant_name ?? null,
          categories: activeDraft.category ? [activeDraft.category] : [],
          severity_score: activeDraft.severity,
          reality_summary: activeIncident.reality_summary,
          matched_claim_id: activeIncident.matched_claim_id ?? null,
          claim_match_confidence: activeIncident.claim_match_confidence ?? null,
          review_notes: activeDraft.reviewNotes,
        },
      );

      setFeedState((currentState) => ({
        ...currentState,
        adminIncidents: currentState.adminIncidents.map((incident) =>
          incident.id === updatedIncident.id ? updatedIncident : incident,
        ),
        adminError: null,
      }));
      setDrafts((currentDrafts) => ({
        ...currentDrafts,
        [updatedIncident.id]: createReviewDraft(updatedIncident),
      }));
    } catch {
      setFeedState((currentState) => ({
        ...currentState,
        adminError: "Unable to save the review decision right now.",
      }));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSelectIncident(incidentId: string) {
    setSelectedIncidentId(incidentId);
    setIsDetailLoading(true);
    setDetailError(null);

    try {
      const detail = await fetchIncidentDetail(incidentId);
      setIncidentDetail(detail);
    } catch {
      setIncidentDetail(null);
      setDetailError("Unable to load incident details right now.");
    } finally {
      setIsDetailLoading(false);
    }
  }

  function updateDraft<K extends keyof ReviewDraft>(
    field: K,
    value: ReviewDraft[K],
  ) {
    if (!activeIncident) {
      return;
    }

    setDrafts((currentDrafts) => ({
      ...currentDrafts,
      [activeIncident.id]: {
        ...(currentDrafts[activeIncident.id] ??
          createReviewDraft(activeIncident)),
        [field]: value,
      },
    }));
  }

  function handleUnlockAdmin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedToken = adminTokenInput.trim();

    if (!trimmedToken) {
      window.localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
      setAdminToken(null);
      return;
    }

    window.localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, trimmedToken);
    setAdminToken(trimmedToken);
  }

  function handleCategoryFilterChange(category: string | undefined) {
    setReaderFilters((current) => ({
      ...current,
      category,
      page: 1,
    }));
  }

  function handleYearFilterChange(yearValue: string) {
    const nextYear = yearValue ? Number(yearValue) : undefined;

    setReaderFilters((current) => {
      const validMonths = nextYear
        ? (filters?.months_by_year?.[String(nextYear)] ?? [])
        : [];
      const nextMonth =
        current.month && validMonths.includes(current.month)
          ? current.month
          : undefined;

      return {
        ...current,
        year: nextYear,
        month: nextMonth,
        page: 1,
      };
    });
  }

  function handleMonthFilterChange(monthValue: string) {
    setReaderFilters((current) => ({
      ...current,
      month: monthValue ? Number(monthValue) : undefined,
      page: 1,
    }));
  }

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">AI Reality Check</p>
        <h1>AI Reality Check</h1>
        <p className="lede">
          A calm feed of reviewed AI failures, grounded in credible reporting.
        </p>
        <p className="body-copy">
          This slice pairs a searchable public feed with a lightweight editor
          queue so readers and reviewers can both work from the same source of
          truth.
        </p>
        {filters ? (
          <>
            <div className="filter-row" aria-label="Category tags">
              {filters.categories.map((category) => (
                <button
                  aria-pressed={readerFilters.category === category}
                  className={`filter-pill-button${readerFilters.category === category ? " is-active" : ""}`}
                  key={category}
                  type="button"
                  onClick={() =>
                    handleCategoryFilterChange(
                      readerFilters.category === category
                        ? undefined
                        : category,
                    )
                  }
                >
                  {category}
                </button>
              ))}
            </div>

            <div className="reader-filter-grid">
              <label className="field">
                <span>Filter by category</span>
                <select
                  value={readerFilters.category ?? ""}
                  onChange={(event) =>
                    handleCategoryFilterChange(event.target.value || undefined)
                  }
                >
                  <option value="">All categories</option>
                  {filters.categories.map((category) => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Filter by year</span>
                <select
                  value={readerFilters.year?.toString() ?? ""}
                  onChange={(event) =>
                    handleYearFilterChange(event.target.value)
                  }
                >
                  <option value="">All years</option>
                  {availableYears.map((year) => (
                    <option key={year} value={year}>
                      {year}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Filter by month</span>
                <select
                  disabled={!readerFilters.year}
                  value={readerFilters.month?.toString() ?? ""}
                  onChange={(event) =>
                    handleMonthFilterChange(event.target.value)
                  }
                >
                  <option value="">All months</option>
                  {availableMonths.map((month) => (
                    <option key={month} value={month}>
                      {month}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Filter by company</span>
                <select
                  value={readerFilters.company ?? ""}
                  onChange={(event) =>
                    setReaderFilters((current) => ({
                      ...current,
                      company: event.target.value || undefined,
                      page: 1,
                    }))
                  }
                >
                  <option value="">All companies</option>
                  {filters.companies.map((company) => (
                    <option key={company} value={company}>
                      {company}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </>
        ) : null}
      </section>

      <section className="feed-card signals-card" aria-live="polite">
        <div className="section-header">
          <p className="section-kicker">Current slice</p>
          <h2>Incident signals</h2>
        </div>
        {!isLoading && !error && incidents.length === 0 ? (
          <p className="body-copy">No incidents match this slice yet.</p>
        ) : null}
        {!isLoading && !error && incidents.length > 0 ? (
          <div className="signals-grid">
            <article className="signal-panel">
              <div className="signal-panel-header">
                <div>
                  <p className="signal-panel-kicker">Monthly count</p>
                  <h3>Monthly incident count</h3>
                </div>
                <p className="signal-panel-note">
                  Built from the incidents currently in view.
                </p>
              </div>
              {monthlyIncidentPoints.length < 2 ? (
                <p className="signal-fallback">
                  Only one month is currently in view, so this chart stays
                  intentionally minimal.
                </p>
              ) : null}
              <ol className="signal-timeline" aria-label="Monthly incident count">
                {monthlyIncidentPoints.map((point) => {
                  const incidentLabel =
                    point.count === 1 ? "1 incident" : `${point.count} incidents`;

                  return (
                    <li className="signal-timeline-row" key={point.monthKey}>
                      <div className="signal-timeline-copy">
                        <span>{point.label}</span>
                        <span>{incidentLabel}</span>
                      </div>
                      <div className="signal-bar-track" aria-hidden="true">
                        <div
                          className="signal-bar"
                          style={{
                            width: `${Math.max(
                              (point.count / maxMonthlyCount) * 100,
                              16,
                            )}%`,
                          }}
                        />
                      </div>
                    </li>
                  );
                })}
              </ol>
            </article>

            <article className="signal-panel">
              <div className="signal-panel-header">
                <div>
                  <p className="signal-panel-kicker">Category mix</p>
                  <h3>Category distribution</h3>
                </div>
                <p className="signal-panel-note">
                  Shared tags across the incidents currently in view.
                </p>
              </div>
              <div className="signal-distribution">
                <div
                  aria-label="Category distribution donut chart"
                  className="donut-chart"
                  role="img"
                  style={donutChartStyle}
                >
                  <div className="donut-chart-core">
                    <strong>{incidents.length}</strong>
                    <span>{incidents.length === 1 ? "incident" : "incidents"}</span>
                  </div>
                </div>
                <ul className="distribution-list">
                  {categorySegments.map((segment) => (
                    <li className="distribution-item" key={segment.category}>
                      <span
                        aria-hidden="true"
                        className="distribution-swatch"
                        style={{ backgroundColor: segment.color }}
                      />
                      <span className="distribution-label">{segment.category}</span>
                      <span className="distribution-count">{segment.count}</span>
                      <span className="distribution-percentage">
                        {segment.percentage}%
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </article>
          </div>
        ) : null}
      </section>

      <section className="feed-card" aria-live="polite">
        <div className="section-header">
          <p className="section-kicker">Reviewed incidents</p>
          <h2>Latest entries</h2>
        </div>
        {isLoading ? <p>Loading incident feed...</p> : null}
        {error ? <p>{error}</p> : null}
        {!isLoading && !error ? (
          <div className="incident-list">
            {incidents.map((incident) => (
              <article className="incident-item" key={incident.id}>
                <div className="incident-meta">
                  <span>{incident.company_involved}</span>
                  <span>Severity {incident.severity_score}</span>
                  <span>{incident.date_logged}</span>
                </div>
                <h3>{incident.headline}</h3>
                <p className="body-copy">{incident.reality_summary}</p>
                {incident.matched_claim ? (
                  <section
                    className="claim-block"
                    aria-label="Claim vs. reality"
                  >
                    <p className="claim-kicker">Claim vs. reality</p>
                    <p className="claim-quote">
                      {incident.matched_claim.original_claim}
                    </p>
                    <div className="claim-meta">
                      <span>{incident.matched_claim.claimant_name}</span>
                      <span>{incident.matched_claim.claim_date}</span>
                      <span>
                        Confidence{" "}
                        {Math.round(
                          incident.matched_claim.match_confidence * 100,
                        )}
                        %
                      </span>
                    </div>
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
                  className="secondary-action"
                  type="button"
                  onClick={() => void handleSelectIncident(incident.id)}
                >
                  View details
                </button>
              </article>
            ))}
          </div>
        ) : null}
      </section>

      {selectedIncidentId ? (
        <section className="feed-card" aria-live="polite">
          <div className="section-header">
            <p className="section-kicker">Incident detail</p>
            <h2>Incident detail</h2>
          </div>
          {isDetailLoading ? <p>Loading incident details...</p> : null}
          {detailError ? <p>{detailError}</p> : null}
          {!isDetailLoading && !detailError && incidentDetail ? (
            <div className="detail-grid">
              <article className="incident-item">
                <div className="incident-meta">
                  <span>{incidentDetail.company_involved}</span>
                  <span>Severity {incidentDetail.severity_score}</span>
                  <span>{incidentDetail.date_logged}</span>
                </div>
                <h3>{incidentDetail.headline}</h3>
                <p className="body-copy">{incidentDetail.reality_summary}</p>
                {incidentDetail.matched_claim ? (
                  <section
                    className="claim-block"
                    aria-label="Claim vs. reality"
                  >
                    <p className="claim-kicker">Claim vs. reality</p>
                    <p className="claim-quote">
                      {incidentDetail.matched_claim.original_claim}
                    </p>
                    <div className="claim-meta">
                      <span>{incidentDetail.matched_claim.claimant_name}</span>
                      <span>{incidentDetail.matched_claim.claim_date}</span>
                    </div>
                  </section>
                ) : null}
              </article>

              <aside className="source-list">
                <h3>Sources</h3>
                {incidentDetail.sources.map((source) => (
                  <article className="source-item" key={source.id}>
                    <p className="source-publisher">{source.publisher}</p>
                    <p className="body-copy">
                      {source.title ?? source.source_url}
                    </p>
                    <a href={source.source_url}>{source.source_url}</a>
                  </article>
                ))}
              </aside>
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="feed-card" aria-live="polite">
        <div className="section-header">
          <p className="section-kicker">Internal review</p>
          <h2>Editor queue</h2>
        </div>
        <form className="admin-auth-form" onSubmit={handleUnlockAdmin}>
          <label className="field">
            <span>Admin token</span>
            <input
              name="admin-token"
              value={adminTokenInput}
              onChange={(event) => setAdminTokenInput(event.target.value)}
            />
          </label>
          <button className="secondary-action" type="submit">
            Unlock admin
          </button>
        </form>
        {isAdminLoading ? <p>Loading review queue...</p> : null}
        {adminError ? <p>{adminError}</p> : null}
        {!isAdminLoading && !adminError && activeIncident && activeDraft ? (
          <div className="review-grid">
            <article className="incident-item">
              <div className="incident-meta">
                <span>{activeIncident.status}</span>
                <span>Severity {activeIncident.severity_score}</span>
                <span>{activeIncident.date_logged}</span>
              </div>
              <h3>{activeIncident.headline}</h3>
              <p className="body-copy">{activeIncident.reality_summary}</p>
              <p className="body-copy">{activeIncident.review_notes}</p>
            </article>

            <form
              className="review-form"
              onSubmit={(event) => {
                event.preventDefault();
                void handleApproveIncident();
              }}
            >
              <label className="field">
                <span>Company</span>
                <input
                  name="company"
                  value={activeDraft.company}
                  onChange={(event) =>
                    updateDraft("company", event.target.value)
                  }
                />
              </label>

              <label className="field">
                <span>Category</span>
                <input
                  list="category-options"
                  name="category"
                  value={activeDraft.category}
                  onChange={(event) =>
                    updateDraft("category", event.target.value)
                  }
                />
              </label>
              <datalist id="category-options">
                {filters?.categories.map((category) => (
                  <option key={category} value={category} />
                ))}
              </datalist>

              <label className="field">
                <span>Severity</span>
                <input
                  min="1"
                  max="5"
                  name="severity"
                  type="number"
                  value={activeDraft.severity}
                  onChange={(event) =>
                    updateDraft("severity", Number(event.target.value))
                  }
                />
              </label>

              <label className="field">
                <span>Review Notes</span>
                <input
                  name="review-notes"
                  value={activeDraft.reviewNotes}
                  onChange={(event) =>
                    updateDraft("reviewNotes", event.target.value)
                  }
                />
              </label>

              <button
                className="primary-action"
                disabled={isSaving}
                type="submit"
              >
                {isSaving ? "Saving..." : "Approve Incident"}
              </button>
            </form>
          </div>
        ) : null}
      </section>
    </main>
  );
}

type ReviewDraft = {
  company: string;
  category: string;
  severity: number;
  reviewNotes: string;
};

function readStoredAdminToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage.getItem(ADMIN_TOKEN_STORAGE_KEY);
}

function createReviewDraft(incident: AdminIncident): ReviewDraft {
  return {
    company: incident.company_involved,
    category: incident.categories[0] ?? "",
    severity: incident.severity_score,
    reviewNotes: incident.review_notes ?? "",
  };
}

function buildMonthlyIncidentPoints(
  incidents: Incident[],
): MonthlyIncidentPoint[] {
  const monthCounts = new Map<string, number>();

  for (const incident of incidents) {
    const monthKey = incident.date_logged.slice(0, 7);
    monthCounts.set(monthKey, (monthCounts.get(monthKey) ?? 0) + 1);
  }

  return Array.from(monthCounts.entries())
    .sort(([leftMonth], [rightMonth]) => leftMonth.localeCompare(rightMonth))
    .map(([monthKey, count]) => ({
      monthKey,
      count,
      label: MONTH_LABEL_FORMATTER.format(new Date(`${monthKey}-01T00:00:00Z`)),
    }));
}

function buildCategoryDistributionSegments(
  incidents: Incident[],
): CategoryDistributionSegment[] {
  const categoryCounts = new Map<string, number>();

  for (const incident of incidents) {
    for (const category of incident.categories) {
      categoryCounts.set(category, (categoryCounts.get(category) ?? 0) + 1);
    }
  }

  const totalCategoryCount = Array.from(categoryCounts.values()).reduce(
    (total, count) => total + count,
    0,
  );

  return Array.from(categoryCounts.entries())
    .sort(([leftCategory, leftCount], [rightCategory, rightCount]) => {
      if (leftCount !== rightCount) {
        return rightCount - leftCount;
      }

      return leftCategory.localeCompare(rightCategory);
    })
    .map(([category, count], index) => ({
      category,
      count,
      percentage:
        totalCategoryCount === 0
          ? 0
          : Math.round((count / totalCategoryCount) * 100),
      color: SIGNAL_COLORS[index % SIGNAL_COLORS.length],
    }));
}

function buildDonutChartStyle(
  segments: CategoryDistributionSegment[],
): CSSProperties {
  if (segments.length === 0) {
    return {
      backgroundImage:
        "conic-gradient(rgba(39, 65, 95, 0.12) 0deg 360deg)",
    };
  }

  let currentAngle = 0;
  const gradientStops = segments.map((segment) => {
    const startAngle = currentAngle;
    const nextAngle = currentAngle + segment.percentage * 3.6;
    currentAngle = nextAngle;
    return `${segment.color} ${startAngle}deg ${nextAngle}deg`;
  });

  if (currentAngle < 360) {
    gradientStops.push(
      `${segments[segments.length - 1].color} ${currentAngle}deg 360deg`,
    );
  }

  return {
    backgroundImage: `conic-gradient(${gradientStops.join(", ")})`,
  };
}
