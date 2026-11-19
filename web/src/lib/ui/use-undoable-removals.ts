"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface Removal {
  id: string;
  label: string;
  commit: () => Promise<void>;
  timer: ReturnType<typeof setTimeout> | null;
  busy: boolean;
}

/** Delay durable removal; Undo never needs to reconstruct a deleted upload. */
export function useUndoableRemovals() {
  const pending = useRef(new Map<string, Removal>());
  const [items, setItems] = useState<Array<{ id: string; label: string; busy: boolean }>>([]);
  const publish = useCallback(() => setItems([...pending.current.values()].map(({ id, label, busy }) => ({ id, label, busy }))), []);
  const commit = useCallback(async (id: string) => {
    const item = pending.current.get(id);
    if (!item || item.busy) return;
    if (item.timer) clearTimeout(item.timer);
    item.timer = null;
    item.busy = true;
    publish();
    try { await item.commit(); }
    finally { pending.current.delete(id); publish(); }
  }, [publish]);
  const resume = useCallback((id: string) => {
    const item = pending.current.get(id);
    if (!item || item.busy || item.timer) return;
    item.timer = setTimeout(() => { void commit(id); }, 8000);
  }, [commit]);
  const pause = useCallback((id: string) => {
    const item = pending.current.get(id);
    if (!item || item.busy) return;
    if (item.timer) clearTimeout(item.timer);
    item.timer = null;
  }, []);
  const stage = useCallback((id: string, label: string, action: () => Promise<void>) => {
    if (pending.current.has(id)) return;
    pending.current.set(id, { id, label, commit: action, busy: false, timer: null });
    resume(id);
    publish();
  }, [publish, resume]);
  const undo = useCallback((id: string) => {
    const item = pending.current.get(id);
    if (!item || item.busy) return;
    if (item.timer) clearTimeout(item.timer);
    pending.current.delete(id);
    publish();
  }, [publish]);
  useEffect(() => {
    const flush = () => { for (const id of pending.current.keys()) void commit(id); };
    window.addEventListener("pagehide", flush);
    return () => { window.removeEventListener("pagehide", flush); flush(); };
  }, [commit]);
  return { items, stage, undo, pause, resume };
}
