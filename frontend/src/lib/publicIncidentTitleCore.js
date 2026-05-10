export const ENGLISH_TITLE_WORD_LIMIT = 14;
export const ENGLISH_TITLE_GRAPHEME_LIMIT = 90;
export const CHINESE_TITLE_GRAPHEME_LIMIT = 52;

const ELLIPSIS = "...";

export function buildOriginalIncidentTitle(incident, locale = "en") {
  if (locale === "zh") {
    return firstNonBlankText(
      incident.headline_zh,
      incident.headline_en,
      incident.headline,
    );
  }

  return firstNonBlankText(
    incident.headline_en,
    incident.headline,
    incident.headline_zh,
  );
}

export function buildIncidentDisplayTitle(incident, locale = "en") {
  const originalTitle = buildOriginalIncidentTitle(incident, locale);
  const legalCaseName = shouldUseLegalCaseTitle(incident, originalTitle)
    ? extractLegalCaseName(originalTitle)
    : null;

  if (legalCaseName) {
    return locale === "zh"
      ? `AI 法律幻觉：${legalCaseName}`
      : `AI legal hallucination: ${legalCaseName}`;
  }

  const cleanedTitle = stripLongEnumerations(originalTitle, locale);

  return locale === "zh"
    ? clampGraphemes(cleanedTitle, CHINESE_TITLE_GRAPHEME_LIMIT, locale)
    : clampEnglishTitle(cleanedTitle);
}

function firstNonBlankText(...values) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }

  return "Incident";
}

function shouldUseLegalCaseTitle(incident, title) {
  return (
    incident.source_family === "legal_hallucination" ||
    /legal hallucination/i.test(title) ||
    /法律幻觉|AI幻觉|AI\s*法律幻觉/i.test(title)
  );
}

function extractLegalCaseName(title) {
  const normalizedTitle = normalizeWhitespace(title);
  const chineseRecordMatch = normalizedTitle.match(/记录\s*([^，。]+?)案(?:[，。]|$)/);

  if (chineseRecordMatch?.[1]) {
    return cleanChineseCaseName(chineseRecordMatch[1]);
  }

  const recordsIndex = normalizedTitle.toLowerCase().indexOf("records ");
  if (recordsIndex === -1) {
    return null;
  }

  const candidate = normalizedTitle.slice(recordsIndex + "records ".length);
  const stopIndex = findLegalCaseStopIndex(candidate);
  const caseName =
    stopIndex === -1 ? candidate : candidate.slice(0, stopIndex).trim();

  return cleanCaseName(caseName);
}

function findLegalCaseStopIndex(value) {
  const lowerValue = value.toLowerCase();
  const stopPhrases = [
    " in ca ",
    " in sc ",
    " in n.d",
    " in s.d",
    " in e.d",
    " in w.d",
    " in c.d",
    " in m.d",
    " in d.",
    " in high court",
    " in family court",
    " in supreme court",
    " with ",
    " linked ",
    ". nature:",
    " nature:",
    ". outcome:",
    " outcome:",
  ];
  const indexes = stopPhrases
    .map((phrase) => lowerValue.indexOf(phrase))
    .filter((index) => index > 3);

  return indexes.length ? Math.min(...indexes) : -1;
}

function cleanCaseName(value) {
  const caseName = normalizeWhitespace(value)
    .replace(/^[：:\-\s]+/, "")
    .replace(/[，。;:\-\s]+$/g, "")
    .trim();

  return caseName || null;
}

function cleanChineseCaseName(value) {
  const rawCaseName = normalizeWhitespace(value);
  const lawsuitSeparatorIndex = rawCaseName.lastIndexOf("诉");

  if (lawsuitSeparatorIndex === -1) {
    return cleanCaseName(rawCaseName);
  }

  const leftParty = cleanChineseLeftParty(
    rawCaseName.slice(0, lawsuitSeparatorIndex),
  );
  const rightParty = rawCaseName.slice(lawsuitSeparatorIndex + 1);

  return cleanCaseName(`${leftParty} v. ${rightParty}`);
}

function cleanChineseLeftParty(value) {
  const withoutCourtPrefix = value.replace(/^.*(?:法院|法庭|仲裁庭|委员会)/u, "");
  const latinSuffix = withoutCourtPrefix.match(
    /[A-Za-z0-9][A-Za-z0-9 .,'&()/-]*$/u,
  )?.[0];

  return latinSuffix ?? withoutCourtPrefix;
}

function stripLongEnumerations(title, locale) {
  const cleanedTitle = normalizeWhitespace(title)
    .replace(
      /\s+(Nature|Outcome|Hallucination Details|Ruling\/Sanction|AI Use|Key Judicial Reasoning):[\s\S]*$/i,
      "",
    )
    .replace(/\s*(性质：|结果：|幻觉细节：|裁定\/制裁：)[\s\S]*$/u, "")
    .trim();

  return cleanedTitle || buildFallbackTitle(locale);
}

function buildFallbackTitle(locale) {
  return locale === "zh" ? "AI 事件" : "AI incident";
}

function clampEnglishTitle(title) {
  const words = normalizeWhitespace(title).split(" ").filter(Boolean);
  const wordTrimmed =
    words.length > ENGLISH_TITLE_WORD_LIMIT
      ? `${words.slice(0, ENGLISH_TITLE_WORD_LIMIT).join(" ")}${ELLIPSIS}`
      : words.join(" ");

  if (
    graphemeLength(wordTrimmed, "en") <= ENGLISH_TITLE_GRAPHEME_LIMIT ||
    words.length === 0
  ) {
    return wordTrimmed;
  }

  const limitedWords = [];
  for (const word of words.slice(0, ENGLISH_TITLE_WORD_LIMIT)) {
    const nextTitle = [...limitedWords, word].join(" ");
    if (
      graphemeLength(`${nextTitle}${ELLIPSIS}`, "en") >
      ENGLISH_TITLE_GRAPHEME_LIMIT
    ) {
      break;
    }
    limitedWords.push(word);
  }

  return limitedWords.length
    ? `${limitedWords.join(" ")}${ELLIPSIS}`
    : clampGraphemes(wordTrimmed, ENGLISH_TITLE_GRAPHEME_LIMIT, "en");
}

function clampGraphemes(value, limit, locale) {
  const graphemes = splitGraphemes(normalizeWhitespace(value), locale);

  if (graphemes.length <= limit) {
    return graphemes.join("");
  }

  return `${graphemes.slice(0, Math.max(limit - ELLIPSIS.length, 1)).join("").trimEnd()}${ELLIPSIS}`;
}

function graphemeLength(value, locale) {
  return splitGraphemes(value, locale).length;
}

function splitGraphemes(value, locale) {
  if (typeof Intl !== "undefined" && "Segmenter" in Intl) {
    return [
      ...new Intl.Segmenter(locale, { granularity: "grapheme" }).segment(value),
    ].map((segment) => segment.segment);
  }

  return Array.from(value);
}

function normalizeWhitespace(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}
