import assert from "node:assert/strict";
import { test } from "node:test";
import { moveQueueEntry } from "../src/lib/ui/reorder-queue.ts";

test("every move preserves track occurrences, input and the active occurrence", () => {
  const queue = ["duplicate", "other", "duplicate", "last"];
  for (let active = -1; active < queue.length; active++) {
    for (let from = 0; from < queue.length; from++) {
      for (let to = 0; to < queue.length; to++) {
        const result = moveQueueEntry(queue, active, from, to);
        const occurrences = [0, 1, 2, 3];
        occurrences.splice(to, 0, ...occurrences.splice(from, 1));
        assert.deepEqual(result.queue, occurrences.map((index) => queue[index]));
        assert.equal(result.queueIndex, active === -1 ? -1 : occurrences.indexOf(active));
        assert.deepEqual(queue, ["duplicate", "other", "duplicate", "last"]);
      }
    }
  }
});

test("invalid positions leave the queue and playback untouched", () => {
  const queue = ["one", "two"];
  for (const [from, to] of [[-1, 0], [0, 2], [2, 0], [0, -1], [0.5, 1], [0, NaN]]) {
    const result = moveQueueEntry(queue, 1, from, to);
    assert.equal(result.queue, queue);
    assert.equal(result.queueIndex, 1);
  }
});
