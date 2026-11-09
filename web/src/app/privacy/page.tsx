import PrivacyPolicyContent from "@/components/privacy-policy-content";
import { pageMetadata } from "@/lib/page-metadata";

export const generateMetadata = () => pageMetadata("/privacy");

export default function PrivacyPolicyPage() {
  return <PrivacyPolicyContent />;
}
