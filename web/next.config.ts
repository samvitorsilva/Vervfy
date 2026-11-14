import type { NextConfig } from "next";
import {
  getBackendOrigin,
  validateStagingSiteUrl,
} from "./staging-backend-url";

const environment = process.env.VERVFY_ENVIRONMENT;
const backendOrigin = getBackendOrigin(
  process.env.BACKEND_URL,
  environment,
);
validateStagingSiteUrl(process.env.SITE_URL, environment);

const nextConfig: NextConfig = {
  poweredByHeader: false,
  devIndicators: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Strict-Transport-Security", value: "max-age=31536000" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
      {
        source: "/forgot-password",
        headers: [
          { key: "Cache-Control", value: "private, no-store" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
      {
        source: "/reset-password",
        headers: [
          { key: "Cache-Control", value: "private, no-store" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
      {
        source: "/sw.js",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Service-Worker-Allowed", value: "/" },
          { key: "Content-Type", value: "application/javascript; charset=utf-8" },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backendOrigin}/api/:path*` },
      { source: "/backend-auth/login", destination: `${backendOrigin}/login` },
      { source: "/backend-auth/register", destination: `${backendOrigin}/register` },
      { source: "/logout", destination: `${backendOrigin}/logout` },
    ];
  },
};

export default nextConfig;
