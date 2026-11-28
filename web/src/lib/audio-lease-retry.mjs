const MAX_ATTEMPTS = 3;
const MAX_RETRY_AFTER_MS = 2_000;

export async function requestWithBoundedRetries(request, wait, signal) {
  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt += 1) {
    if (signal.aborted) {
      throw signal.reason ?? new DOMException("Aborted", "AbortError");
    }

    let response;
    try {
      response = await request(signal);
    } catch (error) {
      if (signal.aborted || attempt === MAX_ATTEMPTS - 1) throw error;
      await wait(250 * 2 ** attempt, signal);
      continue;
    }

    if (response.status !== 429 && response.status !== 503) return response;
    if (attempt === MAX_ATTEMPTS - 1) return response;

    const retryAfter = Number(response.headers.get("Retry-After"));
    const delay = Number.isFinite(retryAfter) && retryAfter >= 0
      ? Math.min(retryAfter * 1_000, MAX_RETRY_AFTER_MS)
      : 250 * 2 ** attempt;
    await wait(delay, signal);
  }

  throw new Error("Retry limit reached");
}
