import { pageMetadata } from "@/lib/page-metadata";
import ResetPasswordForm from "@/components/auth/reset-password-form";

export async function generateMetadata() {
  return pageMetadata("/reset-password");
}

export default function ResetPasswordPage() {
  return <ResetPasswordForm />;
}
