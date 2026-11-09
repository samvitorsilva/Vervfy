import type { MetadataRoute } from "next";
import { siteUrl } from "@/lib/site-metadata";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: ["/privacy", "/terms", "/credits"],
      disallow: ["/$", "/api/", "/backend-auth/", "/logout", "/login", "/register"],
    },
    sitemap: new URL("/sitemap.xml", siteUrl).href,
  };
}
