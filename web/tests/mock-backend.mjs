import { createServer } from "node:http";

const port = 8100;
const testCookie = "vervfy_playwright_session=authenticated";
const csrfToken = "playwright-csrf-token";
const sampleRate = 22_050;
const sampleCount = sampleRate * 30;
const dataSize = sampleCount * 2;
const audio = Buffer.alloc(44 + dataSize);
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
let artistPhotoSource = "none";
let signedAudioUrlVersion = 0;
let expireNextMediaUrl = false;
let mediaFailuresRemaining = 0;
const expiredMediaTokens = new Set();
const artistPhoto = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGMUCahgwAaYsIoOWgkAsMwA7Nwb4ScAAAAASUVORK5CYII=",
  "base64",
);

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
    duration: 30,
    has_cover: false,
    cover_source: "placeholder",
    cover_url: `/api/tracks/${id}/cover`,
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

  if (url.pathname === "/__test/expire-next-media" && request.method === "POST") {
    expireNextMediaUrl = true;
    send(response, 204, "");
    return;
  }

  if (url.pathname === "/__test/fail-media" && request.method === "POST") {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    const payload = JSON.parse(Buffer.concat(chunks).toString() || "{}");
    mediaFailuresRemaining =
      Number.isInteger(payload.count) && payload.count > 0 ? payload.count : 1;
    send(response, 204, "");
    return;
  }

  const signedAudio = url.pathname.match(
    /^\/storage\/v1\/object\/sign\/songs\/(playwright-track-\d+)\.wav$/,
  );
  if (signedAudio && url.searchParams.has("token") && request.method === "GET") {
    const token = url.searchParams.get("token");
    if (request.headers["sec-fetch-dest"] === "audio" && expireNextMediaUrl) {
      expiredMediaTokens.add(token);
      expireNextMediaUrl = false;
    }
    const corsHeaders = {
      "Access-Control-Allow-Origin": "http://127.0.0.1:3100",
      "Access-Control-Expose-Headers": "Accept-Ranges, Content-Length, Content-Range",
      "Accept-Ranges": "bytes",
      "Content-Type": "audio/wav",
      Vary: "Origin",
    };
    if (expiredMediaTokens.has(token)) {
      send(response, 403, "signed URL expired", corsHeaders);
      return;
    }
    if (
      request.headers["sec-fetch-dest"] === "audio" &&
      mediaFailuresRemaining > 0
    ) {
      mediaFailuresRemaining -= 1;
      send(response, 503, "temporary media failure", corsHeaders);
      return;
    }
    const range = request.headers.range?.match(/^bytes=(\d+)-(\d*)$/);
    if (!range) {
      send(response, 200, audio, {
        ...corsHeaders,
        "Content-Length": String(audio.length),
      });
      return;
    }
    const start = Number(range[1]);
    const end = Math.min(
      range[2] ? Number(range[2]) : audio.length - 1,
      audio.length - 1,
    );
    if (start > end || start >= audio.length) {
      send(response, 416, "", {
        ...corsHeaders,
        "Content-Range": `bytes */${audio.length}`,
      });
      return;
    }
    send(response, 206, audio.subarray(start, end + 1), {
      ...corsHeaders,
      "Content-Length": String(end - start + 1),
      "Content-Range": `bytes ${start}-${end}/${audio.length}`,
    });
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
    artistPhotoSource = "none";
    signedAudioUrlVersion = 0;
    expireNextMediaUrl = false;
    mediaFailuresRemaining = 0;
    expiredMediaTokens.clear();
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

  if (url.pathname === "/api/config" && request.method === "GET") {
    json(response, 200, { lyrics_provider_lrclib: true });
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

  if (url.pathname === "/api/artists/profile" && request.method === "GET") {
    json(response, 200, {
      profile: {
        bio: "Vervfy Test Artist is a verified test profile.",
        genre: "Pop",
        source: "Wikipedia",
        source_url: "https://en.wikipedia.org/wiki/Vervfy_Test_Artist",
        source_modified: "true",
      },
    });
    return;
  }

  if (url.pathname === "/api/artists/images" && request.method === "GET") {
    json(response, 200, {
      artists: {
        vervfytestartist: {
          audiodb_id: null,
          image_url: null,
          banner_url: null,
          status: "not_found",
          user_photo_url:
            artistPhotoSource === "user"
              ? "/api/artists/photo?name=Vervfy%20Test%20Artist"
              : null,
          pending: false,
        },
      },
    });
    return;
  }

  if (url.pathname === "/api/artists/photo" && request.method === "GET") {
    if (artistPhotoSource !== "user") {
      json(response, 404, { detail: "No artist photo" });
      return;
    }
    send(response, 200, artistPhoto, {
      "Content-Type": "image/png",
    });
    return;
  }

  if (url.pathname === "/api/artists/photo" && ["PUT", "DELETE"].includes(request.method ?? "")) {
    if (request.headers["x-csrf-token"] !== csrfToken) {
      json(response, 403, { detail: "CSRF verification failed" });
      return;
    }
    if (request.method === "PUT") {
      let uploadedBytes = 0;
      for await (const chunk of request) uploadedBytes += chunk.length;
      if (!uploadedBytes) {
        json(response, 400, { detail: "Empty image upload" });
        return;
      }
      artistPhotoSource = "user";
    } else {
      artistPhotoSource = "none";
    }
    json(response, 200, { photo_url: "/api/artists/photo?name=Vervfy%20Test%20Artist" });
    return;
  }

  if (url.pathname === "/api/tracks" && request.method === "GET") {
    const orderedTracks = [...tracks].sort(
      (left, right) =>
        left.artist.toLowerCase().localeCompare(right.artist.toLowerCase()) ||
        left.title.toLowerCase().localeCompare(right.title.toLowerCase()),
    );
    json(response, 200, { tracks: orderedTracks });
    return;
  }

  if (url.pathname === "/api/tracks/covers" && request.method === "GET") {
    json(response, 200, { covers: {}, pending: false });
    return;
  }

  const trackCover = url.pathname.match(/^\/api\/tracks\/([^/]+)\/cover$/);
  if (trackCover && request.method === "GET") {
    const track = tracks.find((item) => item.id === decodeURIComponent(trackCover[1]));
    if (!track) {
      json(response, 404, { detail: "Track not found" });
      return;
    }
    send(response, 200, '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#8b7fff"/></svg>', {
      "Content-Type": "image/svg+xml",
    });
    return;
  }

  if (trackCover && ["PUT", "DELETE"].includes(request.method ?? "")) {
    if (request.headers["x-csrf-token"] !== csrfToken) {
      json(response, 403, { detail: "CSRF verification failed" });
      return;
    }
    const track = tracks.find((item) => item.id === decodeURIComponent(trackCover[1]));
    if (!track) {
      json(response, 404, { detail: "Track not found" });
      return;
    }
    if (request.method === "PUT") {
      let uploadedBytes = 0;
      for await (const chunk of request) uploadedBytes += chunk.length;
      if (!uploadedBytes) {
        json(response, 400, { detail: "Empty image upload" });
        return;
      }
      track.cover_source = "user";
      track.has_cover = true;
    } else {
      track.cover_source = "placeholder";
      track.has_cover = false;
    }
    json(response, 200, { cover_source: track.cover_source });
    return;
  }

  const trackDetails = url.pathname.match(/^\/api\/tracks\/([^/]+)$/);
  if (trackDetails && request.method === "PATCH") {
    if (request.headers["x-csrf-token"] !== csrfToken) {
      json(response, 403, { detail: "CSRF verification failed" });
      return;
    }
    const track = tracks.find((item) => item.id === decodeURIComponent(trackDetails[1]));
    if (!track) {
      json(response, 404, { detail: "Track not found" });
      return;
    }
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    Object.assign(track, JSON.parse(Buffer.concat(chunks).toString()));
    json(response, 200, track);
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

  const audioStream = url.pathname.match(/^\/api\/tracks\/(playwright-track-\d+)\/stream$/);
  if (audioStream && request.method === "GET") {
    signedAudioUrlVersion += 1;
    send(response, 302, "", {
      Location: `http://127.0.0.1:8100/storage/v1/object/sign/songs/${audioStream[1]}.wav?token=mock-${signedAudioUrlVersion}`,
      "Cache-Control": "private, no-store",
    });
    return;
  }

  json(response, 404, { detail: "Not found" });
});

server.listen(port, "127.0.0.1");
