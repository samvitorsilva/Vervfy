import { createServer } from "node:http";

const port = 8100;
const testCookie = "vervfy_playwright_session=authenticated";
const csrfToken = "playwright-csrf-token";
const audio = Buffer.alloc(44 + 22_050 * 6 * 2);
const sampleRate = 22_050;
const sampleCount = sampleRate * 6;
const dataSize = sampleCount * 2;
audio.write("RIFF", 0);
audio.writeUInt32LE(36 + dataSize, 4);
audio.write("WAVE", 8);
audio.write("fmt ", 12);
audio.writeUInt32LE(16, 16);
audio.writeUInt16LE(1, 20);
audio.writeUInt16LE(1, 22);
audio.writeUInt32LE(sampleRate, 24);
audio.writeUInt32LE(sampleRate * 2, 28);
audio.writeUInt16LE(2, 32);
audio.writeUInt16LE(16, 34);
audio.write("data", 36);
audio.writeUInt32LE(dataSize, 40);
for (let index = 0; index < sampleCount; index += 1) {
  const sample = Math.sin((2 * Math.PI * 440 * index) / sampleRate) * 0.15;
  audio.writeInt16LE(Math.round(sample * 32_767), 44 + index * 2);
}

let playlists = [];
let tracks = [];
let rateLimitedUploads = 1;

function send(response, status, body, headers = {}) {
  response.writeHead(status, {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    ...headers,
  });
  response.end(body);
}

function json(response, status, value, headers = {}) {
  send(response, status, JSON.stringify(value), {
    "Content-Type": "application/json; charset=utf-8",
    ...headers,
  });
}

function isAuthenticated(request) {
  return (request.headers.cookie ?? "").includes(testCookie);
}

function trackPayload(id, title) {
  return {
    id,
    title,
    artist: "Vervfy Test Artist",
    album: "Playwright Test Album",
    duration: 6,
    has_cover: false,
    cover_url: "",
    stream_url: `/api/tracks/${id}/stream`,
    custom_lyrics: null,
  };
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://127.0.0.1:${port}`);
  if (url.pathname === "/__health") {
    send(response, 200, "ok");
    return;
  }

  if (url.pathname === "/login" && request.method === "POST") {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    const form = new URLSearchParams(Buffer.concat(chunks).toString());
    if (
      form.get("username") !== "playwright" ||
      form.get("password") !== "playwright-test-password" ||
      form.get("csrf_token") !== csrfToken
    ) {
      send(
        response,
        400,
        JSON.stringify({ detail: "Incorrect username or password" }),
        { "Content-Type": "application/json; charset=utf-8" },
      );
      return;
    }
    playlists = [];
    tracks = [];
    rateLimitedUploads = 1;
    send(response, 303, "", {
      Location: "/",
      "Set-Cookie": `${testCookie}; Path=/; HttpOnly; SameSite=Lax`,
    });
    return;
  }

  if (url.pathname === "/api/me" && request.method === "GET") {
    if (!isAuthenticated(request)) {
      json(response, 401, { detail: "Not authenticated" });
      return;
    }
    json(response, 200, {
      id: "playwright-user",
      username: "playwright",
      email: null,
      created_at: 1_700_000_000,
      photo_url: "/api/account/photo",
      track_count: tracks.length,
    });
    return;
  }

  if (url.pathname === "/api/csrf" && request.method === "GET") {
    json(response, 200, { csrf_token: csrfToken });
    return;
  }

  if (!isAuthenticated(request)) {
    json(response, 401, { detail: "Not authenticated" });
    return;
  }

  if (url.pathname === "/api/account/photo" && request.method === "GET") {
    send(response, 200, '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="16" fill="#54e8d4"/></svg>', {
      "Content-Type": "image/svg+xml",
    });
    return;
  }

  if (url.pathname.startsWith("/artists/") && request.method === "GET") {
    json(response, 200, {
      deezer_id: 123,
      name: decodeURIComponent(url.pathname.slice("/artists/".length)),
      picture: "https://cdn-images.dzcdn.net/verified-test-photo.jpg",
      fans: 10,
      url: "https://www.deezer.com/artist/123",
      fetched_at: "2026-10-03T00:00:00+00:00",
    });
    return;
  }

  if (url.pathname === "/api/artists/photo" && request.method === "GET") {
    json(response, 200, {
      picture: "https://cdn-images.dzcdn.net/verified-test-photo.jpg",
      nb_fan: 10,
    });
    return;
  }

  if (url.pathname === "/api/artists/profile" && request.method === "GET") {
    json(response, 200, {
      profile: {
        bio: "Vervfy Test Artist is a verified test profile.",
        genre: "Pop",
        source: "Test artist source",
        source_url: "https://example.com/artist",
      },
    });
    return;
  }

  if (url.pathname === "/api/tracks" && request.method === "GET") {
    json(response, 200, { tracks });
    return;
  }

  if (url.pathname === "/api/library/state" && request.method === "GET") {
    json(
      response,
      200,
      { favorites: [], playlists },
      { ETag: '"playwright-state-v1"' },
    );
    return;
  }

  if (url.pathname === "/api/library/state" && request.method === "PUT") {
    if (request.headers["x-csrf-token"] !== csrfToken) {
      json(response, 403, { detail: "CSRF verification failed" });
      return;
    }
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    const payload = JSON.parse(Buffer.concat(chunks).toString());
    playlists = Array.isArray(payload.playlists) ? payload.playlists : [];
    json(response, 200, { favorites: [], playlists }, { ETag: '"playwright-state-v2"' });
    return;
  }

  if (url.pathname === "/api/library/upload" && request.method === "POST") {
    if (request.headers["x-csrf-token"] !== csrfToken) {
      json(response, 403, { detail: "CSRF verification failed" });
      return;
    }
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    if (rateLimitedUploads > 0) {
      rateLimitedUploads -= 1;
      json(response, 429, { detail: "Too many requests" }, { "Retry-After": "1" });
      return;
    }
    const body = Buffer.concat(chunks).toString("latin1");
    const filename = body.match(/filename="([^"]+)"/)?.[1] ?? `track-${tracks.length + 1}.wav`;
    const title = filename.replace(/\.[^.]+$/, "");
    const uploadedTrack = trackPayload(`playwright-track-${tracks.length + 1}`, title);
    tracks.push(uploadedTrack);
    json(response, 200, uploadedTrack);
    return;
  }

  if (/^\/api\/tracks\/playwright-track-\d+\/stream$/.test(url.pathname) && request.method === "GET") {
    const range = request.headers.range?.match(/^bytes=(\d+)-(\d*)$/);
    if (!range) {
      send(response, 200, audio, {
        "Content-Type": "audio/wav",
        "Content-Length": String(audio.length),
        "Accept-Ranges": "bytes",
      });
      return;
    }
    const start = Number(range[1]);
    const requestedEnd = range[2] ? Number(range[2]) : audio.length - 1;
    const end = Math.min(requestedEnd, audio.length - 1);
    if (start > end || start >= audio.length) {
      send(response, 416, "", { "Content-Range": `bytes */${audio.length}` });
      return;
    }
    send(response, 206, audio.subarray(start, end + 1), {
      "Content-Type": "audio/wav",
      "Content-Length": String(end - start + 1),
      "Content-Range": `bytes ${start}-${end}/${audio.length}`,
      "Accept-Ranges": "bytes",
    });
    return;
  }

  json(response, 404, { detail: "Not found" });
});

server.listen(port, "127.0.0.1");
