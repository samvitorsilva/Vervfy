import assert from "node:assert/strict";
import { test } from "node:test";
import { requestWithBoundedRetries } from "../src/lib/audio-lease-retry.mjs";

const response = (status, retryAfter) => new Response("", {
  status,
  headers: retryAfter === undefined ? {} : { "Retry-After": retryAfter },
});

test("429 retries once and honors a bounded Retry-After", async () => {
  const calls = [];
  const waits = [];
  const result = await requestWithBoundedRetries(
    async () => [response(429, "9"), response(200)][calls.push("request") - 1],
    async (milliseconds) => waits.push(milliseconds),
    new AbortController().signal,
  );
  assert.equal(result.status, 200);
  assert.deepEqual(calls, ["request", "request"]);
  assert.deepEqual(waits, [2_000]);
});

test("503 retries stop after three total attempts", async () => {
  let calls = 0;
  let waits = 0;
  const result = await requestWithBoundedRetries(
    async () => { calls += 1; return response(503); },
    async () => { waits += 1; },
    new AbortController().signal,
  );
  assert.equal(result.status, 503);
  assert.equal(calls, 3);
  assert.equal(waits, 2);
});

test("quota response returns immediately without retry", async () => {
  let calls = 0;
  const result = await requestWithBoundedRetries(
    async () => { calls += 1; return response(402); },
    async () => assert.fail("Quota response must not wait for retry"),
    new AbortController().signal,
  );
  assert.equal(result.status, 402);
  assert.equal(calls, 1);
});

test("cancellation during retry wait prevents another request", async () => {
  const controller = new AbortController();
  let calls = 0;
  const pending = requestWithBoundedRetries(
    async () => { calls += 1; return response(503); },
    async (_milliseconds, signal) => new Promise((resolve, reject) => {
      if (signal.aborted) { reject(signal.reason); return; }
      signal.addEventListener("abort", () => reject(signal.reason), { once: true });
    }),
    controller.signal,
  );
  controller.abort(new DOMException("Track changed", "AbortError"));
  await assert.rejects(pending, { name: "AbortError" });
  assert.equal(calls, 1);
});

test("network exceptions use the same bounded retry count", async () => {
  let calls = 0;
  const waits = [];
  await assert.rejects(requestWithBoundedRetries(
    async () => { calls += 1; throw new TypeError("offline"); },
    async (milliseconds) => waits.push(milliseconds),
    new AbortController().signal,
  ), /offline/);
  assert.equal(calls, 3);
  assert.deepEqual(waits, [250, 500]);
});
