import type { FormEvent } from "react";
import { useEffect, useState } from "react";

import { fetchAdminIncidentQueue, updateAdminIncident } from "../lib/api";
import type { AdminIncident } from "../types/incident";

const ADMIN_TOKEN_STORAGE_KEY = "ai-reality-check-admin-token";

type ReviewDraft = {
  company: string;
  category: string;
  severity: number;
  reviewNotes: string;
};

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

  const activeIncident =
    adminIncidents.find((incident) => incident.id === activeReviewId) ??
    adminIncidents[0] ??
    null;
  const activeDraft = activeIncident
    ? (drafts[activeIncident.id] ?? createReviewDraft(activeIncident))
    : null;

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

        setAdminIncidents(response.items);
        setDrafts(
          Object.fromEntries(
            response.items.map((incident) => [
              incident.id,
              createReviewDraft(incident),
            ]),
          ),
        );
        setActiveReviewId((currentActiveReviewId) => {
          if (
            currentActiveReviewId &&
            response.items.some((incident) => incident.id === currentActiveReviewId)
          ) {
            return currentActiveReviewId;
          }

          return response.items[0]?.id ?? null;
        });
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

  async function handleApproveIncident() {
    if (!activeIncident || !activeDraft || !adminToken) {
      return;
    }

    setIsSaving(true);
    setAdminError(null);

    try {
      const updatedIncident = await updateAdminIncident(adminToken, activeIncident.id, {
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

      setAdminIncidents((currentIncidents) =>
        currentIncidents.map((incident) =>
          incident.id === updatedIncident.id ? updatedIncident : incident,
        ),
      );
      setDrafts((currentDrafts) => ({
        ...currentDrafts,
        [updatedIncident.id]: createReviewDraft(updatedIncident),
      }));
    } catch {
      setAdminError("Unable to save the review decision right now.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="hero-card">
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

      <section className="feed-card" aria-live="polite">
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

      <div className="public-dashboard-grid">
        <section
          aria-label="Review queue"
          className="feed-card public-section"
          role="region"
        >
          <div className="section-header">
            <p className="section-kicker">Queue</p>
            <h2>Editor queue</h2>
          </div>
          {isAdminLoading ? <p>Loading review queue...</p> : null}
          {!isAdminLoading && !adminError && adminIncidents.length === 0 ? (
            <p className="body-copy">No incidents are waiting for review right now.</p>
          ) : null}
          {!isAdminLoading && !adminError && adminIncidents.length > 0 ? (
            <div className="public-archive-list">
              {adminIncidents.map((incident) => {
                const isSelected = incident.id === activeIncident?.id;

                return (
                  <button
                    aria-pressed={isSelected}
                    className={`public-archive-item${isSelected ? " is-selected" : ""}`}
                    key={incident.id}
                    type="button"
                    onClick={() => setActiveReviewId(incident.id)}
                  >
                    <span className="public-archive-item-date">{incident.status}</span>
                    <span className="public-archive-item-title">
                      {incident.headline_en ?? incident.headline}
                    </span>
                    <span className="public-archive-item-meta">
                      Open review for {incident.headline_en ?? incident.headline}
                    </span>
                  </button>
                );
              })}
            </div>
          ) : null}
        </section>

        <section className="feed-card public-section" aria-live="polite">
          <div className="section-header">
            <p className="section-kicker">Review operations</p>
            <h2>Incident review</h2>
          </div>
          {!isAdminLoading && !adminError && activeIncident && activeDraft ? (
            <div className="review-grid">
              <article className="incident-item">
                <div className="incident-meta">
                  <span>{activeIncident.company_involved}</span>
                  <span>Severity {activeIncident.severity_score}</span>
                  <span>{activeIncident.date_logged}</span>
                </div>
                <h3>{activeIncident.headline_en ?? activeIncident.headline}</h3>
                <p className="body-copy">{activeIncident.reality_summary_en ?? activeIncident.reality_summary}</p>
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
                {activeIncident.legitimacy_reasoning ? (
                  <p className="body-copy">{activeIncident.legitimacy_reasoning}</p>
                ) : null}
                {activeIncident.source_validation_summary ? (
                  <p className="body-copy">{activeIncident.source_validation_summary}</p>
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

                <button
                  className="primary-action"
                  disabled={isSaving}
                  type="submit"
                >
                  {isSaving ? "Saving..." : "Approve incident"}
                </button>
              </form>
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
    severity: incident.severity_score,
    reviewNotes: incident.review_notes ?? "",
  };
}
