import type { Metadata } from "next";
import AuthForm from "@/components/auth/auth-form";

export const metadata: Metadata = {
  title: "Create an account",
  description: "Create a Vervfy account to organize and listen to your music library.",
};

export default function RegisterPage() {
  return <AuthForm mode="register" />;
}
