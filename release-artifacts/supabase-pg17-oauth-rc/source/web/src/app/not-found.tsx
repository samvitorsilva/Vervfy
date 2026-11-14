import type { Metadata } from "next";
import NotFoundContent from "@/components/not-found-content";

export const metadata: Metadata = {
  title: "Page not found",
  description: "The requested Vervfy page could not be found.",
};

export default function NotFound() {
  return <NotFoundContent />;
}
