import type { Metadata } from "next";
import AuthForm from "@/components/auth/auth-form";
import { websiteMetadata } from "@/lib/site-metadata";

export const metadata: Metadata = websiteMetadata("Create an account", "Create a Vervfy account to organize and listen to your music library.", "/register", false);

export default function RegisterPage() {
  return <AuthForm mode="register" />;
}
