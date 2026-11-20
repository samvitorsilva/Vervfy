import type { Metadata } from "next";
import { cookies } from "next/headers";
import Homepage from "@/components/homepage";
import { siteUrl, websiteMetadata } from "@/lib/site-metadata";

const title = "Vervfy – Personal Music Player & Online MP3 Library";
const description =
  "Upload, organize, and play your own music online with Vervfy. Create playlists, save favorites, view lyrics, and enjoy your personal MP3 library.";

export const metadata: Metadata = {
  ...websiteMetadata(title, description, "/"),
  title: { absolute: title },
};

export default async function HomePage() {
  // Cookie presence is only a hint for the initial UI, never proof of authentication.
  const cookieStore = await cookies();
  const hasSessionCookie = Boolean(cookieStore.get("auralis_session")?.value);
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Vervfy",
    url: new URL("/", siteUrl).href,
    applicationCategory: "MultimediaApplication",
    operatingSystem: "Web",
    description,
    featureList: [
      "Personal music library",
      "MP3 uploads and playback",
      "Playlists and favorites",
      "Lyrics and artist information",
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
