"use client";

import { Fragment } from "react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent,
} from "react";
import { apiFetch, expectOk } from "@/lib/api/client";
import { artistNames } from "@/components/artist-explorer";
import type { CachedLyrics, RepeatMode, TrackRecord } from "@/store/player-store";
import { usePlayerStore } from "@/store/player-store";

interface TimedLine {
  time: number;
  text: string;
}

function syncSafeInteger(bytes: Uint8Array, offset: number): number {
  return (
    ((bytes[offset] & 0x7f) << 21) |
    ((bytes[offset + 1] & 0x7f) << 14) |
    ((bytes[offset + 2] & 0x7f) << 7) |
    (bytes[offset + 3] & 0x7f)
  );
}

function bigEndianInteger(bytes: Uint8Array, offset: number, length: number): number {
  let value = 0;
  for (let index = 0; index < length; index += 1) {
    value = value * 256 + bytes[offset + index];
  }
  return value;
}

function decodeId3Text(bytes: Uint8Array, encoding: number): string {
  try {
    const decoderName =
      encoding === 0 ? "latin1" : encoding === 1 ? "utf-16" : encoding === 2 ? "utf-16be" : "utf-8";
    return new TextDecoder(decoderName).decode(bytes).replace(/\0+$/g, "");
  } catch {
    return "";
  }
}

function findId3Terminator(bytes: Uint8Array, start: number, wide: boolean): number {
  const step = wide ? 2 : 1;
  for (let index = start; index < bytes.length - (wide ? 1 : 0); index += step) {
    if (bytes[index] === 0 && (!wide || bytes[index + 1] === 0)) return index;
  }
  return bytes.length;
}

function removeUnsynchronization(bytes: Uint8Array): Uint8Array {
  const output: number[] = [];
  for (let index = 0; index < bytes.length; index += 1) {
    output.push(bytes[index]);
    if (bytes[index] === 0xff && bytes[index + 1] === 0) index += 1;
  }
  return Uint8Array.from(output);
}

function parseSynchronizedId3Frame(frame: Uint8Array): TimedLine[] | null {
  try {
    const encoding = frame[0];
    const wide = encoding === 1 || encoding === 2;
    let index = 6;
    const descriptionEnd = findId3Terminator(frame, index, wide);
    index = descriptionEnd + (wide ? 2 : 1);
    const lines: TimedLine[] = [];
    while (index < frame.length) {
      const textEnd = findId3Terminator(frame, index, wide);
      if (textEnd >= frame.length) break;
      const text = decodeId3Text(frame.subarray(index, textEnd), encoding);
      index = textEnd + (wide ? 2 : 1);
      if (index + 4 > frame.length) break;
      const timestamp = bigEndianInteger(frame, index, 4);
      index += 4;
      if (Number.isFinite(timestamp)) {
        lines.push({ time: timestamp * (frame[4] === 1 ? 26.122 : 1), text });
      }
    }
    return lines.length ? lines.sort((left, right) => left.time - right.time) : null;
  } catch {
    return null;
  }
}

function parseUnsynchronizedId3Frame(frame: Uint8Array): string | null {
  try {
    const encoding = frame[0];
    const wide = encoding === 1 || encoding === 2;
    const descriptionEnd = findId3Terminator(frame, 4, wide);
    const text = decodeId3Text(frame.subarray(descriptionEnd + (wide ? 2 : 1)), encoding).trim();
    return text || null;
  } catch {
    return null;
  }
}

