"use client";

import { useState, type ReactNode } from "react";
import { apiFetch, expectOk } from "@/lib/api/client";

export default function LogoutButton({
  className = "auth-submit",
  children,
  ariaLabel,
}: {
  className?: string;
  children?: ReactNode;
  ariaLabel?: string;
}) {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function logout() {
    setPending(true);
    setError(null);
    try {
      const response = await apiFetch(
        "/logout",
        { method: "POST", redirect: "follow" },
        { csrf: true },
      );
      await expectOk(response);
      window.location.assign("/login");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not log out.",
      );
      setPending(false);
    }
  }

  return (
    <>
      {error && <div className="auth-error" role="alert">{error}</div>}
      <button className={className} type="button" aria-label={ariaLabel} onClick={logout} disabled={pending}>
        {pending ? "Logging out…" : children ?? "Log out"}
      </button>
    </>
  );
}
