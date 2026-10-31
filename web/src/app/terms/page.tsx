import type { Metadata } from "next";
import TermsContent from "@/components/terms-content";

export const metadata: Metadata = {
  title: "Terms and Conditions",
  description: "Terms for using the Vervfy music library service.",
};

export default function TermsPage() {
  return <TermsContent />;
}
