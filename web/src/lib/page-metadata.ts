import { cookies, headers } from "next/headers";
import type { Metadata } from "next";
import { languageFromAcceptLanguage, languageFromLocale, type Language } from "@/lib/language";
import { websiteMetadata } from "@/lib/site-metadata";

const localizedTitles: Record<string, Record<Language, string>> = {
  "/credits": {
    en: "Credits and data sources",
    "pt-BR": "Créditos e fontes de dados",
    fr: "Crédits et sources de données",
    es: "Créditos y fuentes de datos",
  },
  "/privacy": {
    en: "Privacy Policy",
    "pt-BR": "Política de Privacidade",
    fr: "Politique de confidentialité",
    es: "Política de privacidad",
  },
  "/terms": {
    en: "Terms and Conditions",
    "pt-BR": "Termos e Condições",
    fr: "Conditions générales",
    es: "Términos y condiciones",
  },
};

const descriptions: Record<string, string> = {
  "/credits": "Attribution, licenses, and data sources used by Vervfy.",
  "/privacy": "How Vervfy handles account, library, and device information.",
  "/terms": "Terms for using the Vervfy music library service.",
};

export async function pageMetadata(path: string): Promise<Metadata> {
  const cookieStore = await cookies();
  const language =
    languageFromLocale(cookieStore.get("vervfy-language")?.value) ??
    languageFromAcceptLanguage((await headers()).get("accept-language"));
  const titles = localizedTitles[path];
  const description = descriptions[path];
  if (!titles || !description) throw new Error(`Unknown metadata path: ${path}`);

  return websiteMetadata(titles[language], description, path);
}
