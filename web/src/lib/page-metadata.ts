import { cookies, headers } from "next/headers";
import type { Metadata } from "next";
import { languageFromAcceptLanguage, languageFromLocale, type Language } from "@/lib/language";
import { websiteMetadata } from "@/lib/site-metadata";

const localizedTitles: Record<string, Record<Language, string>> = {
  "/forgot-password": {
    en: "Forgot password",
    "pt-BR": "Esqueceu a senha",
    fr: "Mot de passe oublié",
    es: "Contraseña olvidada",
  },
  "/reset-password": {
    en: "Reset password",
    "pt-BR": "Redefinir senha",
    fr: "Réinitialiser le mot de passe",
    es: "Restablecer contraseña",
  },
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
  "/forgot-password": "Request secure password reset instructions for your Vervfy account.",
  "/reset-password": "Choose a new password for your Vervfy account.",
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

  if (path === "/forgot-password" || path === "/reset-password") {
    return { title: titles[language], description, robots: { index: false, follow: false }, referrer: "no-referrer" };
  }
  return websiteMetadata(titles[language], description, path);
}
