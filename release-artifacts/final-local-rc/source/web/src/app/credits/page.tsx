import type { Metadata } from "next";
import CreditsPage from "@/components/credits-page";

export const metadata: Metadata = {
  title: "Credits and data sources",
  description: "Attribution, licenses, and data sources used by Vervfy.",
};

export default function CreditsRoute() {
  return <CreditsPage />;
}
