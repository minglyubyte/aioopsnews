import { useEffect, useState } from "react";

import {
  PUBLIC_COPY,
  type ReaderLocale,
  type ReaderTheme,
} from "../lib/locale";
import { normalizeSiteUrl } from "../lib/publicIncidentRoutes";
import {
  READER_LOCALE_STORAGE_KEY,
  READER_THEME_STORAGE_KEY,
  readStoredReaderLocale,
  readStoredReaderTheme,
} from "../lib/publicReaderPreferences";
import PublicSiteFooter from "./PublicSiteFooter";
import "./public-dashboard.css";

const DETAIL_PAGE_BRAND = "AI Oops News";

export default function PublicDisclaimerPage() {
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
    const canonicalUrl = `${getCanonicalSiteUrl()}/disclaimer`;

    document.title = `${copy.disclaimerPageTitle} | ${DETAIL_PAGE_BRAND}`;
    setMetaDescription(copy.disclaimerPageIntro);
    setCanonicalLink(canonicalUrl);
    setRobotsMeta("noindex,follow");
    removeStructuredData();
  }, [copy.disclaimerPageIntro, copy.disclaimerPageTitle]);

  return (
    <main className="public-dashboard public-case-page" data-theme={readerTheme}>
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

        <section className="public-panel public-disclaimer-page">
          <p className="public-kicker">{copy.disclaimerPageKicker}</p>
          <h1>{copy.disclaimerPageTitle}</h1>
          <p className="case-dek">{copy.disclaimerPageIntro}</p>
          <div className="public-disclaimer-body">
            <p>{copy.disclaimerFullBody}</p>
          </div>
        </section>

        <PublicSiteFooter copy={copy} hideDisclaimerLink />
      </div>
    </main>
  );
}

function getCanonicalSiteUrl() {
  const configuredSiteUrl = import.meta.env.VITE_PUBLIC_SITE_URL;

  if (configuredSiteUrl?.trim()) {
    return normalizeSiteUrl(configuredSiteUrl);
  }

  return normalizeSiteUrl(window.location.origin);
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

function setRobotsMeta(content: string) {
  let robotsMeta = document.querySelector<HTMLMetaElement>(
    'meta[name="robots"]',
  );

  if (!robotsMeta) {
    robotsMeta = document.createElement("meta");
    robotsMeta.name = "robots";
    document.head.append(robotsMeta);
  }

  robotsMeta.content = content;
}

function removeStructuredData() {
  document
    .querySelector<HTMLScriptElement>('script[type="application/ld+json"]')
    ?.remove();
}
