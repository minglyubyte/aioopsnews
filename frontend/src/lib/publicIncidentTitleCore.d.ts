import type { PublicIncidentBase } from "../types/incident";
import type { ReaderLocale } from "./locale";

export const ENGLISH_TITLE_WORD_LIMIT: 14;
export const ENGLISH_TITLE_GRAPHEME_LIMIT: 90;
export const CHINESE_TITLE_GRAPHEME_LIMIT: 52;

export function buildOriginalIncidentTitle(
  incident: PublicIncidentBase,
  locale?: ReaderLocale,
): string;

export function buildIncidentDisplayTitle(
  incident: PublicIncidentBase,
  locale?: ReaderLocale,
): string;
