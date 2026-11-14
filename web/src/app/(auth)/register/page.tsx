import type { Metadata } from "next";
import AuthForm from "@/components/auth/auth-form";
import { isGoogleOAuthEnabled } from "@/lib/google-oauth-config";
import { websiteMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = websiteMetadata("Create an account", "Create a Vervfy account to organize and listen to your music library.", "/register", false);

export default async function RegisterPage() {
  const googleEnabled = await isGoogleOAuthEnabled();
  return <AuthForm mode="register" googleEnabled={googleEnabled} />;
}
