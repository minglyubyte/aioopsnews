import { useEffect, useState } from "react";

import {
  fetchAdminIncidentQueue,
  fetchIncidentFeed,
  fetchIncidentFilters,
  updateAdminIncident,
} from "./lib/api";
import type {
  AdminIncident,
  Incident,
  IncidentFilters,
} from "./types/incident";

type FeedState = {
  incidents: Incident[];
  adminIncidents: AdminIncident[];
  filters: IncidentFilters | null;
  isLoading: boolean;
  error: string | null;
  adminError: string | null;
};

const initialState: FeedState = {
  incidents: [],
  adminIncidents: [],
  filters: null,
  isLoading: true,
  error: null,
  adminError: null,
};

export default function App() {
  const [
    { incidents, adminIncidents, filters, isLoading, error, adminError },
    setFeedState,
  ] = useState<FeedState>(initialState);
  const [drafts, setDrafts] = useState<Record<string, ReviewDraft>>({});
  const [activeReviewId, setActiveReviewId] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const activeIncident =
    adminIncidents.find((incident) => incident.id === activeReviewId) ??
    adminIncidents[0] ??
    null;
  const activeDraft = activeIncident
    ? (drafts[activeIncident.id] ?? createReviewDraft(activeIncident))
    : null;

  useEffect(() => {
    let isCancelled = false;

    async function loadFeed() {
      try {
        const [feedResponse, filterResponse, adminQueueResponse] =
          await Promise.all([
            fetchIncidentFeed(),
            fetchIncidentFilters(),
            fetchAdminIncidentQueue(),
          ]);

        if (!isCancelled) {
          const nextActiveIncident = adminQueueResponse.items[0] ?? null;
          setFeedState({
            incidents: feedResponse.items,
            adminIncidents: adminQueueResponse.items,
            filters: filterResponse,
            isLoading: false,
            error: null,
            adminError: null,
          });
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
      } catch {
        if (!isCancelled) {
          setFeedState({
            incidents: [],
            adminIncidents: [],
            filters: null,
            isLoading: false,
            error: "Unable to load the incident feed right now.",
            adminError: "Unable to load the review queue right now.",
          });
        }
      }
    }

    void loadFeed();

    return () => {
      isCancelled = true;
    };
  }, []);

  async function handleApproveIncident() {
    if (!activeIncident || !activeDraft) {
      return;
    }

    setIsSaving(true);

    try {
      const updatedIncident = await updateAdminIncident(activeIncident.id, {
        status: "approved",
        company_involved: activeDraft.company,
        claimant_name: activeIncident.claimant_name ?? null,
        categories: activeDraft.category ? [activeDraft.category] : [],
        severity_score: activeDraft.severity,
        reality_summary: activeIncident.reality_summary,
        matched_claim_id: activeIncident.matched_claim_id ?? null,
        claim_match_confidence: activeIncident.claim_match_confidence ?? null,
        review_notes: activeDraft.reviewNotes,
      });

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

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">AI Reality Check</p>
        <h1>AI Reality Check</h1>
        <p className="lede">
          A calm feed of reviewed AI failures, grounded in credible reporting.
        </p>
        <p className="body-copy">
          This slice now pairs the public feed with a lightweight editor queue
          so reviewers can approve enriched incidents without leaving the app.
        </p>
        {filters ? (
          <div className="filter-row" aria-label="Available filters">
            {filters.categories.map((category) => (
              <span className="filter-pill" key={category}>
                {category}
              </span>
            ))}
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
                <div className="tag-row">
                  {incident.categories.map((category) => (
                    <span className="tag" key={category}>
                      {category}
                    </span>
                  ))}
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </section>

      <section className="feed-card" aria-live="polite">
        <div className="section-header">
          <p className="section-kicker">Internal review</p>
          <h2>Editor queue</h2>
        </div>
        {isLoading ? <p>Loading review queue...</p> : null}
        {adminError ? <p>{adminError}</p> : null}
        {!isLoading && !adminError && activeIncident && activeDraft ? (
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

function createReviewDraft(incident: AdminIncident): ReviewDraft {
  return {
    company: incident.company_involved,
    category: incident.categories[0] ?? "",
    severity: incident.severity_score,
    reviewNotes: incident.review_notes ?? "",
  };
}
