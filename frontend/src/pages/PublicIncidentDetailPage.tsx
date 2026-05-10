import { useEffect, useState } from "react";

import { fetchIncidentDetail } from "../lib/api";
import { PUBLIC_COPY } from "../lib/locale";
import type { IncidentAnalysis, IncidentDetail } from "../types/incident";
import "./public-dashboard.css";

type PublicIncidentDetailPageProps = {
  incidentId: string;
};

export default function PublicIncidentDetailPage({
  incidentId,
}: PublicIncidentDetailPageProps) {
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const copy = PUBLIC_COPY.en;

  useEffect(() => {
    let isCancelled = false;

    async function loadIncident() {
      setIsLoading(true);
      setError(null);

      try {
        const detail = await fetchIncidentDetail(incidentId);

        if (!isCancelled) {
          setIncident(detail);
        }
      } catch {
        if (!isCancelled) {
          setIncident(null);
          setError(copy.detailError);
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadIncident();

    return () => {
      isCancelled = true;
    };
  }, [copy.detailError, incidentId]);

  useEffect(() => {
    if (!incident) {
      document.title = `${copy.brand} | Incident`;
      setMetaDescription(copy.positioning);
      return;
    }

    document.title = `${incident.headline_en ?? incident.headline} | ${
      copy.brand
    }`;
    setMetaDescription(
      firstNonBlankText(
        incident.analysis.incident_summary_en,
        incident.reality_summary_en,
        incident.reality_summary,
      ) ?? copy.positioning,
    );
  }, [copy.brand, copy.positioning, incident]);

  return (
    <main className="public-dashboard" data-theme="light">
      <div className="public-frame">
        <section className="public-panel public-detail-section">
          <div className="section-header">
            <p className="public-kicker">{copy.detailKicker}</p>
            <h1>{copy.detailTitle}</h1>
          </div>

          {isLoading ? (
            <p className="body-copy" aria-busy="true">
              {copy.detailLoading}
            </p>
          ) : null}
          {error ? <p>{error}</p> : null}
          {!isLoading && !error && incident ? (
            <div className="public-detail-grid">
              <article className="public-incident-card public-detail-card">
                <div className="incident-meta">
                  <span>{incident.company_involved}</span>
                  <span>{severityLabel(incident.severity_score)}</span>
                  <span>{formatDate(incident.date_logged)}</span>
                </div>
                <h2>{incident.headline_en ?? incident.headline}</h2>
                <p className="body-copy">
                  {firstNonBlankText(
                    incident.analysis.incident_summary_en,
                    incident.reality_summary_en,
                    incident.reality_summary,
                  )}
                </p>
                <div className="tag-row">
                  {incident.categories.map((category) => (
                    <span className="tag" key={category}>
                      {category}
                    </span>
                  ))}
                </div>
                <DetailBlock
                  title={copy.whatHappenedTitle}
                  value={localizedAnalysisText(
                    incident.analysis,
                    "what_happened",
                  )}
                />
                <DetailBlock
                  title={copy.aiFailurePointTitle}
                  value={
                    localizedAnalysisText(
                      incident.analysis,
                      "ai_failure_point",
                    ) ?? copy.aiFailurePointUnavailable
                  }
                />
                <DetailBlock
                  title={copy.whyItMattersTitle}
                  value={localizedAnalysisText(
                    incident.analysis,
                    "why_it_matters",
                  )}
                />
                <DetailBlock
                  title={copy.evidenceSummaryTitle}
                  value={localizedAnalysisText(
                    incident.analysis,
                    "evidence_summary",
                  )}
                />
              </article>

              <aside className="public-panel public-source-panel">
                <p className="public-kicker">{copy.reportingTrailKicker}</p>
                <h2>{copy.primarySourceTrailTitle}</h2>
                <div className="public-source-list">
                  {incident.sources.length === 0 ? (
                    <p className="body-copy">{copy.noSources}</p>
                  ) : (
                    incident.sources.map((source) => (
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
        </section>
      </div>
    </main>
  );
}

function DetailBlock({
  title,
  value,
}: {
  title: string;
  value: string | null;
}) {
  if (!value) {
    return null;
  }

  return (
    <section className="public-detail-block">
      <p className="public-claim-kicker">{title}</p>
      <p className="body-copy">{value}</p>
    </section>
  );
}

function localizedAnalysisText(
  analysis: IncidentAnalysis,
  key:
    | "incident_summary"
    | "what_happened"
    | "ai_failure_point"
    | "why_it_matters"
    | "evidence_summary",
) {
  const englishKey = `${key}_en` as keyof IncidentAnalysis;
  const baseKey = key as keyof IncidentAnalysis;

  return firstNonBlankText(analysis[englishKey], analysis[baseKey]);
}

function firstNonBlankText(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }

  return null;
}

function severityLabel(severity: number) {
  return `Severity ${severity}`;
}

function formatDate(dateValue: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(`${dateValue}T00:00:00Z`));
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
