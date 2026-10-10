"use client";

import { Fragment, memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  FormEvent,
  KeyboardEvent as ReactKeyboardEvent,
  MouseEvent as ReactMouseEvent,
  PointerEvent as ReactPointerEvent,
  ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { apiFetch, expectOk, fetchWithRetry, uploadWithRetry } from "@/lib/api/client";
import type { Account, LibraryState } from "@/lib/api/types";
import LogoutButton from "@/components/auth/logout-button";
import AccountSettings from "@/components/account-settings";
import ArtistExplorer, { artistNames } from "@/components/artist-explorer";
import LyricsOverlay, { lookupLyrics, parseLyricsText } from "@/components/lyrics-overlay";
import VisualizerOverlay from "@/components/visualizer-overlay";
import {
  usePlayerStore,
  type CachedLyrics,
  type LibraryView,
  type PlaylistRecord,
  type TrackRecord,
} from "@/store/player-store";

interface ServerTrack {
  id: string;
  title: string;
  artist: string;
  album: string;
  duration: number;
  has_cover: boolean;
  cover_url: string;
  stream_url: string;
  artist_image_url?: string | null;
  custom_lyrics?: string | null;
}

interface LibraryMeta {
  favorites: string[];
  playlists: PlaylistRecord[];
}

interface OfflineTrackRecord {
  id: string;
  accountId: string;
  trackId: string;
  title: string;
  artist: string;
  album: string;
  duration: number;
  customLyrics: string | null;
  audio: Blob;
  cover?: Blob | null;
  dateAdded: number;
}

const OFFLINE_DATABASE = "auralis-db";
const OFFLINE_DATABASE_VERSION = 2;
const OFFLINE_STORE = "offlineTracks";

const FALLBACK_ART = "/gemini-svg.svg";
const AURA_PALETTE = [
  ["#8b7fff", "#54e8d4"],
  ["#ff8fb1", "#8b7fff"],
  ["#54e8d4", "#3aa0ff"],
  ["#ffb86b", "#ff6b9d"],
  ["#6bd6ff", "#8b7fff"],
  ["#c084fc", "#54e8d4"],
];

interface PlaybackAttempt {
  src: string;
  retryCount: number;
  retryTimer: number | null;
  requestId: number;
  loading: boolean;
  failed: boolean;
}

function logAudioFailure(context: string, audio: HTMLAudioElement, error: unknown): void {
  const errorName =
    error instanceof Error
      ? error.name
      : error && typeof error === "object" && "name" in error && typeof error.name === "string"
        ? error.name
        : "UnknownError";
  const errorMessage =
    error instanceof Error
      ? error.message
      : error && typeof error === "object" && "message" in error && typeof error.message === "string"
        ? error.message
        : String(error);
  console.warn(`[audio] ${context}`, {
    name: errorName,
    message: errorMessage,
    code: audio.error?.code ?? null,
    networkState: audio.networkState,
    readyState: audio.readyState,
  });
}

function generateAura(seed: string): string {
  let hash = 0;
  for (let index = 0; index < seed.length; index += 1) {
    hash = (Math.imul(31, hash) + seed.charCodeAt(index)) | 0;
  }
  hash = Math.abs(hash);
  const [first, second] = AURA_PALETTE[hash % AURA_PALETTE.length];
  const angle = (hash % 360) * (Math.PI / 180);
  const x = Math.round(50 + Math.cos(angle) * 15);
  const y = Math.round(50 + Math.sin(angle) * 15);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300"><defs><radialGradient id="a" cx="${x}%" cy="${y}%" r="75%"><stop stop-color="${first}"/><stop offset=".5" stop-color="${second}" stop-opacity=".34"/><stop offset="1" stop-color="#0c0e14" stop-opacity="0"/></radialGradient><radialGradient id="b" cx="${100 - x}%" cy="${100 - y}%" r="60%"><stop stop-color="${second}"/><stop offset="1" stop-color="#0c0e14" stop-opacity="0"/></radialGradient></defs><rect width="300" height="300" fill="#12151e"/><rect width="300" height="300" fill="url(#a)" opacity=".9"/><rect width="300" height="300" fill="url(#b)" opacity=".55"/></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

function normalizeMeta(value: LibraryState): LibraryMeta {
  return {
    favorites: [...new Set(value.favorites.filter((id) => typeof id === "string"))].sort(),
    playlists: value.playlists.map((playlist) => ({
      id: playlist.id,
      name: playlist.name,
      trackIds: [...new Set(playlist.trackIds)],
    })),
  };
}

function activePreviewLine(lines: NonNullable<CachedLyrics["lines"]>, timeMs: number): number {
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

const TrackImage = memo(function TrackImage({
  track,
  className = "",
}: {
  track: TrackRecord;
  className?: string;
}) {
  return (
    <img
      className={className}
      src={track.coverUrl || FALLBACK_ART}
      alt=""
      loading="lazy"
      onError={(event) => {
        if (event.currentTarget.src !== new URL(FALLBACK_ART, window.location.href).href) {
          event.currentTarget.src = FALLBACK_ART;
        }
      }}
    />
  );
});

function PlaybackSeek({
  audioElement,
  duration,
  onSeek,
  onResume,
  className = "",
  variant,
}: {
  audioElement: HTMLAudioElement | null;
  duration: number;
  onSeek: (time: number) => void;
  onResume: () => void;
  className?: string;
  variant: "mobile" | "player";
}) {
  const [currentTime, setCurrentTime] = useState(0);
  const [scrubbingTime, setScrubbingTime] = useState<number | null>(null);
  const dragRef = useRef<{ pointerId: number; wasPlaying: boolean } | null>(null);

  useEffect(() => {
    if (!audioElement) return;
    const update = () => setCurrentTime(audioElement.currentTime || 0);
    audioElement.addEventListener("timeupdate", update);
    audioElement.addEventListener("loadedmetadata", update);
    audioElement.addEventListener("durationchange", update);
    audioElement.addEventListener("seeked", update);
    update();
    return () => {
      audioElement.removeEventListener("timeupdate", update);
      audioElement.removeEventListener("loadedmetadata", update);
      audioElement.removeEventListener("durationchange", update);
      audioElement.removeEventListener("seeked", update);
    };
  }, [audioElement]);

  const displayedTime = scrubbingTime ?? currentTime;
  const progress = duration ? Math.min(100, (displayedTime / duration) * 100) : 0;
  function timeAtPosition(clientX: number, element: HTMLDivElement): number {
    const bounds = element.getBoundingClientRect();
    const ratio = bounds.width
      ? Math.max(0, Math.min(1, (clientX - bounds.left) / bounds.width))
      : 0;
    return ratio * duration;
  }
  function beginSeek(event: ReactPointerEvent<HTMLDivElement>) {
    if (!audioElement || !duration || !event.isPrimary || event.button !== 0) return;
    event.preventDefault();
    dragRef.current = { pointerId: event.pointerId, wasPlaying: !audioElement.paused };
    event.currentTarget.setPointerCapture(event.pointerId);
    setScrubbingTime(timeAtPosition(event.clientX, event.currentTarget));
    if (!audioElement.paused) audioElement.pause();
  }
  function continueSeek(event: ReactPointerEvent<HTMLDivElement>) {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    setScrubbingTime(timeAtPosition(event.clientX, event.currentTarget));
  }
  function finishSeek(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!audioElement || !drag || drag.pointerId !== event.pointerId) return;
    onSeek(timeAtPosition(event.clientX, event.currentTarget));
    dragRef.current = null;
    setScrubbingTime(null);
    if (drag.wasPlaying) onResume();
  }
  const seekBar = (
    <div
      className={`seek${variant === "mobile" ? " mobile-seek" : ""}`}
      role="slider"
      tabIndex={duration ? 0 : -1}
      aria-label="Track progress"
      aria-valuemin={0}
      aria-valuemax={duration}
      aria-valuenow={displayedTime}
      aria-valuetext={`${formatTime(displayedTime)} of ${formatTime(duration)}`}
      onPointerDown={beginSeek}
      onPointerMove={continueSeek}
      onPointerUp={finishSeek}
      onPointerCancel={finishSeek}
      onKeyDown={(event: ReactKeyboardEvent<HTMLDivElement>) => {
        if (!audioElement || !duration) return;
        const offsets: Record<string, number> = {
          ArrowRight: 5,
          ArrowLeft: -5,
          Home: -duration,
          End: duration,
        };
        const offset = offsets[event.key];
        if (offset === undefined) return;
        event.preventDefault();
        seekAudio(audioElement, offset);
      }}
    >
      <div className="seek-track">
        <div className="seek-fill" style={{ width: `${progress}%` }} />
      </div>
      <div className="seek-thumb" style={{ left: `${progress}%` }} />
    </div>
  );

  if (variant === "mobile") {
    return (
      <div className="mobile-seek-row">
        {seekBar}
        <div className="mobile-times">
          <span>{formatTime(displayedTime)}</span>
          <span>{formatTime(duration)}</span>
        </div>
      </div>
    );
  }
  return (
    <div className={`seek-row${className ? ` ${className}` : ""}`}>
      <span className="time">{formatTime(displayedTime)}</span>
      {seekBar}
      <span className="time right">{formatTime(duration)}</span>
    </div>
  );
}

function parseLegacyMeta(value: unknown): LibraryMeta | null {
  let parsed = value;
  if (typeof parsed === "string") {
    try {
      parsed = JSON.parse(parsed) as unknown;
    } catch {
      return null;
    }
  }
  if (typeof parsed !== "object" || parsed === null) return null;
  const record = parsed as Record<string, unknown>;
  const favorites = Array.isArray(record.favorites)
    ? record.favorites.filter((id): id is string => typeof id === "string")
    : [];
  const playlists = Array.isArray(record.playlists)
    ? record.playlists.flatMap((value) => {
        if (typeof value !== "object" || value === null) return [];
        const playlist = value as Record<string, unknown>;
        if (typeof playlist.id !== "string" || typeof playlist.name !== "string") return [];
        const rawTrackIds = Array.isArray(playlist.trackIds)
          ? playlist.trackIds
          : Array.isArray(playlist.fingerprints)
            ? playlist.fingerprints
            : [];
        return [{
          id: playlist.id,
          name: playlist.name,
          trackIds: [...new Set(rawTrackIds.filter((id): id is string => typeof id === "string"))],
        }];
      })
    : [];
  return {
    favorites: [...new Set(favorites)].sort(),
    playlists,
  };
}

async function readLegacyMeta(): Promise<LibraryMeta | null> {
  if (typeof indexedDB === "undefined") return null;
  return new Promise((resolve) => {
    let settled = false;
    let database: IDBDatabase | null = null;
    const finish = (result: LibraryMeta | null) => {
      if (settled) return;
      settled = true;
      database?.close();
      resolve(result);
    };

    const request = indexedDB.open("auralis-db", 2);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("kv")) db.createObjectStore("kv");
      if (!db.objectStoreNames.contains("handles")) db.createObjectStore("handles");
      if (!db.objectStoreNames.contains("offlineTracks")) {
        db.createObjectStore("offlineTracks", { keyPath: "id" });
      }
    };
    request.onerror = () => finish(null);
    request.onblocked = () => finish(null);
    request.onsuccess = () => {
      database = request.result;
      if (!database.objectStoreNames.contains("kv")) {
        finish(null);
        return;
      }
      const transaction = database.transaction("kv", "readonly");
      const valueRequest = transaction.objectStore("kv").get("auralis:library");
      valueRequest.onsuccess = () => finish(parseLegacyMeta(valueRequest.result));
      valueRequest.onerror = () => finish(null);
      transaction.onerror = () => finish(null);
    };
  });
}

function openOfflineDatabase(): Promise<IDBDatabase> {
  if (typeof indexedDB === "undefined") {
    return Promise.reject(new Error("Offline storage is not available in this browser."));
  }
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(OFFLINE_DATABASE, OFFLINE_DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains("kv")) database.createObjectStore("kv");
      if (!database.objectStoreNames.contains("handles")) database.createObjectStore("handles");
      if (!database.objectStoreNames.contains(OFFLINE_STORE)) {
        database.createObjectStore(OFFLINE_STORE, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("Could not open offline storage."));
    request.onblocked = () => reject(new Error("Offline storage is busy in another browser tab."));
  });
}

async function readOfflineTracks(accountId: string): Promise<OfflineTrackRecord[]> {
  const database = await openOfflineDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(OFFLINE_STORE, "readonly");
    const request = transaction.objectStore(OFFLINE_STORE).getAll();
    request.onsuccess = () => {
      resolve(
        (request.result as OfflineTrackRecord[]).filter(
          (record) =>
            record.accountId === accountId &&
            typeof record.trackId === "string" &&
            record.audio instanceof Blob,
        ),
      );
    };
    request.onerror = () => reject(request.error ?? new Error("Could not read offline tracks."));
    transaction.oncomplete = () => database.close();
    transaction.onabort = () => {
      database.close();
      reject(transaction.error ?? new Error("Could not read offline tracks."));
    };
  });
}

async function writeOfflineTrack(record: OfflineTrackRecord): Promise<void> {
  const database = await openOfflineDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(OFFLINE_STORE, "readwrite");
    transaction.objectStore(OFFLINE_STORE).put(record);
    transaction.oncomplete = () => {
      database.close();
      resolve();
    };
    transaction.onerror = () => reject(transaction.error ?? new Error("Could not save the offline track."));
    transaction.onabort = () => {
      database.close();
      reject(transaction.error ?? new Error("Could not save the offline track."));
    };
  });
}

async function deleteOfflineTrack(accountId: string, trackId: string): Promise<void> {
  const database = await openOfflineDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(OFFLINE_STORE, "readwrite");
    transaction.objectStore(OFFLINE_STORE).delete(`${accountId}:${trackId}`);
    transaction.oncomplete = () => {
      database.close();
      resolve();
    };
    transaction.onerror = () => reject(transaction.error ?? new Error("Could not remove the offline track."));
    transaction.onabort = () => {
      database.close();
      reject(transaction.error ?? new Error("Could not remove the offline track."));
    };
  });
}

