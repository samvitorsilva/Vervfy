"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { getCsrfToken } from "@/lib/api/client";
import { LanguageSelect, useLanguage } from "@/lib/i18n";
import SiteFooter from "@/components/site-footer";

type AuthMode = "login" | "register";

export default function AuthForm({ mode }: { mode: AuthMode }) {
  const { t, translateError } = useLanguage();
  const isLogin = mode === "login";
  const endpoint = `/backend-auth/${mode}`;
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [csrfError, setCsrfError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordIncorrect, setPasswordIncorrect] = useState(false);
  const [pending, setPending] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);
  const [googleOnboarding, setGoogleOnboarding] = useState(false);
  const isGoogleOnboarding = googleOnboarding && googleEnabled;
  const passwordInputRef = useRef<HTMLInputElement>(null);
  const passwordLength = Array.from(password).length;
  const passwordBytes = new TextEncoder().encode(password).length;
  const passwordHint = isLogin
    ? t("Your password is checked when you log in. If it doesn't match, check it and try again.")
    : passwordBytes > 72
      ? t("Password must be 72 UTF-8 bytes or fewer. Remove some characters.")
      : passwordLength < 8
        ? passwordLength > 0
          ? t(passwordLength === 7
            ? "Add 1 more character to meet the 8-character minimum."
            : "Add {count} more characters to meet the 8-character minimum.")
              .replace("{count}", String(8 - passwordLength))
          : t("Use at least 8 characters.")
        : t("Password meets the 8-character minimum.");
  const passwordInvalid = isLogin
    ? passwordIncorrect
    : passwordLength > 0 && (passwordLength < 8 || passwordBytes > 72);

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

  useEffect(() => {
    let active = true;
    let statusFrame: number | undefined;
    void fetch("/api/config", { credentials: "same-origin", cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const config: unknown = await response.json();
        if (
          active &&
          typeof config === "object" &&
          config !== null &&
          "google_oauth_enabled" in config &&
          config.google_oauth_enabled === true
        ) {
          setGoogleEnabled(true);
        }
      })
      .catch(() => undefined);

    const url = new URL(window.location.href);
    const googleStatus = url.searchParams.get("google");
    if (googleStatus) {
      statusFrame = window.requestAnimationFrame(() => {
        if (!active) return;
        if (googleStatus === "complete") {
          setGoogleOnboarding(true);
        } else if (googleStatus === "failed") {
          setError(t("Google sign-up could not be completed. Try again."));
        }
        url.searchParams.delete("google");
        window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
      });
    }
    return () => {
      active = false;
      if (statusFrame !== undefined) window.cancelAnimationFrame(statusFrame);
    };
  }, [t]);

  async function handleGoogleOnboarding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csrfToken || pending) return;
    setPending(true);
    setError(null);
    try {
      const response = await fetch("/api/auth/google/onboarding", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        redirect: "manual",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({ username: username.trim() }),
      });
      if (response.status === 303 || response.type === "opaqueredirect") {
        window.location.assign("/");
        return;
      }
      const result = (await response.json().catch(() => null)) as {
        detail?: unknown;
      } | null;
      const detail = typeof result?.detail === "string"
        ? result.detail
        : t("Google sign-up could not be completed. Try again.");
      setError(translateError(detail, "Google sign-up could not be completed. Try again."));
    } catch (reason) {
      setError(
        translateError(
          reason instanceof Error ? reason.message : "",
          "The authentication request could not be completed.",
        ),
      );
    } finally {
      setPending(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csrfToken || pending) return;

    setPending(true);
    setError(null);
    setPasswordIncorrect(false);
    const body = new URLSearchParams({
      username: username.trim(),
      password: String(new FormData(event.currentTarget).get("password") ?? ""),
      csrf_token: csrfToken,
    });
    if (!isLogin) body.set("email", email);

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        redirect: "manual",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });

      if (response.status === 303 || response.type === "opaqueredirect") {
        window.location.assign("/");
        return;
      }

      const result = (await response.json().catch(() => null)) as {
        detail?: unknown;
      } | null;
      const detail = typeof result?.detail === "string"
        ? result.detail
        : `Could not ${isLogin ? "log in" : "create the account"} (${response.status}).`;
      const incorrectPassword = isLogin && detail === "Incorrect username or password";
      setPasswordIncorrect(incorrectPassword);
      setError(translateError(detail, "The authentication request could not be completed."));
      if (incorrectPassword) passwordInputRef.current?.focus();
    } catch (reason) {
      setError(
        translateError(
          reason instanceof Error ? reason.message : "",
          "The authentication request could not be completed.",
        ),
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="auth-brand">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/gemini-svg.svg" alt="" width={28} height={28} />
          Vervfy
        </div>
        <LanguageSelect className="auth-language-select" />
        <h1 className="auth-title">
          {t(isGoogleOnboarding ? "Choose your username" : isLogin ? "Welcome back" : "Create your account")}
        </h1>
        <p className="auth-sub">
          {isGoogleOnboarding
            ? t("Your Google account is verified. Choose a unique username for Vervfy.")
            : isLogin
            ? t("Log in to reach your synced library.")
            : t("Your library, uploads, and covers will be synced to it.")}
        </p>

        {(error || csrfError) && (
          <div id="auth-error" className="auth-error" role="alert">
            {error || csrfError}
          </div>
        )}

        {isGoogleOnboarding ? (
          <form onSubmit={handleGoogleOnboarding}>
            <div className="auth-field">
              <label htmlFor="username">{t("Username")}</label>
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                minLength={3}
                maxLength={32}
                pattern="[a-zA-Z0-9_.\-]+"
                required
                autoFocus
                value={username}
                onChange={(event) => {
                  setUsername(event.currentTarget.value);
                  setError(null);
                }}
              />
            </div>
            <button
              className="auth-submit"
              type="submit"
              disabled={!csrfToken || pending || !!csrfError}
            >
              {pending ? t("Creating account…") : t("Create account")}
            </button>
          </form>
        ) : null}

        {!isGoogleOnboarding && googleEnabled ? (
          <div className="auth-provider">
            <a
              className="auth-google"
              href={`/api/auth/google/start?purpose=${isLogin ? "login" : "signup"}`}
            >
              <svg viewBox="0 0 48 48" aria-hidden="true">
                <path fill="#4285F4" d="M43.6 24.5c0-1.4-.1-2.8-.4-4.1H24v7.8h11a9.4 9.4 0 0 1-4.1 6.2v5.1h6.6c3.9-3.6 6.1-8.8 6.1-15Z" />
                <path fill="#34A853" d="M24 44c5.5 0 10.1-1.8 13.5-4.8l-6.6-5.1c-1.8 1.2-4.1 2-6.9 2-5.3 0-9.8-3.6-11.4-8.4H5.8v5.3A20.4 20.4 0 0 0 24 44Z" />
                <path fill="#FBBC05" d="M12.6 27.7a12.3 12.3 0 0 1 0-7.4V15H5.8a20.3 20.3 0 0 0 0 18l6.8-5.3Z" />
                <path fill="#EA4335" d="M24 12c3 0 5.7 1 7.8 3.1l5.8-5.8A19.4 19.4 0 0 0 24 4 20.4 20.4 0 0 0 5.8 15l6.8 5.3C14.2 15.6 18.7 12 24 12Z" />
              </svg>
              {t("Continue with Google")}
            </a>
            <div className="auth-divider"><span>{t("or")}</span></div>
          </div>
        ) : null}

        {!isGoogleOnboarding ? <form onSubmit={handleSubmit}>
          <div className="auth-field">
            <label htmlFor="username">{t("Username")}</label>
            <input
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              maxLength={isLogin ? 32 : undefined}
              minLength={isLogin ? undefined : 3}
              pattern={isLogin ? undefined : "[a-zA-Z0-9_.\\-]+"}
              required
              autoFocus
              value={username}
              onChange={(event) => {
                setUsername(event.currentTarget.value);
                setError(null);
                setPasswordIncorrect(false);
              }}
            />
          </div>
          {!isLogin && (
            <div className="auth-field">
              <label htmlFor="email">{t("Email (optional, not used to sign in)")}</label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.currentTarget.value)}
              />
            </div>
          )}
          <div className="auth-field">
            <label htmlFor="password">{t("Password")}</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete={isLogin ? "current-password" : "new-password"}
              minLength={isLogin ? undefined : 8}
              required
              ref={passwordInputRef}
              value={password}
              aria-invalid={passwordInvalid}
              aria-describedby={passwordIncorrect ? "auth-error password-hint" : "password-hint"}
              onChange={(event) => {
                setPassword(event.currentTarget.value);
                setError(null);
                setPasswordIncorrect(false);
              }}
            />
            <p
              id="password-hint"
              className={`auth-password-hint${passwordInvalid ? " error" : !isLogin && passwordLength >= 8 && passwordBytes <= 72 ? " ok" : ""}`}
              aria-live="polite"
            >
              {passwordHint}
            </p>
          </div>
          <button
            className="auth-submit"
            type="submit"
            disabled={!csrfToken || pending || !!csrfError}
          >
            {pending
              ? isLogin
                ? t("Logging in…")
                : t("Creating account…")
              : isLogin
                ? t("Log in")
                : t("Create account")}
          </button>
        </form> : null}

        {!isGoogleOnboarding ? <div className="auth-footer">
          {t(isLogin ? "No account yet? " : "Already have an account? ")}
          <Link href={isLogin ? "/register" : "/login"}>
            {t(isLogin ? "Create one" : "Log in")}
          </Link>
          {isLogin ? (
            <>
              {" · "}
              <Link href="/forgot-password">{t("Forgot password?")}</Link>
            </>
          ) : null}
        </div> : null}
        <SiteFooter showLanguage={false} />
      </section>
    </main>
  );
}
