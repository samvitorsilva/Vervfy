import type { Metadata } from "next";
import { cookies } from "next/headers";
import Homepage from "@/components/homepage";
import { websiteMetadata } from "@/lib/site-metadata";

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
  return <Homepage hasSessionCookie={hasSessionCookie} />;
}
