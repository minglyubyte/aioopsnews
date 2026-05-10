import type { ReaderLocale, ReaderTheme } from "./locale";

export const READER_LOCALE_STORAGE_KEY = "ai-reality-check-locale";
export const READER_THEME_STORAGE_KEY = "ai-reality-check-theme";

export function readStoredReaderLocale(): ReaderLocale {
  const storedLocale = window.localStorage.getItem(READER_LOCALE_STORAGE_KEY);
  return storedLocale === "zh" ? "zh" : "en";
}

export function readStoredReaderTheme(): ReaderTheme {
  const storedTheme = window.localStorage.getItem(READER_THEME_STORAGE_KEY);
  return storedTheme === "dark" ? "dark" : "light";
}
