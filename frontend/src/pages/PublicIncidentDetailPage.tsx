import { useEffect, useState, type CSSProperties } from "react";

import { fetchIncidentDetail } from "../lib/api";
import {
  PUBLIC_COPY,
  type ReaderLocale,
  type ReaderTheme,
} from "../lib/locale";
import { useInView } from "../lib/useInView";
import { buildIncidentUrl } from "../lib/publicIncidentRoutes";
import { localizePublicCategory } from "../lib/publicDashboardLocalization";
import {
  READER_LOCALE_STORAGE_KEY,
  READER_THEME_STORAGE_KEY,
  readStoredReaderLocale,
  readStoredReaderTheme,
} from "../lib/publicReaderPreferences";
import type {
  IncidentAnalysis,
  IncidentDetail,
  IncidentSource,
} from "../types/incident";
import "./public-dashboard.css";

type PublicIncidentDetailPageProps = {
  incidentId: string;
};

type CaseMotionStyle = CSSProperties & {
  "--detail-index"?: number;
  "--source-index"?: number;
};

const DETAIL_PAGE_BRAND = "AI Oops News";

export default function PublicIncidentDetailPage({
  incidentId,
}: PublicIncidentDetailPageProps) {
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [readerLocale, setReaderLocale] = useState<ReaderLocale>(() =>
    readStoredReaderLocale(),
  );
  const [readerTheme, setReaderTheme] = useState<ReaderTheme>(() =>
    readStoredReaderTheme(),
  );
  const copy = PUBLIC_COPY[readerLocale];

  useEffect(() => {
    window.localStorage.setItem(READER_LOCALE_STORAGE_KEY, readerLocale);
  }, [readerLocale]);

  useEffect(() => {
    window.localStorage.setItem(READER_THEME_STORAGE_KEY, readerTheme);
  }, [readerTheme]);

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

    const canonicalUrl = buildIncidentUrl(incident, getCanonicalSiteUrl());
    const description =
      buildIncidentMetaDescription(incident, readerLocale) ?? copy.positioning;

    document.title = buildIncidentPageTitle(incident, readerLocale);
    setMetaDescription(description);
    setCanonicalLink(canonicalUrl);
    setStructuredData(
      buildIncidentStructuredData(incident, canonicalUrl, readerLocale),
    );
  }, [copy.brand, copy.positioning, incident, readerLocale]);

  return (
    <main
      className="public-dashboard public-case-page"
      data-theme={readerTheme}
    >
      <div className="case-shell">
        <header className="case-site-header">
          <a className="case-brand-link" href="/">
            {copy.brand}
          </a>
          <div className="case-header-actions">
            <div
              aria-label={copy.languageSwitchLabel}
              className="public-toggle-group"
              role="group"
            >
              <button
                aria-pressed={readerLocale === "en"}
                className={`public-toggle-button${readerLocale === "en" ? " is-active" : ""}`}
                onClick={() => setReaderLocale("en")}
                type="button"
              >
                English
              </button>
              <button
                aria-pressed={readerLocale === "zh"}
                className={`public-toggle-button${readerLocale === "zh" ? " is-active" : ""}`}
                onClick={() => setReaderLocale("zh")}
                type="button"
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
                onClick={() => setReaderTheme("light")}
                type="button"
              >
                {copy.lightTheme}
              </button>
              <button
                aria-pressed={readerTheme === "dark"}
                className={`public-toggle-button${readerTheme === "dark" ? " is-active" : ""}`}
                onClick={() => setReaderTheme("dark")}
                type="button"
              >
                {copy.darkTheme}
              </button>
            </div>
            <a className="case-back-link" href="/">
              {copy.detailBackToFeed}
            </a>
          </div>
        </header>

        {isLoading ? (
          <section className="case-loading-state">
            <p className="body-copy" aria-busy="true">
              {copy.detailLoading}
            </p>
          </section>
        ) : null}
        {error ? (
          <section className="case-loading-state">
            <p>{error}</p>
          </section>
        ) : null}
        {!isLoading && !error && incident ? (
          <IncidentCaseFile
            copy={copy}
            incident={incident}
            readerLocale={readerLocale}
          />
        ) : null}
      </div>
    </main>
  );
}

