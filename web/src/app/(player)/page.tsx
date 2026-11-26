import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import Homepage from "@/components/homepage";
import { siteUrl, websiteMetadata } from "@/lib/site-metadata";

import { homepageFeatures, homepageSeo } from "@/lib/homepage-seo";
import { languageFromAcceptLanguage, languageFromLocale } from "@/lib/language";

async function homepageLanguage() {
  return languageFromLocale((await cookies()).get("vervfy-language")?.value) ??
    languageFromAcceptLanguage((await headers()).get("accept-language"));
}

export async function generateMetadata(): Promise<Metadata> {
  const { title, description } = homepageSeo[await homepageLanguage()];
  return {
    ...websiteMetadata(title, description, "/"),
    title: { absolute: title },
  };
}

export default async function HomePage() {
  // Cookie presence is only a hint for the initial UI, never proof of authentication.
  const cookieStore = await cookies();
  const hasSessionCookie = Boolean(cookieStore.get("auralis_session")?.value);
  const language = await homepageLanguage();
  const { description } = homepageSeo[language];
  const structuredData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebSite",
        "@id": new URL("/#website", siteUrl).href,
        name: "Vervfy",
        url: new URL("/", siteUrl).href,
      },
      {
        "@type": "SoftwareApplication",
        name: "Vervfy",
        url: new URL("/", siteUrl).href,
        applicationCategory: "MultimediaApplication",
        operatingSystem: "Web",
        description,
        inLanguage: language,
        featureList: homepageFeatures[language],
      },
    ],
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(structuredData).replace(/</g, "\\u003c"),
        }}
      />
      <Homepage hasSessionCookie={hasSessionCookie} />
    </>
  );
}
