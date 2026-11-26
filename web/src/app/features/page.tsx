import { cookies, headers } from "next/headers";
import FeaturesPage from "@/components/features-page";
import { featuresContent } from "@/lib/features-content";
import { languageFromAcceptLanguage, languageFromLocale } from "@/lib/language";
import { websiteMetadata } from "@/lib/site-metadata";
import "./features.css";

export async function generateMetadata() {
  const language = languageFromLocale((await cookies()).get("vervfy-language")?.value) ??
    languageFromAcceptLanguage((await headers()).get("accept-language"));
  const { title, description } = featuresContent[language];
  return websiteMetadata(title, description, "/features");
}

export default function FeaturesRoute() {
  return <FeaturesPage />;
}