function IncidentCaseFile({
  copy,
  incident,
  readerLocale,
}: {
  copy: (typeof PUBLIC_COPY)[ReaderLocale];
  incident: IncidentDetail;
  readerLocale: ReaderLocale;
}) {
  const headline = getIncidentDisplayHeadline(incident, readerLocale);
  const description =
    buildIncidentMetaDescription(incident, readerLocale) ?? copy.positioning;
  const categories = incident.categories.map((category) =>
    localizePublicCategory(category, readerLocale),
  );
  const hasThinDetail = hasInsufficientDetail(incident);
  const [heroRef, heroInView] = useInView<HTMLElement>();
  const [articleRef, articleInView] = useInView<HTMLElement>();
  const [railRef, railInView] = useInView<HTMLElement>();
  const [sourceListRef, sourceListInView] = useInView<HTMLDivElement>();
  const [continueRef, continueInView] = useInView<HTMLElement>();

  return (
    <>
      <section
        ref={heroRef}
        className="case-hero"
        aria-labelledby="case-title"
        data-inview={heroInView ? "true" : "false"}
      >
        <p className="public-kicker">{copy.detailCaseKicker}</p>
        <h1 id="case-title">{headline}</h1>
        <p className="case-dek">{description}</p>
        <dl className="case-meta-strip" aria-label="Case metadata">
          <CaseMetaItem
            label={copy.detailCompanyLabel}
            value={localizedCompanyName(incident, readerLocale)}
          />
          <CaseMetaItem
            label={copy.detailDateLabel}
            value={formatDate(incident.date_logged, readerLocale)}
          />
          <CaseMetaItem
            label={copy.detailTrackLabel}
            value={trackLabel(incident.publication_track, readerLocale)}
          />
          <CaseMetaItem
            label={copy.detailEvidenceLabel}
            value={evidenceTierLabel(incident.evidence_tier, readerLocale)}
          />
        </dl>
        <div className="tag-row">
          {categories.map((category) => (
            <span className="tag" key={category}>
              {category}
            </span>
          ))}
          {incident.incident_topic ? (
            <span className="tag">{incident.incident_topic}</span>
          ) : null}
        </div>
      </section>

      <div className="case-layout">
        <article
          ref={articleRef}
          className="case-article"
          data-inview={articleInView ? "true" : "false"}
        >
          {hasThinDetail ? (
            <DetailBlock
              detailIndex={0}
              title={copy.officialDetailPendingTitle}
              value={
                incident.analysis.source_fact_summary ??
                copy.officialDetailPendingBody
              }
            />
          ) : (
            <>
              <DetailBlock
                detailIndex={0}
                title={copy.whatHappenedTitle}
                value={localizedAnalysisText(
                  incident.analysis,
                  "what_happened",
                  readerLocale,
                )}
              />
              <DetailBlock
                detailIndex={1}
                title={copy.aiFailurePointTitle}
                value={
                  localizedAnalysisText(
                    incident.analysis,
                    "ai_failure_point",
                    readerLocale,
                  ) ?? copy.aiFailurePointUnavailable
                }
              />
              <DetailBlock
                detailIndex={2}
                title={copy.whyItMattersTitle}
                value={localizedAnalysisText(
                  incident.analysis,
                  "why_it_matters",
                  readerLocale,
                )}
              />
            </>
          )}
          <DetailBlock
            detailIndex={hasThinDetail ? 1 : 3}
            title={copy.evidenceSummaryTitle}
            value={localizedAnalysisText(
              incident.analysis,
              "evidence_summary",
              readerLocale,
            )}
          />
        </article>

        <aside
          ref={railRef}
          className="case-rail"
          data-inview={railInView ? "true" : "false"}
        >
          <section className="case-rail-card">
            <p className="public-kicker">{copy.detailAtAGlanceTitle}</p>
            <dl className="case-fact-list">
              <CaseMetaItem
                label={copy.detailSeverityLabel}
                value={severityLabel(incident.severity_score, readerLocale)}
              />
              <CaseMetaItem
                label={copy.detailEvidenceLabel}
                value={evidenceTierLabel(incident.evidence_tier, readerLocale)}
              />
              <CaseMetaItem
                label={copy.detailTrackLabel}
                value={trackLabel(incident.publication_track, readerLocale)}
              />
              <CaseMetaItem
                label={copy.detailSourceFamilyLabel}
                value={sourceFamilyLabel(incident.source_family, readerLocale)}
              />
              <CaseMetaItem
                label={copy.detailSourceCountLabel}
                value={copy.detailSourceCount(incident.sources.length)}
              />
            </dl>
          </section>

          <section className="case-rail-card case-source-card">
            <p className="public-kicker">{copy.reportingTrailKicker}</p>
            <h2>{copy.primarySourceTrailTitle}</h2>
            <div
              ref={sourceListRef}
              className="public-source-list"
              data-inview={sourceListInView ? "true" : "false"}
            >
              {incident.sources.length === 0 ? (
                <p className="body-copy">{copy.noSources}</p>
              ) : (
                incident.sources.map((source, sourceIndex) => (
                  <article
                    className="public-source-item"
                    key={source.id}
                    style={
                      {
                        "--source-index": sourceIndex,
                      } as CaseMotionStyle
                    }
                  >
                    <p className="public-source-publisher">
                      {sourcePublisherLabel(source)}
                    </p>
                    <span className="public-source-type">
                      {sourceTypeLabel(source.source_type, readerLocale)}
                    </span>
                    <a href={source.source_url}>{sourceLinkLabel(source)}</a>
                  </article>
                ))
              )}
            </div>
          </section>
        </aside>
      </div>

      <section
        ref={continueRef}
        className="case-continue-panel"
        data-inview={continueInView ? "true" : "false"}
      >
        <p className="public-kicker">{copy.detailContinueKicker}</p>
        <h2>{copy.detailContinueTitle}</h2>
        <p className="body-copy">{copy.detailContinueBody}</p>
        <div className="public-related-actions">
          <a className="secondary-action" href="/">
            {copy.detailBackToFeed}
          </a>
          <span className="tag">{copy.detailSameCompanyPlaceholder}</span>
          <span className="tag">{copy.detailRecentPlaceholder}</span>
          {categories.map((category) => (
            <span className="tag" key={category}>
              {category}
            </span>
          ))}
        </div>
      </section>
    </>
  );
}

