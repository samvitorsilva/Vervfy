"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { getCsrfToken } from "@/lib/api/client";
import { LanguageSelect, useLanguage } from "@/lib/i18n";

type AuthMode = "login" | "register";

export default function AuthForm({ mode }: { mode: AuthMode }) {
  const { t } = useLanguage();
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
            reason instanceof Error ? reason.message : t("Could not load the form."),
          );
        }
      });

    return () => {
      active = false;
    };
  }, [t]);

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
      setError(t(detail));
      if (incorrectPassword) passwordInputRef.current?.focus();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : t("The authentication request could not be completed."),
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
          {t(isLogin ? "Welcome back" : "Create your account")}
        </h1>
        <p className="auth-sub">
          {isLogin
            ? t("Log in to reach your synced library.")
            : t("Your library, uploads, and covers will be synced to it.")}
        </p>

        {(error || csrfError) && (
          <div id="auth-error" className="auth-error" role="alert">
            {error || csrfError}
          </div>
        )}

        <form onSubmit={handleSubmit}>
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
        </form>

        <div className="auth-footer">
          {t(isLogin ? "No account yet? " : "Already have an account? ")}
          <Link href={isLogin ? "/register" : "/login"}>
            {t(isLogin ? "Create one" : "Log in")}
          </Link>
        </div>
      </section>
    </main>
  );
}
