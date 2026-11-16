import type { Metadata } from "next";
import { cookies } from "next/headers";
import Homepage from "@/components/homepage";
import { websiteMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = websiteMetadata(
  "Your personal music library, accessible from anywhere.",
  "Upload your music, organize playlists and favorites, and find lyrics and artist details in one place.",
  "/",
);

export default async function HomePage() {
  // Cookie presence is only a hint for the initial UI, never proof of authentication.
  const cookieStore = await cookies();
  const hasSessionCookie = Boolean(cookieStore.get("auralis_session")?.value);
  return <Homepage hasSessionCookie={hasSessionCookie} />;
}
