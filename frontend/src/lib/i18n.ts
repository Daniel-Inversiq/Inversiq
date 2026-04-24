import enCatalog from "../i18n/en.json";
import nlCatalog from "../i18n/nl.json";

type CatalogValue = string | { [key: string]: CatalogValue };
type Catalog = { [key: string]: CatalogValue };
type SupportedLanguage = "en" | "nl";
type TranslationValues = Record<string, string | number>;

const DEFAULT_LANGUAGE: SupportedLanguage = "en";
const SUPPORTED_LANGUAGES = new Set<SupportedLanguage>(["en", "nl"]);

const catalogs: Record<SupportedLanguage, Catalog> = {
  en: enCatalog as Catalog,
  nl: nlCatalog as Catalog,
};

function normalizeLanguage(raw: string | null | undefined): SupportedLanguage | null {
  if (!raw) {
    return null;
  }

  const base = raw.toLowerCase().split(",")[0]?.split("-")[0]?.split("_")[0]?.trim();
  if (!base) {
    return null;
  }

  return SUPPORTED_LANGUAGES.has(base as SupportedLanguage)
    ? (base as SupportedLanguage)
    : null;
}

function getCookieLanguage(): SupportedLanguage | null {
  if (typeof document === "undefined") {
    return null;
  }

  const match = document.cookie.match(/(?:^|;\s*)lang=([^;]+)/);
  if (!match?.[1]) {
    return null;
  }

  return normalizeLanguage(decodeURIComponent(match[1]));
}

function getBrowserLanguage(): SupportedLanguage | null {
  if (typeof navigator === "undefined") {
    return null;
  }
  return normalizeLanguage(navigator.language);
}

export function getPreferredLanguage(): SupportedLanguage {
  return getCookieLanguage() ?? getBrowserLanguage() ?? DEFAULT_LANGUAGE;
}

function lookupKey(catalog: Catalog, key: string): string | null {
  let current: CatalogValue | undefined = catalog;

  for (const part of key.split(".")) {
    if (!current || typeof current === "string" || !(part in current)) {
      return null;
    }
    current = current[part];
  }

  return typeof current === "string" ? current : null;
}

function interpolate(template: string, values?: TranslationValues): string {
  if (!values) {
    return template;
  }

  return template.replace(/\{(\w+)\}/g, (fullMatch, token: string) => {
    const replacement = values[token];
    return replacement === undefined || replacement === null
      ? fullMatch
      : String(replacement);
  });
}

export function t(
  key: string,
  values?: TranslationValues,
  language?: string,
): string {
  const selectedLanguage = normalizeLanguage(language) ?? getPreferredLanguage();

  const text =
    lookupKey(catalogs[selectedLanguage], key) ??
    lookupKey(catalogs[DEFAULT_LANGUAGE], key) ??
    key;

  return interpolate(text, values);
}

export function getNumberLocale(language?: string): string {
  const selectedLanguage = normalizeLanguage(language) ?? getPreferredLanguage();
  return selectedLanguage === "nl" ? "nl-NL" : "en-US";
}

/** Locale string for `Intl` date formatting (matches preferred UI language). */
export function getDateLocale(language?: string): string {
  const selectedLanguage = normalizeLanguage(language) ?? getPreferredLanguage();
  return selectedLanguage === "nl" ? "nl-NL" : "en-US";
}

const STATUS_KEY_MAP: Record<string, string> = {
  pending: "status.pending",
  completed: "status.completed",
  review_required: "status.review_required",
  needs_review: "status.needs_review",
  processing_failed: "status.processing_failed",
  uncertain: "status.uncertain",
  flagged_damage: "status.flagged_damage",
  failed: "status.failed",
  uploaded: "status.uploaded",
  scheduled: "status.scheduled",
  running: "status.running",
  processing: "status.processing",
  succeeded: "status.succeeded",
  accepted: "status.accepted",
  signed: "status.signed",
  done: "status.done",
  rejected: "status.rejected",
  error: "status.error",
  new: "status.new",
  viewed: "status.viewed",
  sent: "status.sent",
  draft: "status.draft",
  ready: "status.ready",
  in_progress: "status.in_progress",
  unknown: "status.unknown",
  skipped: "status.skipped",
};

export function tStatus(status: string | null | undefined): string {
  const normalized = (status ?? "").trim().toLowerCase();
  if (!normalized) {
    return t("status.unknown");
  }
  const key = STATUS_KEY_MAP[normalized];
  return key ? t(key) : normalized;
}
