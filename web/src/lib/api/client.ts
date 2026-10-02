const CSRF_PATH = "/api/csrf";

export class ApiError extends Error {
  readonly status: number;
  readonly retryAfter: number | null;

  constructor(message: string, status: number, retryAfter: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

let csrfToken: string | null = null;
let csrfRequest: Promise<string> | null = null;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function redirectToLoginOnUnauthorized(input: string, response: Response): void {
  if (
    typeof window !== "undefined" &&
    input.startsWith("/api/") &&
    response.status === 401
  ) {
    window.location.assign("/login");
  }
}

async function responseError(response: Response): Promise<ApiError> {
  let message = `Request failed (${response.status})`;
  const body = await response.text().catch(() => "");

  if (body) {
    try {
      const parsed: unknown = JSON.parse(body);
      if (isRecord(parsed) && typeof parsed.detail === "string") {
        message = parsed.detail;
      }
    } catch {
      const text = body.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
      if (text) message = text.slice(0, 500);
    }
  }

  const retryAfterHeader = response.headers.get("Retry-After");
  const parsedRetryAfter = retryAfterHeader === null ? NaN : Number(retryAfterHeader);
  return new ApiError(
    message,
    response.status,
    Number.isFinite(parsedRetryAfter) ? parsedRetryAfter : null,
  );
}

export async function getCsrfToken(forceRefresh = false): Promise<string> {
  if (csrfToken && !forceRefresh) return csrfToken;
  if (csrfRequest && !forceRefresh) return csrfRequest;

  csrfRequest = (async () => {
    const response = await fetch(CSRF_PATH, {
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!response.ok) throw await responseError(response);

    const payload: unknown = await response.json();
    if (!isRecord(payload) || typeof payload.csrf_token !== "string") {
      throw new Error("The backend returned an invalid CSRF token response.");
    }
    csrfToken = payload.csrf_token;
    return csrfToken;
  })().finally(() => {
    csrfRequest = null;
  });

  return csrfRequest;
}

export interface ApiRequestOptions {
  csrf?: boolean;
  retryCsrfOnForbidden?: boolean;
}

export async function apiFetch(
  input: string,
  init: RequestInit = {},
  options: ApiRequestOptions = {},
): Promise<Response> {
  const send = async (refreshCsrf: boolean): Promise<Response> => {
    const headers = new Headers(init.headers);
    if (options.csrf) {
      headers.set("X-CSRF-Token", await getCsrfToken(refreshCsrf));
    }

    return fetch(input, {
      ...init,
      headers,
      credentials: init.credentials ?? "same-origin",
    });
  };

  let response = await send(false);
  if (options.csrf && options.retryCsrfOnForbidden && response.status === 403) {
    response = await send(true);
  }

  redirectToLoginOnUnauthorized(input, response);
  return response;
}

export async function expectOk(response: Response): Promise<Response> {
  if (!response.ok) throw await responseError(response);
  return response;
}

const wait = (milliseconds: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

export async function fetchWithRetry(
  input: string,
  init: RequestInit = {},
  attempts = 5,
): Promise<Response> {
  let lastError: Error = new Error("The backend is unavailable.");

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30_000);

    try {
      const response = await fetch(input, {
        ...init,
        credentials: init.credentials ?? "same-origin",
        signal: controller.signal,
      });
      redirectToLoginOnUnauthorized(input, response);
      if (
        response.ok ||
        response.status === 401 ||
        response.status === 403 ||
        response.status === 404
      ) {
        return response;
      }
      lastError = await responseError(response);
    } catch (error) {
      lastError =
        error instanceof Error ? error : new Error("The backend is unavailable.");
    } finally {
      clearTimeout(timeout);
    }

    if (attempt < attempts - 1) {
      await wait(Math.min(2_000 * 2 ** attempt, 10_000));
    }
  }

  throw lastError;
}

export async function uploadWithRetry(path: string, file: File): Promise<Response> {
  const body = new FormData();
  body.append("file", file, file.name);

  let rateLimitRetries = 0;
  while (true) {
    const response = await apiFetch(
      path,
      { method: "POST", body },
      { csrf: true, retryCsrfOnForbidden: true },
    );

    if (response.status !== 429) {
      return expectOk(response);
    }

    const retryAfterHeader = response.headers.get("Retry-After");
    const retryAfter = retryAfterHeader === null ? NaN : Number(retryAfterHeader);
    if (Number.isFinite(retryAfter) && retryAfter > 60) {
      throw new ApiError(
        `Upload rate limited. Try again in ${Math.ceil(retryAfter / 60)} min.`,
        429,
        retryAfter,
      );
    }
    if (rateLimitRetries >= 3) {
      throw new ApiError(
        "Upload is still rate limited. Wait a few minutes and try again.",
        429,
        Number.isFinite(retryAfter) ? retryAfter : null,
      );
    }

    await wait(
      Math.min(
        30_000,
        Math.max(1_000, Number.isFinite(retryAfter) ? retryAfter * 1_000 : 1_000),
      ),
    );
    rateLimitRetries += 1;
  }
}
