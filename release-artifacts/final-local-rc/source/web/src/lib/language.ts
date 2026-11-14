export const SUPPORTED_LANGUAGES = ["en", "pt-BR", "fr", "es"] as const;

export type Language = (typeof SUPPORTED_LANGUAGES)[number];

export function languageFromLocale(locale: string | null | undefined): Language | null {
  const normalized = locale?.trim().toLowerCase();
  if (!normalized) return null;
  const primaryLanguage = normalized.split(/[-_]/, 1)[0];
  return (
    SUPPORTED_LANGUAGES.find(
      (supported) => supported.toLowerCase().split("-")[0] === primaryLanguage,
    ) ?? null
  );
}

export function languageFromAcceptLanguage(header: string | null): Language {
  for (const locale of header?.split(",") ?? []) {
    const language = languageFromLocale(locale.split(";")[0]);
    if (language) return language;
  }
  return "en";
}
