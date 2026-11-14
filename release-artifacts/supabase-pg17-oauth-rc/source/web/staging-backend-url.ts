const STAGING_API_ORIGIN = "https://vervfy-staging-api.onrender.com";
const STAGING_WEB_ORIGIN = "https://vervfy-staging-web.onrender.com";

export function getBackendOrigin(
  configuredBackendUrl: string | undefined,
  environment: string | undefined,
): string {
  const configured = configuredBackendUrl?.trim();
  if (!configured) {
    throw new Error("BACKEND_URL must be set to the FastAPI service URL.");
  }

  let backendUrl: URL;
  try {
    backendUrl = new URL(configured);
  } catch {
    throw new Error("BACKEND_URL must be a valid absolute URL.");
  }

  if (!["http:", "https:"].includes(backendUrl.protocol)) {
    throw new Error("BACKEND_URL must use http:// or https://.");
  }

  if (
    environment === "staging" &&
    (backendUrl.origin !== STAGING_API_ORIGIN ||
      backendUrl.pathname !== "/" ||
      backendUrl.search !== "" ||
      backendUrl.hash !== "" ||
      backendUrl.username !== "" ||
      backendUrl.password !== "")
  ) {
    throw new Error(
      "Staging BACKEND_URL must be the approved HTTPS staging API origin.",
    );
  }

  return backendUrl.origin + backendUrl.pathname.replace(/\/+$/, "");
}

export function validateStagingSiteUrl(
  configuredSiteUrl: string | undefined,
  environment: string | undefined,
): void {
  if (environment !== "staging") {
    return;
  }

  const configured = configuredSiteUrl?.trim();
  if (!configured) {
    throw new Error("SITE_URL must be set to the staging frontend origin.");
  }

  let siteUrl: URL;
  try {
    siteUrl = new URL(configured);
  } catch {
    throw new Error("SITE_URL must be a valid absolute URL.");
  }

  if (
    siteUrl.origin !== STAGING_WEB_ORIGIN ||
    siteUrl.pathname !== "/" ||
    siteUrl.search !== "" ||
    siteUrl.hash !== "" ||
    siteUrl.username !== "" ||
    siteUrl.password !== ""
  ) {
    throw new Error(
      "Staging SITE_URL must be the approved HTTPS staging frontend origin.",
    );
  }
}
