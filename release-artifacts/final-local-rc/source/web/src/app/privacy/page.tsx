import type { Metadata } from "next";
import PrivacyPolicyContent from "@/components/privacy-policy-content";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "How Vervfy handles account, library, and device information.",
};

export default function PrivacyPolicyPage() {
  return <PrivacyPolicyContent />;
}
