"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { ApiError, getCsrfToken } from "@/lib/api/client";
import { LanguageSelect, useLanguage } from "@/lib/i18n";
import SiteFooter from "@/components/site-footer";

export default function ForgotPasswordForm() {
  const { t, translateError } = useLanguage();
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [csrfError, setCsrfError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    let active = true;
    void getCsrfToken()
      .then((token) => {
        if (active) setCsrfToken(token);
      })
      .catch((reason: unknown) => {
        if (active) {
          setCsrfError(
            translateError(reason instanceof Error ? reason.message : "", "Could not load the form."),
          );
        }
      });
    return () => {
      active = false;
    };
  }, [translateError]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csrfToken || pending) return;
    setPending(true);
    setError(null);
    try {
      const response = await fetch("/api/auth/forgot-password", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({ email: email.trim() }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        const detail =
          body && typeof body === "object" && typeof body.detail === "string"
            ? body.detail
            : `Request failed (${response.status})`;
        throw new ApiError(detail, response.status);
      }
      setSubmitted(true);
    } catch (reason: unknown) {
      setError(
        translateError(
          reason instanceof Error ? reason.message : "",
          "Could not send reset instructions. Try again.",
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
          {t("Forgot password")}
        </h1>
        <p className="auth-sub">
          {t("Enter your account email. If an account can be recovered with it, we will send instructions.")}
        </p>

        {(error || csrfError) && (
          <div id="auth-error" className="auth-error" role="alert">
            {error || csrfError}
          </div>
        )}

        {submitted ? (
          <p className="auth-notice" role="status">
            {t("If an account exists for that email, we sent password reset instructions.")}
          </p>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="auth-field">
              <label htmlFor="email">{t("Email")}</label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                autoFocus
                maxLength={320}
                value={email}
                onChange={(event) => {
                  setEmail(event.currentTarget.value);
                  setError(null);
                }}
              />
            </div>
            <button
              className="auth-submit"
              type="submit"
              disabled={!csrfToken || pending || !!csrfError}
            >
              {pending ? t("Sending…") : t("Send reset link")}
            </button>
          </form>
        )}

        <div className="auth-footer">
          <Link href="/login">{t("Back to log in")}</Link>
        </div>
        <SiteFooter showLanguage={false} />
      </section>
    </main>
  );
}
