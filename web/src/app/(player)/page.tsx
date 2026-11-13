import type { Metadata } from "next";
import Homepage from "@/components/homepage";
import { websiteMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = websiteMetadata(
  "Your music. Your rules.",
  "Your personal space for music. Upload your tracks, build playlists, discover lyrics, and listen to your collection—all in one place.",
  "/",
);

export default function HomePage() {
  return <Homepage />;
}
