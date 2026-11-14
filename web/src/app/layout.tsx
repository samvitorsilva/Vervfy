import type { Metadata, Viewport } from "next";
import { cookies, headers } from "next/headers";
import type { ReactNode } from "react";
import RootProviders from "@/components/root-providers";
import { languageFromAcceptLanguage, languageFromLocale } from "@/lib/language";
import { siteUrl } from "@/lib/site-metadata";
import "./styles.css";
import "./auth.css";

export const metadata: Metadata = {
  metadataBase: siteUrl,
  title: {
    default: "Vervfy",
    template: "%s | Vervfy",
  },
  description: "Listen to and organize your personal music library with Vervfy.",
  verification: {
    google: "TJcjdYvCNgGT5pSgac4QQfkP-KAybFGY3BR9WfLPVvc",
  },
  icons: {
    icon: [
      { url: "/gemini-svg.svg", type: "image/svg+xml" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: "/apple-icon.png",
  },
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

export default async function RootLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  const requestHeaders = await headers();
  const language =
    languageFromLocale(cookieStore.get("vervfy-language")?.value) ??
    languageFromAcceptLanguage(requestHeaders.get("accept-language"));
  const nonce = requestHeaders.get("x-nonce") ?? undefined;

  return (
    <html lang={language}>
      <head>
        <script
          nonce={nonce}
          dangerouslySetInnerHTML={{
            __html: `if (/(?:^|\\/)reset-password\\/?$/.test(window.location.pathname)) {
  var recoveryValues = new URLSearchParams(window.location.hash.slice(1));
  var recoveryToken = recoveryValues.get("verify") || recoveryValues.get("token");
  if (recoveryToken) {
    window.__vervfyRecoveryLink = {
      token: recoveryToken,
      mode: recoveryValues.has("verify") ? "verify" : "reset"
    };
  }
  window.history.replaceState(null, "", window.location.pathname);
}`,
          }}
        />
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
        <RootProviders initialLanguage={language}>{children}</RootProviders>
      </body>
    </html>
  );
}
