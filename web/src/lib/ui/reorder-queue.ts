/** Move one queue occurrence while keeping the currently playing occurrence. */
export function moveQueueEntry(queue: string[], queueIndex: number, from: number, to: number) {
  if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to < 0 || from >= queue.length || to >= queue.length || from === to) {
    return { queue, queueIndex };
  }
  const next = [...queue];
  const [track] = next.splice(from, 1);
  next.splice(to, 0, track);
  let active = queueIndex;
  if (active === from) active = to;
  else {
    if (from < active) active--;
    if (to <= active) active++;
  }
  return { queue: next, queueIndex: active };
}