function sameMeta(left: LibraryMeta, right: LibraryMeta): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function mergeUnsavedMeta(
  remote: LibraryMeta,
  baseline: LibraryMeta,
  local: LibraryMeta,
): LibraryMeta {
  const mergedFavorites = new Set(remote.favorites);
  const baselineFavorites = new Set(baseline.favorites);
  const localFavorites = new Set(local.favorites);
  for (const id of new Set([...baselineFavorites, ...localFavorites])) {
    if (baselineFavorites.has(id) === localFavorites.has(id)) continue;
    if (localFavorites.has(id)) mergedFavorites.add(id);
    else mergedFavorites.delete(id);
  }

  const baselinePlaylists = new Map(baseline.playlists.map((item) => [item.id, item]));
  const localPlaylists = new Map(local.playlists.map((item) => [item.id, item]));
  const mergedPlaylists = new Map(remote.playlists.map((item) => [item.id, item]));
  for (const id of new Set([...baselinePlaylists.keys(), ...localPlaylists.keys()])) {
    if (
      JSON.stringify(baselinePlaylists.get(id)) ===
      JSON.stringify(localPlaylists.get(id))
    ) {
      continue;
    }
    const localPlaylist = localPlaylists.get(id);
    if (localPlaylist) mergedPlaylists.set(id, localPlaylist);
    else mergedPlaylists.delete(id);
  }

  return {
    favorites: [...mergedFavorites].sort(),
    playlists: [...mergedPlaylists.values()],
  };
}

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) seconds = 0;
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}

function seekAudio(audio: HTMLAudioElement | null, offset: number): void {
  if (!audio) return;
  const duration = Number.isFinite(audio.duration) ? audio.duration : Infinity;
  audio.currentTime = Math.max(0, Math.min(duration, audio.currentTime + offset));
}

function viewName(view: LibraryView, playlists: PlaylistRecord[]): string {
  if (view === "library") return "Library";
  if (view === "offline") return "Offline";
  if (view === "favorites") return "Favorites";
  if (view === "playlists") return "Playlists";
  if (view === "artists") return "Artists";
  if (view === "account") return "Account";
  if (view.startsWith("artist:")) return decodeURIComponent(view.slice("artist:".length));
  return playlists.find((playlist) => `playlist:${playlist.id}` === view)?.name ?? "Playlist";
}

function getMetaFromStore(): LibraryMeta {
  const state = usePlayerStore.getState();
  return {
    favorites: state.tracks.filter((track) => track.favorite).map((track) => track.id).sort(),
    playlists: state.playlists.map((playlist) => ({
      ...playlist,
      trackIds: [...playlist.trackIds],
    })),
  };
}

type IconName = "library" | "playlists" | "heart" | "logout" | "search" | "play" | "pause" | "prev" | "next" | "shuffle" | "repeat" | "queue" | "mini" | "plus" | "close" | "list" | "grid" | "more" | "artist" | "offline" | "account" | "help" | "import" | "volume" | "volume-muted" | "lyrics" | "visualizer" | "drag";

