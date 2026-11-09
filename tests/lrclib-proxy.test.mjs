import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { forwardLrclibRequest } from "../web/src/lib/lrclib-proxy.ts";

const originalFetch = globalThis.fetch;
const originalBackend = process.env.BACKEND_URL;
afterEach(() => {
  globalThis.fetch = originalFetch;
  if (originalBackend === undefined) delete process.env.BACKEND_URL;
  else process.env.BACKEND_URL = originalBackend;
});

for (const status of [401, 403, 429, 503, 302]) {
  test(`lyrics proxy stops before provider fetch when backend returns ${status}`, async () => {
    process.env.BACKEND_URL = "https://backend.example.test";
    let calls = 0;
    globalThis.fetch = async (input) => {
      calls++;
      assert.equal(String(input), "https://backend.example.test/api/lyrics/authorize");
      return new Response("private backend diagnostic", { status });
    };
    const result = await forwardLrclibRequest(new Request("https://app.example.test/api/lyrics/lrclib/search?q=test"), "search");
    assert.equal(calls, 1);
    assert.equal(result.status, status === 302 ? 503 : status);
    assert.equal(result.headers.get("cache-control"), "no-store");
    assert.doesNotMatch(await result.text(), /private backend diagnostic/);
    if (status === 429) assert.equal(result.headers.get("retry-after"), "60");
  });
}

test("lyrics proxy forwards session only to backend, retains provider attribution and filters query", async () => {
  process.env.BACKEND_URL = "https://backend.example.test";
  const calls = [];
  globalThis.fetch = async (input, init) => {
    calls.push(String(input));
    const headers = new Headers(init?.headers);
    assert.ok(init?.signal);
    if (calls.length === 1) {
      assert.equal(headers.get("cookie"), "auralis_session=synthetic");
      assert.equal(init?.redirect, "manual");
      return new Response(null, { status: 204 });
    }
    assert.equal(headers.get("cookie"), null);
    assert.match(headers.get("lrclib-client") ?? "", /^Vervfy\/1.0/);
    assert.equal(init?.redirect, "error");
    return Response.json({ plainLyrics: "Synthetic test lyrics" });
  };
  const result = await forwardLrclibRequest(new Request("https://app.example.test/api/lyrics/lrclib/search?q=test&secret=ignored", {
    headers: { cookie: "auralis_session=synthetic" },
  }), "search");
  assert.equal(result.status, 200);
  assert.equal(calls[1], "https://lrclib.net/api/search?q=test");
});

test("lyrics proxy rejects oversized parameters without network access", async () => {
  globalThis.fetch = async () => { throw new Error("Unexpected network request"); };
  const result = await forwardLrclibRequest(new Request(`https://app.example.test/api/lyrics/lrclib/search?q=${"x".repeat(513)}`), "search");
  assert.equal(result.status, 400);
});

test("lyrics proxy fails closed when backend is not configured", async () => {
  delete process.env.BACKEND_URL;
  globalThis.fetch = async () => { throw new Error("Unexpected network request"); };
  const result = await forwardLrclibRequest(new Request("https://app.example.test/api/lyrics/lrclib/search?q=test"), "search");
  assert.equal(result.status, 502);
});
