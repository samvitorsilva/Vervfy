"use client";

import { useState, type ReactNode } from "react";
import { apiFetch, expectOk } from "@/lib/api/client";
import { useLanguage } from "@/lib/i18n";

export default function LogoutButton({
  className = "auth-submit",
  children,
  ariaLabel,
}: {
  className?: string;
  children?: ReactNode;
  ariaLabel?: string;
}) {
  const { t } = useLanguage();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function logout() {
    setPending(true);
    setError(null);
    try {
      const response = await apiFetch(
        "/logout",
        { method: "POST", redirect: "follow" },
        { csrf: true, retryCsrfOnForbidden: true },
      );
      await expectOk(response);
      window.location.assign("/login");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : t("Could not log out."),
      );
      setPending(false);
    }
  }

  return (
    <>
      {error && <div className="auth-error" role="alert">{error}</div>}
      <button className={className} type="button" aria-label={ariaLabel ? t(ariaLabel) : undefined} onClick={logout} disabled={pending}>
        {pending ? t("Logging out…") : children ?? t("Log out")}
      </button>
    </>
  );
}
