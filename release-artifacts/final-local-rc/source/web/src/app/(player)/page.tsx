import type { Metadata } from "next";
import LibraryApp from "@/components/library-app";

export const metadata: Metadata = {
  title: "Your music library",
  description: "Listen to and organize your personal music library with Vervfy.",
};

export default function HomePage() {
  return <LibraryApp />;
}