async function readEmbeddedLyrics(trackId: string, signal: AbortSignal): Promise<LyricsData | null> {
  const response = await apiFetch(`/api/tracks/${encodeURIComponent(trackId)}/tag-head`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) return null;
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes.length < 10 || bytes[0] !== 0x49 || bytes[1] !== 0x44 || bytes[2] !== 0x33) {
    return null;
  }

  const version = bytes[3];
  const tagEnd = Math.min(bytes.length, 10 + syncSafeInteger(bytes, 6));
  let offset = 10;
  if (version === 2 && (bytes[5] & 0x40) !== 0) return null;
  if (version >= 3 && (bytes[5] & 0x40) !== 0) {
    const extendedSize = version === 3
      ? bigEndianInteger(bytes, offset, 4) + 4
      : syncSafeInteger(bytes, offset);
    offset += extendedSize;
  }
  const body = (bytes[5] & 0x80) !== 0
    ? removeUnsynchronization(bytes.subarray(offset, tagEnd))
    : bytes.subarray(offset, tagEnd);
  offset = 0;

  while (offset + (version === 2 ? 6 : 10) <= body.length) {
    const headerSize = version === 2 ? 6 : 10;
    const idLength = version === 2 ? 3 : 4;
    const frameId = String.fromCharCode(...body.subarray(offset, offset + idLength));
    if (!frameId.trim() || /^\0+$/.test(frameId)) break;
    const frameSize = version === 2
      ? bigEndianInteger(body, offset + 3, 3)
      : version === 4
        ? syncSafeInteger(body, offset + 4)
        : bigEndianInteger(body, offset + 4, 4);
    const frameFlags = version === 2 ? 0 : bigEndianInteger(body, offset + 8, 2);
    const start = offset + headerSize;
    const end = start + frameSize;
    if (!frameSize || end > body.length) break;
    offset = end;
    if (
      version !== 2 &&
      (version === 4 ? (frameFlags & 0x000c) !== 0 : (frameFlags & 0x00c0) !== 0)
    ) continue;

    let frame = body.subarray(start, end);
    if (version === 4 && (frameFlags & 0x0002) !== 0) frame = removeUnsynchronization(frame);
    if (["SYLT", "SLT"].includes(frameId)) {
      const lines = parseSynchronizedId3Frame(frame);
      if (lines) return { source: "sylt", lines };
    }
    if (["USLT", "ULT"].includes(frameId)) {
      const text = parseUnsynchronizedId3Frame(frame);
      if (text) return { source: "uslt", text };
    }
  }
  return null;
}

type LyricsData = CachedLyrics;

function parseLrc(value: string): TimedLine[] {
  const lines: TimedLine[] = [];
  const stamp = /\[(\d{1,2}):(\d{2}(?:[.:]\d{1,3})?)\]/g;
  let offsetMs = 0;
  for (const raw of value.split(/\r?\n/)) {
    const offset = raw.match(/^\s*\[offset\s*:\s*([+-]?\d+)\s*\]\s*$/i);
    if (offset) {
      offsetMs = Number(offset[1]) || 0;
      continue;
    }
    const matches = [...raw.matchAll(stamp)];
    if (!matches.length) continue;
    const text = raw.replace(stamp, "").trim();
    for (const match of matches) {
      const seconds = Number(match[2].replace(":", "."));
      if (!Number.isFinite(seconds)) continue;
      lines.push({
        time: Math.max(0, (Number(match[1]) * 60 + seconds) * 1000 + offsetMs),
        text,
      });
    }
  }
  return lines.sort((left, right) => left.time - right.time);
}

function cleanTitle(value: string): string {
  return value
    .replace(/\s*[\[(]\s*(?:feat(?:uring)?\.?|ft\.?|with)\s+[^\])]*[\])]/gi, "")
    .replace(/\s+(?:feat(?:uring)?\.?|ft\.?|with)\s+.+$/gi, "")
    .replace(/\s*[\[(]\s*(?:explicit|clean|deluxe|bonus|radio\s+edit|live|remaster(?:ed)?)\s*[\])]/gi, "")
    .trim();
}

