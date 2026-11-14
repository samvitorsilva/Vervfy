import type { Metadata } from "next";
import AuthForm from "@/components/auth/auth-form";
import { isGoogleOAuthEnabled } from "@/lib/google-oauth-config";
import { websiteMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = websiteMetadata("Log in", "Log in to your Vervfy account to access your music library.", "/login", false);

export default async function LoginPage() {
  const googleEnabled = await isGoogleOAuthEnabled();
  return <AuthForm mode="login" googleEnabled={googleEnabled} />;
}
