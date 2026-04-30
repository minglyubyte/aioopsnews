import { useEffect, useState } from "react";

import "./demo.css";
import {
  demoIncidents,
  demoMetrics,
  demoPageCopy,
  demoSidebarCards,
} from "./demo-data";
import type {
  DemoIncident,
  DemoLocale,
  LocalizedText,
} from "./demo-types";

type DemoTheme = "light" | "dark";
type DemoSignalPoint = {
  monthKey: string;
  label: string;
  count: number;
};
type DemoSignalSegment = {
  label: string;
  count: number;
  percentage: number;
  color: string;
};

const DEMO_THEME_STORAGE_KEY = "ai-oops-demo-theme";
const DEMO_LOCALE_STORAGE_KEY = "ai-oops-demo-locale";
const DEMO_SIGNAL_COLORS = [
  "#8a3b26",
  "#274b63",
  "#8a6a2a",
  "#5e7041",
  "#6f4b7e",
  "#405061",
];

function readDemoTheme(): DemoTheme {
  const storedTheme = window.localStorage.getItem(DEMO_THEME_STORAGE_KEY);

  if (storedTheme === "light" || storedTheme === "dark") {
    return storedTheme;
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function readDemoLocale(): DemoLocale {
  return window.localStorage.getItem(DEMO_LOCALE_STORAGE_KEY) === "zh"
    ? "zh"
    : "en";
}

function copyForLocale(locale: DemoLocale, text: LocalizedText): string {
  return text[locale];
}

function monthLabelForLocale(locale: DemoLocale, monthKey: string): string {
  return new Intl.DateTimeFormat(locale === "zh" ? "zh-CN" : "en-US", {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${monthKey}-01T00:00:00Z`));
}

function buildDemoSignalPoints(
  incidents: DemoIncident[],
  locale: DemoLocale,
): DemoSignalPoint[] {
  const monthCounts = new Map<string, number>();

  for (const incident of incidents) {
    const monthKey = incident.dateLogged.slice(0, 7);
    monthCounts.set(monthKey, (monthCounts.get(monthKey) ?? 0) + 1);
  }

  return Array.from(monthCounts.entries())
    .sort(([leftMonth], [rightMonth]) => leftMonth.localeCompare(rightMonth))
    .map(([monthKey, count]) => ({
      monthKey,
      count,
      label: monthLabelForLocale(locale, monthKey),
    }));
}

function buildDemoSignalSegments(
  incidents: DemoIncident[],
  locale: DemoLocale,
): DemoSignalSegment[] {
  const categoryCounts = new Map<string, number>();

  for (const incident of incidents) {
    for (const category of incident.categories) {
      const label = copyForLocale(locale, category);
      categoryCounts.set(label, (categoryCounts.get(label) ?? 0) + 1);
    }
  }

  const total = Array.from(categoryCounts.values()).reduce(
    (runningTotal, count) => runningTotal + count,
    0,
  );

  return Array.from(categoryCounts.entries())
    .sort(([leftLabel, leftCount], [rightLabel, rightCount]) => {
      if (leftCount !== rightCount) {
        return rightCount - leftCount;
      }

      return leftLabel.localeCompare(rightLabel);
    })
    .map(([label, count], index) => ({
      label,
      count,
      percentage: total === 0 ? 0 : Math.round((count / total) * 100),
      color: DEMO_SIGNAL_COLORS[index % DEMO_SIGNAL_COLORS.length],
    }));
}

function buildDemoDonutStyle(segments: DemoSignalSegment[]): string {
  if (segments.length === 0) {
    return "conic-gradient(rgba(23, 38, 58, 0.12) 0deg 360deg)";
  }

  let currentAngle = 0;
  const stops = segments.map((segment) => {
    const start = currentAngle;
    const next = currentAngle + segment.percentage * 3.6;
    currentAngle = next;
    return `${segment.color} ${start}deg ${next}deg`;
  });

  if (currentAngle < 360) {
    stops.push(`${segments[segments.length - 1].color} ${currentAngle}deg 360deg`);
  }

  return `conic-gradient(${stops.join(", ")})`;
}

export default function DemoDashboard() {
  const [selectedIncidentId, setSelectedIncidentId] = useState(
    demoIncidents[0]?.id ?? "",
  );
  const [theme, setTheme] = useState<DemoTheme>(() => readDemoTheme());
  const [locale, setLocale] = useState<DemoLocale>(() => readDemoLocale());

  const selectedIncident =
    demoIncidents.find((incident) => incident.id === selectedIncidentId) ??
    demoIncidents[0];
  const signalPoints = buildDemoSignalPoints(demoIncidents, locale);
  const signalSegments = buildDemoSignalSegments(demoIncidents, locale);
  const maxSignalCount = Math.max(...signalPoints.map((point) => point.count), 1);

  useEffect(() => {
    window.localStorage.setItem(DEMO_THEME_STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    window.localStorage.setItem(DEMO_LOCALE_STORAGE_KEY, locale);
  }, [locale]);

  return (
    <main className="demo-shell" data-theme={theme}>
      <div className="demo-frame">
        <section className="demo-hero">
          <div className="demo-hero-topbar">
            <p className="demo-kicker">
              {copyForLocale(locale, demoPageCopy.heroKicker)}
            </p>

            <div className="demo-utility-cluster">
              <div
                aria-label="Demo language switch"
                className="demo-toggle-group"
                role="group"
              >
                <button
                  aria-pressed={locale === "en"}
                  className={`demo-toggle-button${locale === "en" ? " is-active" : ""}`}
                  type="button"
                  onClick={() => setLocale("en")}
                >
                  English
                </button>
                <button
                  aria-pressed={locale === "zh"}
                  className={`demo-toggle-button${locale === "zh" ? " is-active" : ""}`}
                  type="button"
                  onClick={() => setLocale("zh")}
                >
                  中文
                </button>
              </div>

              <div
                aria-label="Demo theme switch"
                className="demo-toggle-group"
                role="group"
              >
                <button
                  aria-pressed={theme === "light"}
                  className={`demo-toggle-button${theme === "light" ? " is-active" : ""}`}
                  type="button"
                  onClick={() => setTheme("light")}
                >
                  Light
                </button>
                <button
                  aria-pressed={theme === "dark"}
                  className={`demo-toggle-button${theme === "dark" ? " is-active" : ""}`}
                  type="button"
                  onClick={() => setTheme("dark")}
                >
                  Dark
                </button>
              </div>
            </div>
          </div>

          <h1>{copyForLocale(locale, demoPageCopy.heroTitle)}</h1>
          <p className="demo-hero-copy">
            {copyForLocale(locale, demoPageCopy.heroCopy)}
          </p>

          <div className="demo-metrics">
            {demoMetrics.map((metric) => (
              <article className="demo-metric" key={metric.label.en}>
                <span className="demo-metric-label">
                  {copyForLocale(locale, metric.label)}
                </span>
                <strong className="demo-metric-value">
                  {copyForLocale(locale, metric.value)}
                </strong>
                <span>{copyForLocale(locale, metric.note)}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="demo-signals">
          <div className="demo-signals-header">
            <div>
              <p className="demo-kicker">
                {copyForLocale(locale, demoPageCopy.signalsKicker)}
              </p>
              <h2>{copyForLocale(locale, demoPageCopy.signalsTitle)}</h2>
            </div>
            <p className="demo-signals-note">
              {copyForLocale(locale, demoPageCopy.signalsMonthlyNote)}
            </p>
          </div>

          <div className="demo-signals-grid">
            <article className="demo-signal-panel">
              <p className="demo-kicker">
                {copyForLocale(locale, demoPageCopy.signalsMonthlyKicker)}
              </p>
              <h3>{copyForLocale(locale, demoPageCopy.signalsMonthlyTitle)}</h3>
              {signalPoints.length < 2 ? (
                <p className="demo-signal-copy">
                  {copyForLocale(locale, demoPageCopy.signalsMonthlyFallback)}
                </p>
              ) : null}
              <ol
                aria-label={copyForLocale(locale, demoPageCopy.signalsMonthlyTitle)}
                className="demo-signal-list"
              >
                {signalPoints.map((point) => (
                  <li className="demo-signal-row" key={point.monthKey}>
                    <div className="demo-signal-meta">
                      <span>{point.label}</span>
                      <span>
                        {point.count}{" "}
                        {locale === "zh"
                          ? "起事件"
                          : point.count === 1
                            ? "incident"
                            : "incidents"}
                      </span>
                    </div>
                    <div aria-hidden="true" className="demo-signal-track">
                      <div
                        className="demo-signal-bar"
                        style={{
                          width: `${Math.max(
                            (point.count / maxSignalCount) * 100,
                            18,
                          )}%`,
                        }}
                      />
                    </div>
                  </li>
                ))}
              </ol>
            </article>

            <article className="demo-signal-panel">
              <p className="demo-kicker">
                {copyForLocale(locale, demoPageCopy.signalsCategoryKicker)}
              </p>
              <h3>{copyForLocale(locale, demoPageCopy.signalsCategoryTitle)}</h3>
              <p className="demo-signal-copy">
                {copyForLocale(locale, demoPageCopy.signalsCategoryNote)}
              </p>
              <div className="demo-signal-distribution">
                <div
                  aria-label={copyForLocale(locale, demoPageCopy.signalsDonutLabel)}
                  className="demo-donut"
                  role="img"
                  style={{
                    backgroundImage: buildDemoDonutStyle(signalSegments),
                  }}
                >
                  <div className="demo-donut-core">
                    <strong>{demoIncidents.length}</strong>
                    <span>
                      {locale === "zh"
                        ? "演示事件"
                        : demoIncidents.length === 1
                          ? "incident"
                          : "incidents"}
                    </span>
                  </div>
                </div>

                <ul className="demo-distribution-list">
                  {signalSegments.map((segment) => (
                    <li className="demo-distribution-item" key={segment.label}>
                      <span
                        aria-hidden="true"
                        className="demo-distribution-swatch"
                        style={{ backgroundColor: segment.color }}
                      />
                      <span>{segment.label}</span>
                      <span>{segment.count}</span>
                      <span>{segment.percentage}%</span>
                    </li>
                  ))}
                </ul>
              </div>
            </article>
          </div>
        </section>

        <section className="demo-grid">
          <aside className="demo-rail">
            <section className="demo-panel">
              <p className="demo-kicker">
                {copyForLocale(locale, demoPageCopy.filterKicker)}
              </p>
              <h3>{copyForLocale(locale, demoPageCopy.filterTitle)}</h3>
              <div className="demo-filter-chips">
                {demoPageCopy.filterChips.map((chip) => (
                  <span className="demo-chip" key={chip.en}>
                    {copyForLocale(locale, chip)}
                  </span>
                ))}
              </div>
            </section>

            {demoSidebarCards.map((card) => (
              <section className="demo-panel" key={card.title.en}>
                <p className="demo-kicker">
                  {copyForLocale(locale, card.title)}
                </p>
                <h3>{copyForLocale(locale, card.title)}</h3>
                <p>{copyForLocale(locale, card.body)}</p>
              </section>
            ))}
          </aside>

          <section className="demo-feed">
            <section className="demo-panel">
              <p className="demo-kicker">
                {copyForLocale(locale, demoPageCopy.latestKicker)}
              </p>
              <h2>{copyForLocale(locale, demoPageCopy.latestTitle)}</h2>

              {demoIncidents.map((incident) => {
                const isSelected = incident.id === selectedIncident.id;
                const localizedHeadline = copyForLocale(
                  locale,
                  incident.headline,
                );

                return (
                  <button
                    aria-label={`Open incident detail for ${localizedHeadline}`}
                    aria-pressed={isSelected}
                    className={`demo-card-button${isSelected ? " is-selected" : ""}`}
                    key={incident.id}
                    type="button"
                    onClick={() => setSelectedIncidentId(incident.id)}
                  >
                    <div className="demo-card-meta">
                      {incident.company} •{" "}
                      {copyForLocale(locale, incident.date)} •{" "}
                      {copyForLocale(locale, incident.severity)}
                    </div>
                    <h3>{localizedHeadline}</h3>
                    <p>{copyForLocale(locale, incident.summary)}</p>
                    <div className="demo-tag-row">
                      {incident.categories.map((category) => (
                        <span className="demo-tag" key={category.en}>
                          {copyForLocale(locale, category)}
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
              <p className="demo-kicker">
                {copyForLocale(locale, demoPageCopy.claimKicker)}
              </p>
              <h3>{copyForLocale(locale, demoPageCopy.claimTitle)}</h3>
              <div className="demo-claim">
                <div className="demo-source-label">
                  {copyForLocale(locale, demoPageCopy.claimLabel)}
                </div>
                <blockquote>
                  “{copyForLocale(locale, demoIncidents[0].claimQuote!)}”
                </blockquote>
                <p>{copyForLocale(locale, demoIncidents[0].claimMeta!)}</p>
              </div>
            </section>

            <section className="demo-panel">
              <p className="demo-kicker">
                {copyForLocale(locale, demoPageCopy.sourceCredibilityKicker)}
              </p>
              <h3>
                {copyForLocale(locale, demoPageCopy.sourceCredibilityTitle)}
              </h3>
              <p>{copyForLocale(locale, demoPageCopy.sourceCredibilityBody)}</p>
            </section>
          </aside>
        </section>

        <section className="demo-spotlight">
          <p className="demo-kicker">
            {copyForLocale(locale, demoPageCopy.spotlightKicker)}
          </p>
          <h2>{copyForLocale(locale, demoPageCopy.spotlightTitle)}</h2>

          <div className="demo-spotlight-grid">
            <article className="demo-spotlight-card">
              <div className="demo-card-meta">
                {selectedIncident.company} •{" "}
                {copyForLocale(locale, selectedIncident.date)} •{" "}
                {copyForLocale(locale, selectedIncident.severity)}
              </div>
              <h3>{copyForLocale(locale, selectedIncident.headline)}</h3>
              <p>{copyForLocale(locale, selectedIncident.summary)}</p>
              <div className="demo-tag-row">
                {selectedIncident.categories.map((category) => (
                  <span className="demo-tag" key={category.en}>
                    {copyForLocale(locale, category)}
                  </span>
                ))}
              </div>
            </article>

            <aside className="demo-panel">
              <p className="demo-kicker">
                {copyForLocale(locale, demoPageCopy.spotlightSourcesKicker)}
              </p>
              <h3>
                {copyForLocale(locale, demoPageCopy.spotlightSourcesTitle)}
              </h3>
              <p className="demo-source-label">
                {copyForLocale(locale, selectedIncident.sourceLabel)}
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
