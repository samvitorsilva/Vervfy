import { connection } from "next/server";
import { getBackendOrigin } from "../../staging-backend-url";

export async function isGoogleOAuthEnabled(): Promise<boolean> {
  await connection();
  const backendOrigin = getBackendOrigin(
    process.env.BACKEND_URL,
    process.env.VERVFY_ENVIRONMENT,
  );
  let response: Response;
  try {
    response = await fetch(`${backendOrigin}/api/config`, { cache: "no-store" });
  } catch (reason) {
    console.error("Could not load Google OAuth configuration for auth page.", reason);
    return false;
  }

  if (!response.ok) {
    console.error(
      `Could not load Google OAuth configuration for auth page (${response.status}).`,
    );
    return false;
  }

  let config: unknown;
  try {
    config = await response.json();
  } catch (reason) {
    console.error("Google OAuth configuration response was not valid JSON.", reason);
    return false;
  }

  return (
    typeof config === "object" &&
    config !== null &&
    "google_oauth_enabled" in config &&
    config.google_oauth_enabled === true
  );
}
