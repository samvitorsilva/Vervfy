import CreditsPage from "@/components/credits-page";
import { pageMetadata } from "@/lib/page-metadata";

export const generateMetadata = () => pageMetadata("/credits");

export default function CreditsRoute() {
  return <CreditsPage />;
}
