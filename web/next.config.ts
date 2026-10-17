import type { NextConfig } from "next";

module.exports = {
  allowedDevOrigins: ['192.168.101.15'],
}

const configuredBackendUrl = process.env.BACKEND_URL?.trim();

if (!configuredBackendUrl) {
  throw new Error("BACKEND_URL must be set to the FastAPI service URL.");
}

const backendUrl = new URL(configuredBackendUrl);
if (!["http:", "https:"].includes(backendUrl.protocol)) {
  throw new Error("BACKEND_URL must use http:// or https://.");
}

const backendOrigin = backendUrl.origin + backendUrl.pathname.replace(/\/+$/, "");

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
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
