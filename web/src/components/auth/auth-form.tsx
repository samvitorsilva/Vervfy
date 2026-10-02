"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { getCsrfToken } from "@/lib/api/client";

type AuthMode = "login" | "register";

export default function AuthForm({ mode }: { mode: AuthMode }) {
  const isLogin = mode === "login";
  const endpoint = `/backend-auth/${mode}`;
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [csrfError, setCsrfError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let active = true;
    void getCsrfToken()
      .then((token) => {
        if (active) setCsrfToken(token);
      })
      .catch((reason: unknown) => {
        if (active) {
          setCsrfError(
            reason instanceof Error ? reason.message : "Could not load the form.",
          );
        }
      });

    return () => {
      active = false;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csrfToken || pending) return;

    setPending(true);
    setError(null);
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
      setError(
        typeof result?.detail === "string"
          ? result.detail
          : `Could not ${isLogin ? "log in" : "create the account"} (${response.status}).`,
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The authentication request could not be completed.",
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
        <h1 className="auth-title">
          {isLogin ? "Welcome back" : "Create your account"}
        </h1>
        <p className="auth-sub">
          {isLogin
            ? "Log in to reach your synced library."
            : "Your library, uploads, and covers will be synced to it."}
        </p>

        {(error || csrfError) && (
          <div className="auth-error" role="alert">
            {error || csrfError}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="auth-field">
            <label htmlFor="username">Username</label>
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
              onChange={(event) => setUsername(event.currentTarget.value)}
            />
          </div>
          {!isLogin && (
            <div className="auth-field">
              <label htmlFor="email">Email (optional, not used to sign in)</label>
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
            <label htmlFor="password">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete={isLogin ? "current-password" : "new-password"}
              minLength={isLogin ? undefined : 8}
              required
            />
          </div>
          <button
            className="auth-submit"
            type="submit"
            disabled={!csrfToken || pending || !!csrfError}
          >
            {pending
              ? isLogin
                ? "Logging in…"
                : "Creating account…"
              : isLogin
                ? "Log in"
                : "Create account"}
          </button>
        </form>

        <div className="auth-footer">
          {isLogin ? "No account yet? " : "Already have an account? "}
          <Link href={isLogin ? "/register" : "/login"}>
            {isLogin ? "Create one" : "Log in"}
          </Link>
        </div>
      </section>
    </main>
  );
}
