import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Vervfy",
    short_name: "Vervfy",
    description: "Your personal music library.",
    start_url: "/",
    display: "standalone",
    background_color: "#0c0e14",
    theme_color: "#0c0e14",
    icons: [
      {
        src: "/gemini-svg.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
