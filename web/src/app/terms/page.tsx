import TermsContent from "@/components/terms-content";
import { pageMetadata } from "@/lib/page-metadata";

export const generateMetadata = () => pageMetadata("/terms");

export default function TermsPage() {
  return <TermsContent />;
}
