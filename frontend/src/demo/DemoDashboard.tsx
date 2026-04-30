import { useState } from "react";

import "./demo.css";
import { demoIncidents, demoMetrics, demoSidebarCards } from "./demo-data";

export default function DemoDashboard() {
  const [selectedIncidentId, setSelectedIncidentId] = useState(
    demoIncidents[0]?.id ?? "",
  );

  const selectedIncident =
    demoIncidents.find((incident) => incident.id === selectedIncidentId) ??
    demoIncidents[0];

  return (
    <main className="demo-shell">
      <div className="demo-frame">
        <section className="demo-hero">
          <p className="demo-kicker">AI Reality Check Demo</p>
          <h1>AI failures, without the hype cycle</h1>
          <p className="demo-hero-copy">
            A reader-facing mock dashboard for calmly tracking documented AI
            failures, the public promises around them, and the operational
            standards required to publish responsibly.
          </p>

          <div className="demo-metrics">
            {demoMetrics.map((metric) => (
              <article className="demo-metric" key={metric.label}>
                <span className="demo-metric-label">{metric.label}</span>
                <strong className="demo-metric-value">{metric.value}</strong>
                <span>{metric.note}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="demo-grid">
          <aside className="demo-rail">
            <section className="demo-panel">
              <p className="demo-kicker">Reader filters</p>
              <h3>Mock taxonomy</h3>
              <div className="demo-filter-chips">
                <span className="demo-chip">Privacy/Security</span>
                <span className="demo-chip">Autonomous Systems</span>
                <span className="demo-chip">Missed Timelines</span>
                <span className="demo-chip">Severity 3+</span>
              </div>
            </section>

            {demoSidebarCards.map((card) => (
              <section className="demo-panel" key={card.title}>
                <p className="demo-kicker">{card.title}</p>
                <h3>{card.title}</h3>
                <p>{card.body}</p>
              </section>
            ))}
          </aside>

          <section className="demo-feed">
            <section className="demo-panel">
              <p className="demo-kicker">Latest incidents</p>
              <h2>Documented breakdowns</h2>

              {demoIncidents.map((incident) => {
                const isSelected = incident.id === selectedIncident.id;

                return (
                  <button
                    className={`demo-card-button${isSelected ? " is-selected" : ""}`}
                    key={incident.id}
                    type="button"
                    onClick={() => setSelectedIncidentId(incident.id)}
                    aria-pressed={isSelected}
                    aria-label={`Open incident detail for ${incident.headline}`}
                  >
                    <div className="demo-card-meta">
                      {incident.company} • {incident.date} • {incident.severity}
                    </div>
                    <h3>{incident.headline}</h3>
                    <p>{incident.summary}</p>
                    <div className="demo-tag-row">
                      {incident.categories.map((category) => (
                        <span className="demo-tag" key={category}>
                          {category}
                        </span>
                      ))}
                    </div>
                  </button>
                );
              })}
            </section>
          </section>

          <aside className="demo-sidebar">
            <section className="demo-panel">
              <p className="demo-kicker">Claim vs. reality</p>
              <h3>Spotlight</h3>
              <div className="demo-claim">
                <div className="demo-source-label">Claim vs. reality</div>
                <blockquote>“{demoIncidents[0].claimQuote}”</blockquote>
                <p>{demoIncidents[0].claimMeta}</p>
              </div>
            </section>

            <section className="demo-panel">
              <p className="demo-kicker">Source credibility</p>
              <h3>Publishing rule</h3>
              <p>
                Entries must link to accountable reporting or primary-source
                material. The feed favors fewer, better-documented incidents
                over broad automated coverage.
              </p>
            </section>
          </aside>
        </section>

        <section className="demo-spotlight">
          <p className="demo-kicker">Incident spotlight</p>
          <h2>Incident spotlight</h2>

          <div className="demo-spotlight-grid">
            <article className="demo-spotlight-card">
              <div className="demo-card-meta">
                {selectedIncident.company} • {selectedIncident.date} •{" "}
                {selectedIncident.severity}
              </div>
              <h3>{selectedIncident.headline}</h3>
              <p>{selectedIncident.summary}</p>
              <div className="demo-tag-row">
                {selectedIncident.categories.map((category) => (
                  <span className="demo-tag" key={category}>
                    {category}
                  </span>
                ))}
              </div>
            </article>

            <aside className="demo-panel">
              <p className="demo-kicker">Sources</p>
              <h3>Reference trail</h3>
              <p className="demo-source-label">
                {selectedIncident.sourceLabel}
              </p>
              <a className="demo-link" href={selectedIncident.sourceUrl}>
                {selectedIncident.sourceUrl}
              </a>
            </aside>
          </div>
        </section>
      </div>
    </main>
  );
}
