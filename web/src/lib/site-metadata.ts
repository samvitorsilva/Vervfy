import type { Metadata } from "next";

const configuredUrl = process.env.SITE_URL ?? process.env.RENDER_EXTERNAL_URL;
if (!configuredUrl && process.env.NODE_ENV === "production") {
  throw new Error("Set SITE_URL to the public frontend origin (or use Render's RENDER_EXTERNAL_URL).");
}
export const siteUrl = new URL(configuredUrl ?? "http://localhost:3000");
if (
  !["http:", "https:"].includes(siteUrl.protocol) ||
  siteUrl.username || siteUrl.password || siteUrl.search || siteUrl.hash ||
  siteUrl.pathname !== "/" ||
  (process.env.NODE_ENV === "production" && siteUrl.protocol !== "https:" &&
    !["localhost", "127.0.0.1", "[::1]"].includes(siteUrl.hostname))
) {
  throw new Error("SITE_URL must be the public HTTPS frontend origin without credentials or a path.");
}

export function websiteMetadata(title: string, description: string, path: string, index = true): Metadata {
  const url = new URL(path, siteUrl);
  const image = {
    url: new URL("/opengraph-image", siteUrl).href,
    width: 1200,
    height: 630,
    alt: "Vervfy — your personal music library",
  };
  return {
    title,
    description,
    metadataBase: siteUrl,
    alternates: { canonical: url.href },
    robots: { index, follow: true },
    openGraph: { type: "website", siteName: "Vervfy", title, description, url, images: [image] },
    twitter: { card: "summary_large_image", title, description, images: [image] },
  };
}
