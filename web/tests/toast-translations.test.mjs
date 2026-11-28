import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const i18n = readFileSync(new URL("../src/lib/i18n.tsx", import.meta.url), "utf8");
const library = readFileSync(new URL("../src/components/library-app.tsx", import.meta.url), "utf8");
const playback = readFileSync(new URL("../src/lib/playback-controller.ts", import.meta.url), "utf8");
const split = i18n.indexOf("const frenchSpanishTranslations:");
assert.ok(split > 0, "Expected translation dictionaries");
const portuguese = i18n.slice(0, split);
const frenchSpanish = i18n.slice(split);

const notificationKeys = [
  "Cover updated.",
  "Cover removed.",
  "Track details saved.",
  "No audio files found in that selection.",
  "Uploading {completed}/{total}…",
  "{count} tracks uploaded; the rest were rate limited. Try again later.",
  "Saved {added} tracks; {failed} failed: {error}",
  "Saved {count} track to your library.",
  "Saved {count} tracks to your library.",
  "Upload failed: {error}",
  "{count} uploads failed: {error}",
  "Those tracks were already in your library.",
  "Cover lookup queued.",
  "Updated your Rediscover playlist.",
  "Created your Rediscover playlist.",
  "Saved offline tracks could not be loaded from this browser.",
  "Renamed playlist to “{name}”.",
  "Created “{name}”.",
  "Your account is still loading. Try again shortly.",
  "Removed “{name}” from offline storage.",
  "Downloaded “{name}” for offline listening.",
  "Removed “{track}” from “{playlist}”.",
  "Could not share this song.",
  "Song details copied to clipboard.",
  "Sharing is not available in this browser.",
  "“{name}” will play next.",
  "Added “{name}” to the queue.",
  "Shuffle on",
  "Shuffle off",
  "Repeat: off",
  "Repeat: all",
  "Repeat: one",
  "Added to “{name}”.",
  "Added “{name}” to the playlist.",
  "Library changes could not be synced: {error}",
  "Removed “{name}” from your library, but its local offline copy could not be cleared.",
  "Removed “{name}” from your library.",
  "Could not retry cover lookup.",
  "Could not save this track offline.",
  "Could not remove the track.",
  "The track could not restart. Please try again.",
  "The track could not start. Please try again.",
  "Playback stopped while buffering. Check your connection and try again.",
  "Press play to start.",
  "Storage quota is temporarily unavailable.",
  "Playback is rate limited. Please wait and try again.",
  "Playback is temporarily unavailable. Please try again soon."
];

test("notification keys exist in Brazilian Portuguese, French and Spanish", () => {
  for (const key of notificationKeys) {
    const marker = JSON.stringify(key) + ":";
    assert.ok(portuguese.includes(marker), "Missing Portuguese: " + key);
    assert.ok(frenchSpanish.includes(marker), "Missing French/Spanish: " + key);
  }
});

test("toast display translates raw controller messages and repeat mode uses explicit keys", () => {
  assert.ok(library.includes('className="toast">{t(toast)}</div>'));
  assert.ok(!library.includes('notify(t(`Repeat: '));
  assert.ok(library.includes('next === "off" ? "Repeat: off" : next === "all" ? "Repeat: all" : "Repeat: one"'));
  for (const key of notificationKeys.slice(-4)) {
    assert.ok(playback.includes(JSON.stringify(key)), "Playback message changed: " + key);
  }
});
