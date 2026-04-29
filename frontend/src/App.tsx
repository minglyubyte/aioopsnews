import { useEffect, useState } from "react";

import { fetchIncidentFeed, fetchIncidentFilters } from "./lib/api";
import type { Incident, IncidentFilters } from "./types/incident";

type FeedState = {
  incidents: Incident[];
  filters: IncidentFilters | null;
  isLoading: boolean;
  error: string | null;
};

const initialState: FeedState = {
  incidents: [],
  filters: null,
  isLoading: true,
  error: null,
};

export default function App() {
  const [{ incidents, filters, isLoading, error }, setFeedState] =
    useState<FeedState>(initialState);

  useEffect(() => {
    let isCancelled = false;

    async function loadFeed() {
      try {
        const [feedResponse, filterResponse] = await Promise.all([
          fetchIncidentFeed(),
          fetchIncidentFilters(),
        ]);

        if (!isCancelled) {
          setFeedState({
            incidents: feedResponse.items,
            filters: filterResponse,
            isLoading: false,
            error: null,
          });
        }
      } catch {
        if (!isCancelled) {
          setFeedState({
            incidents: [],
            filters: null,
            isLoading: false,
            error: "Unable to load the incident feed right now.",
          });
        }
      }
    }

    void loadFeed();

    return () => {
      isCancelled = true;
    };
  }, []);

  return (
    <main className="page-shell">
      <section className="hero-card">
        <p className="eyebrow">AI Reality Check</p>
        <h1>AI Reality Check</h1>
        <p className="lede">
          A calm feed of reviewed AI failures, grounded in credible reporting.
        </p>
        <p className="body-copy">
          This slice wires the frontend to a thin public read API so we can see
          approved incidents before building ingestion and admin tooling.
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
    </main>
  );
}
