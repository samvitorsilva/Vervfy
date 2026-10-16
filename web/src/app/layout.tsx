import type { Metadata, Viewport } from "next";
import { connection } from "next/server";
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
  themeColor: "#0b0d12",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  await connection();
  return (
    <html lang="en">
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
