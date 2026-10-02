import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import RootProviders from "@/components/root-providers";
import "./styles.css";
import "./auth.css";

export const metadata: Metadata = {
  title: "Vervfy",
  description: "Your personal music library.",
  icons: { icon: "/gemini-svg.svg" },
  applicationName: "Vervfy",
  appleWebApp: {
    capable: true,
    title: "Vervfy",
    statusBarStyle: "black-translucent",
  },
};

export const viewport: Viewport = {
  colorScheme: "dark",
  themeColor: "#0c0e14",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Outfit:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <div className="field" aria-hidden="true">
          <div className="field-blob field-blob-a" />
          <div className="field-blob field-blob-b" />
        </div>
        <RootProviders>{children}</RootProviders>
      </body>
    </html>
  );
}
