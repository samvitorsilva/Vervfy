const LRCLIB_BASE_URL = "https://lrclib.net/api";
const LRCLIB_CLIENT = "Vervfy/1.0 (https://github.com/samvitorsilva/Vervfy)";

export async function forwardLrclibRequest(
  request: Request,
  endpoint: "get" | "search",
) {
  const incomingUrl = new URL(request.url);
  const allowedParameters = endpoint === "get"
    ? new Set(["track_name", "artist_name", "album_name", "duration"])
    : new Set(["track_name", "artist_name", "q"]);
  const query = new URLSearchParams();
  for (const [key, value] of incomingUrl.searchParams) {
    if (allowedParameters.has(key) && !query.has(key)) {
      query.set(key, value);
    }
  }

  if (
    (endpoint === "get" && (!query.get("track_name") || !query.get("artist_name"))) ||
    (endpoint === "search" &&
      !((query.get("track_name") && query.get("artist_name")) || query.get("q")))
  ) {
    return Response.json({ detail: "Invalid lyrics lookup parameters." }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${LRCLIB_BASE_URL}/${endpoint}?${query}`, {
      cache: "no-store",
      headers: {
        Accept: "application/json",
        "Lrclib-Client": LRCLIB_CLIENT,
      },
      signal: request.signal,
    });
    const headers = new Headers({
      "Cache-Control": "no-store",
      "Content-Type": upstream.headers.get("Content-Type") ?? "application/json",
    });
    const retryAfter = upstream.headers.get("Retry-After");
    if (retryAfter) headers.set("Retry-After", retryAfter);

    return new Response(upstream.body, { status: upstream.status, headers });
  } catch (error) {
    if (request.signal.aborted) throw error;
    console.error("LRCLIB request failed.", error);
    return Response.json(
      { detail: "Lyrics provider is temporarily unavailable." },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
