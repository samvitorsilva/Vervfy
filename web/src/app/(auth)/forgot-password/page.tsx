import { pageMetadata } from "@/lib/page-metadata";
import ForgotPasswordForm from "@/components/auth/forgot-password-form";

export async function generateMetadata() {
  return pageMetadata("/forgot-password");
}

export default function ForgotPasswordPage() {
  return <ForgotPasswordForm />;
}
