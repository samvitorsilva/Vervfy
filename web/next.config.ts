import type { NextConfig } from "next";

const configuredBackendUrl = process.env.BACKEND_URL?.trim();

if (!configuredBackendUrl) {
  throw new Error("BACKEND_URL must be set to the FastAPI service URL.");
}

const backendUrl = new URL(configuredBackendUrl);
if (!["http:", "https:"].includes(backendUrl.protocol)) {
  throw new Error("BACKEND_URL must use http:// or https://.");
}

const backendOrigin = backendUrl.origin + backendUrl.pathname.replace(/\/+$/, "");
const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com data:",
  "img-src 'self' data: blob: https:",
  "media-src 'self' blob:",
  "connect-src 'self' https://lrclib.net",
  "worker-src 'self' blob:",
  "manifest-src 'self'",
].join("; ");

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy-Report-Only", value: contentSecurityPolicy },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
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