function normalized(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function activeLine(lines: TimedLine[], timeMs: number): number {
  let low = 0;
  let high = lines.length - 1;
  let active = -1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (lines[middle].time <= timeMs) {
      active = middle;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return active;
}

function stampToLrc(lines: TimedLine[]): string {
  return lines
    .map(({ time, text }) => {
      const seconds = Math.max(0, time / 1000);
      const minutes = Math.floor(seconds / 60);
      const remainder = (seconds % 60).toFixed(2).padStart(5, "0");
      return `[${String(minutes).padStart(2, "0")}:${remainder}]${text}`;
    })
    .join("\n");
}

export function parseLyricsText(value: string, source: string): LyricsData {
  const lines = parseLrc(value);
  return lines.length ? { source, lines } : { source, text: value };
}

export async function lookupLyrics(track: TrackRecord, signal: AbortSignal): Promise<LyricsData> {
  if (track.customLyrics?.trim()) return parseLyricsText(track.customLyrics, "custom");

  const leadArtist = track.artist.split(/[,;/]|\b(?:feat(?:uring)?|ft\.?|with)\b/i)[0]?.trim();
  const title = cleanTitle(track.title);
  if (!title || !leadArtist || /^unknown artist$/i.test(leadArtist)) return { source: "none" };

  let embedded: LyricsData | null = null;
  try {
    embedded = await readEmbeddedLyrics(track.id, signal);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
  }
  if (embedded) return embedded;

  const query = new URLSearchParams({
    track_name: title,
    artist_name: leadArtist,
    ...(track.album && !/^unknown album$/i.test(track.album) ? { album_name: track.album } : {}),
    ...(track.duration > 0 ? { duration: String(Math.round(track.duration)) } : {}),
  });
  const response = await fetch(`https://lrclib.net/api/get?${query}`, { cache: "no-store", signal });
  const titleKey = normalized(title);
  const artistKey = normalized(leadArtist);
  const durationTolerance = Math.min(15, Math.max(5, track.duration * 0.06));
  const matchesTrack = (entry: Record<string, unknown>) =>
    normalized(cleanTitle(String(entry.trackName ?? ""))) === titleKey &&
    normalized(String(entry.artistName ?? "").split(/[,;/]|\b(?:feat(?:uring)?|ft\.?|with)\b/i)[0]?.trim() ?? "") === artistKey &&
    (!track.duration ||
      (typeof entry.duration === "number" &&
        entry.duration > 0 &&
        Math.abs(entry.duration - track.duration) <= durationTolerance));
  let candidate: Record<string, unknown> | null = response.ok
    ? (await response.json()) as Record<string, unknown>
    : null;
  if (candidate && !matchesTrack(candidate)) candidate = null;

  if (!candidate) {
    const searches = [
      new URLSearchParams({ track_name: title, artist_name: leadArtist }),
      new URLSearchParams({ q: `${leadArtist} ${title}` }),
    ];
    for (const search of searches) {
      const searchResponse = await fetch(`https://lrclib.net/api/search?${search}`, {
        cache: "no-store",
        signal,
      });
      if (!searchResponse.ok) continue;
      const results: unknown = await searchResponse.json();
      if (!Array.isArray(results)) continue;
      candidate = (results as Record<string, unknown>[])
        .filter(matchesTrack)
        .sort((left, right) => {
          const durationDelta = track.duration
            ? Math.abs(Number(left.duration) - track.duration) -
              Math.abs(Number(right.duration) - track.duration)
            : 0;
          if (durationDelta !== 0) return durationDelta;
          return Number(Boolean(right.syncedLyrics)) - Number(Boolean(left.syncedLyrics));
        })[0] ?? null;
      if (candidate) break;
    }
  }

  if (!candidate || candidate.instrumental === true) return { source: "none" };
  const synced = typeof candidate.syncedLyrics === "string" ? candidate.syncedLyrics.trim() : "";
  const plain = typeof candidate.plainLyrics === "string" ? candidate.plainLyrics.trim() : "";
  if (synced && parseLrc(synced).length) return parseLyricsText(synced, "online-synced");
  return plain ? { source: "online-plain", text: plain } : { source: "none" };
}

function formatTime(value: number): string {
  const seconds = Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0;
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function PlayerIcon({ name }: { name: "previous" | "next" | "play" | "pause" | "shuffle" | "repeat" }) {
  const paths = {
    previous: <><path d="M6 5v14M18 6 8 12l10 6V6Z" /></>,
    next: <><path d="M18 5v14M6 6l10 6-10 6V6Z" /></>,
    play: <path d="m8 5 11 7-11 7V5Z" />,
    pause: <><path d="M8 5v14M16 5v14" /></>,
    shuffle: <><path d="M3 6h3.2l7.2 11H21M17.5 4.5 21 6.5l-3.5 2M3 17.5h3.2l3.2-4.9M17.5 19.5 21 17.5l-3.5-2" /></>,
    repeat: <><path d="m17 3.5 3.5 3.5-3.5 3.5M4 11.5V9.2a3.7 3.7 0 0 1 3.7-3.7h12.8M7 20.5 3.5 17 7 13.5M20 12.5v2.3a3.7 3.7 0 0 1-3.7 3.7H3.5" /></>,
  };
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

export default function LyricsOverlay({
  track,
  currentTime,
  onClose,
  onOpenArtist,
  onToast,
  onPrevious,
  onNext,
  onTogglePlayback,
  onToggleShuffle,
  onToggleRepeat,
  shuffle,
  repeat,
}: {
  track: TrackRecord;
  currentTime: number;
  onClose: () => void;
  onOpenArtist: (name: string) => void;
  onToast: (message: string) => void;
  onPrevious: () => void;
  onNext: () => void;
  onTogglePlayback: () => void;
  onToggleShuffle: () => void;
  onToggleRepeat: () => void;
  shuffle: boolean;
  repeat: RepeatMode;
}) {
  const setTrackLyrics = usePlayerStore((state) => state.setTrackLyrics);
  const setCachedLyrics = usePlayerStore((state) => state.setCachedLyrics);
  const isPlaying = usePlayerStore((state) => state.isPlaying);
  const audioElement = usePlayerStore((state) => state.audioElement);
  const [lyrics, setLyrics] = useState<LyricsData | null>(() =>
    track.customLyrics
      ? parseLyricsText(track.customLyrics, "custom")
      : usePlayerStore.getState().lyricsByTrack[track.id] ?? null,
  );
  const [loading, setLoading] = useState<boolean>(
    () => !track.customLyrics && !usePlayerStore.getState().lyricsByTrack[track.id],
  );
  const [editorOpen, setEditorOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [savePending, setSavePending] = useState(false);
  const [syncLines, setSyncLines] = useState<TimedLine[] | null>(null);
  const [syncText, setSyncText] = useState<string[]>([]);
  const lyricsViewportRef = useRef<HTMLDivElement>(null);
  const lyricsTrackRef = useRef<HTMLDivElement>(null);
  const smoothTimeRef = useRef(currentTime);
  const [smoothCurrentTime, setSmoothCurrentTime] = useState(currentTime);
  const activeTrack = track;

  // `timeupdate` fires only a few times per second. While this view is open,
  // sample the audio clock on animation frames so timed lyrics switch right on
  // their cue, including after a seek.
  useEffect(() => {
    if (!audioElement || !isPlaying) return;
    let frame = 0;
    const update = () => {
      const nextTime = audioElement.currentTime;
      if (Number.isFinite(nextTime) && Math.abs(nextTime - smoothTimeRef.current) >= 0.005) {
        smoothTimeRef.current = nextTime;
        setSmoothCurrentTime(nextTime);
      }
      frame = requestAnimationFrame(update);
    };
    frame = requestAnimationFrame(update);
    return () => cancelAnimationFrame(frame);
  }, [audioElement, isPlaying]);

  const lyricCurrentTime = audioElement && isPlaying ? smoothCurrentTime : currentTime;

  useEffect(() => {
    const currentTrack = track;
    if (currentTrack.customLyrics || usePlayerStore.getState().lyricsByTrack[currentTrack.id]) return;

    let cancelled = false;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);
    const storeLyrics = (value: LyricsData) => {
      if (cancelled) return;
      setCachedLyrics(currentTrack.id, value);
      setLyrics(value);
    };
    async function lookup() {
      setLoading(true);
      try {
        storeLyrics(await lookupLyrics(currentTrack, controller.signal));
      } catch (error) {
        if (!cancelled && !(error instanceof DOMException && error.name === "AbortError")) {
          setLyrics({ source: "none" });
        }
      } finally {
        clearTimeout(timeout);
        if (!cancelled) setLoading(false);
      }
    }
    void lookup();
    return () => {
      cancelled = true;
      controller.abort();
      clearTimeout(timeout);
    };
  }, [track, setCachedLyrics]);

  const lineIndex = useMemo(
    () => (lyrics?.lines ? activeLine(lyrics.lines, lyricCurrentTime * 1000) : -1),
    [lyrics, lyricCurrentTime],
  );
  useEffect(() => {
    const viewport = lyricsViewportRef.current;
    const lyricTrack = lyricsTrackRef.current;
    if (!viewport || !lyricTrack) return;
    const line = lyricTrack.children[Math.max(0, lineIndex)];
    if (!(line instanceof HTMLElement)) return;
    const offset = viewport.clientHeight / 2 - line.offsetTop - line.offsetHeight / 2;
    lyricTrack.style.transform = `translate3d(0, ${offset}px, 0)`;
  }, [lineIndex, lyrics]);
  const duration = audioElement && Number.isFinite(audioElement.duration)
    ? audioElement.duration
    : 0;
  const progress = duration > 0
    ? Math.max(0, Math.min(100, (lyricCurrentTime / duration) * 100))
    : 0;

  function seekTo(event: MouseEvent<HTMLDivElement>) {
    const audio = usePlayerStore.getState().audioElement;
    if (!audio || !duration) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    audio.currentTime = ratio * duration;
  }

  function seekByKeyboard(event: ReactKeyboardEvent<HTMLDivElement>) {
    const audio = usePlayerStore.getState().audioElement;
    if (!audio || !duration) return;
    const offsets: Record<string, number> = {
      ArrowLeft: -5,
      ArrowRight: 5,
      Home: -duration,
      End: duration,
    };
    const offset = offsets[event.key];
    if (offset === undefined) return;
    event.preventDefault();
    audio.currentTime = Math.max(0, Math.min(duration, audio.currentTime + offset));
  }

  async function saveLyrics(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = draft.trim();
    if (!value) {
      onToast("Paste some lyrics first.");
      return;
    }
    setSavePending(true);
    try {
      const savedResponse = await apiFetch(
        `/api/tracks/${encodeURIComponent(activeTrack.id)}/lyrics`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lyrics: value }),
        },
        { csrf: true, retryCsrfOnForbidden: true },
      );
      await expectOk(savedResponse);
      const result = (await savedResponse.json()) as { custom_lyrics: string };
      setTrackLyrics(activeTrack.id, result.custom_lyrics);
      setLyrics(parseLyricsText(result.custom_lyrics, "custom"));
      setDraft(result.custom_lyrics);
      setEditorOpen(false);
      setSyncLines(null);
      onToast("Lyrics saved.");
    } catch (error) {
      onToast(error instanceof Error ? error.message : "Could not save lyrics.");
    } finally {
      setSavePending(false);
    }
  }

  function beginSync() {
    const lines = lyrics?.lines?.length ? lyrics.lines : null;
    const text = lines
      ? lines.filter((line) => line.text.trim()).map((line) => line.text.trim())
      : (lyrics?.text ?? activeTrack.customLyrics ?? "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    if (!text.length) {
      onToast("Add lyrics before syncing them.");
      return;
    }
    setSyncText(text);
    setSyncLines(lines ? lines.filter((line) => line.text.trim()).map((line) => ({ ...line })) : text.map((line) => ({ time: -1, text: line })));
  }

  function stampLine(index: number) {
    const audio = usePlayerStore.getState().audioElement;
    if (!audio || !syncLines) return;
    const next = syncLines.map((line, lineIndex) =>
      lineIndex === index ? { ...line, time: Math.round(audio.currentTime * 1000) } : line,
    );
    setSyncLines(next);
  }

  async function saveSyncedLyrics() {
    if (!syncLines || syncLines.some((line) => line.time < 0)) return;
    if (syncLines.some((line, index) => index > 0 && line.time < syncLines[index - 1].time)) {
      onToast("Lyrics must be tapped in song order. Correct the out-of-order line.");
      return;
    }
    const value = stampToLrc(syncLines.map((line, index) => ({ ...line, text: syncText[index] })));
    setDraft(value);
    setSavePending(true);
    try {
      const response = await apiFetch(
        `/api/tracks/${encodeURIComponent(activeTrack.id)}/lyrics`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lyrics: value }),
        },
        { csrf: true, retryCsrfOnForbidden: true },
      );
      await expectOk(response);
      const result = (await response.json()) as { custom_lyrics: string };
      setTrackLyrics(activeTrack.id, result.custom_lyrics);
      setLyrics(parseLyricsText(result.custom_lyrics, "custom-synced"));
      setDraft(result.custom_lyrics);
      setSyncLines(null);
      onToast("Lyrics synced to the track.");
    } catch (error) {
      onToast(error instanceof Error ? error.message : "Could not save synced lyrics.");
    } finally {
      setSavePending(false);
    }
  }

  const sourceName: Record<string, string> = {
    sylt: "Synced lyrics",
    uslt: "Lyrics",
    custom: "Pasted lyrics",
    "custom-synced": "Synced · adjusted",
    "online-synced": "Synced · LRCLIB",
    "online-plain": "Lyrics · LRCLIB",
  };

  return (
    <div className="lyrics-overlay open" role="dialog" aria-modal="true" aria-label="Lyrics">
      <div className="lyrics-bg" style={{ backgroundImage: `url("${activeTrack.coverUrl}")` }} />
      <header className="lyrics-topbar">
        <button className="lyrics-close" type="button" aria-label="Close lyrics" onClick={onClose}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m6 9 6 6 6-6" /></svg>
        </button>
        <div className="lyrics-topbar-title"><span>NOW PLAYING</span><strong>{activeTrack.title}</strong></div>
        <button className="lyrics-edit-top" type="button" onClick={() => { setDraft(activeTrack.customLyrics ?? lyrics?.text ?? ""); setEditorOpen(true); }}>Edit lyrics</button>
      </header>
      <div className="lyrics-stage">
        <div className="lyrics-side">
          <div className="lyrics-art"><img src={activeTrack.coverUrl} alt="" /></div>
          <div className="lyrics-meta">
            <div className="t">{activeTrack.title}</div>
            <div className="a">
              {artistNames(activeTrack).map((name, index) => (
                <Fragment key={name}>
                  {index > 0 ? <span className="artist-sep">, </span> : null}
                  <button className="artist-link" type="button" onClick={() => onOpenArtist(name)}>
                    {name}
                  </button>
                </Fragment>
              ))}
            </div>
            <div className="lyrics-album">{activeTrack.album}</div>
          </div>
          {lyrics && sourceName[lyrics.source] ? <div className="lyrics-source">{sourceName[lyrics.source]}</div> : null}
        </div>

        <div
          className={`lyrics-viewport${!syncLines && !editorOpen && (!lyrics || (!lyrics.lines?.length && !lyrics.text)) ? " lyrics-viewport-empty" : ""}`}
          ref={lyricsViewportRef}
        >
          {syncLines ? (
            <div className="lyrics-sync-editor">
              <div className="lyrics-editor-heading"><h3>Sync lyrics to audio</h3><p>Start playback, then tap each line when it is sung.</p></div>
              <div className="lyrics-sync-clock">Playback: <strong>{formatTime(lyricCurrentTime)}</strong></div>
              <div className="lyrics-sync-lines">
                {syncLines.map((line, index) => <button type="button" className={`lyrics-sync-line${line.time >= 0 ? " stamped" : ""}`} key={`${index}-${line.text}`} onClick={() => stampLine(index)}><span className="lyrics-sync-line-time">{line.time < 0 ? "Tap at this line" : formatTime(line.time / 1000)}</span><span>{syncText[index]}</span></button>)}
              </div>
              <div className="lyrics-editor-actions"><button className="btn" type="button" onClick={() => setSyncLines(null)}>Back</button><button className="btn" type="button" onClick={() => {
                const audio = usePlayerStore.getState().audioElement;
                if (audio) {
                  audio.currentTime = 0;
                  void audio.play();
                }
              }}>Play from start</button><button className="btn btn-primary" type="button" disabled={savePending || syncLines.some((line) => line.time < 0)} onClick={() => void saveSyncedLyrics()}>Save synced lyrics</button></div>
            </div>
          ) : editorOpen ? (
            <form className="lyrics-editor" onSubmit={saveLyrics}>
              <div className="lyrics-editor-heading"><h3>Add lyrics</h3><p>{activeTrack.title} · {activeTrack.artist}</p></div>
              <textarea className="lyrics-input" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Paste plain lyrics or timestamped LRC lyrics here…" />
              <div className="lyrics-editor-actions"><button className="btn" type="button" onClick={() => setEditorOpen(false)}>Cancel</button><button className="btn btn-primary" type="submit" disabled={savePending}>{savePending ? "Saving…" : "Save lyrics"}</button></div>
            </form>
          ) : loading ? (
            <div className="lyrics-empty"><div className="empty-orb lyrics-loading-orb" /><h3>Searching for lyrics…</h3><p>Checking LRCLIB for a match.</p></div>
          ) : lyrics?.lines?.length ? (
            <div className="lyrics-track" ref={lyricsTrackRef}>
              {lyrics.lines.map((line, index) => <button className={`lyrics-line${index === lineIndex ? " active" : ""}${index < lineIndex ? " past" : ""}`} type="button" key={`${line.time}-${index}`} onClick={() => {
                const audio = usePlayerStore.getState().audioElement;
                if (audio) audio.currentTime = line.time / 1000;
              }}>{line.text || "\u00a0"}</button>)}
            </div>
          ) : lyrics?.text ? (
            <div className="lyrics-plain"><p>{lyrics.text}</p><button className="btn btn-primary lyrics-sync-btn" type="button" onClick={beginSync}>Sync to audio</button><button className="btn lyrics-sync-btn" type="button" onClick={() => setEditorOpen(true)}>Edit lyrics</button></div>
          ) : (
            <div className="lyrics-empty"><div className="empty-orb" /><h3>No lyrics available</h3><p>Vervfy could not find lyrics for this track. Add your own below.</p><button className="btn btn-primary lyrics-paste-btn" type="button" onClick={() => { setDraft(activeTrack.customLyrics ?? ""); setEditorOpen(true); }}>Paste lyrics</button></div>
          )}
        </div>
      </div>
      <div className="lyrics-player">
        <div className="lyrics-player-track">
          <img src={activeTrack.coverUrl} alt="" />
          <span><strong>{activeTrack.title}</strong><small>{activeTrack.artist}</small></span>
        </div>
        <div className="lyrics-player-seek">
          <span className="lyrics-player-time">{formatTime(lyricCurrentTime)}</span>
          <div
            className="seek"
            role="slider"
            tabIndex={duration ? 0 : -1}
            aria-label="Track progress"
            aria-valuemin={0}
            aria-valuemax={duration}
            aria-valuenow={lyricCurrentTime}
            aria-valuetext={`${formatTime(lyricCurrentTime)} of ${formatTime(duration)}`}
            onClick={seekTo}
            onKeyDown={seekByKeyboard}
          >
            <div className="seek-track"><div className="seek-fill" style={{ width: `${progress}%` }} /></div>
            <div className="seek-thumb" style={{ left: `${progress}%` }} />
          </div>
          <span className="lyrics-player-time right">{formatTime(duration)}</span>
        </div>
        <div className="lyrics-player-controls">
          <button className={`tbtn lyrics-mode-button${shuffle ? " on" : ""}`} type="button" aria-label="Shuffle" aria-pressed={shuffle} onClick={onToggleShuffle}><PlayerIcon name="shuffle" /></button>
          <button className="tbtn" type="button" aria-label="Previous track" onClick={onPrevious}><PlayerIcon name="previous" /></button>
          <button className="tbtn tbtn-play" type="button" aria-label={isPlaying ? "Pause" : "Play"} onClick={onTogglePlayback}><PlayerIcon name={isPlaying ? "pause" : "play"} /></button>
          <button className="tbtn" type="button" aria-label="Next track" onClick={onNext}><PlayerIcon name="next" /></button>
          <button className={`tbtn lyrics-mode-button${repeat !== "off" ? " on" : ""}`} type="button" aria-label={`Repeat: ${repeat}`} aria-pressed={repeat !== "off"} onClick={onToggleRepeat}><PlayerIcon name="repeat" />{repeat === "one" ? <small>1</small> : null}</button>
        </div>
        <button className="lyrics-edit-control" type="button" onClick={() => { setDraft(activeTrack.customLyrics ?? lyrics?.text ?? ""); setEditorOpen(true); }}>Edit lyrics</button>
      </div>
    </div>
  );
}
