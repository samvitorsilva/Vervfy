import type { MetadataRoute } from "next";
import { siteUrl } from "@/lib/site-metadata";

export default function sitemap(): MetadataRoute.Sitemap {
  return ["/privacy", "/terms", "/credits"].map((path) => ({
    url: new URL(path, siteUrl).href,
  }));
}