function getCanonicalSiteUrl() {
  const configuredSiteUrl = import.meta.env.VITE_PUBLIC_SITE_URL;

  if (configuredSiteUrl?.trim()) {
    return configuredSiteUrl;
  }

  return window.location.origin;
}

function CaseMetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="case-meta-item">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function DetailBlock({
  detailIndex,
  title,
  value,
}: {
  detailIndex?: number;
  title: string;
  value: string | null;
}) {
  if (!value) {
    return null;
  }

  return (
    <section
      className="case-detail-block"
      style={
        detailIndex === undefined
          ? undefined
          : ({
              "--detail-index": detailIndex,
            } as CaseMotionStyle)
      }
    >
      <p className="public-claim-kicker">{title}</p>
      <p>{value}</p>
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
  locale: ReaderLocale,
) {
  const localizedKey = `${key}_${locale}` as keyof IncidentAnalysis;
  const englishKey = `${key}_en` as keyof IncidentAnalysis;
  const baseKey = key as keyof IncidentAnalysis;

  if (locale === "zh") {
    return firstNonBlankText(
      analysis[localizedKey],
      analysis[englishKey],
      analysis[baseKey],
    );
  }

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

function sourcePublisherLabel(source: IncidentSource) {
  return (
    firstNonBlankText(
      source.publisher,
      sourceHostLabel(source.source_url),
      source.source_type,
    ) ?? "Source"
  );
}

function sourceLinkLabel(source: IncidentSource) {
  return (
    firstNonBlankText(
      source.title,
      readableSourceUrl(source.source_url),
      source.source_url,
    ) ?? "Source link"
  );
}

function sourceHostLabel(sourceUrl: string) {
  try {
    return new URL(sourceUrl).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

function readableSourceUrl(sourceUrl: string) {
  try {
    const url = new URL(sourceUrl);
    const hostname = url.hostname.replace(/^www\./, "");
    return `${hostname}${url.pathname}${url.search}`;
  } catch {
    return sourceUrl;
  }
}

export function getIncidentDisplayHeadline(
  incident: IncidentDetail,
  locale: ReaderLocale = "en",
) {
  if (locale === "zh") {
    return incident.headline_zh ?? incident.headline_en ?? incident.headline;
  }

  return incident.headline_en ?? incident.headline;
}

function localizedCompanyName(incident: IncidentDetail, locale: ReaderLocale) {
  if (locale === "zh") {
    return incident.company_involved_zh ?? incident.company_involved;
  }

  return incident.company_involved;
}

export function buildIncidentMetaDescription(
  incident: IncidentDetail,
  locale: ReaderLocale = "en",
) {
  if (locale === "zh") {
    return firstNonBlankText(
      incident.analysis.incident_summary_zh,
      incident.reality_summary_zh,
      incident.analysis.incident_summary_en,
      incident.reality_summary_en,
      incident.reality_summary,
    );
  }

  return firstNonBlankText(
    incident.analysis.incident_summary_en,
    incident.reality_summary_en,
    incident.reality_summary,
  );
}

export function buildIncidentPageTitle(
  incident: IncidentDetail,
  locale: ReaderLocale = "en",
) {
  return `${getIncidentDisplayHeadline(incident, locale)} | ${DETAIL_PAGE_BRAND}`;
}

function hasInsufficientDetail(incident: IncidentDetail) {
  return (
    incident.source_family === "autonomous_vehicle" &&
    incident.analysis.detail_quality === "insufficient"
  );
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

const SOURCE_TYPE_LABELS_ZH: Record<string, string> = {
  article: "报道来源",
  court: "法院来源",
  imported: "导入来源",
  official: "官方来源",
  regulator: "监管来源",
};

function severityLabel(severity: number, locale: ReaderLocale) {
  if (locale === "zh") {
    return `严重级别 ${severity}`;
  }

  return `Severity ${severity}`;
}

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

function sourceTypeLabel(sourceType: string, locale: ReaderLocale) {
  if (locale === "zh") {
    return (
      SOURCE_TYPE_LABELS_ZH[sourceType] ??
      `${humanizeSnakeCase(sourceType)} 来源`
    );
  }

  return `${humanizeSnakeCase(sourceType)} source`;
}

function humanizeSnakeCase(value: string) {
  const spaced = value.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function formatDate(dateValue: string, locale: ReaderLocale) {
  return new Intl.DateTimeFormat(PUBLIC_COPY[locale].dateLocale, {
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

function setCanonicalLink(href: string) {
  let canonicalLink = document.querySelector<HTMLLinkElement>(
    'link[rel="canonical"]',
  );

  if (!canonicalLink) {
    canonicalLink = document.createElement("link");
    canonicalLink.rel = "canonical";
    document.head.append(canonicalLink);
  }

  canonicalLink.href = href;
}

function setStructuredData(data: Record<string, unknown>) {
  let structuredData = document.querySelector<HTMLScriptElement>(
    'script[type="application/ld+json"]',
  );

  if (!structuredData) {
    structuredData = document.createElement("script");
    structuredData.type = "application/ld+json";
    document.head.append(structuredData);
  }

  structuredData.textContent = JSON.stringify(data);
}

function buildIncidentStructuredData(
  incident: IncidentDetail,
  canonicalUrl: string,
  locale: ReaderLocale,
) {
  const headline = getIncidentDisplayHeadline(incident, locale);
  const description =
    buildIncidentMetaDescription(incident, locale) ?? headline;

  return {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline,
    description,
    datePublished: incident.date_logged,
    dateModified: incident.date_logged,
    mainEntityOfPage: canonicalUrl,
    isAccessibleForFree: true,
    author: {
      "@type": "Organization",
      name: "AI Reality Check",
    },
    publisher: {
      "@type": "Organization",
      name: "AI Reality Check",
    },
    about: incident.categories,
    citation: incident.sources.map((source) => source.source_url),
  };
}