function Icon({ name }: { name: IconName }) {
  const paths: Record<IconName, ReactNode> = {
    library: <><rect x="3.5" y="3.5" width="7" height="7" rx="2"/><rect x="13.5" y="3.5" width="7" height="7" rx="2"/><rect x="3.5" y="13.5" width="7" height="7" rx="2"/><rect x="13.5" y="13.5" width="7" height="7" rx="2"/></>,
    playlists: <><path d="M4 7h12M4 12h12M4 17h8"/><path d="M18 8v8.2"/><circle cx="18" cy="17.5" r="1.8"/></>,
    heart: <path d="M12 20s-7-4.35-9.4-8.9C.8 7.5 3.1 4.2 6.6 4.2c1.9 0 3.3 1.05 4.4 2.55 1.1-1.5 2.5-2.55 4.4-2.55 3.5 0 5.8 3.3 4 6.9C17 15.65 12 20 12 20Z"/>,
    logout: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/></>,
    search: <><circle cx="11" cy="11" r="6.5"/><path d="m20 20-3.8-3.8"/></>,
    play: <path d="M8 5v14l11-7z" fill="currentColor" stroke="none"/>,
    pause: <><path d="M8 6h3v12H8zM15 6h3v12h-3z" fill="currentColor" stroke="none"/></>,
    prev: <path d="M6.5 6.5h2.2v11H6.5zM19.5 6.8 9.8 12l9.7 5.2z" fill="currentColor" stroke="none"/>,
    next: <path d="M15.3 6.5h2.2v11h-2.2zM4.5 6.8 14.2 12l-9.7 5.2z" fill="currentColor" stroke="none"/>,
    shuffle: <><path d="M3 6.5h3.2l7.2 11H21M17.5 4.5 21 6.5l-3.5 2M3 17.5h3.2l3.2-4.9M17.5 19.5 21 17.5l-3.5-2"/></>,
    repeat: <><path d="m17 3.5 3.5 3.5-3.5 3.5M4 11.5V9.2a3.7 3.7 0 0 1 3.7-3.7h12.8M7 20.5 3.5 17 7 13.5M20 12.5v2.3a3.7 3.7 0 0 1-3.7 3.7H3.5"/></>,
    queue: <><path d="M4.5 7h15M4.5 12h9.5M4.5 17h9.5"/></>,
    mini: <><rect x="3.5" y="3.5" width="17" height="17" rx="4"/><rect x="12" y="12" width="7" height="6.5" rx="2" fill="currentColor" stroke="none"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    close: <><path d="m7 7 10 10M17 7 7 17"/></>,
    list: <><path d="M4.5 7h15M4.5 12h15M4.5 17h15"/></>,
    grid: <><rect x="3.5" y="3.5" width="7" height="7" rx="1.8"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.8"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.8"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.8"/></>,
    more: <><circle cx="5" cy="12" r="1.4" fill="currentColor"/><circle cx="12" cy="12" r="1.4" fill="currentColor"/><circle cx="19" cy="12" r="1.4" fill="currentColor"/></>,
    artist: <><circle cx="12" cy="8" r="3.2"/><path d="M5.5 19.2c0-3.2 2.9-5.5 6.5-5.5s6.5 2.3 6.5 5.5"/><circle cx="18.2" cy="9.2" r="2.1"/><path d="M19.5 19.2c0-2.1-1.3-3.8-3.2-4.6"/></>,
    offline: <><path d="M12 4v11"/><path d="m8 11 4 4 4-4M5 20h14"/></>,
    account: <><circle cx="12" cy="8" r="3.4"/><path d="M5 20c0-3.6 3.1-6.2 7-6.2s7 2.6 7 6.2"/></>,
    help: <><circle cx="12" cy="12" r="8.25"/><path d="M9.6 9.4a2.4 2.4 0 1 1 3.1 2.25c-.85.35-1.2.8-1.2 1.7"/><circle cx="12" cy="16.6" r=".7" fill="currentColor" stroke="none"/></>,
    import: <><path d="M12 4v11"/><path d="m8.5 11.5 3.5 3.5 3.5-3.5M5 18.5h14"/></>,
    volume: <><path d="M4 10v4h3l4 3V7l-4 3H4Z"/><path d="M15 9a5 5 0 0 1 0 6M17.5 6.5a8.5 8.5 0 0 1 0 11"/></>,
    "volume-muted": <><path d="M4 10v4h3l4 3V7l-4 3H4Z"/><path d="m16 9 5 6m0-6-5 6"/></>,
    lyrics: <><path d="M6 3.75h8l4 4V20.25H6z"/><path d="M14 3.75v4h4M9 12h6M9 15.5h6"/></>,
    visualizer: <><path d="M5 14v5M5 5v5M12 10v9M12 5v2M19 15v4M19 5v7"/><path d="M3 10h4M10 7h4M17 12h4"/></>,
    drag: <><circle cx="9" cy="5" r="1" fill="currentColor" stroke="none"/><circle cx="15" cy="5" r="1" fill="currentColor" stroke="none"/><circle cx="9" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="15" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="9" cy="19" r="1" fill="currentColor" stroke="none"/><circle cx="15" cy="19" r="1" fill="currentColor" stroke="none"/></>,
  };

  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

export default function LibraryApp() {
  const audioElement = usePlayerStore((state) => state.audioElement);
  const tracks = usePlayerStore((state) => state.tracks);
  const playlists = usePlayerStore((state) => state.playlists);
  const queue = usePlayerStore((state) => state.queue);
  const queueIndex = usePlayerStore((state) => state.queueIndex);
  const view = usePlayerStore((state) => state.view);
  const listMode = usePlayerStore((state) => state.listMode);
  const repeat = usePlayerStore((state) => state.repeat);
  const shuffle = usePlayerStore((state) => state.shuffle);
  const isPlaying = usePlayerStore((state) => state.isPlaying);
  const setTracks = usePlayerStore((state) => state.setTracks);
  const setLibraryMeta = usePlayerStore((state) => state.setLibraryMeta);
  const setQueue = usePlayerStore((state) => state.setQueue);
  const setQueueIndex = usePlayerStore((state) => state.setQueueIndex);
  const setView = usePlayerStore((state) => state.setView);
  const setListMode = usePlayerStore((state) => state.setListMode);
  const setRepeat = usePlayerStore((state) => state.setRepeat);
  const setShuffle = usePlayerStore((state) => state.setShuffle);
  const setPlaying = usePlayerStore((state) => state.setPlaying);
  const lyricsByTrack = usePlayerStore((state) => state.lyricsByTrack);
  const setCachedLyrics = usePlayerStore((state) => state.setCachedLyrics);
  const toggleFavorite = usePlayerStore((state) => state.toggleFavorite);
  const setPlaylists = usePlayerStore((state) => state.setPlaylists);
  const playbackAttemptRef = useRef<PlaybackAttempt | null>(null);
  const runPlaybackAttemptRef = useRef<(attempt: PlaybackAttempt) => void>(() => {});

  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [profile, setProfile] = useState<Account | null>(null);
  const [toast, setToast] = useState("");
  const [queueOpen, setQueueOpen] = useState(false);
  const [lyricsOpen, setLyricsOpen] = useState(false);
  const [visualizerOpen, setVisualizerOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [queuePickerOpen, setQueuePickerOpen] = useState(false);
  const [queueSearch, setQueueSearch] = useState("");
  const [playlistAddTarget, setPlaylistAddTarget] = useState<string | null>(null);
  const [trackMenu, setTrackMenu] = useState<{
    trackId: string;
    top: number;
    left: number;
  } | null>(null);
  const [offlinePendingId, setOfflinePendingId] = useState<string | null>(null);
  const [queueDragIndex, setQueueDragIndex] = useState<number | null>(null);
  const [queueDragOverIndex, setQueueDragOverIndex] = useState<number | null>(null);
  const queuePointerDragRef = useRef<{ pointerId: number; fromIndex: number } | null>(null);
  const previewLineRef = useRef<{ trackId: string; index: number } | null>(null);
  const [playlistModal, setPlaylistModal] = useState<{
    playlist?: PlaylistRecord;
    trackId?: string;
  } | null>(null);
  const [playlistName, setPlaylistName] = useState("");
  const [playlistPicker, setPlaylistPicker] = useState<string | null>(null);
  const [miniMode, setMiniMode] = useState(false);
  const [expandedPlayerOpen, setExpandedPlayerOpen] = useState(false);
  const [playingFromView, setPlayingFromView] = useState<LibraryView | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [lyricsLookupFailedTrackId, setLyricsLookupFailedTrackId] = useState<string | null>(null);
  const [previewLineState, setPreviewLineState] = useState<{ trackId: string; index: number } | null>(null);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.7);
  const [muted, setMuted] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const [isDraggingFiles, setIsDraggingFiles] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const playlistNameInputRef = useRef<HTMLInputElement>(null);
  const expandedPlayerCloseRef = useRef<HTMLButtonElement>(null);
  const expandedPlayerReturnFocusRef = useRef<HTMLElement | null>(null);
  const queuePanelRef = useRef<HTMLElement>(null);

  const baselineRef = useRef<LibraryMeta>({ favorites: [], playlists: [] });
  const etagRef = useRef<string | null>(null);
  const dirtyRef = useRef(false);
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());
  const shufflePlayedRef = useRef(new Set<number>());
  const nextRef = useRef<(automatic: boolean) => void>(() => undefined);
  const toastTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const offlineObjectUrlsRef = useRef(new Set<string>());

  const updateProfilePhoto = useCallback((photoUrl: string | null) => {
    setProfile((current) => current ? { ...current, photo_url: photoUrl } : current);
  }, []);

  useEffect(() => {
    const app = document.getElementById("app");
    if (!app) return;
    app.inert = expandedPlayerOpen;
    return () => {
      app.inert = false;
    };
  }, [expandedPlayerOpen]);

  useEffect(() => {
    const savedMode = window.localStorage.getItem("vervfy:list-mode");
    if (savedMode === "grid" || savedMode === "list") setListMode(savedMode);
  }, [setListMode]);

  useEffect(() => {
    if (expandedPlayerOpen) {
      expandedPlayerCloseRef.current?.focus();
    } else {
      expandedPlayerReturnFocusRef.current?.focus();
      expandedPlayerReturnFocusRef.current = null;
    }
  }, [expandedPlayerOpen]);

  useEffect(() => {
    if (!expandedPlayerOpen) return;
    document.body.classList.add("expanded-player-open");
    return () => document.body.classList.remove("expanded-player-open");
  }, [expandedPlayerOpen]);

  const activeTrackId = queueIndex >= 0 ? queue[queueIndex] ?? null : null;
  const currentTrack = tracks.find((track) => track.id === activeTrackId) ?? null;
  const cachedLyrics = currentTrack ? lyricsByTrack[currentTrack.id] : undefined;
  const previewLyrics = currentTrack?.customLyrics
    ? parseLyricsText(currentTrack.customLyrics, "custom")
    : cachedLyrics;
  const previewLines = previewLyrics?.lines;
  const previewLineIndex = currentTrack && previewLines
    ? previewLineState?.trackId === currentTrack.id
      ? previewLineState.index
      : activePreviewLine(previewLines, currentTime * 1000)
    : -1;
  const previewCurrentLineIndex = previewLines?.length
    ? Math.max(0, Math.min(previewLineIndex < 0 ? 0 : previewLineIndex, previewLines.length - 1))
    : -1;
  const previewNextLineIndex = previewLineIndex < 0 ? 1 : previewCurrentLineIndex + 1;

  useEffect(() => {
    if (!expandedPlayerOpen || !currentTrack || cachedLyrics || currentTrack.customLyrics) return;

    let cancelled = false;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);
    void lookupLyrics(currentTrack, controller.signal)
      .then((lyrics) => {
        if (!cancelled) setCachedLyrics(currentTrack.id, lyrics);
      })
      .catch(() => {
        if (!cancelled) setLyricsLookupFailedTrackId(currentTrack.id);
      })
      .finally(() => clearTimeout(timeout));

    return () => {
      cancelled = true;
      controller.abort();
      clearTimeout(timeout);
    };
  }, [cachedLyrics, currentTrack, expandedPlayerOpen, setCachedLyrics]);

  useEffect(() => {
    if (!expandedPlayerOpen || !currentTrack || !previewLines?.length) return;

    let frame = 0;
    const update = () => {
      const time = audioElement?.currentTime ?? currentTime;
      const next = { trackId: currentTrack.id, index: activePreviewLine(previewLines, time * 1000) };
      const previous = previewLineRef.current;
      if (previous?.trackId !== next.trackId || previous.index !== next.index) {
        previewLineRef.current = next;
        setPreviewLineState(next);
      }
      frame = requestAnimationFrame(update);
    };
    frame = requestAnimationFrame(update);
    return () => cancelAnimationFrame(frame);
  }, [audioElement, currentTime, currentTrack, expandedPlayerOpen, previewLines]);

  const tracksById = useMemo(
    () => new Map(tracks.map((track) => [track.id, track])),
    [tracks],
  );
  const title = viewName(view, playlists);
  const playlistForView = view.startsWith("playlist:")
    ? playlists.find((playlist) => `playlist:${playlist.id}` === view)
    : null;

  const visibleTracks = useMemo(() => {
    let list = tracks;
    if (view === "offline") list = list.filter((track) => track.offline);
    if (view === "favorites") list = list.filter((track) => track.favorite);
    if (view.startsWith("playlist:")) {
      const playlist = playlists.find((item) => `playlist:${item.id}` === view);
      const ids = new Set(playlist?.trackIds ?? []);
      list = list.filter((track) => ids.has(track.id));
    }
    const query = search.trim().toLocaleLowerCase();
    if (query) {
      list = list.filter((track) =>
        `${track.title} ${track.artist} ${track.album}`.toLocaleLowerCase().includes(query),
      );
    }
    if (view.startsWith("artist:")) {
      const artistName = decodeURIComponent(view.slice("artist:".length)).toLocaleLowerCase();
      list = list.filter((track) => track.artist.toLocaleLowerCase().includes(artistName));
    }
    return list;
  }, [playlists, search, tracks, view]);
  const filteredPlaylists = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return query
      ? playlists.filter((playlist) =>
          playlist.name.toLocaleLowerCase().includes(query),
        )
      : playlists;
  }, [playlists, search]);

  const notify = useCallback((message: string) => {
    setToast(message);
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    toastTimeoutRef.current = setTimeout(() => setToast(""), 2600);
  }, []);

  const reloadTracks = useCallback(async () => {
    const response = await expectOk(
      await fetchWithRetry("/api/tracks", { cache: "no-store" }, 3),
    );
    const payload = (await response.json()) as { tracks: ServerTrack[] };
    const previousTracks = usePlayerStore.getState().tracks;
    const previousById = new Map(previousTracks.map((track) => [track.id, track]));
    const nextTracks = payload.tracks.map((track): TrackRecord => ({
      id: track.id,
      title: track.title || "Unknown title",
      artist: track.artist || "Unknown artist",
      album: track.album || "Unknown album",
      duration: track.duration || 0,
      coverUrl: track.has_cover
        ? track.cover_url
        : generateAura(`${track.artist}|${track.album}|${track.title}`),
      remoteCoverUrl: track.has_cover
        ? track.cover_url
        : generateAura(`${track.artist}|${track.album}|${track.title}`),
      streamUrl: track.stream_url,
      artistImageUrl: track.artist_image_url ?? null,
      offlineUrl: previousById.get(track.id)?.offlineUrl ?? null,
      offline: previousById.get(track.id)?.offline ?? false,
      favorite: previousById.get(track.id)?.favorite ?? false,
      customLyrics: track.custom_lyrics ?? previousById.get(track.id)?.customLyrics ?? null,
    }));
    setTracks(nextTracks);
  }, [setTracks]);

  const uploadFiles = useCallback(
    async (selectedFiles: FileList | File[]) => {
      const files = Array.from(selectedFiles).filter(
        (file) =>
          file.type.startsWith("audio/") ||
          /\.(mp3|m4a|mp4|wav|flac|ogg|oga|aac|opus|weba)$/i.test(file.name),
      );
      if (files.length === 0) {
        notify("No audio files found in that selection.");
        return;
      }

      let added = 0;
      let failed = 0;
      let firstFailure = "";
      let rateLimited = false;
      let nextFileIndex = 0;
      let completedFiles = 0;
      const knownTrackIds = new Set(
        usePlayerStore.getState().tracks.map((track) => track.id),
      );
      setUploadStatus(`Uploading 0/${files.length}…`);
      const uploadNext = async () => {
        while (!rateLimited) {
          const index = nextFileIndex;
          nextFileIndex += 1;
          if (index >= files.length) return;
          const file = files[index];
          try {
            const response = await uploadWithRetry("/api/library/upload", file);
            const uploadResult = (await response.json()) as
              | ServerTrack
              | { id: string; status: "processing" };
            let uploadedTrack: ServerTrack | undefined;
            let resolvedFromReload = false;

            if ("status" in uploadResult && uploadResult.status === "processing") {
              for (let attempt = 0; attempt < 60; attempt += 1) {
                await new Promise((resolve) => setTimeout(resolve, 1000));
                const statusResponse = await expectOk(
                  await apiFetch(
                    `/api/library/upload/${encodeURIComponent(uploadResult.id)}`,
                  ),
                );
                const status = (await statusResponse.json()) as {
                  status: string;
                  error?: string | null;
                  track?: ServerTrack;
                  track_id?: string;
                };
                if (status.status === "completed") {
                  uploadedTrack = status.track;
                  if (!uploadedTrack) {
                    await reloadTracks();
                    const refreshedTrack = usePlayerStore.getState().tracks.find(
                      (track) => track.id === status.track_id,
                    );
                    if (!refreshedTrack) {
                      throw new Error("Upload completed but the track is not available yet.");
                    }
                    resolvedFromReload = true;
                  }
                  break;
                }
                if (status.status === "failed") {
                  throw new Error(status.error || "Upload processing failed.");
                }
              }
              if (!uploadedTrack && !resolvedFromReload) {
                throw new Error("Upload is still processing; refresh the library shortly.");
              }
            } else if ("title" in uploadResult && "stream_url" in uploadResult) {
              uploadedTrack = uploadResult;
            } else {
              throw new Error("The upload response was not recognized.");
            }

            if (uploadedTrack) {
              if (!knownTrackIds.has(uploadedTrack.id)) {
                knownTrackIds.add(uploadedTrack.id);
                added += 1;
              }
            } else if (resolvedFromReload) {
              added += 1;
            }
          } catch (error) {
            failed += 1;
            firstFailure =
              firstFailure ||
              (error instanceof Error ? error.message : "Upload failed.");
            if (
              error &&
              typeof error === "object" &&
              "status" in error &&
              error.status === 429
            ) {
              rateLimited = true;
              return;
            }
          } finally {
            completedFiles += 1;
            if (completedFiles % 4 === 0 || completedFiles === files.length) {
              setUploadStatus(`Uploading ${completedFiles}/${files.length}…`);
            }
          }
        }
      };
      await Promise.all(
        Array.from({ length: Math.min(3, files.length) }, () => uploadNext()),
      );

      if (added > 0) await reloadTracks();
      setUploadStatus("");
      if (rateLimited) {
        notify(`${added} uploaded; the rest were rate limited. Try again later.`);
      } else if (added > 0 && failed > 0) {
        notify(`Saved ${added}; ${failed} failed: ${firstFailure}`);
      } else if (added > 0) {
        notify(`Saved ${added} track${added === 1 ? "" : "s"} to your library.`);
      } else if (failed > 0) {
        notify(`${files.length === 1 ? "Upload failed" : `${failed} uploads failed`}: ${firstFailure}`);
      } else {
        notify("Those tracks were already in your library.");
      }
    },
    [notify, reloadTracks],
  );

  const applyMeta = useCallback(
    (meta: LibraryMeta) => {
      const trackIds = new Set(usePlayerStore.getState().tracks.map((track) => track.id));
      const filtered = {
        favorites: meta.favorites.filter((id) => trackIds.has(id)),
        playlists: meta.playlists.map((playlist) => ({
          ...playlist,
          trackIds: playlist.trackIds.filter((id) => trackIds.has(id)),
        })),
      };
      setLibraryMeta(filtered.favorites, filtered.playlists);
    },
    [setLibraryMeta],
  );

  const saveMeta = useCallback(() => {
    dirtyRef.current = true;
    const save = async () => {
      let snapshot = getMetaFromStore();
      if (!etagRef.current) return;
      let conflictRetries = 0;
      while (true) {
        const etag = etagRef.current;
        if (!etag) return;
        const response = await apiFetch(
          "/api/library/state",
          {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
              "If-Match": etag,
            },
            body: JSON.stringify(snapshot),
          },
          { csrf: true, retryCsrfOnForbidden: true },
        );

        if (response.status === 409 && conflictRetries < 2) {
          const latestResponse = await expectOk(
            await fetchWithRetry("/api/library/state", { cache: "no-store" }, 3),
          );
          const remote = normalizeMeta((await latestResponse.json()) as LibraryState);
          const latestLocal = getMetaFromStore();
          const merged = mergeUnsavedMeta(remote, baselineRef.current, latestLocal);
          etagRef.current = latestResponse.headers.get("ETag");
          baselineRef.current = remote;
          applyMeta(merged);
          snapshot = merged;
          conflictRetries += 1;
          continue;
        }
        await expectOk(response);
        etagRef.current = response.headers.get("ETag") ?? etagRef.current;
        baselineRef.current = normalizeMeta((await response.json()) as LibraryState);
        dirtyRef.current = !sameMeta(getMetaFromStore(), snapshot);
        return;
      }
    };

    const queuedSave = saveQueueRef.current.then(save, save);
    saveQueueRef.current = queuedSave.catch((error: unknown) => {
      dirtyRef.current = true;
      notify(
        error instanceof Error
          ? `Library changes could not be synced: ${error.message}`
          : "Library changes could not be synced. Please try again.",
      );
    });
    return saveQueueRef.current;
  }, [applyMeta, notify]);

  const handlePlaybackFailure = useCallback(
    (
      attempt: PlaybackAttempt,
      audio: HTMLAudioElement,
      error: unknown,
      message: string,
    ) => {
      if (
        playbackAttemptRef.current !== attempt ||
        attempt.failed ||
        attempt.retryTimer !== null
      ) {
        return;
      }
      attempt.loading = false;

      const errorName =
        error && typeof error === "object" && "name" in error && typeof error.name === "string"
          ? error.name
          : "";
      if (errorName === "AbortError") {
        return;
      }
      if (
        errorName !== "NotAllowedError" &&
        attempt.retryCount === 0 &&
        (errorName === "NetworkError" ||
          audio.error?.code === MediaError.MEDIA_ERR_ABORTED ||
          audio.error?.code === MediaError.MEDIA_ERR_NETWORK)
      ) {
        attempt.retryCount += 1;
        attempt.retryTimer = window.setTimeout(() => {
          attempt.retryTimer = null;
          if (playbackAttemptRef.current === attempt && audio.src === attempt.src) {
            runPlaybackAttemptRef.current(attempt);
          }
        }, 300);
        return;
      }

      attempt.failed = true;
      setPlaying(false);
      notify(errorName === "NotAllowedError" ? "Press play to start." : message);
    },
    [notify, setPlaying],
  );

  const runPlaybackAttempt = useCallback(
    (attempt: PlaybackAttempt) => {
      const audio = usePlayerStore.getState().audioElement;
      if (!audio || playbackAttemptRef.current !== attempt) return;
      const requestId = ++attempt.requestId;
      attempt.loading = true;
      if (
        audio.src !== attempt.src ||
        audio.error !== null ||
        audio.networkState === HTMLMediaElement.NETWORK_NO_SOURCE
      ) {
        audio.src = attempt.src;
        audio.load();
      }
      setPlaying(true);
      void audio.play().then(
        () => {
          if (playbackAttemptRef.current === attempt && attempt.requestId === requestId) {
            attempt.loading = false;
          }
        },
        (error: unknown) => {
          if (
            playbackAttemptRef.current !== attempt ||
            attempt.requestId !== requestId ||
            audio.src !== attempt.src
          ) {
            return;
          }
          attempt.loading = false;
          if (
            error &&
            typeof error === "object" &&
            "name" in error &&
            error.name === "AbortError"
          ) {
            setPlaying(false);
            return;
          }
          logAudioFailure("play() rejected", audio, error);
          handlePlaybackFailure(
            attempt,
            audio,
            error,
            "The track could not start. Please try again.",
          );
        },
      );
    },
    [handlePlaybackFailure, setPlaying],
  );
  const startTrack = useCallback(
    (trackId: string) => {
      const track = usePlayerStore.getState().tracks.find((item) => item.id === trackId);
      const audio = usePlayerStore.getState().audioElement;
      if (!track || !audio) return;

      const src = new URL(track.offlineUrl || track.streamUrl, window.location.href).href;
      const currentAttempt = playbackAttemptRef.current;
      if (
        currentAttempt?.src === src &&
        !currentAttempt.failed &&
        (currentAttempt.loading || !audio.paused)
      ) {
        return;
      }

      const previousAttempt = playbackAttemptRef.current;
      if (previousAttempt?.retryTimer !== null && previousAttempt?.retryTimer !== undefined) {
        window.clearTimeout(previousAttempt.retryTimer);
      }
      const attempt: PlaybackAttempt = {
        src,
        retryCount: 0,
        retryTimer: null,
        requestId: 0,
        loading: false,
        failed: false,
      };
      playbackAttemptRef.current = attempt;
      runPlaybackAttemptRef.current = runPlaybackAttempt;
      runPlaybackAttempt(attempt);
    },
    [runPlaybackAttempt],
  );

  const handleAudioError = useCallback(
    (audio: HTMLAudioElement) => {
      const error = new Error(audio.error?.message || "Audio element emitted an error");
      error.name = "MediaError";
      logAudioFailure("audio error event", audio, error);

      const attempt = playbackAttemptRef.current;
      if (
        !attempt ||
        audio.src !== attempt.src ||
        (audio.currentSrc && audio.currentSrc !== attempt.src)
      ) {
        return;
      }
      handlePlaybackFailure(
        attempt,
        audio,
        error,
        "This track could not be played. Check the file format or your connection.",
      );
    },
    [handlePlaybackFailure],
  );

  const playFromList = useCallback(
    (list: TrackRecord[], trackId: string) => {
      const ids = list.map((track) => track.id);
      const index = ids.indexOf(trackId);
      if (index < 0) return;
      setPlayingFromView(view);
      shufflePlayedRef.current = new Set([index]);
      setQueue(ids, index);
      startTrack(trackId);
    },
    [setQueue, startTrack, view],
  );

  const playQueueIndex = useCallback(
    (index: number) => {
      const state = usePlayerStore.getState();
      const trackId = state.queue[index];
      if (!trackId) return;
      setQueueIndex(index);
      startTrack(trackId);
    },
    [setQueueIndex, startTrack],
  );

  const playNext = useCallback(
    (automatic: boolean) => {
      const state = usePlayerStore.getState();
      const audio = state.audioElement;
      if (!audio || state.queue.length === 0) return;

      if (automatic && state.repeat === "one") {
        audio.currentTime = 0;
        void audio.play().catch(() => notify("The track could not restart. Please try again."));
        return;
      }

      let nextIndex = state.queueIndex + 1;
      if (state.shuffle) {
        shufflePlayedRef.current.add(state.queueIndex);
        let choices = state.queue
          .map((_, index) => index)
          .filter((index) => index !== state.queueIndex);
        if (automatic && state.repeat === "off") {
          choices = choices.filter((index) => !shufflePlayedRef.current.has(index));
          if (choices.length === 0) {
            audio.pause();
            return;
          }
        } else if (
          automatic &&
          state.repeat === "all" &&
          !choices.some((index) => !shufflePlayedRef.current.has(index))
        ) {
          shufflePlayedRef.current = new Set([state.queueIndex]);
        }
        if (choices.length === 0) choices = [state.queueIndex];
        nextIndex = choices[Math.floor(Math.random() * choices.length)];
        shufflePlayedRef.current.add(nextIndex);
      } else if (nextIndex >= state.queue.length) {
        if (automatic && state.repeat === "off") {
          audio.pause();
          return;
        }
        nextIndex = 0;
      }
      playQueueIndex(nextIndex);
    },
    [notify, playQueueIndex],
  );
  useEffect(() => {
    nextRef.current = playNext;
  }, [playNext]);

  useEffect(() => {
    const panel = queuePanelRef.current;
    if (!panel) return;
    panel.inert = !queueOpen;
    if (queueOpen) panel.removeAttribute("aria-hidden");
    else panel.setAttribute("aria-hidden", "true");
  }, [queueOpen]);

  useEffect(() => {
    if (!trackMenu) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!(event.target instanceof Element)) return;
      if (
        event.target.closest(".track-context-menu") ||
        event.target.closest("[data-track-menu-trigger]")
      ) {
        return;
      }
      setTrackMenu(null);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [trackMenu]);

  useEffect(() => {
    if (playlistModal) playlistNameInputRef.current?.focus();
  }, [playlistModal]);

  const playPrevious = useCallback(() => {
    const state = usePlayerStore.getState();
    const audio = state.audioElement;
    if (!audio || state.queue.length === 0) return;
    if (audio.currentTime > 3) {
      audio.currentTime = 0;
      return;
    }
    playQueueIndex(Math.max(0, state.queueIndex - 1));
  }, [playQueueIndex]);

  const togglePlayback = useCallback(() => {
    if (!audioElement) return;
    if (!currentTrack) {
      if (visibleTracks[0]) playFromList(visibleTracks, visibleTracks[0].id);
      return;
    }
    if (audioElement.paused) {
      if (audioElement.getAttribute("src")) {
        void audioElement.play().catch(() => startTrack(currentTrack.id));
      } else {
        startTrack(currentTrack.id);
      }
    } else {
      const attempt = playbackAttemptRef.current;
      if (attempt?.retryTimer !== null && attempt?.retryTimer !== undefined) {
        window.clearTimeout(attempt.retryTimer);
        attempt.retryTimer = null;
      }
      if (attempt) attempt.requestId += 1;
      audioElement.pause();
    }
  }, [audioElement, currentTrack, playFromList, startTrack, visibleTracks]);

  const toggleCurrentFavorite = useCallback(() => {
    const state = usePlayerStore.getState();
    const trackId = state.queue[state.queueIndex];
    if (!trackId) return;
    state.toggleFavorite(trackId);
    void saveMeta();
  }, [saveMeta]);

  useEffect(() => {
    const mediaSession = navigator.mediaSession;
    if (!mediaSession) return;
    const active = usePlayerStore.getState().tracks.find(
      (track) => track.id === usePlayerStore.getState().queue[usePlayerStore.getState().queueIndex],
    );
    if (!active) {
      mediaSession.metadata = null;
      mediaSession.playbackState = "none";
      return;
    }
    mediaSession.playbackState = usePlayerStore.getState().audioElement?.paused
      ? "paused"
      : "playing";
    if ("MediaMetadata" in window) {
      try {
        mediaSession.metadata = new MediaMetadata({
          title: active.title || "Unknown title",
          artist: active.artist || "Unknown artist",
          album: active.album || "",
          artwork: [96, 128, 192, 256, 384, 512].map((size) => ({
            src: new URL(active.coverUrl, window.location.href).href,
            sizes: `${size}x${size}`,
            type: "image/jpeg",
          })),
        });
      } catch (error) {
        console.warn("Could not set system media metadata", error);
      }
    }

    const actions: Array<[MediaSessionAction, MediaSessionActionHandler]> = [
      ["play", () => togglePlayback()],
      ["pause", () => usePlayerStore.getState().audioElement?.pause()],
      ["previoustrack", () => playPrevious()],
      ["nexttrack", () => nextRef.current(false)],
      ["seekbackward", (details) =>
        seekAudio(
          usePlayerStore.getState().audioElement,
          -(Number(details.seekOffset) || 10),
        )],
      ["seekforward", (details) =>
        seekAudio(
          usePlayerStore.getState().audioElement,
          Number(details.seekOffset) || 10,
        )],
      ["seekto", (details) => {
        const audio = usePlayerStore.getState().audioElement;
        if (audio && Number.isFinite(details.seekTime)) {
          audio.currentTime = Math.max(0, Math.min(audio.duration || Infinity, details.seekTime ?? 0));
        }
      }],
    ];
    for (const [action, handler] of actions) {
      try {
        mediaSession.setActionHandler(action, handler);
      } catch {
        // Unsupported actions are ignored by the browser.
      }
    }
    return () => {
      for (const [action] of actions) {
        try {
          mediaSession.setActionHandler(action, null);
        } catch {
          // Unsupported actions are ignored by the browser.
        }
      }
    };
  }, [activeTrackId, playPrevious, togglePlayback]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        (target.isContentEditable ||
          ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
      ) {
        if (event.key === "Escape") target.blur();
        return;
      }
      if (event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        document.querySelector<HTMLInputElement>(".search-wrap input")?.focus();
        return;
      }
      if (event.key === "Escape") {
        setExpandedPlayerOpen(false);
        setLyricsOpen(false);
        setVisualizerOpen(false);
        setQueueOpen(false);
        setPlaylistPicker(null);
        setPlaylistModal(null);
        setShortcutsOpen(false);
        setTrackMenu(null);
        return;
      }
      if (event.key === "?") {
        setShortcutsOpen((current) => !current);
        return;
      }
      switch (event.key) {
        case " ":
          event.preventDefault();
          togglePlayback();
          break;
        case "ArrowRight":
          if (event.shiftKey) nextRef.current(false);
          else seekAudio(usePlayerStore.getState().audioElement, 5);
          break;
        case "ArrowLeft":
          if (event.shiftKey) playPrevious();
          else seekAudio(usePlayerStore.getState().audioElement, -5);
          break;
        case "ArrowUp":
          event.preventDefault();
          setVolume((current) => Math.min(1, current + 0.05));
          break;
        case "ArrowDown":
          event.preventDefault();
          setVolume((current) => Math.max(0, current - 0.05));
          break;
        case "m":
        case "M":
          setMuted((current) => !current);
          break;
        case "f":
        case "F":
          toggleCurrentFavorite();
          break;
        case "n":
        case "N":
          setMiniMode((current) => !current);
          break;
        case "l":
        case "L":
          setLyricsOpen((current) => !current);
          break;
        case "v":
        case "V":
          setVisualizerOpen((current) => !current);
          break;
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [playPrevious, toggleCurrentFavorite, togglePlayback]);

  useEffect(() => {
    let cancelled = false;
    async function loadLibrary() {
      setLoading(true);
      setLoadError(null);
      try {
        const [tracksResponse, stateResponse, accountResponse] = await Promise.all([
          fetchWithRetry("/api/tracks", { cache: "no-store" }, 3),
          fetchWithRetry("/api/library/state", { cache: "no-store" }, 3),
          fetchWithRetry("/api/me", { cache: "no-store" }, 3),
        ]);
        await expectOk(tracksResponse);
        await expectOk(stateResponse);
        await expectOk(accountResponse);
        const payload = (await tracksResponse.json()) as { tracks: ServerTrack[] };
        const account = (await accountResponse.json()) as Account;
        const nextTracks: TrackRecord[] = payload.tracks.map((track) => ({
          id: track.id,
          title: track.title || "Unknown title",
          artist: track.artist || "Unknown artist",
          album: track.album || "Unknown album",
          duration: track.duration || 0,
          coverUrl: track.has_cover
            ? track.cover_url
            : generateAura(`${track.artist}|${track.album}|${track.title}`),
          remoteCoverUrl: track.has_cover
            ? track.cover_url
            : generateAura(`${track.artist}|${track.album}|${track.title}`),
          streamUrl: track.stream_url,
          artistImageUrl: track.artist_image_url ?? null,
          favorite: false,
          customLyrics: track.custom_lyrics ?? null,
        }));
        const remoteMeta = normalizeMeta((await stateResponse.json()) as LibraryState);
        const legacyMeta = await readLegacyMeta();
        let offlineRecords: OfflineTrackRecord[] = [];
        try {
          offlineRecords = await readOfflineTracks(account.id);
        } catch (error) {
          console.error("Could not load saved offline tracks.", error);
          notify("Saved offline tracks could not be loaded from this browser.");
        }
        const offlineById = new Map(offlineRecords.map((record) => [record.trackId, record]));
        for (const track of nextTracks) {
          const record = offlineById.get(track.id);
          if (!record) continue;
          const offlineUrl = URL.createObjectURL(record.audio);
          offlineObjectUrlsRef.current.add(offlineUrl);
          track.offlineUrl = offlineUrl;
          track.offline = true;
          track.customLyrics = record.customLyrics ?? track.customLyrics;
          if (record.cover instanceof Blob) {
            const coverUrl = URL.createObjectURL(record.cover);
            offlineObjectUrlsRef.current.add(coverUrl);
            track.coverUrl = coverUrl;
          }
        }
        const loadedTrackIds = new Set(nextTracks.map((track) => track.id));
        for (const record of offlineRecords) {
          if (loadedTrackIds.has(record.trackId)) continue;
          const offlineUrl = URL.createObjectURL(record.audio);
          offlineObjectUrlsRef.current.add(offlineUrl);
          const fallbackCover = generateAura(`${record.artist}|${record.album}|${record.title}`);
          let coverUrl = fallbackCover;
          if (record.cover instanceof Blob) {
            coverUrl = URL.createObjectURL(record.cover);
            offlineObjectUrlsRef.current.add(coverUrl);
          }
          nextTracks.push({
            id: record.trackId,
            title: record.title || "Unknown title",
            artist: record.artist || "Unknown artist",
            album: record.album || "Unknown album",
            duration: record.duration || 0,
            coverUrl,
            remoteCoverUrl: fallbackCover,
            streamUrl: "",
            offlineUrl,
            offline: true,
            favorite: false,
            customLyrics: record.customLyrics,
          });
        }
        if (cancelled) return;
        setProfile(account);
        setTracks(nextTracks);
        baselineRef.current = remoteMeta;
        etagRef.current = stateResponse.headers.get("ETag");
        if (
          remoteMeta.favorites.length === 0 &&
          remoteMeta.playlists.length === 0 &&
          legacyMeta &&
          (legacyMeta.favorites.length > 0 || legacyMeta.playlists.length > 0)
        ) {
          applyMeta(legacyMeta);
          void saveMeta();
        } else {
          applyMeta(remoteMeta);
        }
      } catch (error) {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : "Could not load your library.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void loadLibrary();
    return () => {
      cancelled = true;
    };
  }, [applyMeta, notify, saveMeta, setTracks]);

  useEffect(() => {
    if (!audioElement) return;
    const updatePlayback = () => {
      const nextDuration = Number.isFinite(audioElement.duration)
        ? audioElement.duration
        : 0;
      setDuration((currentDuration) =>
        currentDuration === nextDuration ? currentDuration : nextDuration,
      );
      const session = navigator.mediaSession;
      if (
        session?.setPositionState &&
        Number.isFinite(audioElement.duration) &&
        audioElement.duration > 0 &&
        Number.isFinite(audioElement.currentTime)
      ) {
        try {
          session.setPositionState({
            duration: audioElement.duration,
            position: Math.max(0, Math.min(audioElement.currentTime, audioElement.duration)),
            playbackRate: audioElement.playbackRate || 1,
          });
        } catch {
          // Browsers may reject position updates before media metadata is ready.
        }
      }
    };
    const updatePlaybackPosition = () => {
      setCurrentTime(audioElement.currentTime || 0);
      updatePlayback();
    };
    const onPlay = () => {
      setPlaying(true);
      if (navigator.mediaSession) navigator.mediaSession.playbackState = "playing";
    };
    const onPause = () => {
      updatePlaybackPosition();
      setPlaying(false);
      if (navigator.mediaSession) navigator.mediaSession.playbackState = "paused";
    };
    const onEnded = () => nextRef.current(true);
    const onError = () => handleAudioError(audioElement);
    audioElement.addEventListener("timeupdate", updatePlayback);
    audioElement.addEventListener("loadedmetadata", updatePlaybackPosition);
    audioElement.addEventListener("durationchange", updatePlaybackPosition);
    audioElement.addEventListener("seeked", updatePlaybackPosition);
    audioElement.addEventListener("play", onPlay);
    audioElement.addEventListener("pause", onPause);
    audioElement.addEventListener("ended", onEnded);
    audioElement.addEventListener("error", onError);
    updatePlaybackPosition();
    return () => {
      audioElement.removeEventListener("timeupdate", updatePlayback);
      audioElement.removeEventListener("loadedmetadata", updatePlaybackPosition);
      audioElement.removeEventListener("durationchange", updatePlaybackPosition);
      audioElement.removeEventListener("seeked", updatePlaybackPosition);
      audioElement.removeEventListener("play", onPlay);
      audioElement.removeEventListener("pause", onPause);
      audioElement.removeEventListener("ended", onEnded);
      audioElement.removeEventListener("error", onError);
    };
  }, [audioElement, handleAudioError, setPlaying]);

  useEffect(() => {
    document.body.classList.toggle("mini-mode", miniMode);
    return () => document.body.classList.remove("mini-mode");
  }, [miniMode]);

  useEffect(() => {
    const audio = usePlayerStore.getState().audioElement;
    if (!audio) return;
    audio.volume = volume;
    audio.muted = muted;
  }, [audioElement, muted, volume]);

  useEffect(
    () => () => {
      if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
      offlineObjectUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
      offlineObjectUrlsRef.current.clear();
    },
    [],
  );

  function toggleFavoriteFor(track: TrackRecord) {
    toggleFavorite(track.id);
    void saveMeta();
  }

  function createOrRenamePlaylist(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = playlistName.trim();
    if (!name) return;
    const state = usePlayerStore.getState();
    let nextPlaylists: PlaylistRecord[];
    if (playlistModal?.playlist) {
      nextPlaylists = state.playlists.map((playlist) =>
        playlist.id === playlistModal.playlist?.id ? { ...playlist, name } : playlist,
      );
      notify(`Renamed playlist to “${name}”.`);
    } else {
      const playlist: PlaylistRecord = {
        id: crypto.randomUUID().replaceAll("-", ""),
        name,
        trackIds: playlistModal?.trackId ? [playlistModal.trackId] : [],
      };
      nextPlaylists = [...state.playlists, playlist];
      setView(`playlist:${playlist.id}`);
      notify(`Created “${name}”.`);
    }
    setPlaylists(nextPlaylists);
    setPlaylistModal(null);
    setPlaylistName("");
    void saveMeta();
  }

  function addTrackToPlaylist(playlistId: string, trackId: string) {
    const state = usePlayerStore.getState();
    const playlist = state.playlists.find((item) => item.id === playlistId);
    if (!playlist || playlist.trackIds.includes(trackId)) return;
    setPlaylists(
      state.playlists.map((item) =>
        item.id === playlistId ? { ...item, trackIds: [...item.trackIds, trackId] } : item,
      ),
    );
    void saveMeta();
  }

  async function toggleOfflineDownload(track: TrackRecord) {
    if (!profile?.id) {
      notify("Your account is still loading. Try again shortly.");
      return;
    }
    setTrackMenu(null);
    setOfflinePendingId(track.id);
    try {
      if (track.offlineUrl) {
        await deleteOfflineTrack(profile.id, track.id);
        const state = usePlayerStore.getState();
        setTracks(
          state.tracks.map((item) =>
            item.id === track.id
              ? {
                  ...item,
                  offline: false,
                  offlineUrl: null,
                  coverUrl: item.remoteCoverUrl ?? item.coverUrl,
                }
              : item,
          ),
        );
        notify(`Removed “${track.title}” from offline storage.`);
        return;
      }

      const audioResponse = await expectOk(
        await apiFetch(track.streamUrl, { cache: "no-store" }),
      );
      const audio = await audioResponse.blob();
      if (!audio.size) throw new Error("The downloaded track was empty.");

      let cover: Blob | null = null;
      if (track.remoteCoverUrl?.startsWith("/api/tracks/")) {
        const coverResponse = await apiFetch(track.remoteCoverUrl, { cache: "no-store" });
        if (coverResponse.ok) cover = await coverResponse.blob();
        else console.warn(`Could not save the cover for “${track.title}” offline.`);
      }

      await writeOfflineTrack({
        id: `${profile.id}:${track.id}`,
        accountId: profile.id,
        trackId: track.id,
        title: track.title,
        artist: track.artist,
        album: track.album,
        duration: track.duration,
        customLyrics: track.customLyrics ?? null,
        audio,
        cover,
        dateAdded: Date.now(),
      });
      const offlineUrl = URL.createObjectURL(audio);
      offlineObjectUrlsRef.current.add(offlineUrl);
      let coverUrl: string | undefined;
      if (cover) {
        coverUrl = URL.createObjectURL(cover);
        offlineObjectUrlsRef.current.add(coverUrl);
      }
      const state = usePlayerStore.getState();
      setTracks(
        state.tracks.map((item) =>
          item.id === track.id
            ? { ...item, offline: true, offlineUrl, ...(coverUrl ? { coverUrl } : {}) }
            : item,
        ),
      );
      notify(`Downloaded “${track.title}” for offline listening.`);
    } catch (error) {
      console.error("Could not save the offline track.", error);
      notify(error instanceof Error ? error.message : "Could not save this track offline.");
    } finally {
      setOfflinePendingId(null);
    }
  }

  async function removeTrack(track: TrackRecord) {
    if (!window.confirm(`Remove “${track.title}” from your library? This deletes the file.`)) {
      return;
    }
    setTrackMenu(null);
    try {
      await expectOk(
        await apiFetch(
          `/api/tracks/${encodeURIComponent(track.id)}`,
          { method: "DELETE" },
          { csrf: true, retryCsrfOnForbidden: true },
        ),
      );
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not remove the track.");
      return;
    }

    const state = usePlayerStore.getState();
    const activeId = state.queue[state.queueIndex] ?? null;
    const nextTracks = state.tracks.filter((item) => item.id !== track.id);
    const nextPlaylists = state.playlists.map((playlist) => ({
      ...playlist,
      trackIds: playlist.trackIds.filter((id) => id !== track.id),
    }));
    const nextQueue = state.queue.filter((id) => id !== track.id);
    setTracks(nextTracks);
    setPlaylists(nextPlaylists);

    if (activeId === track.id) {
      if (nextQueue.length) {
        const nextIndex = Math.min(state.queueIndex, nextQueue.length - 1);
        setQueue(nextQueue, nextIndex);
        startTrack(nextQueue[nextIndex]);
      } else {
        audioElement?.pause();
        if (audioElement) {
          audioElement.removeAttribute("src");
          audioElement.load();
        }
        setQueue([], -1);
        setPlaying(false);
      }
    } else {
      setQueue(nextQueue, activeId ? nextQueue.indexOf(activeId) : -1);
    }

    let offlineCleanupFailed = false;
    if (profile?.id) {
      try {
        await deleteOfflineTrack(profile.id, track.id);
      } catch (error) {
        offlineCleanupFailed = true;
        console.error("Could not remove the local offline copy.", error);
      }
    }
    void saveMeta();
    notify(
      offlineCleanupFailed
        ? `Removed “${track.title}” from your library, but its local offline copy could not be cleared.`
        : `Removed “${track.title}” from your library.`,
    );
  }

  function removeTrackFromPlaylist(playlistId: string, track: TrackRecord) {
    const state = usePlayerStore.getState();
    const playlist = state.playlists.find((item) => item.id === playlistId);
    if (!playlist || !playlist.trackIds.includes(track.id)) return;
    setPlaylists(
      state.playlists.map((item) =>
        item.id === playlistId
          ? { ...item, trackIds: item.trackIds.filter((id) => id !== track.id) }
          : item,
      ),
    );
    setTrackMenu(null);
    void saveMeta();
    notify(`Removed “${track.title}” from “${playlist.name}”.`);
  }

  function openArtist(name: string) {
    setTrackMenu(null);
    setExpandedPlayerOpen(false);
    setLyricsOpen(false);
    setSearch("");
    setView(`artist:${encodeURIComponent(name)}`);
  }

  function openExpandedPlayer(trigger?: HTMLElement | null) {
    const activeElement = document.activeElement;
    expandedPlayerReturnFocusRef.current =
      trigger ??
      (activeElement instanceof HTMLElement ? activeElement : null);
    setExpandedPlayerOpen(true);
  }

  async function shareTrack(track: TrackRecord) {
    const text = `${track.title} — ${track.artist}`;
    if (navigator.share) {
      try {
        await navigator.share({ title: track.title, text });
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        notify("Could not share this song.");
      }
      return;
    }
    try {
      await navigator.clipboard.writeText(`${text}\n${window.location.href}`);
      notify("Song details copied to clipboard.");
    } catch {
      notify("Sharing is not available in this browser.");
    }
    setTrackMenu(null);
  }

  function addToQueue(track: TrackRecord, playImmediatelyAfterCurrent = false) {
    const state = usePlayerStore.getState();
    const nextQueue = [...state.queue];
    if (playImmediatelyAfterCurrent) {
      const insertAt = state.queueIndex < 0 ? nextQueue.length : state.queueIndex + 1;
      nextQueue.splice(insertAt, 0, track.id);
      setQueue(nextQueue, state.queueIndex < 0 ? 0 : state.queueIndex);
      notify(`“${track.title}” will play next.`);
    } else {
      nextQueue.push(track.id);
      setQueue(nextQueue, state.queueIndex < 0 ? 0 : state.queueIndex);
      notify(`Added “${track.title}” to the queue.`);
    }
  }

  function seekTo(time: number) {
    const audio = usePlayerStore.getState().audioElement;
    if (!audio || !duration) return;
    audio.currentTime = Math.max(0, Math.min(duration, time));
    setCurrentTime(audio.currentTime);
  }

  function updateVolume(event: ReactMouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const nextVolume = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    setPlayerVolume(nextVolume);
  }

  function setPlayerVolume(nextVolume: number) {
    const audio = usePlayerStore.getState().audioElement;
    setVolume(nextVolume);
    setMuted(nextVolume === 0);
    if (audio) {
      audio.volume = nextVolume;
      audio.muted = nextVolume === 0;
    }
  }

  function toggleShuffle() {
    setShuffle(!shuffle);
    shufflePlayedRef.current.clear();
    notify(!shuffle ? "Shuffle on" : "Shuffle off");
  }

  function toggleRepeat() {
    const next = repeat === "off" ? "all" : repeat === "all" ? "one" : "off";
    setRepeat(next);
    notify(`Repeat: ${next}`);
  }

  function reorderQueue(fromIndex: number, targetIndex: number) {
    const state = usePlayerStore.getState();
    if (
      fromIndex < 0 ||
      fromIndex >= state.queue.length ||
      targetIndex < 0 ||
      targetIndex >= state.queue.length ||
      fromIndex === targetIndex
    ) return;

    const nextQueue = [...state.queue];
    const [moved] = nextQueue.splice(fromIndex, 1);
    const insertAt = fromIndex < targetIndex ? targetIndex - 1 : targetIndex;
    nextQueue.splice(insertAt, 0, moved);

    let activeIndex = state.queueIndex;
    if (activeIndex === fromIndex) activeIndex = insertAt;
    else {
      if (fromIndex < activeIndex) activeIndex -= 1;
      if (insertAt <= activeIndex) activeIndex += 1;
    }
    setQueue(nextQueue, activeIndex);
  }

  function removeFromQueue(index: number) {
    const state = usePlayerStore.getState();
    const nextQueue = [...state.queue];
    nextQueue.splice(index, 1);
    let nextIndex = state.queueIndex;
    if (index < nextIndex) nextIndex -= 1;
    else if (index === nextIndex) {
      if (nextQueue.length === 0) {
        audioElement?.pause();
        nextIndex = -1;
      } else {
        nextIndex = Math.min(index, nextQueue.length - 1);
        startTrack(nextQueue[nextIndex]);
      }
    }
    setQueue(nextQueue, nextIndex);
  }

  const count = view === "playlists"
    ? filteredPlaylists.length
    : view === "artists"
      ? new Set(tracks.flatMap(artistNames)).size
      : visibleTracks.length;
  const playlistCoverTracks = (playlist: PlaylistRecord) =>
    playlist.trackIds
      .map((trackId) => tracksById.get(trackId))
      .filter((track): track is TrackRecord => Boolean(track))
      .slice(0, 4);
  const playlistViewCovers = playlistForView
    ? playlistCoverTracks(playlistForView)
    : [];
  const filteredQueueTracks = tracks.filter((track) =>
    `${track.title} ${track.artist}`.toLowerCase().includes(queueSearch.trim().toLowerCase()),
  );
  const playlistTarget = playlists.find((playlist) => playlist.id === playlistAddTarget);
  const tracksAvailableToAdd = playlistTarget
    ? tracks.filter((track) => !playlistTarget.trackIds.includes(track.id))
    : [];

  function toggleTrackMenu(track: TrackRecord, event: ReactMouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    const rect = event.currentTarget.getBoundingClientRect();
    const playlistId = view.startsWith("playlist:") ? view.slice("playlist:".length) : null;
    const inPlaylist = playlists.find((playlist) => playlist.id === playlistId)?.trackIds.includes(track.id);
    const itemCount = 7 + artistNames(track).length + (inPlaylist ? 1 : 0);
    const menuHeight = Math.min(16 + itemCount * 38, window.innerHeight - 16);
    const top = Math.max(
      8,
      Math.min(
        rect.bottom + 6,
        window.innerHeight - menuHeight - 8,
      ),
    );
    const left = Math.max(8, Math.min(rect.right - 204, window.innerWidth - 212));
    setTrackMenu((current) =>
      current?.trackId === track.id ? null : { trackId: track.id, top, left },
    );
  }

  function renderTrackMenu(track: TrackRecord) {
    if (trackMenu?.trackId !== track.id || typeof document === "undefined") return null;
    const playlistId = view.startsWith("playlist:") ? view.slice("playlist:".length) : null;
    const playlist = playlists.find((item) => item.id === playlistId);
    const inPlaylist = playlist?.trackIds.includes(track.id) ?? false;
    return createPortal(
      <div
        className="menu track-context-menu"
        role="menu"
        aria-label={`Options for ${track.title}`}
        style={{ top: trackMenu.top, left: trackMenu.left }}
        onClick={(event) => event.stopPropagation()}
      >
        <button className="menu-item" role="menuitem" type="button" onClick={() => { addToQueue(track, true); setTrackMenu(null); }}>Play next</button>
        <button className="menu-item" role="menuitem" type="button" onClick={() => { addToQueue(track); setTrackMenu(null); }}>Add to queue</button>
        <button className="menu-item" role="menuitem" type="button"         onClick={() => { setExpandedPlayerOpen(false); setPlaylistPicker(track.id); setTrackMenu(null); }}>Add to playlist</button>
        <button
          className="menu-item"
          role="menuitem"
          type="button"
          disabled={offlinePendingId !== null}
          onClick={() => void toggleOfflineDownload(track)}
        >
          {offlinePendingId === track.id
            ? "Saving offline…"
            : track.offlineUrl
              ? "Remove offline download"
              : "Download for offline"}
        </button>
        <button
          className="menu-item"
          role="menuitemcheckbox"
          type="button"
          aria-checked={track.favorite}
          onClick={() => { toggleFavoriteFor(track); setTrackMenu(null); }}
        >
          {track.favorite ? "Remove from liked songs" : "Save to liked songs"}
        </button>
        {artistNames(track).map((name) => (
          <button
            className="menu-item"
            role="menuitem"
            type="button"
            key={name}
            onClick={() => openArtist(name)}
          >
            View artist: {name}
          </button>
        ))}
        <button className="menu-item" role="menuitem" type="button" onClick={() => void shareTrack(track)}>Share song</button>
        {inPlaylist && playlist ? (
          <button className="menu-item" role="menuitem" type="button" onClick={() => removeTrackFromPlaylist(playlist.id, track)}>
            Remove from this playlist
          </button>
        ) : null}
        <div className="menu-sep" />
        <button className="menu-item" role="menuitem" type="button" onClick={() => { setExpandedPlayerOpen(false); void removeTrack(track); }}>
          Remove from library
        </button>
      </div>,
      document.body,
      `track-menu-${track.id}`,
    );
  }

  const renderTrack = (
    track: TrackRecord,
    index: number,
    playList: TrackRecord[] = visibleTracks,
  ) => {
    const playing = activeTrackId === track.id;
    if (listMode === "grid") {
      return (
        <article
          className={`card${playing ? " playing" : ""}`}
          key={`${track.id}-${index}`}
          onClick={() => playFromList(playList, track.id)}
        >
          <button className="card-art" type="button" aria-label={`Play ${track.title}`} onClick={(event) => { event.stopPropagation(); playFromList(playList, track.id); }}>
            <TrackImage track={track} />
            <span className="card-play" aria-hidden="true"><Icon name="play" /></span>
          </button>
          <button
            className="card-queue"
            type="button"
            title="Add to queue"
            aria-label="Add to queue"
            onClick={(event) => {
              event.stopPropagation();
              addToQueue(track);
            }}
          >
            <Icon name="queue" />
          </button>
          <button
            className={`card-fav${track.favorite ? " on" : ""}`}
            type="button"
            title={track.favorite ? "Remove favorite" : "Favorite"}
            aria-label={track.favorite ? "Remove favorite" : "Favorite"}
            onClick={(event) => {
              event.stopPropagation();
              toggleFavoriteFor(track);
            }}
          >
            <Icon name="heart" />
          </button>
          <button
            className="card-menu"
            type="button"
            title="More options"
            aria-label={`More options for ${track.title}`}
            aria-haspopup="menu"
            aria-expanded={trackMenu?.trackId === track.id}
            data-track-menu-trigger
            onClick={(event) => {
              event.stopPropagation();
              toggleTrackMenu(track, event);
            }}
          >
            <Icon name="more" />
          </button>
          {renderTrackMenu(track)}
          <div className="card-title">{track.title}</div>
          <div className="card-sub">
            {artistNames(track).map((name, artistIndex) => (
              <Fragment key={name}>
                {artistIndex > 0 ? <span className="artist-sep">, </span> : null}
                <button
                  className="artist-link"
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    openArtist(name);
                  }}
                >
                  {name}
                </button>
              </Fragment>
            ))}
          </div>
        </article>
      );
    }

    return (
      <div className={`row${playing ? " playing" : ""}`} key={`${track.id}-${index}`}>
        <div className="row-idx">
          <span className="num">{index + 1}</span>
          <button className="play-mini" type="button" aria-label={`Play ${track.title}`} onClick={() => playFromList(playList, track.id)}>
            <Icon name="play" />
          </button>
          <span className="bars"><span /><span /><span /></span>
        </div>
        <div className="row-title-wrap">
          <TrackImage track={track} className="row-art" />
          <span className="row-title-stack">
            <button className="row-title" type="button" onClick={() => playFromList(playList, track.id)}>{track.title}</button>
            <span className="row-meta"><span className="row-artist">
              {artistNames(track).map((name, artistIndex) => (
                <Fragment key={name}>
                  {artistIndex > 0 ? <span className="artist-sep">, </span> : null}
                  <button className="artist-link" type="button" onClick={() => openArtist(name)}>
                    {name}
                  </button>
                </Fragment>
              ))}
            </span></span>
          </span>
        </div>
        <div className="row-album-cell">{track.album}</div>
        <div className="row-time">{track.duration ? formatTime(track.duration) : "--:--"}</div>
        <div className="row-actions">
          <button type="button" title="Add to queue" aria-label="Add to queue" onClick={(event) => { event.stopPropagation(); addToQueue(track); }}><Icon name="queue" /></button>
          <button type="button" className={track.favorite ? "fav-on" : ""} title={track.favorite ? "Remove favorite" : "Favorite"} aria-label={track.favorite ? "Remove favorite" : "Favorite"} aria-pressed={track.favorite} onClick={(event) => { event.stopPropagation(); toggleFavoriteFor(track); }}><Icon name="heart" /></button>
          <button
            type="button"
            title="More options"
            aria-label={`More options for ${track.title}`}
            aria-haspopup="menu"
            aria-expanded={trackMenu?.trackId === track.id}
            data-track-menu-trigger
            onClick={(event) => toggleTrackMenu(track, event)}
          ><Icon name="more" /></button>
          {renderTrackMenu(track)}
        </div>
      </div>
    );
  };

  const renderEmptyState = () => {
    if (search.trim()) {
      return (
        <div className="empty">
          <div className="empty-orb" />
          <h3>No matches for “{search.trim()}”</h3>
          <p>Try another title, artist, or album name.</p>
          <button className="btn" type="button" onClick={() => setSearch("")}>Clear search</button>
        </div>
      );
    }
    if (playlistForView) {
      return (
        <div className="empty playlist-track-empty">
          <div className="empty-orb" />
          <h3>This playlist is empty</h3>
          <p>{tracks.length ? "Add songs from your library to start building it." : "Add music to your library, then come back to build this playlist."}</p>
          {tracks.length ? (
            <button className="btn btn-primary" type="button" onClick={() => setPlaylistAddTarget(playlistForView.id)}>Add from library</button>
          ) : (
            <button className="btn btn-primary" type="button" onClick={() => fileInputRef.current?.click()}>Add music</button>
          )}
        </div>
      );
    }
    if (view === "offline") {
      return (
        <div className="empty">
          <div className="empty-orb"><Icon name="offline" /></div>
          <h3>No offline songs yet</h3>
          <p>Download songs from the library menu to listen without an internet connection.</p>
          <button className="btn btn-primary" type="button" onClick={() => setView("library")}>Browse library</button>
        </div>
      );
    }
    if (tracks.length === 0) {
      return (
        <div className="empty">
          <div className="empty-orb" />
          <h3>Your library is empty</h3>
          <p>Add songs or a folder. Vervfy saves them to your account so they are available on your other devices.</p>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center", marginTop: 6 }}>
            <button className="btn btn-primary" type="button" onClick={() => fileInputRef.current?.click()}>Add music</button>
            <button className="btn" type="button" onClick={() => folderInputRef.current?.click()}>Add folder</button>
          </div>
        </div>
      );
    }
    if (view === "favorites" && !tracks.some((track) => track.favorite)) {
      return (
        <div className="empty">
          <div className="empty-orb" />
          <h3>No favorites yet</h3>
          <p>Use the heart on any song to keep it close. Your favorites sync with your account.</p>
        </div>
      );
    }
    return (
      <div className="empty">
        <div className="empty-orb" />
        <h3>Nothing here yet</h3>
        <p>Your library will show up here when you add music.</p>
      </div>
    );
  };

  const expandedPlayer = expandedPlayerOpen && currentTrack && typeof document !== "undefined"
    ? createPortal(
        <div
          className="mobile-player open"
          role="dialog"
          aria-modal="true"
          aria-label="Now playing"
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.stopPropagation();
              setExpandedPlayerOpen(false);
            }
          }}
        >
          <div
            className="mobile-player-bg"
            style={{ backgroundImage: `url("${currentTrack.coverUrl}")` }}
            aria-hidden="true"
          />
          <header className="mobile-player-head">
            <button
              className="mobile-player-icon"
              type="button"
              aria-label="Close player"
              ref={expandedPlayerCloseRef}
              onClick={() => setExpandedPlayerOpen(false)}
            >
              <Icon name="close" />
            </button>
            <div className="mobile-player-context">
              <span>PLAYING FROM</span>
              <strong>{viewName(playingFromView ?? view, playlists)}</strong>
            </div>
            <button
              className="mobile-player-icon"
              type="button"
              aria-label={`More options for ${currentTrack.title}`}
              aria-haspopup="menu"
              data-track-menu-trigger
              onClick={(event) => toggleTrackMenu(currentTrack, event)}
            >
              <Icon name="more" />
            </button>
          </header>
          <main className="mobile-player-scroll">
            <div className="mobile-player-art">
              <img src={currentTrack.coverUrl || FALLBACK_ART} alt="" />
            </div>
            <section className="mobile-player-info">
              <div className="mobile-player-title-row">
                <div>
                  <h2>{currentTrack.title}</h2>
                  <p>
                    {artistNames(currentTrack).map((name, index) => (
                      <Fragment key={name}>
                        {index > 0 ? <span className="artist-sep">, </span> : null}
                        <button className="artist-link" type="button" onClick={() => openArtist(name)}>
                          {name}
                        </button>
                      </Fragment>
                    ))}
                  </p>
                </div>
                <button
                  className={`mobile-player-fav${currentTrack.favorite ? " on" : ""}`}
                  type="button"
                  aria-label={currentTrack.favorite ? "Remove favorite" : "Favorite"}
                  aria-pressed={currentTrack.favorite}
                  onClick={() => toggleFavoriteFor(currentTrack)}
                >
                  <Icon name="heart" />
                </button>
              </div>
              <PlaybackSeek
                audioElement={audioElement}
                duration={duration}
                onSeek={seekTo}
                onResume={togglePlayback}
                variant="mobile"
              />
              <div className="mobile-transport">
                <button
                  className={`mobile-control${shuffle ? " on" : ""}`}
                  type="button"
                  aria-label="Shuffle"
                  aria-pressed={shuffle}
                  onClick={toggleShuffle}
                ><Icon name="shuffle" /></button>
                <button className="mobile-control" type="button" aria-label="Previous track" onClick={playPrevious}>
                  <Icon name="prev" />
                </button>
                <button className="mobile-play" type="button" aria-label={isPlaying ? "Pause" : "Play"} onClick={togglePlayback}>
                  <Icon name={isPlaying ? "pause" : "play"} />
                </button>
                <button className="mobile-control" type="button" aria-label="Next track" onClick={() => playNext(false)}>
                  <Icon name="next" />
                </button>
                <button
                  className={`mobile-control${repeat !== "off" ? " on" : ""}`}
                  type="button"
                  aria-label={`Repeat: ${repeat}`}
                  aria-pressed={repeat !== "off"}
                  onClick={toggleRepeat}
                ><Icon name="repeat" />{repeat === "one" ? <small>1</small> : null}</button>
              </div>
              <button
                className="mobile-lyrics-preview"
                type="button"
                aria-label="Open full lyrics"
                onClick={() => {
                  setExpandedPlayerOpen(false);
                  setLyricsOpen(true);
                }}
              >
                <span className="mobile-lyrics-heading">
                  <span>Lyrics</span>
                  <span>
                    {previewLines?.length
                      ? "Synced to playback"
                      : previewLyrics?.text
                        ? "Plain lyrics"
                        : "Open full lyrics"}
                  </span>
                </span>
                {previewLines?.length ? (
                  <p aria-live="polite">
                    <span className="lyric-active">
                      {previewLines[previewCurrentLineIndex]?.text}
                    </span>
                    {previewLines[previewNextLineIndex] ? (
                      <span className="lyric-next">
                        {previewLines[previewNextLineIndex].text}
                      </span>
                    ) : null}
                  </p>
                ) : previewLyrics?.text ? (
                  <p>{previewLyrics.text.split(/\r?\n/).filter(Boolean).slice(0, 2).join("\n")}</p>
                ) : (
                  <p>
                    {lyricsLookupFailedTrackId === currentTrack.id
                      ? "Couldn't load lyrics. Tap to retry."
                      : cachedLyrics?.source === "none"
                        ? "No lyrics found for this track."
                        : "Finding lyrics…"}
                  </p>
                )}
              </button>
              <div className="mobile-secondary-actions">
                <button
                  className="mobile-secondary"
                  type="button"
                  onClick={() => {
                    setExpandedPlayerOpen(false);
                    setLyricsOpen(true);
                  }}
                ><span aria-hidden="true">♫</span><span>Lyrics</span></button>
                <button
                  className="mobile-secondary"
                  type="button"
                  aria-pressed={queueOpen}
                  onClick={() => {
                    setExpandedPlayerOpen(false);
                    setQueueOpen(true);
                  }}
                ><Icon name="queue" /><span>Queue</span></button>
              </div>
            </section>
          </main>
        </div>,
        document.body,
      )
    : null;

  return (
    <div id="app">
      <div className="shell" onDragEnter={(event) => {
        if (Array.from(event.dataTransfer.types).includes("Files")) setIsDraggingFiles(true);
      }} onDragOver={(event) => {
        if (Array.from(event.dataTransfer.types).includes("Files")) event.preventDefault();
      }} onDragLeave={(event) => {
        if (event.currentTarget === event.target) setIsDraggingFiles(false);
      }} onDrop={(event) => {
        if (!Array.from(event.dataTransfer.types).includes("Files")) return;
        event.preventDefault();
        setIsDraggingFiles(false);
        void uploadFiles(event.dataTransfer.files);
      }}>
        <nav className="rail" aria-label="Main navigation">
          <div className="logo-mark">
            <div className="logo-squircle"><img className="brand-logo" src="/gemini-svg.svg" alt="" /></div>
            <div className="logo-word">Vervfy</div>
          </div>
          <button className={`rail-btn${view === "library" ? " active" : ""}`} type="button" data-view="library" data-tip="Library" aria-label="Library" aria-current={view === "library" ? "page" : undefined} onClick={() => setView("library")}><Icon name="library" /></button>
          <button className={`rail-btn${view === "offline" ? " active" : ""}`} type="button" data-view="offline" data-tip="Offline" aria-label="Offline" aria-current={view === "offline" ? "page" : undefined} onClick={() => setView("offline")}><Icon name="offline" /></button>
          <button className={`rail-btn${view === "playlists" || view.startsWith("playlist:") ? " active" : ""}`} type="button" data-view="playlists" data-tip="Playlists" aria-label="Playlists" aria-current={view === "playlists" || view.startsWith("playlist:") ? "page" : undefined} onClick={() => setView("playlists")}><Icon name="playlists" /></button>
          <button className={`rail-btn${view === "artists" || view.startsWith("artist:") ? " active" : ""}`} type="button" data-view="artists" data-tip="Artists" aria-label="Artists" aria-current={view === "artists" || view.startsWith("artist:") ? "page" : undefined} onClick={() => setView("artists")}><Icon name="artist" /></button>
          <button className={`rail-btn${view === "favorites" ? " active" : ""}`} type="button" data-view="favorites" data-tip="Favorites" aria-label="Favorites" aria-current={view === "favorites" ? "page" : undefined} onClick={() => setView("favorites")}><Icon name="heart" /></button>
          <button className={`rail-btn${view === "account" ? " active" : ""}`} type="button" data-view="account" data-tip="Account" aria-label="Account" aria-current={view === "account" ? "page" : undefined} onClick={() => setView("account")}><Icon name="account" /></button>
          <div className="rail-spacer" />
          <div className="rail-logout"><LogoutButton className="rail-btn rail-logout-button" ariaLabel="Log out"><Icon name="logout" /></LogoutButton></div>
          <button className="rail-btn rail-shortcuts-button" type="button" data-tip="Shortcuts (?)" aria-label="Shortcuts" onClick={() => setShortcutsOpen(true)}><Icon name="help" /></button>
          <button className="rail-btn rail-import-button" type="button" data-tip="Add music" aria-label="Add music" onClick={() => fileInputRef.current?.click()}><Icon name="import" /></button>
        </nav>

        <div className="main">
          <div className="topbar">
            <button className="home-profile-avatar" type="button" title="Account" aria-label="Open account" onClick={() => setView("account")}>
              {profile?.photo_url
                ? <img src={profile.photo_url} alt="" onError={() => setProfile((current) => current ? { ...current, photo_url: null } : null)} />
                : profile?.username.slice(0, 1).toUpperCase() ?? <Icon name="account" />}
            </button>
            <div className="topbar-id">
              <span className="view-title">{title}</span>
              <span className="view-count">{tracks.length || view === "playlists" || view === "offline" || playlistForView ? `· ${count}` : ""}</span>
            </div>
            {view !== "account" ? (
              <div className="view-toggle" role="group" aria-label="View mode">
                <button type="button" className={listMode === "grid" ? "active" : ""} aria-pressed={listMode === "grid"} title="Grid view" aria-label="Grid view" onClick={() => setListMode("grid")}><Icon name="grid" /></button>
                <button type="button" className={listMode === "list" ? "active" : ""} aria-pressed={listMode === "list"} title="List view" aria-label="List view" onClick={() => setListMode("list")}><Icon name="list" /></button>
              </div>
            ) : null}
            {view !== "account" ? <label className="search-wrap">
              <Icon name="search" />
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search" autoComplete="off" aria-label={view === "playlists" ? "Search playlists" : "Search library"} />
              <span className="kbd">/</span>
            </label> : null}
            {view === "playlists" ? (
              <button className="btn btn-primary" type="button" onClick={() => { setPlaylistName(""); setPlaylistModal({}); }}>
                <Icon name="plus" /> New playlist
              </button>
            ) : view === "account" || view === "artists" || view.startsWith("artist:") || playlistForView ? null : (
              <button className="btn btn-primary" type="button" onClick={() => fileInputRef.current?.click()}>
                <Icon name="import" /> Add music
              </button>
            )}
          </div>

          <div className="content">
            {loading ? (
              <div className="library-skeleton" aria-label="Loading library" aria-busy="true">
                {[0, 1, 2].map((item) => <div className="skeleton-row" key={item}><span className="skeleton-art" /><span className="skeleton-copy"><i /><i /></span><span className="skeleton-time" /></div>)}
              </div>
            ) : loadError ? (
              <div className="empty"><div className="empty-orb" /><h3>Music server unavailable</h3><p>{loadError}</p><button className="btn btn-primary" type="button" onClick={() => window.location.reload()}>Retry connection</button></div>
            ) : (
              <>
                <div hidden={view !== "account"}>
                  <AccountSettings
                    active={view === "account"}
                    onToast={notify}
                    onPhotoChange={updateProfilePhoto}
                  />
                </div>
                <div hidden={view !== "artists" && !view.startsWith("artist:")}>
                  <ArtistExplorer
                    view={view}
                    search={search}
                    listMode={listMode}
                    renderTrack={renderTrack}
                    onPlay={(list, trackId) => {
                      const selectedTrack = trackId ?? list[0]?.id;
                      if (selectedTrack) playFromList(list, selectedTrack);
                    }}
                  />
                </div>
                {view === "account" || view === "artists" || view.startsWith("artist:") ? null : view === "playlists" ? (
              filteredPlaylists.length ? (
                <div className={`pl-grid${listMode === "list" ? " list-mode" : ""}`}>
                  {filteredPlaylists.map((playlist) => {
                    const coverTracks = playlistCoverTracks(playlist);
                    return (
                      <button
                        className="pl-card"
                        type="button"
                        key={playlist.id}
                        aria-label={`Open playlist ${playlist.name}`}
                        onClick={() => setView(`playlist:${playlist.id}`)}
                      >
                        <span className={`playlist-cover${coverTracks.length === 1 ? " single" : ""}${coverTracks.length ? "" : " is-empty"}`} aria-hidden="true">
                          {coverTracks.length
                            ? coverTracks.map((track) => <TrackImage key={track.id} track={track} />)
                            : <Icon name="playlists" />}
                          <span className="playlist-cover-play"><Icon name="play" /></span>
                        </span>
                        <span className="pl-card-info">
                          <span className="pl-name">{playlist.name}</span>
                          <span className="pl-count">{playlist.trackIds.length} {playlist.trackIds.length === 1 ? "song" : "songs"}</span>
                        </span>
                        <span className="pl-card-arrow" aria-hidden="true"><Icon name="next" /></span>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="empty playlist-list-empty">
                  <div className="empty-orb"><Icon name={search.trim() ? "search" : "playlists"} /></div>
                  <h3>{search.trim() ? "No playlists found" : "Your playlists start here"}</h3>
                  <p>{search.trim() ? "Try a different name or clear your search." : "Collect songs into playlists for every mood and moment."}</p>
                  {search.trim()
                    ? <button className="btn" type="button" onClick={() => setSearch("")}>Clear search</button>
                    : <button className="btn btn-primary" type="button" onClick={() => { setPlaylistName(""); setPlaylistModal({}); }}><Icon name="plus" /> Create playlist</button>}
                </div>
              )
            ) : (
              <>
                {playlistForView ? (
                  <div className="playlist-detail">
                    <button className="playlist-back" type="button" onClick={() => setView("playlists")}><Icon name="prev" /> All playlists</button>
                    <section className="playlist-hero">
                      <div className={`playlist-hero-cover${playlistViewCovers.length === 1 ? " single" : ""}${playlistViewCovers.length ? "" : " is-empty"}`} aria-hidden="true">
                        {playlistViewCovers.length
                          ? playlistViewCovers.map((track) => <TrackImage key={track.id} track={track} />)
                          : <Icon name="playlists" />}
                      </div>
                      <div className="playlist-hero-copy">
                        <span className="playlist-eyebrow">PLAYLIST</span>
                        <h1>{playlistForView.name}</h1>
                        <p>{playlistForView.trackIds.length} {playlistForView.trackIds.length === 1 ? "song" : "songs"} in this collection</p>
                        <div className="playlist-actions">
                          <button className="btn btn-primary" type="button" disabled={!visibleTracks.length} onClick={() => {
                            const firstTrack = visibleTracks[0];
                            if (firstTrack) playFromList(visibleTracks, firstTrack.id);
                          }}><Icon name="play" /> Play</button>
                          <button className="btn" type="button" onClick={() => setPlaylistAddTarget(playlistForView.id)}><Icon name="plus" /> Add songs</button>
                          <button className="btn" type="button" onClick={() => { setPlaylistName(playlistForView.name); setPlaylistModal({ playlist: playlistForView }); }}>Rename</button>
                          <button className="btn btn-danger" type="button" onClick={() => {
                            if (!window.confirm(`Delete “${playlistForView.name}”?`)) return;
                            setPlaylists(playlists.filter((item) => item.id !== playlistForView.id));
                            setView("playlists");
                            void saveMeta();
                          }}>Delete</button>
                        </div>
                      </div>
                    </section>
                  </div>
                ) : null}
                {visibleTracks.length ? (
                  <>
                    {playlistForView ? (
                      <div className="playlist-track-heading">
                        <h2>Songs</h2>
                        <span>{visibleTracks.length} {visibleTracks.length === 1 ? "song" : "songs"}</span>
                      </div>
                    ) : null}
                    {listMode === "grid" ? (
                      <div className="grid">{visibleTracks.map(renderTrack)}</div>
                    ) : (
                      <div className="list">
                        <div className="list-head"><div /><div>Title</div><div>Album</div><div>Time</div><div /></div>
                        {visibleTracks.map(renderTrack)}
                      </div>
                    )}
                  </>
                ) : renderEmptyState()}
              </>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      <div id="nowbar" className={`nowbar${currentTrack ? "" : " hidden"}${lyricsOpen ? " lyrics-open" : ""}`} role="region" aria-label="Now playing" aria-hidden={!currentTrack || lyricsOpen} inert={!currentTrack || lyricsOpen}
        onClick={(event) => {
          if (event.target instanceof Element && event.target.closest("button, .seek")) return;
          if (window.matchMedia("(max-width: 900px)").matches) {
            setExpandedPlayerOpen(true);
          }
        }}
      >
        <div className="now-track">
          <span className="now-art-wrap"><span className="now-art"><img id="nowArt" src={currentTrack?.coverUrl ?? FALLBACK_ART} data-artwork={currentTrack?.coverUrl ?? ""} alt="" /></span></span>
          <span className="now-meta">
            <button
              className="now-track-open"
              type="button"
              aria-label={currentTrack ? `Open player for ${currentTrack.title}` : "Open player"}
              onClick={(event) => {
                if (window.matchMedia("(max-width: 900px)").matches) {
                  openExpandedPlayer(event.currentTarget);
                }
              }}
            >
              <span className="now-title">{currentTrack?.title ?? "—"}</span>
            </button>
            <span className="now-artist">
              {currentTrack
                ? artistNames(currentTrack).map((name, index) => (
                    <Fragment key={name}>
                      {index > 0 ? <span className="artist-sep">, </span> : null}
                      <button className="artist-link" type="button" onClick={() => openArtist(name)}>
                        {name}
                      </button>
                    </Fragment>
                  ))
                : "—"}
            </span>
          </span>
          {currentTrack ? <button className={`now-fav${currentTrack.favorite ? " on" : ""}`} type="button" aria-label={currentTrack.favorite ? "Remove favorite" : "Favorite"} aria-pressed={currentTrack.favorite} onClick={() => toggleFavoriteFor(currentTrack)}><Icon name="heart" /></button> : null}
        </div>
        <div className="transport">
          <div className="transport-btns">
            <button className={`tbtn${shuffle ? " on" : ""}`} type="button" title="Shuffle" aria-label="Shuffle" aria-pressed={shuffle} onClick={toggleShuffle}><Icon name="shuffle" /></button>
            <button className="tbtn" type="button" title="Previous" onClick={playPrevious}><Icon name="prev" /></button>
            <button className="tbtn tbtn-play" type="button" title="Play/Pause" onClick={togglePlayback}><Icon name={isPlaying ? "pause" : "play"} /></button>
            <button className="tbtn" type="button" title="Next" onClick={() => playNext(false)}><Icon name="next" /></button>
            <button className={`tbtn${repeat !== "off" ? " on" : ""}`} type="button" title={`Repeat: ${repeat}`} aria-label={`Repeat: ${repeat}`} aria-pressed={repeat !== "off"} onClick={toggleRepeat}><Icon name="repeat" />{repeat === "one" ? <small>1</small> : null}</button>
          </div>
          <PlaybackSeek
            audioElement={audioElement}
            duration={duration}
            onSeek={seekTo}
            onResume={togglePlayback}
            variant="player"
          />
        </div>
        <div className="now-extra">
          <button className={`icon-btn player-control-lyrics${lyricsOpen ? " on" : ""}`} type="button" title="Lyrics (L)" aria-label="Lyrics" aria-pressed={lyricsOpen} onClick={() => setLyricsOpen(true)}><Icon name="lyrics" /></button>
          <button className={`icon-btn player-control-visualizer${visualizerOpen ? " on" : ""}`} type="button" title="Visualizer (V)" aria-label="Visualizer" aria-pressed={visualizerOpen} onClick={() => setVisualizerOpen(true)}><Icon name="visualizer" /></button>
          <button className={`icon-btn player-control-queue${queueOpen ? " on" : ""}`} type="button" title="Queue" aria-label="Queue" aria-pressed={queueOpen} onClick={() => setQueueOpen(!queueOpen)}><Icon name="queue" /></button>
          <button className={`icon-btn player-control-mini${miniMode ? " on" : ""}`} type="button" title="Mini player" aria-label="Mini player" aria-pressed={miniMode} onClick={() => setMiniMode(!miniMode)}><Icon name="mini" /></button>
          <button className={`icon-btn player-control-mute${muted ? " on" : ""}`} type="button" title={muted ? "Unmute" : "Mute"} aria-label={muted ? "Unmute" : "Mute"} aria-pressed={muted} onClick={() => {
          const audio = usePlayerStore.getState().audioElement;
          if (!audio) return;
          const nextMuted = !muted;
          setMuted(nextMuted);
          audio.muted = nextMuted;
          }}><Icon name={muted || volume === 0 ? "volume-muted" : "volume"} /></button>
          <div className="vol-wrap"><div className="vol-track" role="slider" tabIndex={0} aria-label="Volume" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round((muted ? 0 : volume) * 100)} aria-valuetext={`${Math.round((muted ? 0 : volume) * 100)}%`} onClick={updateVolume} onKeyDown={(event) => {
            if (event.key !== "ArrowRight" && event.key !== "ArrowUp" && event.key !== "ArrowLeft" && event.key !== "ArrowDown") return;
            event.preventDefault();
            const direction = event.key === "ArrowRight" || event.key === "ArrowUp" ? 1 : -1;
            setVolume((current) => Math.max(0, Math.min(1, current + direction * 0.05)));
            setMuted(false);
          }}><div className="vol-fill" style={{ width: `${(muted ? 0 : volume) * 100}%` }} /></div></div>
        </div>
      </div>

      {expandedPlayer}
      {lyricsOpen && currentTrack ? (
        <LyricsOverlay
          key={currentTrack.id}
          track={currentTrack}
          currentTime={currentTime}
          onClose={() => setLyricsOpen(false)}
          onOpenArtist={openArtist}
          onToast={notify}
          onPrevious={playPrevious}
          onNext={() => playNext(false)}
          onTogglePlayback={togglePlayback}
          onToggleShuffle={toggleShuffle}
          onToggleRepeat={toggleRepeat}
          shuffle={shuffle}
          repeat={repeat}
        />
      ) : null}
      {visualizerOpen ? <VisualizerOverlay onClose={() => setVisualizerOpen(false)} /> : null}
      {shortcutsOpen ? <div className="queue-picker-overlay open" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" onClick={() => setShortcutsOpen(false)}>
        <section className="queue-picker-card shortcuts-dialog" onClick={(event) => event.stopPropagation()}>
          <div className="queue-picker-head"><h3>Keyboard shortcuts</h3><button className="icon-btn" type="button" aria-label="Close shortcuts" onClick={() => setShortcutsOpen(false)}><Icon name="close" /></button></div>
          <div className="queue-picker-list"><p><kbd>Space</kbd><span>Play / pause</span></p><p><kbd>Shift + ← / →</kbd><span>Previous / next track</span></p><p><kbd>← / →</kbd><span>Seek 5 seconds</span></p><p><kbd>↑ / ↓</kbd><span>Volume</span></p><p><kbd>M</kbd><span>Mute</span></p><p><kbd>F</kbd><span>Favorite current track</span></p><p><kbd>N</kbd><span>Mini player</span></p><p><kbd>L</kbd><span>Lyrics</span></p><p><kbd>V</kbd><span>Visualizer</span></p><p><kbd>/</kbd><span>Search</span></p><p><kbd>?</kbd><span>Shortcuts</span></p><p><kbd>Esc</kbd><span>Close panels</span></p></div>
        </section>
      </div> : null}

      <div className={`mini-player${miniMode ? " open" : ""}`}>
        <div className="mini-drag" />
        <button className="mini-exit" type="button" aria-label="Close mini player" onClick={() => setMiniMode(false)}><Icon name="close" /></button>
        <div className="mini-body">
          <div className="mini-art-wrap"><div className="mini-art"><img src={currentTrack?.coverUrl ?? FALLBACK_ART} alt="" /></div></div>
          <div className="mini-meta"><div className="mini-title">{currentTrack?.title ?? "Nothing playing"}</div><div className="mini-artist">{currentTrack?.artist ?? "Pick a track"}</div></div>
          <PlaybackSeek
            audioElement={audioElement}
            duration={duration}
            onSeek={seekTo}
            onResume={togglePlayback}
            variant="player"
            className="mini-seek"
          />
          <div className="mini-btns"><button className="tbtn" type="button" aria-label="Previous track" onClick={playPrevious}><Icon name="prev" /></button><button className="tbtn tbtn-play" type="button" aria-label="Play or pause" onClick={togglePlayback}><Icon name={isPlaying ? "pause" : "play"} /></button><button className="tbtn" type="button" aria-label="Next track" onClick={() => playNext(false)}><Icon name="next" /></button></div>
        </div>
      </div>

      <aside ref={queuePanelRef} className={`side-panel${queueOpen ? " open" : ""}`} aria-label="Up next">
        <div className="side-head"><h3>Up next</h3><div className="side-head-actions"><button className="icon-btn" type="button" title="Add from library" onClick={() => setQueuePickerOpen(true)}><Icon name="plus" /></button><button className="icon-btn" type="button" title="Close queue" onClick={() => setQueueOpen(false)}><Icon name="close" /></button></div></div>
        <div className="side-body">
          {queue.length === 0 ? <div className="side-empty"><p>Your queue is empty.</p><button className="btn" type="button" onClick={() => setQueuePickerOpen(true)}>Add from library</button></div> : queue.map((trackId, index) => {
            const track = tracks.find((item) => item.id === trackId);
            if (!track) return null;
            return <div
              className={`q-row${index === queueIndex ? " playing" : ""}${queueDragIndex === index ? " dragging" : ""}${queueDragOverIndex === index ? " drag-over" : ""}`}
              key={`${trackId}-${index}`}
              data-queue-index={index}
            ><button
              className="q-drag"
              type="button"
              title={`Drag to reorder ${track.title}`}
              aria-label={`Drag to reorder ${track.title}`}
              onPointerDown={(event) => {
                if (!event.isPrimary || event.button !== 0) return;
                event.preventDefault();
                queuePointerDragRef.current = { pointerId: event.pointerId, fromIndex: index };
                event.currentTarget.setPointerCapture(event.pointerId);
                setQueueDragIndex(index);
              }}
              onPointerMove={(event) => {
                const drag = queuePointerDragRef.current;
                if (!drag || drag.pointerId !== event.pointerId) return;
                const row = document.elementFromPoint(event.clientX, event.clientY)
                  ?.closest<HTMLElement>(".q-row[data-queue-index]");
                const overIndex = row ? Number(row.dataset.queueIndex) : null;
                setQueueDragOverIndex(overIndex !== null && Number.isInteger(overIndex) ? overIndex : null);
              }}
              onPointerUp={(event) => {
                const drag = queuePointerDragRef.current;
                if (!drag || drag.pointerId !== event.pointerId) return;
                const row = document.elementFromPoint(event.clientX, event.clientY)
                  ?.closest<HTMLElement>(".q-row[data-queue-index]");
                const targetIndex = row ? Number(row.dataset.queueIndex) : null;
                queuePointerDragRef.current = null;
                setQueueDragIndex(null);
                setQueueDragOverIndex(null);
                if (targetIndex !== null && Number.isInteger(targetIndex)) {
                  reorderQueue(drag.fromIndex, targetIndex);
                }
              }}
              onPointerCancel={(event) => {
                if (queuePointerDragRef.current?.pointerId !== event.pointerId) return;
                queuePointerDragRef.current = null;
                setQueueDragIndex(null);
                setQueueDragOverIndex(null);
              }}
            ><Icon name="drag" /></button><TrackImage track={track} /><button className="q-meta" type="button" onClick={() => playQueueIndex(index)}><span className="q-title">{track.title}</span><span className="q-artist">{track.artist}</span></button><button className="icon-btn q-remove" type="button" title="Remove from queue" aria-label={`Remove ${track.title} from queue`} onClick={() => removeFromQueue(index)}><Icon name="close" /></button></div>;
          })}
        </div>
      </aside>

      <div className={`queue-picker-overlay${queuePickerOpen ? " open" : ""}`} role="dialog" aria-modal="true" aria-label="Add from library">
        <div className="queue-picker-card">
          <div className="queue-picker-head"><h3>Add from library</h3><button className="icon-btn" type="button" title="Close" onClick={() => setQueuePickerOpen(false)}><Icon name="close" /></button></div>
          <label className="queue-picker-search"><Icon name="search" /><input value={queueSearch} onChange={(event) => setQueueSearch(event.target.value)} placeholder="Search library" aria-label="Search library" /></label>
          <div className="queue-picker-list">{filteredQueueTracks.length ? filteredQueueTracks.map((track) => <button className="qp-row" type="button" key={track.id} onClick={(event) => {
            event.stopPropagation();
            addToQueue(track);
            setQueuePickerOpen(true);
          }}><TrackImage track={track} /><span className="qp-meta"><span className="qp-title">{track.title}</span><span className="qp-artist">{track.artist}</span></span><span className="qp-add"><Icon name="plus" /></span></button>) : <div className="queue-picker-empty">{tracks.length ? "No tracks match your search." : "Your library is empty."}</div>}</div>
        </div>
      </div>

      <div className={`queue-picker-overlay playlist-name-overlay${playlistModal ? " open" : ""}`} role="dialog" aria-modal="true" aria-labelledby="playlistNameTitle">
        <form className="queue-picker-card playlist-name-card" onSubmit={createOrRenamePlaylist}>
          <div className="queue-picker-head"><h3 id="playlistNameTitle">{playlistModal?.playlist ? "Rename playlist" : "New playlist"}</h3><button className="icon-btn" type="button" title="Close" onClick={() => setPlaylistModal(null)}><Icon name="close" /></button></div>
          <label className="playlist-name-label" htmlFor="playlistNameInput">Playlist name</label>
          <input ref={playlistNameInputRef} className="playlist-name-input" id="playlistNameInput" maxLength={200} value={playlistName} onChange={(event) => setPlaylistName(event.target.value)} />
          <div className="playlist-name-actions"><button className="btn" type="button" onClick={() => setPlaylistModal(null)}>Cancel</button><button className="btn btn-primary" type="submit">{playlistModal?.playlist ? "Save" : "Create"}</button></div>
        </form>
      </div>

      <div className={`queue-picker-overlay${playlistPicker ? " open" : ""}`} role="dialog" aria-modal="true" aria-label="Add track to playlist">
        <div className="queue-picker-card">
          <div className="queue-picker-head"><h3>Add to playlist</h3><button className="icon-btn" type="button" title="Close" onClick={() => setPlaylistPicker(null)}><Icon name="close" /></button></div>
          <div className="queue-picker-list">{playlists.length ? playlists.map((playlist) => {
            const trackId = playlistPicker;
            const inPlaylist = trackId ? playlist.trackIds.includes(trackId) : false;
            return <button className={`qp-row${inPlaylist ? " in-playlist" : ""}`} type="button" key={playlist.id} disabled={inPlaylist} onClick={() => {
              if (trackId) addTrackToPlaylist(playlist.id, trackId);
              setPlaylistPicker(null);
              notify(`Added to “${playlist.name}”.`);
            }}><span className="qp-meta"><span className="qp-title">{playlist.name}</span><span className="qp-artist">{playlist.trackIds.length} tracks</span></span><span className="qp-add">{inPlaylist ? "✓" : <Icon name="plus" />}</span></button>;
          }) : <div className="queue-picker-empty">Create a playlist first.</div>}</div>
          <div className="playlist-name-actions"><button className="btn btn-primary" type="button" onClick={() => { setPlaylistPicker(null); setPlaylistName(""); setPlaylistModal({ trackId: playlistPicker ?? undefined }); }}>New playlist</button></div>
        </div>
      </div>

      <div className={`queue-picker-overlay${playlistAddTarget ? " open" : ""}`} role="dialog" aria-modal="true" aria-label="Add tracks to playlist">
        <div className="queue-picker-card">
          <div className="queue-picker-head"><h3>Add from library</h3><button className="icon-btn" type="button" title="Close" onClick={() => setPlaylistAddTarget(null)}><Icon name="close" /></button></div>
          <div className="queue-picker-list">
            {tracksAvailableToAdd.length ? tracksAvailableToAdd.map((track) => <button className="qp-row" type="button" key={track.id} onClick={() => {
              if (playlistAddTarget) addTrackToPlaylist(playlistAddTarget, track.id);
              notify(`Added “${track.title}” to the playlist.`);
            }}><TrackImage track={track} /><span className="qp-meta"><span className="qp-title">{track.title}</span><span className="qp-artist">{track.artist}</span></span><span className="qp-add"><Icon name="plus" /></span></button>) : <div className="queue-picker-empty">{tracks.length ? "Every song in your library is already in this playlist." : "Your library is empty."}</div>}
          </div>
        </div>
      </div>

      <input
        ref={fileInputRef}
        className="hidden-input"
        type="file"
        accept="audio/*,.mp3,.m4a,.mp4,.wav,.flac,.ogg,.oga,.aac,.opus,.weba"
        multiple
        onChange={(event) => {
          if (event.currentTarget.files) void uploadFiles(event.currentTarget.files);
          event.currentTarget.value = "";
        }}
      />
      <input
        ref={folderInputRef}
        className="hidden-input"
        type="file"
        accept="audio/*,.mp3,.m4a,.mp4,.wav,.flac,.ogg,.oga,.aac,.opus,.weba"
        multiple
        {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
        onChange={(event) => {
          if (event.currentTarget.files) void uploadFiles(event.currentTarget.files);
          event.currentTarget.value = "";
        }}
      />
      {isDraggingFiles ? <div className="drop-overlay show" role="status" aria-live="polite" onDragLeave={() => setIsDraggingFiles(false)} onDrop={(event) => {
        event.preventDefault();
        setIsDraggingFiles(false);
        void uploadFiles(event.dataTransfer.files);
      }}><h3>Drop to add music</h3><p>Your files are uploaded to your account.</p></div> : null}
      {uploadStatus ? <div className="toasts" role="status" aria-live="polite" aria-atomic="true"><div className="toast">{uploadStatus}</div></div> : null}
      {toast ? <div className="toasts" role="status" aria-live="polite" aria-atomic="true"><div className="toast">{toast}</div></div> : null}
    </div>
  );
}
