import { expect, test, type APIRequestContext } from "@playwright/test";

const backend = process.env.PLAYWRIGHT_ISOLATION_BACKEND_URL;
test.skip(!backend, "Requires tests/readiness_backend.py; never point this test at production.");

function syntheticWav() {
  const data = Buffer.alloc(1644);
  data.write("RIFF"); data.writeUInt32LE(1636, 4); data.write("WAVEfmt ", 8);
  data.writeUInt32LE(16, 16); data.writeUInt16LE(1, 20); data.writeUInt16LE(1, 22);
  data.writeUInt32LE(8000, 24); data.writeUInt32LE(16000, 28);
  data.writeUInt16LE(2, 32); data.writeUInt16LE(16, 34);
  data.write("data", 36); data.writeUInt32LE(1600, 40);
  return data;
}

async function register(client: APIRequestContext, username: string) {
  const token = await (await client.get("/api/csrf")).json();
  const result = await client.post("/register", {
    form: { username, password: "synthetic-audit-password", csrf_token: token.csrf_token },
    maxRedirects: 0,
  });
  expect(result.status()).toBe(303);
  return (await (await client.get("/api/csrf")).json()).csrf_token as string;
}

test("real API isolates accounts across read, update, stream, delete, photos and playlists", async ({ playwright }) => {
  expect(new URL(backend!).hostname).toBe("127.0.0.1");
  const owner = await playwright.request.newContext({ baseURL: backend });
  const other = await playwright.request.newContext({ baseURL: backend });
  const anonymous = await playwright.request.newContext({ baseURL: backend });
  try {
    const suffix = Date.now().toString(36);
    const ownerCsrf = await register(owner, `owner-${suffix}`);
    const otherCsrf = await register(other, `other-${suffix}`);
    const ownerHeaders = { "x-csrf-token": ownerCsrf };
    const otherHeaders = { "x-csrf-token": otherCsrf };
    const upload = await owner.post("/api/library/upload", {
      headers: ownerHeaders,
      multipart: { file: { name: "audit.wav", mimeType: "audio/wav", buffer: syntheticWav() } },
    });
    expect(upload.status()).toBe(200);
    const track = await upload.json();
    expect((await owner.get(`/api/tracks/${track.id}/stream`, { maxRedirects: 0 })).status()).toBe(302);
    await expect((await other.get("/api/tracks")).json()).resolves.toEqual({ tracks: [] });

    for (const path of [`/api/tracks/${track.id}/stream`, `/api/tracks/${track.id}/cover`, "/api/library/upload/foreign-job"]) {
      expect((await other.get(path, { maxRedirects: 0 })).status()).toBe(404);
      expect((await anonymous.get(path, { maxRedirects: 0 })).status()).toBe(401);
    }
    expect((await other.patch(`/api/tracks/${track.id}`, { headers: otherHeaders, data: { title: "changed", artist: "changed", album: "changed" } })).status()).toBe(404);
    expect((await other.put(`/api/tracks/${track.id}/lyrics`, { headers: otherHeaders, data: { lyrics: "changed" } })).status()).toBe(404);
    expect((await other.delete(`/api/tracks/${track.id}`, { headers: otherHeaders })).status()).toBe(404);
    expect((await other.post("/api/library/listening", { headers: otherHeaders, data: { trackId: track.id } })).status()).toBe(404);
    expect((await other.patch(`/api/tracks/${encodeURIComponent("' OR 1=1 --")}`, { headers: otherHeaders, data: { title: "changed", artist: "changed", album: "changed" } })).status()).toBe(404);

    const before = await owner.get("/api/library/state");
    expect((await owner.put("/api/library/state", { headers: { ...ownerHeaders, "if-match": before.headers().etag }, data: {
      favorites: [track.id], playlists: [{ id: `playlist-${suffix}`, name: "Private", trackIds: [track.id] }],
    } })).status()).toBe(200);
    const otherState = await other.get("/api/library/state");
    const filtered = await other.put("/api/library/state", { headers: { ...otherHeaders, "if-match": otherState.headers().etag }, data: {
      favorites: [track.id], playlists: [{ id: `other-${suffix}`, name: "Other", trackIds: [track.id] }],
    } });
    expect(filtered.status()).toBe(200);
    const filteredState = await filtered.json();
    expect(filteredState.favorites).toEqual([]);
    expect(filteredState.playlists[0].trackIds).toEqual([]);
    expect((await other.post(`/api/library/playlists/playlist-${suffix}/listening`, { headers: otherHeaders })).status()).toBe(404);
    const collision = await other.put("/api/library/state", { headers: { ...otherHeaders, "if-match": filtered.headers().etag }, data: {
      favorites: [], playlists: [{ id: `playlist-${suffix}`, name: "Overwrite", trackIds: [] }],
    } });
    expect(collision.status()).toBe(409);
    expect((await (await owner.get("/api/library/state")).json()).playlists[0].name).toBe("Private");

    const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGMUCahgwAaYsIoOWgkAsMwA7Nwb4ScAAAAASUVORK5CYII=", "base64");
    expect((await owner.post("/api/account/photo", { headers: ownerHeaders, multipart: { file: { name: "photo.png", mimeType: "image/png", buffer: png } } })).status()).toBe(200);
    expect((await other.get("/api/account/photo")).status()).toBe(404);
    expect((await owner.put("/api/artists/photo", { headers: ownerHeaders, multipart: { name: "Synthetic Artist", file: { name: "photo.png", mimeType: "image/png", buffer: png } } })).status()).toBe(200);
    expect((await other.get("/api/artists/photo?name=Synthetic%20Artist")).status()).toBe(404);
    expect((await other.put(`/api/tracks/${track.id}/cover`, { headers: otherHeaders, multipart: { file: { name: "cover.png", mimeType: "image/png", buffer: png } } })).status()).toBe(404);
    expect((await other.delete(`/api/tracks/${track.id}/cover`, { headers: otherHeaders })).status()).toBe(404);
    expect((await owner.get(`/api/tracks/${track.id}/cover`)).status()).toBe(200);
    expect((await (await owner.get("/api/tracks")).json()).tracks[0].title).toBe(track.title);
  } finally {
    await owner.dispose(); await other.dispose(); await anonymous.dispose();
  }
});
