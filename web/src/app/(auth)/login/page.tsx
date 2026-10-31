import type { Metadata } from "next";
import AuthForm from "@/components/auth/auth-form";

export const metadata: Metadata = {
  title: "Log in",
  description: "Log in to your Vervfy account to access your music library.",
};

export default function LoginPage() {
  return <AuthForm mode="login" />;
}
