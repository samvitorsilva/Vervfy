import type { Metadata } from "next";
import Homepage from "@/components/homepage";
import { websiteMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = websiteMetadata(
  "Your personal music library, accessible from anywhere.",
  "Upload your music, organize playlists and favorites, and find lyrics and artist details in one place.",
  "/",
);

export default function HomePage() {
  return <Homepage />;
}
