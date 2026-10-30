"use client";

import { Fragment, memo, useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
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
import ResilientImage from "@/components/resilient-image";
import VisualizerOverlay from "@/components/visualizer-overlay";
import { useLanguage } from "@/lib/i18n";
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
  cover_source?: TrackRecord["coverSource"];
  cover_url: string;
  stream_url: string;
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
const AUDIO_FILE_ACCEPT = "audio/*,.mp3,.m4a,.wav,.flac,.ogg,.oga,.aac,.opus,.weba";
const AUDIO_FILE_EXTENSION = /\.(mp3|m4a|wav|flac|ogg|oga|aac|opus|weba)$/i;

const AURA_PALETTE = [
  ["#8b7fff", "#54e8d4"],
  ["#ff8fb1", "#8b7fff"],
  ["#54e8d4", "#3aa0ff"],
  ["#ffb86b", "#ff6b9d"],
  ["#6bd6ff", "#8b7fff"],
  ["#c084fc", "#54e8d4"],
] as const;

function hashCoverSeed(seed: string): number {
  let hash = 0;
  for (let index = 0; index < seed.length; index += 1) {
    hash = (Math.imul(31, hash) + seed.charCodeAt(index)) | 0;
  }
  return Math.abs(hash);
}

interface PlaybackAttempt {
  trackId: string;
  src: string;
  retrySource: string | null;
  retryCount: number;
  retryTimer: number | null;
  stallTimer: number | null;
  restoreMetadataListener: (() => void) | null;
  requestId: number;
  loading: boolean;
  failed: boolean;
  hasPlayed: boolean;
  wantsPlayback: boolean;
  recovering: boolean;
  recoveryPosition: number | null;
  signedUrlRefreshed: boolean;
  listenedSeconds: number;
  lastListenPosition: number | null;
  listenRecorded: boolean;
}

interface ListeningPeriodSummary {
  playCount: number;
  topTracks: Array<{ trackId: string; playCount: number }>;
  topArtists: Array<{ artist: string; playCount: number }>;
}

interface ListeningSummary {
  lastPlayedAt: Record<string, number>;
  month: ListeningPeriodSummary;
  year: ListeningPeriodSummary;
  monthStart: number;
  yearLabel: string;
  asOf: number;
}

const MAX_PLAYBACK_RETRIES = 3;
const PLAYBACK_STALL_TIMEOUT_MS = 5_000;
const PLAYBACK_START_TIMEOUT_MS = 15_000;
const SKIP_DEBOUNCE_MS = 400;

function logAudioFailure(context: string, audio: HTMLAudioElement, error: unknown): void {
  const errorName =
    error instanceof Error
      ? error.name
      : error && typeof error === "object" && "name" in error && typeof error.name === "string"
        ? error.name
        : "UnknownError";
  console.warn(`[audio] ${context}`, {
    name: errorName,
    code: audio.error?.code ?? null,
    networkState: audio.networkState,
    readyState: audio.readyState,
  });
}

function generateAura(seed: string): string {
  const hash = hashCoverSeed(seed);
  const [first, second] = AURA_PALETTE[hash % AURA_PALETTE.length];
  const angle = (hash % 360) * (Math.PI / 180);
  const x = Math.round(50 + Math.cos(angle) * 15);
  const y = Math.round(50 + Math.sin(angle) * 15);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300"><defs><radialGradient id="a" cx="${x}%" cy="${y}%" r="75%"><stop stop-color="${first}"/><stop offset=".5" stop-color="${second}" stop-opacity=".34"/><stop offset="1" stop-color="#0c0e14" stop-opacity="0"/></radialGradient><radialGradient id="b" cx="${100 - x}%" cy="${100 - y}%" r="60%"><stop stop-color="${second}"/><stop offset="1" stop-color="#0c0e14" stop-opacity="0"/></radialGradient></defs><rect width="300" height="300" fill="#12151e"/><rect width="300" height="300" fill="url(#a)" opacity=".9"/><rect width="300" height="300" fill="url(#b)" opacity=".55"/></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

function GeneratedAura({ seed, className = "" }: { seed: string; className?: string }) {
  const hash = hashCoverSeed(seed);
  const id = `aura-${useId().replace(/:/g, "")}`;
  const [first, second] = AURA_PALETTE[hash % AURA_PALETTE.length];
  const angle = (hash % 360) * (Math.PI / 180);
  const x = Math.round(50 + Math.cos(angle) * 15);
  const y = Math.round(50 + Math.sin(angle) * 15);
  return (
    <svg className={`generated-aura ${className}`} viewBox="0 0 300 300" aria-hidden="true">
      <defs>
        <radialGradient id={`${id}-a`} cx={`${x}%`} cy={`${y}%`} r="75%">
          <stop stopColor={first} />
          <stop offset=".5" stopColor={second} stopOpacity=".34" />
          <stop offset="1" stopColor="#0c0e14" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={`${id}-b`} cx={`${100 - x}%`} cy={`${100 - y}%`} r="60%">
          <stop stopColor={second} />
          <stop offset="1" stopColor="#0c0e14" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="300" height="300" fill="#12151e" />
      <rect className="generated-aura-first" width="300" height="300" fill={`url(#${id}-a)`} opacity=".9" />
      <rect className="generated-aura-second" width="300" height="300" fill={`url(#${id}-b)`} opacity=".55" />
    </svg>
  );
}

const FALLBACK_ART = generateAura("Unknown song");

function trackThumbnailUrl(src: string, size: number): string {
  try {
    const url = new URL(src, "https://vervfy.invalid");
    if (!/^\/api\/tracks\/[^/]+\/cover$/.test(url.pathname)) return src;
    url.searchParams.set("size", String(size));
    return src.startsWith("/") ? `${url.pathname}${url.search}` : url.href;
  } catch {
    return src;
  }
}

function coverUrlForTrack(
  track: Pick<ServerTrack, "artist" | "album" | "title" | "cover_url" | "cover_source" | "has_cover">,
): string {
  const source = track.cover_source ?? "unknown";
  const hasGeneratedCover = ["generated", "placeholder", "unknown"].includes(source);
  if (!track.has_cover && hasGeneratedCover) {
    return generateAura(`${track.artist}|${track.album}|${track.title}`);
  }
  return track.cover_url || generateAura(`${track.artist}|${track.album}|${track.title}`);
}

function normalizeMeta(value: LibraryState): LibraryMeta {
  return {
    favorites: [...new Set(value.favorites.filter((id) => typeof id === "string"))].sort(),
    playlists: value.playlists.map((playlist) => ({
      id: playlist.id,
      name: playlist.name,
      trackIds: [...new Set(playlist.trackIds)],
      lastPlayedAt: typeof playlist.lastPlayedAt === "number" ? playlist.lastPlayedAt : null,
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
  thumbnail = false,
}: {
  track: TrackRecord;
  className?: string;
  thumbnail?: boolean;
}) {
  if (
    !track.hasCover &&
    ["generated", "placeholder", "unknown"].includes(track.coverSource ?? "unknown")
  ) {
    return (
      <GeneratedAura
        seed={`${track.artist}|${track.album}|${track.title}`}
        className={className}
      />
    );
  }
  const fallback = generateAura(`${track.artist}|${track.album}|${track.title}`);
  const coverUrl = track.coverUrl || fallback;
  const src = thumbnail ? trackThumbnailUrl(coverUrl, 128) : coverUrl;
  return <ResilientImage key={`${track.id}:${src}`} src={src} fallbackSrc={fallback} className={className} />;
});

function ListeningRecapCard({
  title,
  period,
  summary,
  tracksById,
  onPlay,
  showHeading = true,
}: {
  title: string;
  period: string;
  summary: ListeningPeriodSummary;
  tracksById: Map<string, TrackRecord>;
  onPlay: (track: TrackRecord) => void;
  showHeading?: boolean;
}) {
  const { language, t } = useLanguage();
  const numberFormat = useMemo(() => new Intl.NumberFormat(language), [language]);
  const maxTrackPlayCount = Math.max(
    0,
    ...summary.topTracks.map((item) => item.playCount),
  );
  const topTracks = summary.topTracks.flatMap((item) => {
    const track = tracksById.get(item.trackId);
    return track ? [{ item, track }] : [];
  });
  const artistArtwork = new Map<string, TrackRecord>();
  for (const { track } of topTracks) {
    const key = track.artist.trim().toLocaleLowerCase();
    if (track.hasCover && track.coverUrl && !artistArtwork.has(key)) {
      artistArtwork.set(key, track);
    }
  }
  for (const track of tracksById.values()) {
    const key = track.artist.trim().toLocaleLowerCase();
    if (track.hasCover && track.coverUrl && !artistArtwork.has(key)) {
      artistArtwork.set(key, track);
    }
  }
  return (
    <section className="recap-period">
      {showHeading ? (
        <div className="recap-period-heading">
          <div>
            <span className="recap-period-label">{period}</span>
            <h2>{title}</h2>
          </div>
          <p className="recap-period-total">
            <strong>{numberFormat.format(summary.playCount)}</strong> {t("plays")}
          </p>
        </div>
      ) : (
        <p className="recap-period-total yearly-recap-total">
          <strong>{numberFormat.format(summary.playCount)}</strong> {t("plays")}
        </p>
      )}
      {topTracks.length ? (
        <div className="recap-top-tracks">
          <h3 className="recap-track-label">
            {t("Top {count} tracks").replace(
              "{count}",
              numberFormat.format(topTracks.length),
            )}
          </h3>
          {topTracks.map(({ item, track }, index) => {
            return (
              <button
                className="recap-track"
                key={item.trackId}
                type="button"
                onClick={() => onPlay(track)}
                aria-label={`${t("Play")} ${track.title}, ${numberFormat.format(item.playCount)} ${t("plays")}`}
              >
                <span className="recap-rank">{index + 1}</span>
                <TrackImage track={track} className="recap-art" thumbnail />
                <span className="recap-track-copy">
                  <strong>{track.title}</strong>
                  <small>{track.artist}</small>
                </span>
                <span className="recap-play-count">
                  <span>{numberFormat.format(item.playCount)}×</span>
                  <span className="recap-play-bar" aria-hidden="true">
                    <span
                      style={{
                        width: maxTrackPlayCount
                          ? `${(Math.max(0, item.playCount) / maxTrackPlayCount) * 100}%`
                          : "0%",
                      }}
                    />
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      ) : (
        <p className="recap-empty">{t("No qualifying listens in this period yet.")}</p>
      )}
      {summary.topArtists.length ? (
        <div className="recap-artists">
          <h3>{t("Top artists")}</h3>
          <ul className="recap-artist-list" aria-label={t("Top artists")}>
            {summary.topArtists.slice(0, 3).map((artist, index) => {
              const artwork = artistArtwork.get(
                artist.artist.trim().toLocaleLowerCase(),
              );
              return (
                <li className="recap-artist-row" key={artist.artist}>
                  <span className="recap-artist-rank" aria-hidden="true">
                    {index + 1}
                  </span>
                  <span className="recap-artist-avatar" aria-hidden="true">
                    {artwork ? (
                      <TrackImage
                        track={artwork}
                        className="recap-artist-cover"
                        thumbnail
                      />
                    ) : (
                      <span>{artist.artist.trim().slice(0, 1).toLocaleUpperCase()}</span>
                    )}
                  </span>
                  <span className="recap-artist-copy">
                    <span className="recap-artist-name">{artist.artist}</span>
                    <span className="recap-artist-count">
                      {numberFormat.format(artist.playCount)} {t("plays")}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

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
  const { t } = useLanguage();
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
      aria-label={t("Track progress")}
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
  if (view === "recap") return "Recap";
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

type IconName = "library" | "playlists" | "heart" | "logout" | "search" | "play" | "pause" | "prev" | "next" | "shuffle" | "repeat" | "queue" | "plus" | "close" | "list" | "grid" | "more" | "artist" | "offline" | "account" | "help" | "import" | "volume" | "volume-muted" | "lyrics" | "visualizer" | "info" | "drag" | "timer" | "clock";

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
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/></>,
    drag: <><circle cx="9" cy="5" r="1" fill="currentColor" stroke="none"/><circle cx="15" cy="5" r="1" fill="currentColor" stroke="none"/><circle cx="9" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="15" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="9" cy="19" r="1" fill="currentColor" stroke="none"/><circle cx="15" cy="19" r="1" fill="currentColor" stroke="none"/></>,
    timer: <><circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 1.5M9 2h6M12 5V2"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
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

interface TrackMenuPortalProps {
  track: TrackRecord;
  anchor: HTMLButtonElement;
  view: LibraryView;
  playlists: PlaylistRecord[];
  offlinePendingId: string | null;
  expandedPlayerOpen: boolean;
  onPlayNext: () => void;
  onAddToQueue: () => void;
  onAddToPlaylist: () => void;
  onToggleOffline: () => void;
  onToggleFavorite: () => void;
  onViewArtist: (name: string) => void;
  onOpenSleepTimer: () => void;
  onShare: () => void;
  onRemoveFromPlaylist?: () => void;
  onAddOrChangeCover: () => void;
  onRetryCover: () => void;
  onCoverInfo: () => void;
  onEditDetails: () => void;
  onRemove: () => void;
}

function TrackMenuPortal({
  track,
  anchor,
  view,
  playlists,
  offlinePendingId,
  expandedPlayerOpen,
  onPlayNext,
  onAddToQueue,
  onAddToPlaylist,
  onToggleOffline,
  onToggleFavorite,
  onViewArtist,
  onOpenSleepTimer,
  onShare,
  onRemoveFromPlaylist,
  onAddOrChangeCover,
  onRetryCover,
  onCoverInfo,
  onEditDetails,
  onRemove,
}: TrackMenuPortalProps) {
  const { t } = useLanguage();
  const menuRef = useRef<HTMLDivElement>(null);
  const playlistId = view.startsWith("playlist:") ? view.slice("playlist:".length) : null;
  const playlist = playlists.find((item) => item.id === playlistId);
  const inPlaylist = playlist?.trackIds.includes(track.id) ?? false;
  const hasPlaceholderCover = ["placeholder", "unknown", "generated"].includes(track.coverSource ?? "unknown");

  useLayoutEffect(() => {
    const menu = menuRef.current;
    if (!menu) return;
    const reposition = () => {
      if (!anchor.isConnected) return;
      const anchorRect = anchor.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      const menuWidth = menu.offsetWidth;
      const menuHeight = menu.offsetHeight;
      const below = anchorRect.bottom + 6;
      const above = anchorRect.top - menuHeight - 6;
      const top =
        below + menuHeight <= viewportHeight - 8
          ? below
          : above >= 8
            ? above
            : Math.max(8, Math.min(below, viewportHeight - menuHeight - 8));
      const left = Math.max(
        8,
        Math.min(anchorRect.right - menuWidth, viewportWidth - menuWidth - 8),
      );
      menu.style.top = `${top}px`;
      menu.style.left = `${left}px`;
      menu.style.maxHeight = `${Math.max(120, viewportHeight - 16)}px`;
    };
    reposition();
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
    return () => {
      window.removeEventListener("resize", reposition);
      window.removeEventListener("scroll", reposition, true);
    };
  }, [anchor]);

  return createPortal(
    <div
      ref={menuRef}
      className="menu track-context-menu"
      role="menu"
      aria-label={`${t("Options for")} ${track.title}`}
      style={{ top: 8, left: 8 }}
      onClick={(event) => event.stopPropagation()}
    >
      <button className="menu-item" role="menuitem" type="button" onClick={onPlayNext}>{t("Play next")}</button>
      <button className="menu-item" role="menuitem" type="button" onClick={onAddToQueue}>{t("Add to queue")}</button>
      <button className="menu-item" role="menuitem" type="button" onClick={onAddToPlaylist}>{t("Add to playlist")}</button>
      <button
        className="menu-item"
        role="menuitem"
        type="button"
        disabled={offlinePendingId !== null}
        onClick={onToggleOffline}
      >
        {offlinePendingId === track.id
          ? t("Saving offline…")
          : track.offlineUrl
            ? t("Remove offline download")
            : t("Download for offline")}
      </button>
      <button
        className="menu-item"
        role="menuitemcheckbox"
        type="button"
        aria-checked={track.favorite}
        onClick={onToggleFavorite}
      >
        {track.favorite ? t("Remove from liked songs") : t("Save to liked songs")}
      </button>
      {artistNames(track).map((name) => (
        <button
          className="menu-item"
          role="menuitem"
          type="button"
          key={name}
          onClick={() => onViewArtist(name)}
        >
          View artist: {name}
        </button>
      ))}
      {expandedPlayerOpen ? (
        <button
          className="menu-item"
          role="menuitem"
          type="button"
          aria-haspopup="dialog"
          onClick={onOpenSleepTimer}
        >
          {t("Sleep timer")}
        </button>
      ) : null}
      <button className="menu-item" role="menuitem" type="button" onClick={onShare}>{t("Share song")}</button>
      {inPlaylist && playlist ? (
        <button className="menu-item" role="menuitem" type="button" onClick={onRemoveFromPlaylist}>
          {t("Remove from this playlist")}
        </button>
      ) : null}
      <div className="menu-sep" />
      <button className={`menu-item${hasPlaceholderCover ? " cover-menu-item" : ""}`} role="menuitem" type="button" onClick={onAddOrChangeCover}>
        <span>{t(hasPlaceholderCover ? "Add cover" : "Change cover")}</span>
        {hasPlaceholderCover ? <small>{t("Generated placeholder")}</small> : null}
      </button>
      {track.coverSource !== "upload" && track.coverSource !== "user" ? (
        <button className="menu-item" role="menuitem" type="button" onClick={onRetryCover}>
          {t("Retry cover")}
        </button>
      ) : null}
      {expandedPlayerOpen && track.coverSource === "musicbrainz" ? (
        <button className="menu-item" role="menuitem" type="button" aria-haspopup="dialog" onClick={onCoverInfo}>
          {t("Cover art info")}
        </button>
      ) : null}
      <button className="menu-item" role="menuitem" type="button" onClick={onEditDetails}>
        {t("Edit track details")}
      </button>
      <div className="menu-sep" />
      <button className="menu-item" role="menuitem" type="button" onClick={onRemove}>
        {t("Remove from library")}
      </button>
    </div>,
    document.body,
    `track-menu-${track.id}`,
  );
}

export default function LibraryApp() {
  const { t, language } = useLanguage();
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
  const playbackStatus = usePlayerStore((state) => state.playbackStatus);
  const sleepTimerEndsAt = usePlayerStore((state) => state.sleepTimerEndsAt);
  const sleepTimerEndTrackId = usePlayerStore((state) => state.sleepTimerEndTrackId);
  const setTracks = usePlayerStore((state) => state.setTracks);
  const setLibraryMeta = usePlayerStore((state) => state.setLibraryMeta);
  const setQueue = usePlayerStore((state) => state.setQueue);
  const setQueueIndex = usePlayerStore((state) => state.setQueueIndex);
  const setView = usePlayerStore((state) => state.setView);
  const setListMode = usePlayerStore((state) => state.setListMode);
  const setRepeat = usePlayerStore((state) => state.setRepeat);
  const setShuffle = usePlayerStore((state) => state.setShuffle);
  const setPlaying = usePlayerStore((state) => state.setPlaying);
  const setPlaybackStatus = usePlayerStore((state) => state.setPlaybackStatus);
  const setSleepTimer = usePlayerStore((state) => state.setSleepTimer);
  const lyricsByTrack = usePlayerStore((state) => state.lyricsByTrack);
  const setCachedLyrics = usePlayerStore((state) => state.setCachedLyrics);
  const toggleFavorite = usePlayerStore((state) => state.toggleFavorite);
  const setPlaylists = usePlayerStore((state) => state.setPlaylists);
  const playbackAttemptRef = useRef<PlaybackAttempt | null>(null);
  const runPlaybackAttemptRef = useRef<(attempt: PlaybackAttempt) => void>(() => {});
  const skipStartTimerRef = useRef<number | null>(null);
  const coverInfoButtonRef = useRef<HTMLButtonElement>(null);
  const coverInfoPopoverRef = useRef<HTMLElement>(null);
  const coverInfoReturnFocusRef = useRef<HTMLElement | null>(null);
  const yearlyRecapDialogRef = useRef<HTMLDialogElement>(null);
  const mobilePlayerMenuButtonRef = useRef<HTMLButtonElement>(null);
  const sleepTimerControlRef = useRef<HTMLDivElement>(null);
  const sleepTimerPopoverRef = useRef<HTMLElement>(null);
  const playlistPlaybackRef = useRef<string | null>(null);

  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [profile, setProfile] = useState<Account | null>(null);
  const [listeningSummary, setListeningSummary] = useState<ListeningSummary | null>(null);
  const [listeningError, setListeningError] = useState<string | null>(null);
  const [yearlyRecapOpen, setYearlyRecapOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [queueOpen, setQueueOpen] = useState(false);
  const [lyricsOpen, setLyricsOpen] = useState(false);
  const [coverInfoTrackId, setCoverInfoTrackId] = useState<string | null>(null);
  const [visualizerOpen, setVisualizerOpen] = useState(false);
  const [sleepTimerOpen, setSleepTimerOpen] = useState(false);
  const [sleepTimerRemaining, setSleepTimerRemaining] = useState(0);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [queuePickerOpen, setQueuePickerOpen] = useState(false);
  const [queueSearch, setQueueSearch] = useState("");
  const [playlistAddTarget, setPlaylistAddTarget] = useState<string | null>(null);
  const [playlistAddSearch, setPlaylistAddSearch] = useState("");
  const [trackMenu, setTrackMenu] = useState<{
    trackId: string;
    anchor: HTMLButtonElement;
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
  const [coverEditorTrack, setCoverEditorTrack] = useState<TrackRecord | null>(null);
  const [coverFile, setCoverFile] = useState<File | null>(null);
  const [coverPreview, setCoverPreview] = useState<string | null>(null);
  const [coverPending, setCoverPending] = useState(false);
  const [coverError, setCoverError] = useState("");
  const [applyCoverToAlbum, setApplyCoverToAlbum] = useState(false);
  const [replaceAlbumUserCovers, setReplaceAlbumUserCovers] = useState(false);
  const [metadataEditorTrack, setMetadataEditorTrack] = useState<TrackRecord | null>(null);
  const [metadataDraft, setMetadataDraft] = useState({ title: "", artist: "", album: "" });
  const [metadataPending, setMetadataPending] = useState(false);
  const [metadataError, setMetadataError] = useState("");
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
  const coverFileInputRef = useRef<HTMLInputElement>(null);
  const coverPreviewUrlRef = useRef<string | null>(null);
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
  const trackCoverPollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const trackCoverPollAttemptsRef = useRef(0);
  const refreshTrackCoversRef = useRef<() => Promise<void>>(async () => undefined);

  useEffect(
    () => () => {
      if (skipStartTimerRef.current !== null) {
        window.clearTimeout(skipStartTimerRef.current);
      }
    },
    [],
  );

  const updateProfilePhoto = useCallback((photoUrl: string | null) => {
    setProfile((current) => current ? { ...current, photo_url: photoUrl } : current);
  }, []);

  const loadListeningSummary = useCallback(async () => {
    const response = await expectOk(
      await fetchWithRetry("/api/library/listening", { cache: "no-store" }, 3),
    );
    setListeningSummary((await response.json()) as ListeningSummary);
    setListeningError(null);
  }, []);

  const recordTrackListen = useCallback(
    async (trackId: string) => {
      try {
        const response = await apiFetch(
          "/api/library/listening",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ trackId }),
          },
          { csrf: true, retryCsrfOnForbidden: true },
        );
        await expectOk(response);
        await loadListeningSummary();
      } catch (error) {
        console.error("Could not save listening history.", error);
        setListeningError("Listening history could not be saved. Recaps may be out of date.");
      }
    },
    [loadListeningSummary],
  );

  useEffect(() => {
    if (!profile) return;
    let cancelled = false;
    const load = async () => {
      try {
        const response = await expectOk(
          await fetchWithRetry("/api/library/listening", { cache: "no-store" }, 3),
        );
        const summary = (await response.json()) as ListeningSummary;
        if (!cancelled) {
          setListeningSummary(summary);
          setListeningError(null);
        }
      } catch (error) {
        if (!cancelled) {
          console.error("Could not load listening history.", error);
          setListeningError("Listening history could not be loaded.");
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [profile]);

  useEffect(() => {
    const shell = document.querySelector<HTMLElement>("#app > .shell");
    if (!shell) return;
    shell.inert = expandedPlayerOpen;
    return () => {
      shell.inert = false;
    };
  }, [expandedPlayerOpen]);

  useEffect(() => {
    try {
      const savedMode = window.localStorage.getItem("vervfy:list-mode");
      if (savedMode === "grid" || savedMode === "list") setListMode(savedMode);
    } catch (error) {
      console.warn("Could not read the saved list view preference.", error);
    }
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
  const coverInfoOpen =
    coverInfoTrackId === currentTrack?.id && currentTrack?.coverSource === "musicbrainz";
  useEffect(() => {
    if (coverInfoOpen) coverInfoPopoverRef.current?.focus();
  }, [coverInfoOpen]);
  useEffect(() => {
    if (!coverInfoOpen) return;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (
        target instanceof Node &&
        !coverInfoPopoverRef.current?.contains(target) &&
        !coverInfoButtonRef.current?.contains(target)
      ) {
        setCoverInfoTrackId(null);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [coverInfoOpen]);
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
    if (
      !expandedPlayerOpen ||
      !currentTrack ||
      (cachedLyrics && cachedLyrics.source !== "online-plain") ||
      currentTrack.customLyrics
    ) return;

    let cancelled = false;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);
    void lookupLyrics(currentTrack, controller.signal, {
      forceRefresh: cachedLyrics?.source === "online-plain",
    })
      .then((lyrics) => {
        if (
          !cancelled &&
          lyrics.source !== "none" &&
          !(lyrics.source === "online-plain" && cachedLyrics?.source === "online-plain")
        ) {
          setCachedLyrics(currentTrack.id, lyrics);
        }
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
  const rediscoveryTracks = useMemo(() => {
    if (!listeningSummary) return [];
    const cutoff = listeningSummary.asOf - 30 * 24 * 60 * 60;
    return tracks
      .filter((track) => {
        const lastPlayedAt = listeningSummary.lastPlayedAt[track.id];
        return lastPlayedAt !== undefined && lastPlayedAt < cutoff;
      })
      .sort((first, second) => {
        const firstPlayedAt = listeningSummary.lastPlayedAt[first.id] ?? 0;
        const secondPlayedAt = listeningSummary.lastPlayedAt[second.id] ?? 0;
        return firstPlayedAt - secondPlayedAt;
      });
  }, [listeningSummary, tracks]);
  const hasRediscoveryPlaylist = playlists.some((playlist) => playlist.name === "Rediscover");
  const recapMonthLabel = listeningSummary
    ? new Intl.DateTimeFormat(language, { month: "long", year: "numeric" }).format(
        new Date(listeningSummary.monthStart * 1000),
      )
    : "";
  const recapTrackDateFormatter = useMemo(
    () => new Intl.DateTimeFormat(language, { month: "short", day: "numeric", year: "numeric" }),
    [language],
  );
  const recapNumberFormatter = useMemo(
    () => new Intl.NumberFormat(language),
    [language],
  );
  const canOpenYearlyRecap = listeningSummary
    ? new Date(listeningSummary.asOf * 1000).getUTCMonth() === 11
    : false;
  useEffect(() => {
    if (yearlyRecapOpen && yearlyRecapDialogRef.current && !yearlyRecapDialogRef.current.open) {
      yearlyRecapDialogRef.current.showModal();
    }
  }, [yearlyRecapOpen]);
  const trackMenuTrack = trackMenu ? tracksById.get(trackMenu.trackId) ?? null : null;
  const title = t(viewName(view, playlists));
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
  const playlistRecommendations = useMemo(() => {
    const cutoff = (listeningSummary?.asOf ?? 0) - 30 * 24 * 60 * 60;
    return playlists
      .map((playlist) => ({
        playlist,
        tracks: playlist.trackIds
          .map((trackId) => tracksById.get(trackId))
          .filter((track): track is TrackRecord => Boolean(track)),
      }))
      .filter(({ playlist, tracks }) =>
        tracks.length > 0 &&
        (playlist.lastPlayedAt == null || playlist.lastPlayedAt < cutoff),
      )
      .sort((first, second) =>
        (first.playlist.lastPlayedAt ?? 0) - (second.playlist.lastPlayedAt ?? 0),
      )
      .slice(0, 3);
  }, [listeningSummary?.asOf, playlists, tracksById]);

  const notify = useCallback((message: string) => {
    setToast(message);
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    toastTimeoutRef.current = setTimeout(() => setToast(""), 2600);
  }, []);

  const recordPlaylistListen = useCallback(
    async (playlistId: string) => {
      try {
        const response = await expectOk(
          await apiFetch(
            `/api/library/playlists/${encodeURIComponent(playlistId)}/listening`,
            { method: "POST" },
            { csrf: true, retryCsrfOnForbidden: true },
          ),
        );
        const result = (await response.json()) as {
          playlistId?: unknown;
          lastPlayedAt?: unknown;
        };
        const lastPlayedAt = result.lastPlayedAt;
        if (
          result.playlistId !== playlistId ||
          typeof lastPlayedAt !== "number" ||
          !Number.isFinite(lastPlayedAt)
        ) {
          throw new Error("The server returned invalid playlist listening data.");
        }
        setPlaylists(
          usePlayerStore.getState().playlists.map((playlist) =>
            playlist.id === playlistId
              ? { ...playlist, lastPlayedAt }
              : playlist,
          ),
        );
      } catch (error) {
        console.error("Could not save playlist listening history.", error);
        notify("Playlist listening history could not be saved.");
      }
    },
    [notify, setPlaylists],
  );

  const reloadTracks = useCallback(async () => {
    trackCoverPollAttemptsRef.current = 0;
    if (trackCoverPollRef.current) clearTimeout(trackCoverPollRef.current);
    const response = await expectOk(
      await fetchWithRetry("/api/tracks", { cache: "no-store" }, 3),
    );
    const payload = (await response.json()) as { tracks: ServerTrack[] };
    const previousTracks = usePlayerStore.getState().tracks;
    const previousById = new Map(previousTracks.map((track) => [track.id, track]));
    const nextTracks = payload.tracks.map((track): TrackRecord => {
      const previous = previousById.get(track.id);
      const keepCachedImage =
        previous?.coverSource === "audiodb" &&
        !track.has_cover &&
        (track.cover_source === "placeholder" || track.cover_source === "generated");
      const fallback = coverUrlForTrack(track);
      return {
        id: track.id,
        title: track.title || "Unknown title",
        artist: track.artist || "Unknown artist",
        album: track.album || "Unknown album",
        duration: track.duration || 0,
        hasCover: track.has_cover,
        coverUrl: keepCachedImage ? previous.coverUrl : fallback,
        remoteCoverUrl: keepCachedImage ? previous.remoteCoverUrl : fallback,
        streamUrl: track.stream_url,
        coverSource: keepCachedImage ? "audiodb" : track.cover_source ?? "unknown",
        offlineUrl: previous?.offlineUrl ?? null,
        offline: previous?.offline ?? false,
        favorite: previous?.favorite ?? false,
        customLyrics: track.custom_lyrics ?? previous?.customLyrics ?? null,
      };
    });
    setTracks(nextTracks);
    void refreshTrackCoversRef.current();
  }, [setTracks]);

  const refreshTrackCovers = useCallback(async () => {
    if (trackCoverPollAttemptsRef.current >= 5) return;
    trackCoverPollAttemptsRef.current += 1;
    try {
      const response = await expectOk(
        await fetchWithRetry("/api/tracks/covers", { cache: "no-store" }, 2),
      );
      const payload = (await response.json()) as {
        covers: Record<
          string,
          {
            cover_url: string | null;
            cover_source?: TrackRecord["coverSource"];
            status: string;
          }
        >;
        pending: boolean;
      };
      const cached = payload.covers ?? {};
      setTracks(
        usePlayerStore.getState().tracks.map((track) => {
          const result = cached[track.id];
          if (
            !result?.cover_url ||
            track.offline ||
            track.hasCover ||
            track.coverSource === "embedded" ||
            track.coverSource === "upload" ||
            track.coverSource === "user" ||
            track.coverSource === "musicbrainz" ||
            track.coverSource === "audiodb"
          ) {
            return track;
          }
          const coverUrl = coverUrlForTrack({
            ...track,
            has_cover: track.hasCover ?? false,
            cover_url: result.cover_url,
            cover_source: result.cover_source ?? "generated",
          });
          return {
            ...track,
            coverUrl,
            remoteCoverUrl: coverUrl,
            coverSource: result.cover_source ?? "generated",
          };
        }),
      );
      if (trackCoverPollRef.current) clearTimeout(trackCoverPollRef.current);
      if (payload.pending && trackCoverPollAttemptsRef.current < 5) {
        trackCoverPollRef.current = setTimeout(
          () => void refreshTrackCoversRef.current(),
          12_000,
        );
      }
    } catch (error) {
      console.warn("[covers] Could not refresh TheAudioDB track covers.", error);
      if (trackCoverPollRef.current) clearTimeout(trackCoverPollRef.current);
      if (trackCoverPollAttemptsRef.current < 5) {
        trackCoverPollRef.current = setTimeout(
          () => void refreshTrackCoversRef.current(),
          30_000,
        );
      }
    }
  }, [setTracks]);
  useEffect(() => {
    refreshTrackCoversRef.current = refreshTrackCovers;
  }, [refreshTrackCovers]);

  useEffect(
    () => () => {
      if (trackCoverPollRef.current) clearTimeout(trackCoverPollRef.current);
    },
    [],
  );

  function openCoverEditor(track: TrackRecord) {
    setTrackMenu(null);
    setExpandedPlayerOpen(false);
    setCoverFile(null);
    setCoverError("");
    setApplyCoverToAlbum(false);
    setReplaceAlbumUserCovers(false);
    setCoverEditorTrack(track);
  }

  function closeCoverEditor() {
    if (coverPreviewUrlRef.current) URL.revokeObjectURL(coverPreviewUrlRef.current);
    coverPreviewUrlRef.current = null;
    setCoverPreview(null);
    setCoverFile(null);
    setCoverError("");
    setApplyCoverToAlbum(false);
    setReplaceAlbumUserCovers(false);
    setCoverEditorTrack(null);
  }

  function openMetadataEditor(track: TrackRecord) {
    setTrackMenu(null);
    setExpandedPlayerOpen(false);
    setMetadataDraft({ title: track.title, artist: track.artist, album: track.album });
    setMetadataError("");
    setMetadataEditorTrack(track);
  }

  async function saveCover() {
    if (!coverEditorTrack || !coverFile) {
      setCoverError(t("Choose cover image."));
      return;
    }
    setCoverPending(true);
    setCoverError("");
    try {
      const form = new FormData();
      form.append("file", coverFile);
      form.append("apply_to_album", String(applyCoverToAlbum));
      form.append("replace_user_covers", String(applyCoverToAlbum && replaceAlbumUserCovers));
      await expectOk(
        await apiFetch(
          `/api/tracks/${encodeURIComponent(coverEditorTrack.id)}/cover`,
          { method: "PUT", body: form },
          { csrf: true, retryCsrfOnForbidden: true },
        ),
      );
      await reloadTracks();
      notify(t("Cover updated."));
      closeCoverEditor();
    } catch (error) {
      setCoverError(error instanceof Error ? error.message : t("Could not update cover."));
    } finally {
      setCoverPending(false);
    }
  }

  async function removeCover() {
    if (!coverEditorTrack) return;
    setCoverPending(true);
    setCoverError("");
    try {
      await expectOk(
        await apiFetch(
          `/api/tracks/${encodeURIComponent(coverEditorTrack.id)}/cover`,
          { method: "DELETE" },
          { csrf: true, retryCsrfOnForbidden: true },
        ),
      );
      await reloadTracks();
      notify(t("Cover removed."));
      closeCoverEditor();
    } catch (error) {
      setCoverError(error instanceof Error ? error.message : t("Could not remove cover."));
    } finally {
      setCoverPending(false);
    }
  }

  async function saveTrackDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!metadataEditorTrack) return;
    setMetadataPending(true);
    setMetadataError("");
    try {
      await expectOk(
        await apiFetch(
          `/api/tracks/${encodeURIComponent(metadataEditorTrack.id)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              title: metadataDraft.title.trim(),
              artist: metadataDraft.artist.trim(),
              album: metadataDraft.album.trim(),
            }),
          },
          { csrf: true, retryCsrfOnForbidden: true },
        ),
      );
      await reloadTracks();
      setMetadataEditorTrack(null);
      notify(t("Track details saved."));
    } catch (error) {
      setMetadataError(
        error instanceof Error ? error.message : t("Could not update track details."),
      );
    } finally {
      setMetadataPending(false);
    }
  }

  const uploadFiles = useCallback(
    async (selectedFiles: FileList | File[]) => {
      const files = Array.from(selectedFiles).filter(
        (file) =>
          file.type.startsWith("audio/") ||
          ((!file.type || file.type === "application/octet-stream") &&
            AUDIO_FILE_EXTENSION.test(file.name)),
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

  async function retryCoverLookup(track: TrackRecord) {
    setTrackMenu(null);
    try {
      await expectOk(
        await apiFetch(
          `/api/tracks/${encodeURIComponent(track.id)}/cover/retry`,
          { method: "POST" },
          { csrf: true, retryCsrfOnForbidden: true },
        ),
      );
      notify(t("Cover lookup queued."));
      window.setTimeout(() => {
        void reloadTracks();
      }, 2500);
    } catch (error) {
      notify(error instanceof Error ? error.message : t("Could not retry cover lookup."));
    }
  }

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

  const createRediscoveryPlaylist = useCallback(() => {
    if (rediscoveryTracks.length === 0) return;
    const state = usePlayerStore.getState();
    const existing = state.playlists.find((playlist) => playlist.name === "Rediscover");
    const playlist: PlaylistRecord = existing
      ? { ...existing, trackIds: rediscoveryTracks.map((track) => track.id) }
      : {
          id: crypto.randomUUID().replaceAll("-", ""),
          name: "Rediscover",
          trackIds: rediscoveryTracks.map((track) => track.id),
        };
    setPlaylists(
      existing
        ? state.playlists.map((item) => (item.id === existing.id ? playlist : item))
        : [...state.playlists, playlist],
    );
    void saveMeta();
    notify(existing ? "Updated your Rediscover playlist." : "Created your Rediscover playlist.");
  }, [notify, rediscoveryTracks, saveMeta, setPlaylists]);

  const handlePlaybackFailure = useCallback(
    (
      attempt: PlaybackAttempt,
      audio: HTMLAudioElement,
      error: unknown,
      message: string,
      failureKind: "media" | "stalled" = "media",
    ) => {
      if (
        playbackAttemptRef.current !== attempt ||
        attempt.failed ||
        attempt.retryTimer !== null ||
        !attempt.wantsPlayback
      ) {
        return;
      }
      attempt.loading = false;

      const errorName =
        error && typeof error === "object" && "name" in error && typeof error.name === "string"
          ? error.name
          : "";
      const mediaErrorCode = audio.error?.code;
      const retryableNetworkError =
        failureKind === "stalled" ||
        errorName === "NetworkError" ||
        mediaErrorCode === MediaError.MEDIA_ERR_ABORTED ||
        mediaErrorCode === MediaError.MEDIA_ERR_NETWORK;
      const unsupportedMediaError =
        errorName === "NotSupportedError" ||
        mediaErrorCode === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED;
      const retryable =
        retryableNetworkError ||
        (unsupportedMediaError && !attempt.signedUrlRefreshed);

      if (!retryable || attempt.retryCount >= MAX_PLAYBACK_RETRIES) {
        attempt.failed = true;
        attempt.wantsPlayback = false;
        attempt.recovering = false;
        if (attempt.retryTimer !== null) {
          window.clearTimeout(attempt.retryTimer);
          attempt.retryTimer = null;
        }
        if (attempt.restoreMetadataListener) {
          audio.removeEventListener("loadedmetadata", attempt.restoreMetadataListener);
          attempt.restoreMetadataListener = null;
        }
        if (attempt.stallTimer !== null) {
          window.clearTimeout(attempt.stallTimer);
          attempt.stallTimer = null;
        }
        audio.pause();
        setPlaying(false);
        setPlaybackStatus("failed");
        notify(errorName === "NotAllowedError" ? "Press play to start." : message);
        return;
      }

      if (attempt.restoreMetadataListener) {
        audio.removeEventListener("loadedmetadata", attempt.restoreMetadataListener);
        attempt.restoreMetadataListener = null;
      }
      attempt.recoveryPosition = Number.isFinite(audio.currentTime)
        ? audio.currentTime
        : null;
      attempt.recovering = true;
      const reusableSignedSource =
        [audio.currentSrc, attempt.retrySource].find(
          (source) => source && source !== attempt.src,
        ) ?? null;
      const refreshSignedUrl =
        !attempt.signedUrlRefreshed &&
        (attempt.retryCount > 0 || reusableSignedSource === null);
      if (refreshSignedUrl) attempt.signedUrlRefreshed = true;
      attempt.retrySource = refreshSignedUrl
        ? null
        : reusableSignedSource;
      attempt.retryCount += 1;
      setPlaybackStatus("buffering");
      logAudioFailure("retrying playback", audio, error);

      const delay = Math.min(500 * 2 ** (attempt.retryCount - 1), 4_000);
      attempt.retryTimer = window.setTimeout(() => {
        attempt.retryTimer = null;
        if (
          playbackAttemptRef.current !== attempt ||
          !attempt.wantsPlayback
        ) {
          return;
        }
        audio.pause();
        runPlaybackAttemptRef.current(attempt);
      }, delay);
    },
    [notify, setPlaybackStatus, setPlaying],
  );

  const runPlaybackAttempt = useCallback(
    (attempt: PlaybackAttempt) => {
      const audio = usePlayerStore.getState().audioElement;
      if (!audio || playbackAttemptRef.current !== attempt) return;
      const requestId = ++attempt.requestId;
      const source = attempt.retrySource ?? attempt.src;
      attempt.loading = true;
      const needsLoad =
        audio.src !== source ||
        audio.error !== null ||
        audio.networkState === HTMLMediaElement.NETWORK_NO_SOURCE;
      if (needsLoad) {
        attempt.recovering = true;
        if (audio.src !== source) {
          audio.pause();
          audio.removeAttribute("src");
          audio.load();
        }
        audio.src = source;
        audio.load();
      }
      setPlaying(true);
      setPlaybackStatus("buffering");

      const startPlayback = () => {
        attempt.restoreMetadataListener = null;
        if (
          playbackAttemptRef.current !== attempt ||
          attempt.requestId !== requestId ||
          !attempt.wantsPlayback
        ) {
          return;
        }
        if (attempt.recoveryPosition !== null && attempt.recoveryPosition > 0) {
          const position = attempt.recoveryPosition;
          const duration = audio.duration;
          audio.currentTime =
            Number.isFinite(duration) && duration > 0
              ? Math.min(position, duration)
              : position;
        }
        attempt.recoveryPosition = null;
        void audio.play().then(
          () => {
            if (playbackAttemptRef.current === attempt && attempt.requestId === requestId) {
              attempt.loading = false;
            }
          },
          (error: unknown) => {
            if (
              playbackAttemptRef.current !== attempt ||
              attempt.requestId !== requestId
            ) {
              return;
            }
            attempt.loading = false;
            if (
              error &&
              typeof error === "object" &&
              "name" in error &&
              error.name === "AbortError" &&
              !attempt.wantsPlayback
            ) {
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
      };

      if (
        attempt.recoveryPosition !== null &&
        attempt.recoveryPosition > 0 &&
        audio.readyState < HTMLMediaElement.HAVE_METADATA
      ) {
        const onMetadata = () => {
          if (attempt.restoreMetadataListener === onMetadata) {
            attempt.restoreMetadataListener = null;
          }
          startPlayback();
        };
        attempt.restoreMetadataListener = onMetadata;
        audio.addEventListener("loadedmetadata", onMetadata, { once: true });
        return;
      }
      startPlayback();
    },
    [handlePlaybackFailure, setPlaybackStatus, setPlaying],
  );
  const beginTrack = useCallback(
    (trackId: string) => {
      const track = usePlayerStore.getState().tracks.find((item) => item.id === trackId);
      const audio = usePlayerStore.getState().audioElement;
      if (!track || !audio) return;

      const src = new URL(track.offlineUrl || track.streamUrl, window.location.href).href;
      const currentAttempt = playbackAttemptRef.current;
      if (
        currentAttempt?.src === src &&
        !currentAttempt.failed &&
        currentAttempt.wantsPlayback &&
        (currentAttempt.loading || !audio.paused)
      ) {
        return;
      }

      const previousAttempt = playbackAttemptRef.current;
      if (previousAttempt?.retryTimer !== null && previousAttempt?.retryTimer !== undefined) {
        window.clearTimeout(previousAttempt.retryTimer);
      }
      if (previousAttempt?.stallTimer !== null && previousAttempt?.stallTimer !== undefined) {
        window.clearTimeout(previousAttempt.stallTimer);
      }
      if (previousAttempt?.restoreMetadataListener) {
        audio.removeEventListener(
          "loadedmetadata",
          previousAttempt.restoreMetadataListener,
        );
      }
      const attempt: PlaybackAttempt = {
        trackId,
        src,
        retrySource: null,
        retryCount: 0,
        retryTimer: null,
        stallTimer: null,
        restoreMetadataListener: null,
        requestId: 0,
        loading: false,
        failed: false,
        hasPlayed: false,
        wantsPlayback: true,
        recovering: false,
        recoveryPosition: null,
        signedUrlRefreshed: false,
        listenedSeconds: 0,
        lastListenPosition: null,
        listenRecorded: false,
      };
      playbackAttemptRef.current = attempt;
      runPlaybackAttemptRef.current = runPlaybackAttempt;
      runPlaybackAttempt(attempt);
    },
    [runPlaybackAttempt],
  );
  const startTrack = useCallback(
    (trackId: string, debounceSkip = false) => {
      if (skipStartTimerRef.current !== null) {
        window.clearTimeout(skipStartTimerRef.current);
        skipStartTimerRef.current = null;
      }

      if (debounceSkip) {
        const audio = usePlayerStore.getState().audioElement;
        const previousAttempt = playbackAttemptRef.current;
        if (previousAttempt) {
          previousAttempt.wantsPlayback = false;
          previousAttempt.requestId += 1;
          if (previousAttempt.retryTimer !== null) {
            window.clearTimeout(previousAttempt.retryTimer);
          }
          if (previousAttempt.stallTimer !== null) {
            window.clearTimeout(previousAttempt.stallTimer);
          }
          if (previousAttempt.restoreMetadataListener && audio) {
            audio.removeEventListener(
              "loadedmetadata",
              previousAttempt.restoreMetadataListener,
            );
          }
          playbackAttemptRef.current = null;
        }
        if (audio) {
          audio.pause();
          audio.removeAttribute("src");
          audio.load();
        }
        skipStartTimerRef.current = window.setTimeout(() => {
          skipStartTimerRef.current = null;
          beginTrack(trackId);
        }, SKIP_DEBOUNCE_MS);
        return;
      }

      beginTrack(trackId);
    },
    [beginTrack],
  );

  const handleAudioError = useCallback(
    (audio: HTMLAudioElement) => {
      const error = new Error("Audio element emitted a media error");
      error.name =
        audio.error?.code === MediaError.MEDIA_ERR_NETWORK
          ? "NetworkError"
          : audio.error?.code === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED
            ? "NotSupportedError"
            : "MediaError";
      logAudioFailure("audio error event", audio, error);

      const attempt = playbackAttemptRef.current;
      if (
        !attempt ||
        (audio.src !== attempt.src && audio.src !== attempt.retrySource) ||
        (attempt.recovering &&
          audio.error?.code === MediaError.MEDIA_ERR_ABORTED)
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
    (list: TrackRecord[], trackId: string, playlistId?: string) => {
      const ids = list.map((track) => track.id);
      const index = ids.indexOf(trackId);
      if (index < 0) return;
      const sourcePlaylistId =
        playlistId ?? (view.startsWith("playlist:") ? view.slice("playlist:".length) : null);
      playlistPlaybackRef.current = sourcePlaylistId;
      setPlayingFromView(sourcePlaylistId ? `playlist:${sourcePlaylistId}` : view);
      shufflePlayedRef.current = new Set([index]);
      setQueue(ids, index);
      startTrack(trackId);
    },
    [setQueue, startTrack, view],
  );

  const playQueueIndex = useCallback(
    (index: number, debounceSkip = false) => {
      const state = usePlayerStore.getState();
      const trackId = state.queue[index];
      if (!trackId) return;
      setQueueIndex(index);
      startTrack(trackId, debounceSkip);
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
        nextIndex = 0;
      }
      playQueueIndex(nextIndex, !automatic);
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
    if (!sleepTimerEndsAt) return;
    let completed = false;
    const updateRemaining = () => {
      const remaining = Math.ceil((sleepTimerEndsAt - Date.now()) / 1000);
      if (remaining <= 0) {
        if (completed) return;
        completed = true;
        usePlayerStore.getState().audioElement?.pause();
        setSleepTimer(null, null);
        setPlaying(false);
        setPlaybackStatus("paused");
        setSleepTimerRemaining(0);
        return;
      }
      setSleepTimerRemaining(remaining);
    };
    const interval = window.setInterval(updateRemaining, 1000);
    return () => window.clearInterval(interval);
  }, [setPlaybackStatus, setPlaying, setSleepTimer, sleepTimerEndsAt]);

  useEffect(() => {
    if (!sleepTimerOpen) return;
    const onPointerDown = (event: PointerEvent) => {
      if (
        event.target instanceof Node &&
        !sleepTimerControlRef.current?.contains(event.target) &&
        !sleepTimerPopoverRef.current?.contains(event.target)
      ) {
        setSleepTimerOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSleepTimerOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [sleepTimerOpen]);

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
    playQueueIndex(Math.max(0, state.queueIndex - 1), true);
  }, [playQueueIndex]);

  const togglePlayback = useCallback(() => {
    if (!audioElement) return;
    if (!currentTrack) {
      if (visibleTracks[0]) playFromList(visibleTracks, visibleTracks[0].id);
      return;
    }
    if (isPlaying) {
      const attempt = playbackAttemptRef.current;
      if (attempt) {
        attempt.wantsPlayback = false;
        attempt.recovering = false;
        attempt.requestId += 1;
        if (attempt.retryTimer !== null) {
          window.clearTimeout(attempt.retryTimer);
          attempt.retryTimer = null;
        }
        if (attempt.stallTimer !== null) {
          window.clearTimeout(attempt.stallTimer);
          attempt.stallTimer = null;
        }
      }
      audioElement.pause();
      setPlaying(false);
      setPlaybackStatus("paused");
    } else {
      startTrack(currentTrack.id);
    }
  }, [
    audioElement,
    currentTrack,
    isPlaying,
    playFromList,
    setPlaybackStatus,
    setPlaying,
    startTrack,
    visibleTracks,
  ]);

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
        setCoverInfoTrackId(null);
        if (coverInfoOpen) coverInfoButtonRef.current?.focus();
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
  }, [coverInfoOpen, playPrevious, toggleCurrentFavorite, togglePlayback]);

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
          hasCover: track.has_cover,
          coverUrl: coverUrlForTrack(track),
          remoteCoverUrl: coverUrlForTrack(track),
          streamUrl: track.stream_url,
          coverSource: track.cover_source ?? "unknown",
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
        trackCoverPollAttemptsRef.current = 0;
        if (trackCoverPollRef.current) clearTimeout(trackCoverPollRef.current);
        void refreshTrackCoversRef.current();
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
    let lastPlaybackTime = audioElement.currentTime;
    const clearStallTimer = (attempt: PlaybackAttempt | null) => {
      if (attempt?.stallTimer !== null && attempt?.stallTimer !== undefined) {
        window.clearTimeout(attempt.stallTimer);
        attempt.stallTimer = null;
      }
    };
    const onPlaybackProgress = () => {
      const currentTime = audioElement.currentTime;
      const madeProgress = currentTime > lastPlaybackTime + 0.05;
      lastPlaybackTime = currentTime;
      if (!madeProgress) return;
      const attempt = playbackAttemptRef.current;
      if (attempt?.wantsPlayback && !audioElement.paused) {
        const listenDelta =
          attempt.lastListenPosition === null
            ? 0
            : currentTime - attempt.lastListenPosition;
        if (listenDelta > 0 && listenDelta <= 5) {
          attempt.listenedSeconds += listenDelta;
        }
        attempt.lastListenPosition = currentTime;
        const listenThreshold =
          audioElement.duration > 0
            ? Math.min(30, audioElement.duration / 2)
            : 30;
        if (!attempt.listenRecorded && attempt.listenedSeconds >= listenThreshold) {
          attempt.listenRecorded = true;
          void recordTrackListen(attempt.trackId);
          const playlistId = playlistPlaybackRef.current;
          if (playlistId) {
            playlistPlaybackRef.current = null;
            void recordPlaylistListen(playlistId);
          }
        }
      }
      clearStallTimer(attempt);
      if (
        attempt?.wantsPlayback &&
        !audioElement.paused &&
        audioElement.readyState >= HTMLMediaElement.HAVE_FUTURE_DATA
      ) {
        setPlaybackStatus("playing");
      }
    };
    const onLoadedMetadata = () => {
      lastPlaybackTime = audioElement.currentTime;
      updatePlaybackPosition();
    };
    const onSeeked = () => {
      lastPlaybackTime = audioElement.currentTime;
      const attempt = playbackAttemptRef.current;
      if (attempt) attempt.lastListenPosition = audioElement.currentTime;
      updatePlaybackPosition();
    };
    const onPlaying = () => {
      const attempt = playbackAttemptRef.current;
      if (attempt) {
        attempt.hasPlayed = true;
        attempt.lastListenPosition = audioElement.currentTime;
        attempt.recovering = false;
        attempt.retryCount = 0;
        attempt.signedUrlRefreshed = false;
        attempt.retrySource = audioElement.currentSrc || attempt.retrySource;
      }
      clearStallTimer(attempt);
      setPlaying(true);
      setPlaybackStatus("playing");
      if (navigator.mediaSession) navigator.mediaSession.playbackState = "playing";
    };
    const onBuffering = () => {
      const attempt = playbackAttemptRef.current;
      if (!attempt?.wantsPlayback || audioElement.paused) return;
      setPlaybackStatus("buffering");
      if (attempt.stallTimer !== null) return;

      const stalledAt = audioElement.currentTime;
      attempt.stallTimer = window.setTimeout(() => {
        attempt.stallTimer = null;
        if (
          playbackAttemptRef.current === attempt &&
          attempt.wantsPlayback &&
          !audioElement.paused &&
          !audioElement.ended &&
          audioElement.currentTime <= stalledAt + 0.1
        ) {
          handlePlaybackFailure(
            attempt,
            audioElement,
            new Error("Playback made no progress after a buffer event"),
            "Playback stopped while buffering. Check your connection and try again.",
            "stalled",
          );
        }
      }, attempt.hasPlayed ? PLAYBACK_STALL_TIMEOUT_MS : PLAYBACK_START_TIMEOUT_MS);
    };
    const onPlay = () => {
      setPlaying(true);
      setPlaybackStatus("buffering");
      if (navigator.mediaSession) navigator.mediaSession.playbackState = "playing";
    };
    const onPause = () => {
      const attempt = playbackAttemptRef.current;
      if (
        attempt?.recovering ||
        (attempt?.wantsPlayback &&
          audioElement.error !== null &&
          audioElement.error !== undefined)
      ) {
        return;
      }
      clearStallTimer(attempt);
      if (attempt) {
        attempt.wantsPlayback = false;
        attempt.lastListenPosition = null;
      }
      updatePlaybackPosition();
      setPlaying(false);
      setPlaybackStatus(attempt?.failed ? "failed" : "paused");
      if (navigator.mediaSession) navigator.mediaSession.playbackState = "paused";
    };
    const onEnded = () => {
      const state = usePlayerStore.getState();
      if (
        state.sleepTimerEndTrackId &&
        state.sleepTimerEndTrackId === state.queue[state.queueIndex]
      ) {
        state.setSleepTimer(null, null);
        state.setPlaying(false);
        state.setPlaybackStatus("paused");
        return;
      }
      nextRef.current(true);
    };
    const onError = () => handleAudioError(audioElement);
    audioElement.addEventListener("timeupdate", updatePlayback);
    audioElement.addEventListener("timeupdate", onPlaybackProgress);
    audioElement.addEventListener("loadedmetadata", onLoadedMetadata);
    audioElement.addEventListener("durationchange", updatePlaybackPosition);
    audioElement.addEventListener("seeked", onSeeked);
    audioElement.addEventListener("playing", onPlaying);
    audioElement.addEventListener("waiting", onBuffering);
    audioElement.addEventListener("stalled", onBuffering);
    audioElement.addEventListener("play", onPlay);
    audioElement.addEventListener("pause", onPause);
    audioElement.addEventListener("ended", onEnded);
    audioElement.addEventListener("error", onError);
    updatePlaybackPosition();
    return () => {
      audioElement.removeEventListener("timeupdate", updatePlayback);
      audioElement.removeEventListener("timeupdate", onPlaybackProgress);
      audioElement.removeEventListener("loadedmetadata", onLoadedMetadata);
      audioElement.removeEventListener("durationchange", updatePlaybackPosition);
      audioElement.removeEventListener("seeked", onSeeked);
      audioElement.removeEventListener("playing", onPlaying);
      audioElement.removeEventListener("waiting", onBuffering);
      audioElement.removeEventListener("stalled", onBuffering);
      audioElement.removeEventListener("play", onPlay);
      audioElement.removeEventListener("pause", onPause);
      audioElement.removeEventListener("ended", onEnded);
      audioElement.removeEventListener("error", onError);
      const attempt = playbackAttemptRef.current;
      clearStallTimer(attempt);
      if (attempt?.retryTimer !== null && attempt?.retryTimer !== undefined) {
        window.clearTimeout(attempt.retryTimer);
        attempt.retryTimer = null;
      }
      if (attempt?.restoreMetadataListener) {
        audioElement.removeEventListener("loadedmetadata", attempt.restoreMetadataListener);
        attempt.restoreMetadataListener = null;
      }
    };
  }, [
    audioElement,
    handleAudioError,
    handlePlaybackFailure,
    recordTrackListen,
    recordPlaylistListen,
    setPlaybackStatus,
    setPlaying,
  ]);

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
        const attempt = playbackAttemptRef.current;
        if (attempt) {
          attempt.wantsPlayback = false;
          attempt.recovering = false;
          attempt.requestId += 1;
          if (attempt.retryTimer !== null) {
            window.clearTimeout(attempt.retryTimer);
            attempt.retryTimer = null;
          }
          if (attempt.stallTimer !== null) {
            window.clearTimeout(attempt.stallTimer);
            attempt.stallTimer = null;
          }
          if (attempt.restoreMetadataListener && audioElement) {
            audioElement.removeEventListener(
              "loadedmetadata",
              attempt.restoreMetadataListener,
            );
            attempt.restoreMetadataListener = null;
          }
        }
        audioElement?.pause();
        if (audioElement) {
          audioElement.removeAttribute("src");
          audioElement.load();
        }
        setQueue([], -1);
        setPlaying(false);
        setPlaybackStatus("paused");
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
  const filteredTracksAvailableToAdd = tracksAvailableToAdd.filter((track) =>
    `${track.title} ${track.artist} ${track.album}`
      .toLocaleLowerCase()
      .includes(playlistAddSearch.trim().toLocaleLowerCase()),
  );

  function openPlaylistAdd(playlistId: string) {
    setPlaylistAddSearch("");
    setPlaylistAddTarget(playlistId);
  }

  function toggleTrackMenu(track: TrackRecord, event: ReactMouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    const anchor = event.currentTarget;
    setTrackMenu((current) =>
      current?.trackId === track.id
        ? null
        : { trackId: track.id, anchor },
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
            <TrackImage track={track} thumbnail />
            <span className="card-play" aria-hidden="true"><Icon name="play" /></span>
          </button>
          <button
            className="card-queue"
            type="button"
            title={t("Add to queue")}
            aria-label={t("Add to queue")}
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
            title={t(track.favorite ? "Remove favorite" : "Favorite")}
            aria-label={t(track.favorite ? "Remove favorite" : "Favorite")}
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
            title={t("More options")}
            aria-label={`${t("More options for")} ${track.title}`}
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
          <TrackImage track={track} className="row-art" thumbnail />
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
          <button type="button" title={t("Add to queue")} aria-label={t("Add to queue")} onClick={(event) => { event.stopPropagation(); addToQueue(track); }}><Icon name="queue" /></button>
          <button type="button" className={track.favorite ? "fav-on" : ""} title={t(track.favorite ? "Remove favorite" : "Favorite")} aria-label={t(track.favorite ? "Remove favorite" : "Favorite")} aria-pressed={track.favorite} onClick={(event) => { event.stopPropagation(); toggleFavoriteFor(track); }}><Icon name="heart" /></button>
          <button
            type="button"
            title={t("More options")}
            aria-label={`${t("More options for")} ${track.title}`}
            aria-haspopup="menu"
            aria-expanded={trackMenu?.trackId === track.id}
            data-track-menu-trigger
            onClick={(event) => toggleTrackMenu(track, event)}
          ><Icon name="more" /></button>
        </div>
      </div>
    );
  };

  const renderEmptyState = () => {
    if (search.trim()) {
      return (
        <div className="empty">
          <div className="empty-orb" />
          <h3>{t("No matches for")} “{search.trim()}”</h3>
          <p>{t("Try another title, artist, or album name.")}</p>
          <button className="btn" type="button" onClick={() => setSearch("")}>{t("Clear search")}</button>
        </div>
      );
    }
    if (playlistForView) {
      return (
        <div className="empty playlist-track-empty">
          <div className="empty-orb" />
          <h3>{t("This playlist is empty")}</h3>
          <p>{tracks.length ? t("Add songs from your library to start building it.") : t("Add music to your library, then come back to build this playlist.")}</p>
          {tracks.length ? (
            <button className="btn btn-primary" type="button" onClick={() => openPlaylistAdd(playlistForView.id)}>{t("Add from library")}</button>
          ) : (
            <button className="btn btn-primary" type="button" onClick={() => fileInputRef.current?.click()}>{t("Add music")}</button>
          )}
        </div>
      );
    }
    if (view === "offline") {
      return (
        <div className="empty">
          <div className="empty-orb"><Icon name="offline" /></div>
          <h3>{t("No offline songs yet")}</h3>
          <p>{t("Download songs from the library menu to listen without an internet connection.")}</p>
          <button className="btn btn-primary" type="button" onClick={() => setView("library")}>{t("Browse library")}</button>
        </div>
      );
    }
    if (tracks.length === 0) {
      return (
        <div className="empty">
          <div className="empty-orb" />
          <h3>{t("Your library is empty")}</h3>
          <p>{t("Add songs or a folder. Vervfy saves them to your account so they are available on your other devices.")}</p>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center", marginTop: 6 }}>
            <button className="btn btn-primary" type="button" onClick={() => fileInputRef.current?.click()}>{t("Add music")}</button>
            <button className="btn" type="button" onClick={() => folderInputRef.current?.click()}>{t("Add folder")}</button>
          </div>
        </div>
      );
    }
    if (view === "favorites" && !tracks.some((track) => track.favorite)) {
      return (
        <div className="empty">
          <div className="empty-orb" />
          <h3>{t("No favorites yet")}</h3>
          <p>{t("Use the heart on any song to keep it close. Your favorites sync with your account.")}</p>
        </div>
      );
    }
    return (
      <div className="empty">
        <div className="empty-orb" />
        <h3>{t("Nothing here yet")}</h3>
        <p>{t("Your library will show up here when you add music.")}</p>
      </div>
    );
  };

  const expandedPlayer = expandedPlayerOpen && currentTrack && typeof document !== "undefined"
    ? createPortal(
        <div
          className="mobile-player open"
          data-playback-status={playbackStatus}
          role="dialog"
          aria-modal="true"
          aria-label={t("Now playing")}
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
              aria-label={t("Close player")}
              ref={expandedPlayerCloseRef}
              onClick={() => setExpandedPlayerOpen(false)}
            >
              <Icon name="close" />
            </button>
            <div className="mobile-player-context">
              <span>{t("PLAYING FROM")}</span>
              <strong>{t(viewName(playingFromView ?? view, playlists))}</strong>
            </div>
            <button
              className="mobile-player-icon"
              type="button"
              aria-label={`${t("More options for")} ${currentTrack.title}`}
              aria-haspopup="menu"
              data-track-menu-trigger
              ref={mobilePlayerMenuButtonRef}
              onClick={(event) => toggleTrackMenu(currentTrack, event)}
            >
              <Icon name="more" />
            </button>
          </header>
          <main className="mobile-player-scroll">
            <div className="mobile-player-art">
              <TrackImage track={currentTrack} />
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
                  aria-label={t(currentTrack.favorite ? "Remove favorite" : "Favorite")}
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
                  aria-label={t("Shuffle")}
                  aria-pressed={shuffle}
                  onClick={toggleShuffle}
                ><Icon name="shuffle" /></button>
                <button className="mobile-control" type="button" aria-label={t("Previous track")} onClick={playPrevious}>
                  <Icon name="prev" />
                </button>
                <button
                  className="mobile-play"
                  type="button"
                  aria-label={t(isPlaying ? "Pause" : "Play")}
                  aria-busy={playbackStatus === "buffering"}
                  title={playbackStatus === "failed" ? t("Playback failed. Press play to retry.") : undefined}
                  onClick={togglePlayback}
                >
                  <Icon name={isPlaying ? "pause" : "play"} />
                </button>
                <button className="mobile-control" type="button" aria-label={t("Next track")} onClick={() => playNext(false)}>
                  <Icon name="next" />
                </button>
                <button
                  className={`mobile-control${repeat !== "off" ? " on" : ""}`}
                  type="button"
                  aria-label={t(`Repeat: ${repeat}`)}
                  aria-pressed={repeat !== "off"}
                  onClick={toggleRepeat}
                ><Icon name="repeat" />{repeat === "one" ? <small>1</small> : null}</button>
              </div>
              <button
                className="mobile-lyrics-preview"
                type="button"
                aria-label={t("Open full lyrics")}
                onClick={() => {
                  setExpandedPlayerOpen(false);
                  setLyricsOpen(true);
                }}
              >
                <span className="mobile-lyrics-heading">
                  <span>{t("Lyrics")}</span>
                  <span>
                    {previewLines?.length
                      ? t("Synced to playback")
                      : previewLyrics?.text
                          ? t("Plain lyrics")
                          : t("Open full lyrics")}
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
                      ? t("Couldn't load lyrics. Tap to retry.")
                      : cachedLyrics?.source === "none"
                        ? t("No lyrics found for this track.")
                        : cachedLyrics?.source === "disabled"
                          ? t("Paste your own lyrics.")
                        : t("Finding lyrics…")}
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
                ><span aria-hidden="true">♫</span><span>{t("Lyrics")}</span></button>
                <button
                  className="mobile-secondary"
                  type="button"
                  aria-pressed={queueOpen}
                  onClick={() => {
                    setExpandedPlayerOpen(false);
                    setQueueOpen(true);
                  }}
                ><Icon name="queue" /><span>{t("Queue")}</span></button>
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
        <nav className="rail" aria-label={t("Main navigation")}>
          <div className="logo-mark">
            <div className="logo-squircle"><img className="brand-logo" src="/gemini-svg.svg" alt="" /></div>
            <div className="logo-word">Vervfy</div>
          </div>
          <button className={`rail-btn${view === "library" ? " active" : ""}`} type="button" data-view="library" data-tip={t("Library")} aria-label={t("Library")} aria-current={view === "library" ? "page" : undefined} onClick={() => setView("library")}><Icon name="library" /></button>
          <button className={`rail-btn${view === "offline" ? " active" : ""}`} type="button" data-view="offline" data-tip={t("Offline")} aria-label={t("Offline")} aria-current={view === "offline" ? "page" : undefined} onClick={() => setView("offline")}><Icon name="offline" /></button>
          <button className={`rail-btn${view === "playlists" || view.startsWith("playlist:") ? " active" : ""}`} type="button" data-view="playlists" data-tip={t("Playlists")} aria-label={t("Playlists")} aria-current={view === "playlists" || view.startsWith("playlist:") ? "page" : undefined} onClick={() => setView("playlists")}><Icon name="playlists" /></button>
          <button className={`rail-btn${view === "recap" ? " active" : ""}`} type="button" data-view="recap" data-tip={t("Recap")} aria-label={t("Recap")} aria-current={view === "recap" ? "page" : undefined} onClick={() => setView("recap")}><Icon name="clock" /></button>
          <button className={`rail-btn${view === "artists" || view.startsWith("artist:") ? " active" : ""}`} type="button" data-view="artists" data-tip={t("Artists")} aria-label={t("Artists")} aria-current={view === "artists" || view.startsWith("artist:") ? "page" : undefined} onClick={() => setView("artists")}><Icon name="artist" /></button>
          <button className={`rail-btn${view === "favorites" ? " active" : ""}`} type="button" data-view="favorites" data-tip={t("Favorites")} aria-label={t("Favorites")} aria-current={view === "favorites" ? "page" : undefined} onClick={() => setView("favorites")}><Icon name="heart" /></button>
          <button className={`rail-btn${view === "account" ? " active" : ""}`} type="button" data-view="account" data-tip={t("Account")} aria-label={t("Account")} aria-current={view === "account" ? "page" : undefined} onClick={() => setView("account")}><Icon name="account" /></button>
          <div className="rail-spacer" />
          <div className="rail-logout"><LogoutButton className="rail-btn rail-logout-button" ariaLabel="Log out"><Icon name="logout" /></LogoutButton></div>
          <button className="rail-btn rail-shortcuts-button" type="button" data-tip={t("Shortcuts (?)")} aria-label={t("Shortcuts")} onClick={() => setShortcutsOpen(true)}><Icon name="help" /></button>
          <button className="rail-btn rail-import-button" type="button" data-tip={t("Add music")} aria-label={t("Add music")} onClick={() => fileInputRef.current?.click()}><Icon name="import" /></button>
        </nav>

        <div className="main">
          <div className="topbar">
            <button className="home-profile-avatar" type="button" title={t("Account")} aria-label={t("Open account")} onClick={() => setView("account")}>
              {profile?.photo_url
                ? <img src={profile.photo_url} alt="" onError={() => setProfile((current) => current ? { ...current, photo_url: null } : null)} />
                : profile?.username.slice(0, 1).toUpperCase() ?? <Icon name="account" />}
            </button>
            <div className="topbar-id">
              <span className="view-title">{title}</span>
              <span className="view-count">{view !== "recap" && (tracks.length || view === "playlists" || view === "offline" || playlistForView) ? `· ${count}` : ""}</span>
            </div>
            {view !== "account" && view !== "recap" ? (
              <div className="view-toggle" role="group" aria-label={t("View mode")}>
                <button type="button" className={listMode === "grid" ? "active" : ""} aria-pressed={listMode === "grid"} title={t("Grid view")} aria-label={t("Grid view")} onClick={() => setListMode("grid")}><Icon name="grid" /></button>
                <button type="button" className={listMode === "list" ? "active" : ""} aria-pressed={listMode === "list"} title={t("List view")} aria-label={t("List view")} onClick={() => setListMode("list")}><Icon name="list" /></button>
              </div>
            ) : null}
            {view !== "account" && view !== "recap" ? <label className="search-wrap">
              <Icon name="search" />
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("Search")} autoComplete="off" aria-label={t(view === "playlists" ? "Search playlists" : "Search library")} />
              <span className="kbd">/</span>
            </label> : null}
            {view === "playlists" ? (
              <button className="btn btn-primary" type="button" onClick={() => { setPlaylistName(""); setPlaylistModal({}); }}>
                <Icon name="plus" /> {t("New playlist")}
              </button>
            ) : view === "account" || view === "recap" || view === "artists" || view.startsWith("artist:") || playlistForView ? null : (
              <button className="btn btn-primary" type="button" onClick={() => fileInputRef.current?.click()}>
                <Icon name="import" /> {t("Add music")}
              </button>
            )}
          </div>

          <div className="content">
            {loading ? (
              <div className="library-skeleton" aria-label={t("Loading library")} aria-busy="true">
                {[0, 1, 2].map((item) => <div className="skeleton-row" key={item}><span className="skeleton-art" /><span className="skeleton-copy"><i /><i /></span><span className="skeleton-time" /></div>)}
              </div>
            ) : loadError ? (
              <div className="empty"><div className="empty-orb" /><h3>{t("Music server unavailable")}</h3><p>{loadError}</p><button className="btn btn-primary" type="button" onClick={() => window.location.reload()}>{t("Retry connection")}</button></div>
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
                {view === "account" || view === "artists" || view.startsWith("artist:") ? null : view === "recap" ? (
                  <div className="recap-page">
                    <div className="recap-overview">
                      <section className="recap-intro">
                        <h2>{t("Your listening, over time")}</h2>
                        <p>{t("Recaps only include listens recorded since listening history was added. Earlier plays aren't available.")}</p>
                      </section>
                      {canOpenYearlyRecap ? (
                        <button
                          className="recap-yearly-trigger"
                          type="button"
                          onClick={() => setYearlyRecapOpen(true)}
                          aria-haspopup="dialog"
                        >
                          <span>{t("Yearly recap")}</span>
                          <strong>{listeningSummary?.yearLabel}</strong>
                        </button>
                      ) : null}
                    </div>
                    {listeningError ? <p className="recap-notice" role="status">{t(listeningError)}</p> : null}
                    {listeningSummary ? (
                      <>
                        <div className="recap-periods">
                          <ListeningRecapCard
                            title={recapMonthLabel}
                            period={t("Monthly recap")}
                            summary={listeningSummary.month}
                            tracksById={tracksById}
                            onPlay={(track) => playFromList(tracks, track.id)}
                          />
                        </div>
                        <section className="recap-rediscover">
                          <div className="recap-rediscover-heading">
                            <div className="recap-rediscover-copy">
                              <div className="recap-rediscover-title">
                                <h2>{t("Rediscover these songs")}</h2>
                                <span className="recap-rediscover-count">
                                  <strong>{recapNumberFormatter.format(rediscoveryTracks.length)}</strong> {t("songs")}
                                </span>
                              </div>
                              <p>{t("Last played more than 30 days ago.")}</p>
                            </div>
                            <div className="recap-rediscover-action">
                              <button
                                className="btn btn-primary"
                                type="button"
                                disabled={!rediscoveryTracks.length}
                                aria-describedby={
                                  rediscoveryTracks.length
                                    ? undefined
                                    : "recap-rediscover-disabled-reason"
                                }
                                onClick={createRediscoveryPlaylist}
                              >
                                <Icon name="plus" />
                                {t(hasRediscoveryPlaylist ? "Update Rediscover playlist" : "Create Rediscover playlist")}
                              </button>
                              {!rediscoveryTracks.length ? (
                                <p
                                  className="recap-disabled-hint"
                                  id="recap-rediscover-disabled-reason"
                                >
                                  {t("No songs have a recorded listen older than 30 days yet.")}
                                </p>
                              ) : null}
                            </div>
                          </div>
                          {rediscoveryTracks.length ? (
                            <div className="recap-top-tracks">
                              {rediscoveryTracks.slice(0, 12).map((track) => {
                                const lastPlayedAt = listeningSummary.lastPlayedAt[track.id];
                                if (lastPlayedAt === undefined) return null;
                                const lastPlayedLabel = t("Last played {date}").replace(
                                  "{date}",
                                  recapTrackDateFormatter.format(new Date(lastPlayedAt * 1000)),
                                );
                                return (
                                  <button
                                    className="recap-track recap-rediscover-track"
                                    key={track.id}
                                    type="button"
                                    onClick={() => playFromList(rediscoveryTracks, track.id)}
                                    aria-label={`${t("Play")} ${track.title}, ${lastPlayedLabel}`}
                                  >
                                    <TrackImage track={track} className="recap-art" thumbnail />
                                    <span className="recap-track-copy">
                                      <strong>{track.title}</strong>
                                      <small>{track.artist}</small>
                                      <small className="recap-last-played">{lastPlayedLabel}</small>
                                    </span>
                                  </button>
                                );
                              })}
                              {rediscoveryTracks.length > 12 ? (
                                <p className="recap-more">
                                  {t("{count} more songs are included in your playlist.").replace(
                                    "{count}",
                                    String(rediscoveryTracks.length - 12),
                                  )}
                                </p>
                              ) : null}
                            </div>
                          ) : null}
                        </section>
                      </>
                    ) : (
                      <div className="recap-loading" aria-live="polite">
                        {listeningError
                          ? <p>{t("Your recap is unavailable right now.")}</p>
                          : <p>{t("Loading your listening history…")}</p>}
                      </div>
                    )}
                  </div>
                ) : view === "playlists" ? (
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
                            ? coverTracks.map((track) => <TrackImage key={track.id} track={track} thumbnail />)
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
                  <h3>{search.trim() ? t("No playlists found") : t("Your playlists start here")}</h3>
                  <p>{search.trim() ? t("Try a different name or clear your search.") : t("Collect songs into playlists for every mood and moment.")}</p>
                  {search.trim()
                    ? <button className="btn" type="button" onClick={() => setSearch("")}>{t("Clear search")}</button>
                    : <button className="btn btn-primary" type="button" onClick={() => { setPlaylistName(""); setPlaylistModal({}); }}><Icon name="plus" /> {t("Create playlist")}</button>}
                </div>
              )
            ) : (
              <>
                {view === "library" && !search.trim() && playlistRecommendations.length > 0 ? (
                  <section className="playlist-recommendations" aria-labelledby="playlist-recommendations-title">
                    <div className="playlist-recommendations-heading">
                      <div>
                        <h2 id="playlist-recommendations-title">{t("Playlists to revisit")}</h2>
                        <p>{t("Playlists you haven't heard in 30 days, or haven't played yet.")}</p>
                      </div>
                    </div>
                    <div className="playlist-recommendations-list">
                      {playlistRecommendations.map(({ playlist, tracks: recommendationTracks }) => {
                        const coverTracks = playlistCoverTracks(playlist);
                        const lastPlayed = playlist.lastPlayedAt
                          ? t("Last played {date}").replace(
                              "{date}",
                              recapTrackDateFormatter.format(new Date(playlist.lastPlayedAt * 1000)),
                            )
                          : t("Not played yet");
                        const playLabel = t("Play playlist {name}").replace("{name}", playlist.name);
                        const trackCount = recommendationTracks.length;
                        const firstTrack = recommendationTracks[0];
                        return (
                          <article className="playlist-recommendation" key={playlist.id}>
                            <button
                              className="playlist-recommendation-open"
                              type="button"
                              aria-label={`${t("Open playlist")} ${playlist.name}`}
                              onClick={() => setView(`playlist:${playlist.id}`)}
                            >
                              <span className={`playlist-recommendation-cover playlist-cover${coverTracks.length === 1 ? " single" : ""}`}>
                                {coverTracks.map((track) => (
                                  <TrackImage key={track.id} track={track} thumbnail />
                                ))}
                              </span>
                              <span className="playlist-recommendation-copy">
                                <strong>{playlist.name}</strong>
                                <small>{trackCount} {t("songs")}</small>
                                <small className="playlist-recommendation-last-played">{lastPlayed}</small>
                              </span>
                            </button>
                            <button
                              className="playlist-recommendation-play"
                              type="button"
                              aria-label={playLabel}
                              disabled={!firstTrack}
                              onClick={() => {
                                if (firstTrack) {
                                  playFromList(recommendationTracks, firstTrack.id, playlist.id);
                                }
                              }}
                            >
                              <Icon name="play" />
                            </button>
                          </article>
                        );
                      })}
                    </div>
                  </section>
                ) : null}
                {playlistForView ? (
                  <div className="playlist-detail">
                    <button className="playlist-back" type="button" onClick={() => setView("playlists")}><Icon name="prev" /> {t("All playlists")}</button>
                    <section className="playlist-hero">
                      <div className={`playlist-hero-cover${playlistViewCovers.length === 1 ? " single" : ""}${playlistViewCovers.length ? "" : " is-empty"}`} aria-hidden="true">
                        {playlistViewCovers.length
                          ? playlistViewCovers.map((track) => <TrackImage key={track.id} track={track} thumbnail />)
                          : <Icon name="playlists" />}
                      </div>
                      <div className="playlist-hero-copy">
                        <span className="playlist-eyebrow">{t("PLAYLIST")}</span>
                        <h1>{playlistForView.name}</h1>
                        <p>{playlistForView.trackIds.length} {t(playlistForView.trackIds.length === 1 ? "song" : "songs")} {t("in this collection")}</p>
                        <div className="playlist-actions">
                          <button className="btn btn-primary" type="button" disabled={!visibleTracks.length} onClick={() => {
                            const firstTrack = visibleTracks[0];
                            if (firstTrack) playFromList(visibleTracks, firstTrack.id);
                          }}><Icon name="play" /> {t("Play")}</button>
                          <button className="btn" type="button" onClick={() => openPlaylistAdd(playlistForView.id)}><Icon name="plus" /> {t("Add songs")}</button>
                          <button className="btn" type="button" onClick={() => { setPlaylistName(playlistForView.name); setPlaylistModal({ playlist: playlistForView }); }}>{t("Rename")}</button>
                          <button className="btn btn-danger" type="button" onClick={() => {
                            if (!window.confirm(`Delete “${playlistForView.name}”?`)) return;
                            setPlaylists(playlists.filter((item) => item.id !== playlistForView.id));
                            setView("playlists");
                            void saveMeta();
                          }}>{t("Delete")}</button>
                        </div>
                      </div>
                    </section>
                  </div>
                ) : null}
                {visibleTracks.length ? (
                  <>
                    {playlistForView ? (
                      <div className="playlist-track-heading">
                        <h2>{t("Songs")}</h2>
                        <span>{visibleTracks.length} {t(visibleTracks.length === 1 ? "song" : "songs")}</span>
                      </div>
                    ) : null}
                    {listMode === "grid" ? (
                      <div className="grid">{visibleTracks.map(renderTrack)}</div>
                    ) : (
                      <div className="list">
                        <div className="list-head"><div /><div>{t("Title")}</div><div>{t("Album")}</div><div>{t("Time")}</div><div /></div>
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

      <div id="nowbar" className={`nowbar${currentTrack ? "" : " hidden"}${lyricsOpen ? " lyrics-open" : ""}`} data-playback-status={playbackStatus} role="region" aria-label={t("Now playing")} aria-hidden={!currentTrack || lyricsOpen || expandedPlayerOpen} inert={!currentTrack || lyricsOpen || expandedPlayerOpen}
        onClick={(event) => {
          if (event.target instanceof Element && event.target.closest("button, .seek")) return;
          if (window.matchMedia("(max-width: 900px)").matches) {
            setExpandedPlayerOpen(true);
          }
        }}
      >
        <div className="now-track">
          <span className="now-art-wrap"><span className="now-art">{currentTrack ? <TrackImage track={currentTrack} /> : <img src={FALLBACK_ART} alt="" />}</span></span>
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
          {currentTrack ? <button className={`now-fav${currentTrack.favorite ? " on" : ""}`} type="button" aria-label={t(currentTrack.favorite ? "Remove favorite" : "Favorite")} aria-pressed={currentTrack.favorite} onClick={() => toggleFavoriteFor(currentTrack)}><Icon name="heart" /></button> : null}
        </div>
        <div className="transport">
          <div className="transport-btns">
            <button className={`tbtn${shuffle ? " on" : ""}`} type="button" title={t("Shuffle")} aria-label={t("Shuffle")} aria-pressed={shuffle} onClick={toggleShuffle}><Icon name="shuffle" /></button>
            <button className="tbtn" type="button" title={t("Previous track")} aria-label={t("Previous track")} onClick={playPrevious}><Icon name="prev" /></button>
            <button
              className="tbtn tbtn-play"
              type="button"
              title={playbackStatus === "failed" ? t("Playback failed. Press play to retry.") : t("Play or pause")}
              aria-label={t(isPlaying ? "Pause" : "Play")}
              aria-busy={playbackStatus === "buffering"}
              onClick={togglePlayback}
            ><Icon name={isPlaying ? "pause" : "play"} /></button>
            <button className="tbtn" type="button" title={t("Next track")} aria-label={t("Next track")} onClick={() => playNext(false)}><Icon name="next" /></button>
            <button className={`tbtn${repeat !== "off" ? " on" : ""}`} type="button" title={t(`Repeat: ${repeat}`)} aria-label={t(`Repeat: ${repeat}`)} aria-pressed={repeat !== "off"} onClick={toggleRepeat}><Icon name="repeat" />{repeat === "one" ? <small>1</small> : null}</button>
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
          {currentTrack?.coverSource === "musicbrainz" ? (
            <button
              ref={coverInfoButtonRef}
              className={`icon-btn player-control-cover-info${coverInfoOpen ? " on" : ""}`}
              type="button"
              title={t("Cover art info")}
              aria-label={t("Cover art info")}
              aria-haspopup="dialog"
              aria-expanded={coverInfoOpen}
              aria-controls="cover-art-info"
              onClick={(event) => {
                coverInfoReturnFocusRef.current = event.currentTarget;
                setCoverInfoTrackId(coverInfoOpen ? null : currentTrack?.id ?? null);
              }}
            >
              <Icon name="info" />
            </button>
          ) : null}
          <button className={`icon-btn player-control-lyrics${lyricsOpen ? " on" : ""}`} type="button" title={t("Lyrics (L)")} aria-label={t("Lyrics")} aria-pressed={lyricsOpen} onClick={() => setLyricsOpen(true)}><Icon name="lyrics" /></button>
          <button className={`icon-btn player-control-visualizer${visualizerOpen ? " on" : ""}`} type="button" title={t("Visualizer (V)")} aria-label={t("Visualizer")} aria-pressed={visualizerOpen} onClick={() => setVisualizerOpen(true)}><Icon name="visualizer" /></button>
          <button className={`icon-btn player-control-queue${queueOpen ? " on" : ""}`} type="button" title={t("Queue")} aria-label={t("Queue")} aria-pressed={queueOpen} onClick={() => setQueueOpen(!queueOpen)}><Icon name="queue" /></button>
          <div className="sleep-timer-control" ref={sleepTimerControlRef}>
            <button
              className={`icon-btn player-control-sleep-timer${sleepTimerEndsAt || sleepTimerEndTrackId ? " on" : ""}`}
              type="button"
              title={t("Sleep timer")}
              aria-label={t("Sleep timer")}
              aria-haspopup="dialog"
              aria-expanded={sleepTimerOpen}
              aria-controls="sleep-timer-options"
              aria-pressed={Boolean(sleepTimerEndsAt || sleepTimerEndTrackId)}
              disabled={!currentTrack}
              onClick={() => setSleepTimerOpen((open) => !open)}
            >
              <Icon name="timer" />
            </button>
            {sleepTimerOpen
              ? createPortal(
                  <div
                    className={expandedPlayerOpen ? "sleep-timer-overlay open player-sheet" : ""}
                    onClick={(event) => {
                      if (event.target === event.currentTarget) setSleepTimerOpen(false);
                    }}
                  >
                    <section
                      id="sleep-timer-options"
                      ref={sleepTimerPopoverRef}
                      className={expandedPlayerOpen ? "sleep-timer-card" : "sleep-timer-popover"}
                      role="dialog"
                      aria-modal={expandedPlayerOpen || undefined}
                      aria-label={t("Sleep timer")}
                      onClick={(event) => event.stopPropagation()}
                    >
                      <div className="sleep-timer-heading">
                        <h3>{t("Sleep timer")}</h3>
                        <button
                          className="icon-btn"
                          type="button"
                          aria-label={t("Close")}
                          onClick={() => setSleepTimerOpen(false)}
                        >
                          <Icon name="close" />
                        </button>
                      </div>
                      <p className="sleep-timer-status" aria-live="polite">
                        {sleepTimerEndTrackId
                          ? t("At end of track")
                          : sleepTimerEndsAt
                            ? `${t("Time remaining")}: ${formatTime(sleepTimerRemaining)}`
                            : t("No timer set")}
                      </p>
                      <div className="sleep-timer-options">
                        {[5, 10, 15, 30, 45, 60].map((minutes) => (
                          <button
                            type="button"
                            className="sleep-timer-option"
                            key={minutes}
                            onClick={() => {
                              setSleepTimerRemaining(minutes * 60);
                              setSleepTimer(Date.now() + minutes * 60_000, null);
                              setSleepTimerOpen(false);
                            }}
                          >
                            {t(`${minutes} minutes`)}
                          </button>
                        ))}
                        <button
                          type="button"
                          className="sleep-timer-option"
                          onClick={() => {
                            if (currentTrack) setSleepTimer(null, currentTrack.id);
                            setSleepTimerOpen(false);
                          }}
                        >
                          {t("At end of track")}
                        </button>
                      </div>
                      {sleepTimerEndsAt || sleepTimerEndTrackId ? (
                        <button
                          className="sleep-timer-cancel"
                          type="button"
                          onClick={() => {
                            setSleepTimer(null, null);
                            setSleepTimerOpen(false);
                          }}
                        >
                          {t("Turn off timer")}
                        </button>
                      ) : null}
                    </section>
                  </div>,
                  document.body,
                )
              : null}
          </div>
          <button
            className={`icon-btn player-control-offline${currentTrack?.offlineUrl ? " on" : ""}`}
            type="button"
            title={t(currentTrack?.offlineUrl ? "Remove offline download" : "Download for offline listening")}
            aria-label={t(currentTrack?.offlineUrl ? "Remove offline download" : "Download for offline listening")}
            aria-pressed={Boolean(currentTrack?.offlineUrl)}
            aria-busy={offlinePendingId === currentTrack?.id}
            disabled={!currentTrack || offlinePendingId !== null}
            onClick={() => {
              if (currentTrack) void toggleOfflineDownload(currentTrack);
            }}
          >
            <Icon name="offline" />
          </button>
          <button className={`icon-btn player-control-mute${muted ? " on" : ""}`} type="button" title={muted ? "Unmute" : "Mute"} aria-label={muted ? "Unmute" : "Mute"} aria-pressed={muted} onClick={() => {
          const audio = usePlayerStore.getState().audioElement;
          if (!audio) return;
          const nextMuted = !muted;
          setMuted(nextMuted);
          audio.muted = nextMuted;
          }}><Icon name={muted || volume === 0 ? "volume-muted" : "volume"} /></button>
          <div className="vol-wrap"><div className="vol-track" role="slider" tabIndex={0} aria-label={t("Volume")} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round((muted ? 0 : volume) * 100)} aria-valuetext={`${Math.round((muted ? 0 : volume) * 100)}%`} onClick={updateVolume} onKeyDown={(event) => {
            if (event.key !== "ArrowRight" && event.key !== "ArrowUp" && event.key !== "ArrowLeft" && event.key !== "ArrowDown") return;
            event.preventDefault();
            const direction = event.key === "ArrowRight" || event.key === "ArrowUp" ? 1 : -1;
            setVolume((current) => Math.max(0, Math.min(1, current + direction * 0.05)));
            setMuted(false);
          }}><div className="vol-fill" style={{ width: `${(muted ? 0 : volume) * 100}%` }} /></div></div>
        </div>
      </div>

      {coverInfoOpen && currentTrack?.coverSource === "musicbrainz" ? (
        createPortal(
          <section
            id="cover-art-info"
            ref={coverInfoPopoverRef}
            className="cover-info-popover"
            role="dialog"
            tabIndex={-1}
            aria-label={t("Cover art information")}
            onClick={(event) => event.stopPropagation()}
          >
          <div className="cover-info-heading">
            <span className="cover-info-icon"><Icon name="info" /></span>
            <div>
              <p>{t("NOW PLAYING")}</p>
              <h2>{t("Cover art source")}</h2>
            </div>
            <button
              className="icon-btn"
              type="button"
              aria-label={t("Close cover art information")}
              onClick={() => {
                setCoverInfoTrackId(null);
                const returnFocusTarget = coverInfoReturnFocusRef.current ?? coverInfoButtonRef.current;
                returnFocusTarget?.focus();
                coverInfoReturnFocusRef.current = null;
              }}
            >
              <Icon name="close" />
            </button>
          </div>
          <p className="cover-info-copy">
            {t("This cover is provided through MusicBrainz and the Cover Art Archive.")}
          </p>
          <p className="cover-info-note">
            {t("Vervfy links to the image instead of storing a copy.")}
          </p>
          <div className="cover-info-links">
            <a href="https://musicbrainz.org/" target="_blank" rel="noopener noreferrer">
              MusicBrainz <span aria-hidden="true">↗</span>
            </a>
            <a href="https://coverartarchive.org/" target="_blank" rel="noopener noreferrer">
              Cover Art Archive <span aria-hidden="true">↗</span>
            </a>
            <a href="/credits">{t("View all credits")} <span aria-hidden="true">→</span></a>
          </div>
          </section>,
          document.body,
        )
      ) : null}

      {expandedPlayer}
      {trackMenu && trackMenuTrack ? (
        <TrackMenuPortal
          track={trackMenuTrack}
          anchor={trackMenu.anchor}
          view={view}
          playlists={playlists}
          offlinePendingId={offlinePendingId}
          expandedPlayerOpen={expandedPlayerOpen}
          onPlayNext={() => {
            addToQueue(trackMenuTrack, true);
            setTrackMenu(null);
          }}
          onAddToQueue={() => {
            addToQueue(trackMenuTrack);
            setTrackMenu(null);
          }}
          onAddToPlaylist={() => {
            setExpandedPlayerOpen(false);
            setPlaylistPicker(trackMenuTrack.id);
            setTrackMenu(null);
          }}
          onToggleOffline={() => void toggleOfflineDownload(trackMenuTrack)}
          onToggleFavorite={() => {
            toggleFavoriteFor(trackMenuTrack);
            setTrackMenu(null);
          }}
          onViewArtist={openArtist}
          onOpenSleepTimer={() => {
            setTrackMenu(null);
            setSleepTimerOpen(true);
          }}
          onShare={() => {
            setTrackMenu(null);
            void shareTrack(trackMenuTrack);
          }}
          onRemoveFromPlaylist={
            view.startsWith("playlist:")
              ? () => removeTrackFromPlaylist(view.slice("playlist:".length), trackMenuTrack)
              : undefined
          }
          onAddOrChangeCover={() => openCoverEditor(trackMenuTrack)}
          onRetryCover={() => void retryCoverLookup(trackMenuTrack)}
          onCoverInfo={() => {
            coverInfoReturnFocusRef.current = mobilePlayerMenuButtonRef.current;
            setCoverInfoTrackId(trackMenuTrack.id);
            setTrackMenu(null);
          }}
          onEditDetails={() => openMetadataEditor(trackMenuTrack)}
          onRemove={() => {
            setExpandedPlayerOpen(false);
            void removeTrack(trackMenuTrack);
          }}
        />
      ) : null}
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
      {yearlyRecapOpen && listeningSummary && typeof document !== "undefined"
        ? createPortal(
            <dialog
              ref={yearlyRecapDialogRef}
              className="yearly-recap-dialog"
              aria-labelledby="yearly-recap-title"
              onClose={() => setYearlyRecapOpen(false)}
              onClick={(event) => {
                if (event.target !== event.currentTarget) return;
                const bounds = event.currentTarget.getBoundingClientRect();
                if (
                  event.clientX < bounds.left ||
                  event.clientX > bounds.right ||
                  event.clientY < bounds.top ||
                  event.clientY > bounds.bottom
                ) {
                  yearlyRecapDialogRef.current?.close();
                }
              }}
            >
              <header className="yearly-recap-header">
                <div>
                  <span className="recap-period-label">{t("Yearly recap")}</span>
                  <h2 id="yearly-recap-title">{listeningSummary.yearLabel}</h2>
                </div>
                <button
                  className="icon-btn"
                  type="button"
                  aria-label={t("Close")}
                  onClick={() => yearlyRecapDialogRef.current?.close()}
                >
                  <Icon name="close" />
                </button>
              </header>
              <ListeningRecapCard
                title={listeningSummary.yearLabel}
                period={t("Yearly recap")}
                summary={listeningSummary.year}
                tracksById={tracksById}
                onPlay={(track) => playFromList(tracks, track.id)}
                showHeading={false}
              />
            </dialog>,
            document.body,
          )
        : null}
      {shortcutsOpen ? <div className="queue-picker-overlay open" role="dialog" aria-modal="true" aria-label={t("Keyboard shortcuts")} onClick={() => setShortcutsOpen(false)}>
        <section className="queue-picker-card shortcuts-dialog" onClick={(event) => event.stopPropagation()}>
          <div className="queue-picker-head"><h3>{t("Keyboard shortcuts")}</h3><button className="icon-btn" type="button" aria-label={t("Close shortcuts")} onClick={() => setShortcutsOpen(false)}><Icon name="close" /></button></div>
          <div className="queue-picker-list"><p><kbd>{t("Space")}</kbd><span>{t("Play / pause")}</span></p><p><kbd>Shift + ← / →</kbd><span>{t("Previous / next track")}</span></p><p><kbd>← / →</kbd><span>{t("Seek 5 seconds")}</span></p><p><kbd>↑ / ↓</kbd><span>{t("Volume")}</span></p><p><kbd>M</kbd><span>{t("Mute")}</span></p><p><kbd>F</kbd><span>{t("Favorite current track")}</span></p><p><kbd>L</kbd><span>{t("Lyrics")}</span></p><p><kbd>V</kbd><span>{t("Visualizer")}</span></p><p><kbd>/</kbd><span>{t("Search")}</span></p><p><kbd>?</kbd><span>{t("Shortcuts")}</span></p><p><kbd>Esc</kbd><span>{t("Close panels")}</span></p></div>
        </section>
      </div> : null}

      <aside ref={queuePanelRef} className={`side-panel${queueOpen ? " open" : ""}`} aria-label={t("Up next")}>
        <div className="side-head"><h3>{t("Up next")}</h3><div className="side-head-actions"><button className="icon-btn" type="button" title={t("Add from library")} onClick={() => setQueuePickerOpen(true)}><Icon name="plus" /></button><button className="icon-btn" type="button" title={t("Close queue")} onClick={() => setQueueOpen(false)}><Icon name="close" /></button></div></div>
        <div className="side-body">
          {queue.length === 0 ? <div className="side-empty"><p>{t("Your queue is empty.")}</p><button className="btn" type="button" onClick={() => setQueuePickerOpen(true)}>{t("Add from library")}</button></div> : queue.map((trackId, index) => {
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
            ><Icon name="drag" /></button><TrackImage track={track} thumbnail /><button className="q-meta" type="button" onClick={() => playQueueIndex(index)}><span className="q-title">{track.title}</span><span className="q-artist">{track.artist}</span></button><button className="icon-btn q-remove" type="button" title={t("Remove from queue")} aria-label={`${t("Remove from queue")}: ${track.title}`} onClick={() => removeFromQueue(index)}><Icon name="close" /></button></div>;
          })}
        </div>
      </aside>

      <div className={`queue-picker-overlay${queuePickerOpen ? " open" : ""}`} role="dialog" aria-modal="true" aria-label={t("Add from library")}>
        <div className="queue-picker-card">
          <div className="queue-picker-head"><h3>{t("Add from library")}</h3><button className="icon-btn" type="button" title={t("Close")} onClick={() => setQueuePickerOpen(false)}><Icon name="close" /></button></div>
          <label className="queue-picker-search"><Icon name="search" /><input value={queueSearch} onChange={(event) => setQueueSearch(event.target.value)} placeholder={t("Search library")} aria-label={t("Search library")} /></label>
          <div className="queue-picker-list">{filteredQueueTracks.length ? filteredQueueTracks.map((track) => <button className="qp-row" type="button" key={track.id} onClick={(event) => {
            event.stopPropagation();
            addToQueue(track);
            setQueuePickerOpen(true);
          }}><TrackImage track={track} thumbnail /><span className="qp-meta"><span className="qp-title">{track.title}</span><span className="qp-artist">{track.artist}</span></span><span className="qp-add"><Icon name="plus" /></span></button>) : <div className="queue-picker-empty">{tracks.length ? t("No tracks match your search.") : t("Your library is empty")}</div>}</div>
        </div>
      </div>

      <div className={`queue-picker-overlay playlist-name-overlay${playlistModal ? " open" : ""}`} role="dialog" aria-modal="true" aria-labelledby="playlistNameTitle">
        <form className="queue-picker-card playlist-name-card" onSubmit={createOrRenamePlaylist}>
          <div className="queue-picker-head"><h3 id="playlistNameTitle">{playlistModal?.playlist ? t("Rename playlist") : t("New playlist")}</h3><button className="icon-btn" type="button" title={t("Close")} onClick={() => setPlaylistModal(null)}><Icon name="close" /></button></div>
          <label className="playlist-name-label" htmlFor="playlistNameInput">{t("Playlist name")}</label>
          <input ref={playlistNameInputRef} className="playlist-name-input" id="playlistNameInput" maxLength={200} value={playlistName} onChange={(event) => setPlaylistName(event.target.value)} />
          <div className="playlist-name-actions"><button className="btn" type="button" onClick={() => setPlaylistModal(null)}>{t("Cancel")}</button><button className="btn btn-primary" type="submit">{playlistModal?.playlist ? t("Save") : t("Create")}</button></div>
        </form>
      </div>

      <div className={`queue-picker-overlay${playlistPicker ? " open" : ""}`} role="dialog" aria-modal="true" aria-label={t("Add track to playlist")}>
        <div className="queue-picker-card">
          <div className="queue-picker-head"><h3>{t("Add to playlist")}</h3><button className="icon-btn" type="button" title={t("Close")} onClick={() => setPlaylistPicker(null)}><Icon name="close" /></button></div>
          <div className="queue-picker-list">{playlists.length ? playlists.map((playlist) => {
            const trackId = playlistPicker;
            const inPlaylist = trackId ? playlist.trackIds.includes(trackId) : false;
            return <button className={`qp-row${inPlaylist ? " in-playlist" : ""}`} type="button" key={playlist.id} disabled={inPlaylist} onClick={() => {
              if (trackId) addTrackToPlaylist(playlist.id, trackId);
              setPlaylistPicker(null);
              notify(`Added to “${playlist.name}”.`);
            }}><span className="qp-meta"><span className="qp-title">{playlist.name}</span><span className="qp-artist">{playlist.trackIds.length} {t("tracks")}</span></span><span className="qp-add">{inPlaylist ? "✓" : <Icon name="plus" />}</span></button>;
          }) : <div className="queue-picker-empty">{t("Create a playlist first.")}</div>}</div>
          <div className="playlist-name-actions"><button className="btn btn-primary" type="button" onClick={() => { setPlaylistPicker(null); setPlaylistName(""); setPlaylistModal({ trackId: playlistPicker ?? undefined }); }}>{t("New playlist")}</button></div>
        </div>
      </div>

      <div className={`queue-picker-overlay${playlistAddTarget ? " open" : ""}`} role="dialog" aria-modal="true" aria-label={t("Add tracks to playlist")}>
        <div className="queue-picker-card">
          <div className="queue-picker-head"><h3>{t("Add from library")}</h3><button className="icon-btn" type="button" title={t("Close")} onClick={() => setPlaylistAddTarget(null)}><Icon name="close" /></button></div>
          <label className="queue-picker-search">
            <Icon name="search" />
            <input
              type="search"
              value={playlistAddSearch}
              onChange={(event) => setPlaylistAddSearch(event.target.value)}
              placeholder={t("Search songs, artists, or albums")}
              aria-label={t("Search songs, artists, or albums")}
            />
          </label>
          <div className="queue-picker-list">
            {filteredTracksAvailableToAdd.length ? filteredTracksAvailableToAdd.map((track) => <button className="qp-row" type="button" key={track.id} onClick={() => {
              if (playlistAddTarget) addTrackToPlaylist(playlistAddTarget, track.id);
              notify(`Added “${track.title}” to the playlist.`);
            }}><TrackImage track={track} thumbnail /><span className="qp-meta"><span className="qp-title">{track.title}</span><span className="qp-artist">{track.artist}</span></span><span className="qp-add"><Icon name="plus" /></span></button>) : <div className="queue-picker-empty">{tracksAvailableToAdd.length ? t("No tracks match your search.") : tracks.length ? t("Every song in your library is already in this playlist.") : t("Your library is empty.")}</div>}
          </div>
        </div>
      </div>

      {coverEditorTrack ? (
        <div
          className="queue-picker-overlay open"
          role="dialog"
          aria-modal="true"
          aria-labelledby="coverEditorTitle"
          onClick={(event) => {
            if (event.target === event.currentTarget && !coverPending) closeCoverEditor();
          }}
        >
          <section className="queue-picker-card track-editor-card">
            <div className="queue-picker-head">
              <h3 id="coverEditorTitle">{t("Cover for")} {coverEditorTrack.title}</h3>
              <button className="icon-btn" type="button" aria-label={t("Close")} onClick={closeCoverEditor} disabled={coverPending}>
                <Icon name="close" />
              </button>
            </div>
            <img
              className="track-cover-preview"
              src={coverPreview ?? coverEditorTrack.coverUrl}
              alt={`${t("Current cover for")} ${coverEditorTrack.title}`}
            />
            <p className="track-editor-help">{t("JPEG, PNG, or WebP; up to 5 MB.")}</p>
            <label className="track-editor-check">
              <input
                type="checkbox"
                checked={applyCoverToAlbum}
                disabled={!coverEditorTrack.album.trim() || /^unknown album$/i.test(coverEditorTrack.album.trim()) || coverPending}
                onChange={(event) => {
                  setApplyCoverToAlbum(event.currentTarget.checked);
                  if (!event.currentTarget.checked) setReplaceAlbumUserCovers(false);
                }}
              />
              <span>{t("Apply to all tracks of this album")}</span>
            </label>
            {!coverEditorTrack.album.trim() || /^unknown album$/i.test(coverEditorTrack.album.trim()) ? (
              <p className="track-editor-help">{t("An album name is required to apply a cover to the album.")}</p>
            ) : null}
            {applyCoverToAlbum ? (
              <label className="track-editor-check track-editor-check-warning">
                <input
                  type="checkbox"
                  checked={replaceAlbumUserCovers}
                  disabled={coverPending}
                  onChange={(event) => setReplaceAlbumUserCovers(event.currentTarget.checked)}
                />
                <span>{t("Also replace covers you uploaded on this album")}</span>
              </label>
            ) : null}
            <input
              ref={coverFileInputRef}
              className="hidden-input"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(event) => {
                const selected = event.currentTarget.files?.[0] ?? null;
                event.currentTarget.value = "";
                if (!selected) return;
                if (selected.size > 5 * 1024 * 1024) {
                  setCoverError(t("Cover image must be 5 MB or smaller."));
                  return;
                }
                if (!["image/jpeg", "image/png", "image/webp"].includes(selected.type)) {
                  setCoverError(t("Choose a JPEG, PNG, or WebP image."));
                  return;
                }
                if (coverPreviewUrlRef.current) URL.revokeObjectURL(coverPreviewUrlRef.current);
                const previewUrl = URL.createObjectURL(selected);
                coverPreviewUrlRef.current = previewUrl;
                setCoverFile(selected);
                setCoverPreview(previewUrl);
                setCoverError("");
              }}
            />
            <div className="track-editor-error" role="alert">{coverError}</div>
            <div className="playlist-name-actions">
              <button className="btn" type="button" onClick={() => coverFileInputRef.current?.click()} disabled={coverPending}>
                {t("Choose cover image")}
              </button>
              {coverEditorTrack.coverSource === "user" ? (
                <button className="btn btn-danger" type="button" onClick={() => void removeCover()} disabled={coverPending}>
                  {coverPending ? t("Removing cover…") : t("Remove cover")}
                </button>
              ) : null}
              {coverEditorTrack.coverSource !== "upload" && coverEditorTrack.coverSource !== "user" ? (
                <button
                  className="btn"
                  type="button"
                  onClick={() => void retryCoverLookup(coverEditorTrack)}
                  disabled={coverPending}
                >
                  {t("Retry cover")}
                </button>
              ) : null}
              <button className="btn btn-primary" type="button" onClick={() => void saveCover()} disabled={coverPending || !coverFile}>
                {coverPending ? t("Saving cover…") : t("Save cover")}
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {metadataEditorTrack ? (
        <div
          className="queue-picker-overlay open"
          role="dialog"
          aria-modal="true"
          aria-labelledby="trackDetailsTitle"
          onClick={(event) => {
            if (event.target === event.currentTarget && !metadataPending) setMetadataEditorTrack(null);
          }}
        >
          <form className="queue-picker-card track-editor-card" onSubmit={saveTrackDetails}>
            <div className="queue-picker-head">
              <h3 id="trackDetailsTitle">{t("Track details")}</h3>
              <button className="icon-btn" type="button" aria-label={t("Close")} onClick={() => setMetadataEditorTrack(null)} disabled={metadataPending}>
                <Icon name="close" />
              </button>
            </div>
            {(["title", "artist", "album"] as const).map((field) => (
              <label className="track-editor-field" key={field}>
                <span>{t(field === "title" ? "Title" : field === "artist" ? "Artist" : "Album")}</span>
                <input
                  maxLength={200}
                  required
                  value={metadataDraft[field]}
                  onChange={(event) => setMetadataDraft((current) => ({ ...current, [field]: event.target.value }))}
                />
              </label>
            ))}
            <div className="track-editor-error" role="alert">{metadataError}</div>
            <div className="playlist-name-actions">
              <button className="btn" type="button" onClick={() => setMetadataEditorTrack(null)} disabled={metadataPending}>{t("Cancel")}</button>
              <button className="btn btn-primary" type="submit" disabled={metadataPending}>
                {metadataPending ? t("Saving…") : t("Save changes")}
              </button>
            </div>
          </form>
        </div>
      ) : null}

      <input
        ref={fileInputRef}
        className="hidden-input"
        type="file"
        accept={AUDIO_FILE_ACCEPT}
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
        accept={AUDIO_FILE_ACCEPT}
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
      }}><h3>{t("Drop to add music")}</h3><p>{t("Your files are uploaded to your account.")}</p></div> : null}
      {uploadStatus && typeof document !== "undefined"
        ? createPortal(<div className="toasts" role="status" aria-live="polite" aria-atomic="true"><div className="toast">{uploadStatus}</div></div>, document.body)
        : null}
      {toast && typeof document !== "undefined"
        ? createPortal(<div className="toasts" role="status" aria-live="polite" aria-atomic="true"><div className="toast">{toast}</div></div>, document.body)
        : null}
    </div>
  );
}
