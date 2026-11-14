"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, getCsrfToken } from "@/lib/api/client";
import { LanguageSelect, useLanguage } from "@/lib/i18n";
import SiteFooter from "@/components/site-footer";

declare global {
  interface Window {
    __vervfyRecoveryLink?: { token: string; mode: "reset" | "verify" };
  }
}

type LinkMode = "reset" | "verify" | "missing";

export default function ResetPasswordForm() {
  const { t, translateError } = useLanguage();
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [csrfError, setCsrfError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [linkMode, setLinkMode] = useState<LinkMode>("missing");
  const [token, setToken] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);
  const [verificationSent, setVerificationSent] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [pending, setPending] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const initialLink = useRef<{ token: string | null; mode: LinkMode } | null>(null);
  const passwordLength = Array.from(password).length;
  const passwordBytes = new TextEncoder().encode(password).length;
  const passwordHint =
    passwordBytes > 72
      ? t("Password must be 72 UTF-8 bytes or fewer. Remove some characters.")
      : passwordLength < 8
        ? passwordLength > 0
          ? t(passwordLength === 7
            ? "Add 1 more character to meet the 8-character minimum."
            : "Add {count} more characters to meet the 8-character minimum.")
            .replace("{count}", String(8 - passwordLength))
          : t("Use at least 8 characters.")
        : t("Password meets the 8-character minimum.");
  const passwordInvalid =
    passwordLength > 0 && (passwordLength < 8 || passwordBytes > 72);
  const confirmationMismatch =
    confirmation.length > 0 && confirmation !== password;

  useEffect(() => {
    let active = true;
    void getCsrfToken()
      .then((value) => {
        if (active) setCsrfToken(value);
      })
      .catch((reason: unknown) => {
        if (active) {
          setCsrfError(
            translateError(
              reason instanceof Error ? reason.message : "",
              "Could not load the form.",
            ),
          );
        }
      });
    return () => {
      active = false;
    };
  }, [translateError]);

  useEffect(() => {
    if (initialLink.current === null) {
      const preloadedLink = window.__vervfyRecoveryLink;
      if (preloadedLink) {
        initialLink.current = preloadedLink;
        delete window.__vervfyRecoveryLink;
      } else {
        const values = new URLSearchParams(window.location.hash.slice(1));
        const resetToken = values.get("token");
        const verificationToken = values.get("verify");
        initialLink.current = verificationToken
          ? { token: verificationToken, mode: "verify" }
          : resetToken
            ? { token: resetToken, mode: "reset" }
            : { token: null, mode: "missing" };
      }
      window.history.replaceState(null, "", window.location.pathname);
    }

    const { token: initialToken, mode } = initialLink.current;
    const frame = window.requestAnimationFrame(() => {
      initialLink.current = null;
      setToken(initialToken);
      setLinkMode(mode);
      setInitialized(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  async function handleVerification(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csrfToken || !token || pending) return;
    setPending(true);
    setError(null);
    try {
      const response = await fetch("/api/auth/verify-reset-email", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({ token }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        const detail =
          body &&
          typeof body === "object" &&
          "detail" in body &&
          typeof body.detail === "string"
            ? body.detail
            : `Request failed (${response.status})`;
        throw new ApiError(detail, response.status);
      }
      setVerificationSent(true);
      setToken(null);
    } catch (reason: unknown) {
      setError(
        translateError(
          reason instanceof Error ? reason.message : "",
          "This verification link is invalid or has expired.",
        ),
      );
      setToken(null);
    } finally {
      setPending(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csrfToken || !token || pending) return;
    if (password !== confirmation) {
      setError(t("Passwords do not match."));
      return;
    }

    setPending(true);
    setError(null);
    try {
      const response = await fetch("/api/auth/reset-password", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({ token, password }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        const detail =
          body &&
          typeof body === "object" &&
          "detail" in body &&
          typeof body.detail === "string"
            ? body.detail
            : `Request failed (${response.status})`;
        throw new ApiError(detail, response.status);
      }
      setToken(null);
      setSubmitted(true);
    } catch (reason: unknown) {
      setError(
        translateError(
          reason instanceof Error ? reason.message : "",
          "This reset link is invalid or has expired.",
        ),
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="auth-brand">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/gemini-svg.svg" alt="" width={28} height={28} />
          Vervfy
        </div>
        <LanguageSelect className="auth-language-select" />
        <h1 id="auth-title" className="auth-title">
          {t(linkMode === "verify" ? "Verify your email" : "Reset your password")}
        </h1>
        <p className="auth-sub">
          {linkMode === "verify"
            ? t("Confirm this email address to continue resetting your password.")
            : t("Choose a new password for your Vervfy account.")}
        </p>

        {(error || csrfError) && (
          <div className="auth-error" role="alert">
            {error || csrfError}
          </div>
        )}

        {submitted ? (
          <>
            <p className="auth-notice" role="status">
              {t("Your password has been updated. You can log in with your new password.")}
            </p>
            <div className="auth-footer">
              <Link href="/login">{t("Back to log in")}</Link>
            </div>
          </>
        ) : verificationSent ? (
          <p className="auth-notice" role="status">
            {t("If you own this email address, reset instructions will arrive shortly.")}
          </p>
        ) : linkMode === "verify" ? (
          <form onSubmit={handleVerification}>
            <button
              className="auth-submit"
              type="submit"
              disabled={!csrfToken || !token || pending || !!csrfError}
            >
              {pending
                ? t("Verifying your email…")
                : t("Verify email and continue")}
            </button>
          </form>
        ) : linkMode === "missing" || !initialized ? (
          <p className="auth-notice" role="status">
            {initialized
              ? t("This reset link is invalid or has expired.")
              : t("Checking your reset link…")}
          </p>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="auth-field">
              <label htmlFor="password">{t("New password")}</label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="new-password"
                minLength={8}
                maxLength={72}
                required
                autoFocus
                value={password}
                aria-invalid={passwordInvalid}
                aria-describedby="password-hint"
                onChange={(event) => {
                  setPassword(event.currentTarget.value);
                  setError(null);
                }}
              />
              <p
                id="password-hint"
                className={`auth-password-hint${passwordInvalid ? " error" : passwordLength >= 8 && passwordBytes <= 72 ? " ok" : ""}`}
                aria-live="polite"
              >
                {passwordHint}
              </p>
            </div>
            <div className="auth-field">
              <label htmlFor="confirmation">{t("Confirm new password")}</label>
              <input
                id="confirmation"
                name="confirmation"
                type="password"
                autoComplete="new-password"
                required
                value={confirmation}
                aria-invalid={confirmationMismatch}
                aria-describedby={confirmationMismatch ? "confirmation-hint" : undefined}
                onChange={(event) => {
                  setConfirmation(event.currentTarget.value);
                  setError(null);
                }}
              />
              {confirmationMismatch ? (
                <p id="confirmation-hint" className="auth-password-hint error">
                  {t("Passwords do not match.")}
                </p>
              ) : null}
            </div>
            <button
              className="auth-submit"
              type="submit"
              disabled={
                !csrfToken ||
                pending ||
                !!csrfError ||
                passwordInvalid ||
                passwordLength < 8 ||
                confirmation !== password
              }
            >
              {pending ? t("Updating password…") : t("Reset password")}
            </button>
          </form>
        )}

        {!submitted ? (
          <div className="auth-footer">
            <Link href="/forgot-password">{t("Request another reset link")}</Link>
            {" · "}
            <Link href="/login">{t("Back to log in")}</Link>
          </div>
        ) : null}
        <SiteFooter showLanguage={false} />
      </section>
    </main>
  );
}
