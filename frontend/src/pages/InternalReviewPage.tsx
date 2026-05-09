import type { FormEvent } from "react";
import { useEffect, useRef, useState } from "react";

import {
  fetchAdminIncidentQueue,
  updateAdminIncident,
  upgradeAdminIncidentToAccident,
} from "../lib/api";
import type { AdminIncident, AdminIncidentUpdateRequest } from "../types/incident";

const ADMIN_TOKEN_STORAGE_KEY = "ai-reality-check-admin-token";

type ReviewDraft = {
  company: string;
  category: string;
  severity: number;
  reviewNotes: string;
};

type QueueSortMode = "date" | "severity";

export default function InternalReviewPage() {
  const [adminTokenInput, setAdminTokenInput] = useState(
    () => readStoredAdminToken() ?? "",
  );
  const [adminToken, setAdminToken] = useState<string | null>(() =>
    readStoredAdminToken(),
  );
  const [adminIncidents, setAdminIncidents] = useState<AdminIncident[]>([]);
  const [activeReviewId, setActiveReviewId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, ReviewDraft>>({});
  const [isAdminLoading, setIsAdminLoading] = useState(false);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isQueueCollapsed, setIsQueueCollapsed] = useState(true);
  const [queueSortMode, setQueueSortMode] = useState<QueueSortMode>("date");
  const [shouldRevealReviewPanel, setShouldRevealReviewPanel] = useState(false);
  const reviewPanelRef = useRef<HTMLElement | null>(null);
  const sortedAdminIncidents = sortAdminIncidents(adminIncidents, queueSortMode);

  const activeIncident =
    sortedAdminIncidents.find((incident) => incident.id === activeReviewId) ??
    sortedAdminIncidents[0] ??
    null;
  const activeDraft = activeIncident
    ? (drafts[activeIncident.id] ?? createReviewDraft(activeIncident))
    : null;

  useEffect(() => {
    if (!shouldRevealReviewPanel || !activeIncident) {
      return;
    }

    setShouldRevealReviewPanel(false);

    if (
      typeof window === "undefined" ||
      !window.matchMedia("(max-width: 959px)").matches
    ) {
      return;
    }

    reviewPanelRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
    reviewPanelRef.current?.focus();
  }, [activeIncident, shouldRevealReviewPanel]);

  useEffect(() => {
    let isCancelled = false;
    const resolvedAdminToken = adminToken;

    if (resolvedAdminToken === null) {
      setAdminIncidents([]);
      setDrafts({});
      setActiveReviewId(null);
      setIsAdminLoading(false);
      setAdminError("Admin access required");
      return () => {
        isCancelled = true;
      };
    }

    const token = resolvedAdminToken;

    async function loadAdminQueue() {
      setIsAdminLoading(true);
      setAdminError(null);

      try {
        const response = await fetchAdminIncidentQueue(token);

        if (isCancelled) {
          return;
        }

        applyAdminQueue(response.items);
      } catch (loadError) {
        if (isCancelled) {
          return;
        }

        setAdminIncidents([]);
        setDrafts({});
        setActiveReviewId(null);
        setAdminError(
          loadError instanceof Error && loadError.message === "Request failed: 401"
            ? "Admin token was rejected."
            : "Unable to load the review queue right now.",
        );
      } finally {
        if (!isCancelled) {
          setIsAdminLoading(false);
        }
      }
    }

    void loadAdminQueue();

    return () => {
      isCancelled = true;
    };
  }, [adminToken]);

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
        ...(currentDrafts[activeIncident.id] ?? createReviewDraft(activeIncident)),
        [field]: value,
      },
    }));
  }

  function handleSelectIncident(incidentId: string) {
    setActiveReviewId(incidentId);
    setShouldRevealReviewPanel(true);
  }

  function applyAdminQueue(
    incidents: AdminIncident[],
    preferredActiveReviewId?: string | null,
  ) {
    setAdminIncidents(incidents);
    setDrafts(
      Object.fromEntries(
        incidents.map((incident) => [incident.id, createReviewDraft(incident)]),
      ),
    );

    const sortedResponseItems = sortAdminIncidents(incidents, queueSortMode);
    setActiveReviewId((currentActiveReviewId) => {
      const resolvedActiveReviewId =
        preferredActiveReviewId === undefined
          ? currentActiveReviewId
          : preferredActiveReviewId;

      if (
        resolvedActiveReviewId &&
        incidents.some((incident) => incident.id === resolvedActiveReviewId)
      ) {
        return resolvedActiveReviewId;
      }

      return sortedResponseItems[0]?.id ?? null;
    });
  }

  async function handleSubmitReview(status: AdminIncidentUpdateRequest["status"]) {
    if (!activeIncident || !activeDraft || !adminToken) {
      return;
    }

    setIsSaving(true);
    setAdminError(null);
    let reviewSaved = false;

    try {
      await updateAdminIncident(adminToken, activeIncident.id, {
        status,
        company_involved: activeDraft.company,
        claimant_name: activeIncident.claimant_name ?? null,
        categories: activeDraft.category ? [activeDraft.category] : [],
        severity_score: activeDraft.severity,
        reality_summary: activeIncident.reality_summary,
        matched_claim_id: activeIncident.matched_claim_id ?? null,
        claim_match_confidence: activeIncident.claim_match_confidence ?? null,
        review_notes: activeDraft.reviewNotes,
      });
      reviewSaved = true;
      setIsAdminLoading(true);

      const refreshedQueue = await fetchAdminIncidentQueue(adminToken);
      applyAdminQueue(refreshedQueue.items, activeIncident.id);
    } catch {
      setAdminError(
        reviewSaved
          ? "Review saved, but the queue could not be refreshed."
          : "Unable to save the review decision right now.",
      );
    } finally {
      setIsAdminLoading(false);
      setIsSaving(false);
    }
  }

  async function handleUpgradeNewsToAccident() {
    if (!activeIncident || !adminToken) {
      return;
    }

    setIsSaving(true);
    setAdminError(null);
    let upgraded = false;

    try {
      await upgradeAdminIncidentToAccident(adminToken, activeIncident.id);
      upgraded = true;
      setIsAdminLoading(true);

      const refreshedQueue = await fetchAdminIncidentQueue(adminToken);
      applyAdminQueue(refreshedQueue.items, activeIncident.id);
    } catch {
      setAdminError(
        upgraded
          ? "News item upgraded, but the queue could not be refreshed."
          : "Unable to upgrade this AI news item right now.",
      );
    } finally {
      setIsAdminLoading(false);
      setIsSaving(false);
    }
  }

  return (
    <main className="page-shell internal-review-page">
      <section className="hero-card internal-review-hero">
        <p className="eyebrow">Hidden route</p>
        <h1>Internal review</h1>
        <p className="lede">
          Staff review tools for queue decisions, legitimacy checks, and duplicate
          handling.
        </p>
        <p className="body-copy">
          This page stays operational on purpose: unlock the queue, inspect the
          review context, and approve incidents without the public dashboard
          storytelling.
        </p>
      </section>

      <section className="feed-card internal-review-auth" aria-live="polite">
        <div className="section-header">
          <p className="section-kicker">Authentication</p>
          <h2>Admin access</h2>
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
        {adminError ? <p>{adminError}</p> : null}
      </section>

      <div className="internal-review-workspace">
        <section
          aria-label="Review queue"
          className="feed-card internal-review-queue"
          role="region"
        >
          <div className="section-header">
            <p className="section-kicker">Queue</p>
            <h2>Editor queue</h2>
            <p className="body-copy internal-review-section-copy">
              Choose an incident waiting for editorial review.
            </p>
          </div>
          <div className="internal-review-queue-toolbar">
            <label className="field internal-review-sort-field">
              <span>Sort queue</span>
              <select
                aria-label="Sort queue"
                value={queueSortMode}
                onChange={(event) =>
                  setQueueSortMode(event.target.value as QueueSortMode)
                }
              >
                <option value="date">Date (newest first)</option>
                <option value="severity">Severity (highest first)</option>
              </select>
            </label>
            <button
              className="secondary-action internal-review-queue-toggle"
              type="button"
              onClick={() => setIsQueueCollapsed((current) => !current)}
            >
              {isQueueCollapsed ? "Expand queue" : "Collapse queue"}
            </button>
          </div>
          {isAdminLoading ? <p>Loading review queue...</p> : null}
          {!isAdminLoading && !adminError && adminIncidents.length === 0 ? (
            <p className="body-copy">No incidents are waiting for review right now.</p>
          ) : null}
          {!isAdminLoading &&
          !adminError &&
          adminIncidents.length > 0 ? (
            <div
              className={`public-archive-list internal-review-queue-list${isQueueCollapsed ? " is-collapsed" : ""}`}
            >
              {sortedAdminIncidents.map((incident) => {
                const isSelected = incident.id === activeIncident?.id;

                return (
                  <button
                    aria-label={`Open review for ${incident.headline_en ?? incident.headline}`}
                    aria-pressed={isSelected}
                    className={`public-archive-item internal-review-queue-item${isSelected ? " is-selected" : ""}`}
                    key={incident.id}
                    type="button"
                    onClick={() => handleSelectIncident(incident.id)}
                  >
                    <span className="internal-review-queue-status">
                      Status: {incident.status}
                    </span>
                    <span className="public-archive-item-title internal-review-queue-title">
                      {incident.headline_en ?? incident.headline}
                    </span>
                    <span className="internal-review-queue-details">
                      <span className="internal-review-queue-detail">
                        {incident.company_involved}
                      </span>
                      <span className="internal-review-queue-detail">
                        Severity{" "}
                        {incident.suggested_severity_score ?? incident.severity_score}
                      </span>
                      <span className="internal-review-queue-detail">
                        {incident.date_logged}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          ) : null}
        </section>

        <section
          ref={reviewPanelRef}
          aria-live="polite"
          className="feed-card internal-review-panel"
          tabIndex={-1}
        >
          <div className="section-header">
            <p className="section-kicker">Review operations</p>
            <h2>Incident review</h2>
            <p className="body-copy internal-review-section-copy">
              Review and approve the selected incident.
            </p>
          </div>
          {!isAdminLoading && !adminError && activeIncident && activeDraft ? (
            <div className="internal-review-panel-body">
              <div className="internal-review-active-summary">
                <p className="eyebrow internal-review-summary-kicker">
                  Selected incident
                </p>
                <h3>{activeIncident.headline_en ?? activeIncident.headline}</h3>
                <div className="incident-meta">
                  <span>{formatQueueStatus(activeIncident.status)}</span>
                  <span>{activeIncident.company_involved}</span>
                  <span>{activeIncident.date_logged}</span>
                </div>
              </div>

              <div className="review-grid">
                <article className="incident-item">
                  <div className="incident-meta">
                    <span>{activeIncident.company_involved}</span>
                    <span>Severity {activeIncident.severity_score}</span>
                    <span>{activeIncident.date_logged}</span>
                  </div>
                  <h3>{activeIncident.headline_en ?? activeIncident.headline}</h3>
                  <p className="body-copy">
                    {activeIncident.reality_summary_en ?? activeIncident.reality_summary}
                  </p>
                  {activeIncident.review_notes ? (
                    <p className="body-copy">{activeIncident.review_notes}</p>
                  ) : null}
                  {activeIncident.legitimacy_score !== null &&
                  activeIncident.legitimacy_score !== undefined ? (
                    <p className="body-copy">
                      Legitimacy score {Math.round(activeIncident.legitimacy_score * 100)}%
                    </p>
                  ) : null}
                  {activeIncident.legitimacy_label ? (
                    <p className="body-copy">{activeIncident.legitimacy_label}</p>
                  ) : null}
                  {activeIncident.suggested_severity_score ? (
                    <div className="body-copy">
                      <p>
                        Suggested severity {activeIncident.suggested_severity_score}
                      </p>
                      {activeIncident.severity_confidence !== null &&
                      activeIncident.severity_confidence !== undefined ? (
                        <p>
                          Confidence{" "}
                          {Math.round(activeIncident.severity_confidence * 100)}%
                        </p>
                      ) : null}
                      {activeIncident.severity_flags &&
                      activeIncident.severity_flags.length > 0 ? (
                        <p>Flags: {activeIncident.severity_flags.join(", ")}</p>
                      ) : null}
                      {activeIncident.severity_reasoning ? (
                        <p>{activeIncident.severity_reasoning}</p>
                      ) : null}
                      {activeIncident.severity_model ? (
                        <p>Suggested by {activeIncident.severity_model}</p>
                      ) : null}
                    </div>
                  ) : null}
                  {activeIncident.legitimacy_reasoning ? (
                    <p className="body-copy">{activeIncident.legitimacy_reasoning}</p>
                  ) : null}
                  {activeIncident.source_validation_summary ? (
                    <p className="body-copy">{activeIncident.source_validation_summary}</p>
                  ) : null}
                  {activeIncident.analysis?.detail_quality &&
                  activeIncident.analysis.detail_quality !== "not_applicable" ? (
                    <div className="body-copy">
                      <p>
                        Detail quality: {activeIncident.analysis.detail_quality}
                      </p>
                      {activeIncident.analysis.detail_quality_reasons &&
                      activeIncident.analysis.detail_quality_reasons.length > 0 ? (
                        <p>
                          {formatDetailQualityReasons(
                            activeIncident.analysis.detail_quality_reasons,
                          )}
                        </p>
                      ) : null}
                      {activeIncident.analysis.source_fact_summary ? (
                        <p>{activeIncident.analysis.source_fact_summary}</p>
                      ) : null}
                    </div>
                  ) : null}
                  {activeIncident.sources.length > 0 ? (
                    <section className="source-list internal-review-source-list">
                      <h4 className="internal-review-source-heading">Sources</h4>
                      {activeIncident.sources.map((source) => (
                        <article className="source-item" key={source.id}>
                          <p className="internal-review-source-type">
                            {formatSourceTypeLabel(source.source_type)}
                          </p>
                          {source.publisher ? (
                            <p className="source-publisher">{source.publisher}</p>
                          ) : null}
                          <a
                            className="internal-review-source-link"
                            href={source.source_url}
                            rel="noreferrer"
                            target="_blank"
                          >
                            {source.title ?? source.source_url}
                          </a>
                          <p className="internal-review-source-url">
                            {source.source_url}
                          </p>
                        </article>
                      ))}
                    </section>
                  ) : null}
                  {activeIncident.duplicate_status ? (
                    <p className="body-copy">
                      Duplicate status {activeIncident.duplicate_status}
                    </p>
                  ) : null}
                  {activeIncident.duplicate_of_incident_id ? (
                    <p className="body-copy">
                      Canonical incident {activeIncident.duplicate_of_incident_id}
                    </p>
                  ) : null}
                  {activeIncident.canonical_incident_id ? (
                    <p className="body-copy">
                      Canonical record {activeIncident.canonical_incident_id}
                    </p>
                  ) : null}
                  {activeIncident.duplicate_candidates.map((candidate) => (
                    <p className="body-copy" key={candidate.candidate_incident_id}>
                      Potential duplicate: {candidate.candidate_incident_id} ({Math.round(candidate.embedding_score * 100)}%)
                    </p>
                  ))}
                  {activeIncident.publication_track === "accident_watch" ? (
                    <button
                      className="secondary-action"
                      disabled={isSaving}
                      type="button"
                      onClick={() => {
                        void handleUpgradeNewsToAccident();
                      }}
                    >
                      Upgrade AI news to accident review
                    </button>
                  ) : null}
                </article>

                <form
                  className="review-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void handleSubmitReview("approved");
                  }}
                >
                  <label className="field">
                    <span>Company</span>
                    <input
                      name="company"
                      value={activeDraft.company}
                      onChange={(event) => updateDraft("company", event.target.value)}
                    />
                  </label>

                  <label className="field">
                    <span>Category</span>
                    <input
                      name="category"
                      value={activeDraft.category}
                      onChange={(event) => updateDraft("category", event.target.value)}
                    />
                  </label>

                  <label className="field">
                    <span>Severity</span>
                    <input
                      max="5"
                      min="1"
                      name="severity"
                      type="number"
                      value={activeDraft.severity}
                      onChange={(event) =>
                        updateDraft("severity", Number(event.target.value))
                      }
                    />
                  </label>

                  <label className="field">
                    <span>Review notes</span>
                    <input
                      name="review-notes"
                      value={activeDraft.reviewNotes}
                      onChange={(event) =>
                        updateDraft("reviewNotes", event.target.value)
                      }
                    />
                  </label>

                  <div className="review-actions">
                    <button
                      className="primary-action"
                      disabled={isSaving}
                      type="submit"
                    >
                      {isSaving ? "Saving..." : "Approve incident"}
                    </button>
                    <button
                      className="secondary-action danger-action"
                      disabled={isSaving}
                      type="button"
                      onClick={() => {
                        void handleSubmitReview("rejected");
                      }}
                    >
                      {isSaving ? "Saving..." : "Reject incident"}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}

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
    severity: incident.suggested_severity_score ?? incident.severity_score,
    reviewNotes: incident.review_notes ?? "",
  };
}

function formatQueueStatus(status: string): string {
  if (status === "pending_llm_escalation") {
    return "pending llm escalation";
  }
  return status;
}

function formatSourceTypeLabel(sourceType: string): string {
  if (sourceType === "primary") {
    return "Primary source";
  }
  if (sourceType === "secondary") {
    return "Secondary source";
  }
  if (sourceType === "imported") {
    return "Imported source";
  }

  return `${sourceType.split("_").join(" ")} source`;
}

function formatDetailQualityReasons(reasons: string[]): string {
  return reasons.map(formatDetailQualityReason).join(", ");
}

function formatDetailQualityReason(reason: string): string {
  const labels: Record<string, string> = {
    missing_evidence_text: "Missing evidence text",
    missing_collision_object: "missing collision object",
    missing_location_context: "missing location context",
    missing_automation_state: "missing automation state",
    missing_narrative_excerpt: "missing narrative excerpt",
    missing_what_happened: "missing what happened",
    missing_ai_failure_point: "missing AI failure point",
    missing_why_it_matters: "missing why it matters",
    template_forensic_copy: "template forensic copy",
  };
  return labels[reason] ?? reason.split("_").join(" ");
}

function sortAdminIncidents(
  incidents: AdminIncident[],
  sortMode: QueueSortMode = "date",
): AdminIncident[] {
  return [...incidents].sort((left, right) => {
    if (sortMode === "severity") {
      const leftSeverity = left.suggested_severity_score ?? left.severity_score;
      const rightSeverity = right.suggested_severity_score ?? right.severity_score;

      if (rightSeverity !== leftSeverity) {
        return rightSeverity - leftSeverity;
      }
    }

    return right.date_logged.localeCompare(left.date_logged);
  });
}
