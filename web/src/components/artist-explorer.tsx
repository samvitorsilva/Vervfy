"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { apiFetch } from "@/lib/api/client";
import { usePlayerStore, type ListMode, type TrackRecord } from "@/store/player-store";

interface Artist {
  name: string;
  tracks: TrackRecord[];
  albums: Set<string>;
  duration: number;
}

interface ArtistData {
  deezer_id: number;
  name: string;
  picture: string | null;
  fans: number | null;
  url: string;
  fetched_at: string;
}

export function artistNames(track: TrackRecord): string[] {
  const names = track.artist
    .split(/\s*(?:,|;|\/|\bfeat(?:uring)?\.?|\bft\.?|\bwith\b)\s*/i)
    .flatMap((part) => part.split(/\s+and\s+/i))
    .map((part) => part.trim())
    .filter(Boolean);
  return [...new Set(names)];
}

function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  const hours = Math.floor(minutes / 60);
  return hours === 0 ? `${minutes} min` : `${hours} hr${minutes % 60 ? ` ${minutes % 60} min` : ""}`;
}

function safeExternalUrl(value: unknown): string | null {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

function artistKey(name: string): string {
  return name.toLocaleLowerCase();
}

async function fetchArtistData(name: string): Promise<ArtistData> {
  const response = await apiFetch(`/api/artists/${encodeURIComponent(name)}`);
  if (!response.ok) throw new Error(`Artist lookup failed (${response.status})`);
  return (await response.json()) as ArtistData;
}

export default function ArtistExplorer({
  view,
  search,
  listMode,
  onPlay,
  renderTrack,
}: {
  view: string;
  search: string;
  listMode: ListMode;
  onPlay: (tracks: TrackRecord[], startTrackId?: string) => void;
  renderTrack: (track: TrackRecord, index: number, playList: TrackRecord[]) => ReactNode;
}) {
  const tracks = usePlayerStore((state) => state.tracks);
  const setView = usePlayerStore((state) => state.setView);
  const [artistDataByName, setArtistDataByName] = useState<Record<string, ArtistData>>({});
  const [profile, setProfile] = useState<Record<string, unknown> | null>(null);
  const [loadedArtist, setLoadedArtist] = useState<string | null>(null);
  const artistDataRef = useRef(artistDataByName);
  const artistRequestsRef = useRef(new Map<string, Promise<ArtistData>>());

  useEffect(() => {
    artistDataRef.current = artistDataByName;
  }, [artistDataByName]);

  const loadArtistData = useCallback((name: string): Promise<ArtistData> => {
    const key = artistKey(name);
    const pending = artistRequestsRef.current.get(key);
    if (pending) return pending;
    const request = fetchArtistData(name).finally(() => {
      artistRequestsRef.current.delete(key);
    });
    artistRequestsRef.current.set(key, request);
    return request;
  }, []);

  const saveArtistData = useCallback((key: string, data: ArtistData) => {
    setArtistDataByName((current) => ({ ...current, [key]: data }));
  }, []);

  const artists = useMemo(() => {
    const map = new Map<string, Artist>();
    for (const track of tracks) {
      for (const name of artistNames(track)) {
        const key = artistKey(name);
        const existing = map.get(key);
        if (existing) {
          if (!existing.tracks.some((item) => item.id === track.id)) existing.tracks.push(track);
          if (track.album && !/^unknown album$/i.test(track.album)) existing.albums.add(track.album.toLocaleLowerCase());
          if (track.duration > 0) existing.duration += track.duration;
          continue;
        }
        map.set(key, {
          name,
          tracks: [track],
          albums: new Set(track.album && !/^unknown album$/i.test(track.album) ? [track.album.toLocaleLowerCase()] : []),
          duration: Math.max(0, track.duration),
        });
      }
    }
    return [...map.values()].sort((left, right) => left.name.localeCompare(right.name));
  }, [tracks]);

  const decodedArtist = view.startsWith("artist:")
    ? decodeURIComponent(view.slice("artist:".length))
    : null;
  const currentArtist = decodedArtist
    ? artists.find((artist) => artistKey(artist.name) === artistKey(decodedArtist)) ?? null
    : null;
  const visibleArtists = useMemo(
    () =>
      artists.filter((artist) =>
        artist.name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()),
      ),
    [artists, search],
  );
  const visibleArtistNames = useMemo(
    () => visibleArtists.map((artist) => artist.name).join("\0"),
    [visibleArtists],
  );
  const artistTracks = currentArtist?.tracks.filter((track) =>
    `${track.title} ${track.artist} ${track.album}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()),
  ) ?? [];

  useEffect(() => {
    if (view !== "artists") return;

    const pending = visibleArtists.filter((artist) => {
      const key = artistKey(artist.name);
      return !(key in artistDataRef.current);
    });
    for (const artist of pending) {
      const key = artistKey(artist.name);
      void loadArtistData(artist.name)
        .then((data) => saveArtistData(key, data))
        .catch((error) => console.warn("Artist lookup unavailable", error));
    }
  }, [loadArtistData, saveArtistData, view, visibleArtistNames, visibleArtists]);

  useEffect(() => {
    if (!currentArtist) return;
    let cancelled = false;
    const key = artistKey(currentArtist.name);
    const query = new URLSearchParams({ name: currentArtist.name });
    const artistDataRequest =
      artistDataRef.current[key]
        ? Promise.resolve(artistDataRef.current[key])
        : loadArtistData(currentArtist.name);

    void artistDataRequest
      .then((data) => {
        saveArtistData(key, data);
        if (!cancelled) setLoadedArtist(currentArtist.name);
      })
      .catch((error) => {
        console.warn("Artist lookup unavailable", error);
        if (!cancelled) setLoadedArtist(currentArtist.name);
      });
    void apiFetch(`/api/artists/profile?${query}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`Profile lookup failed (${response.status})`);
        return (await response.json()) as { profile: Record<string, unknown> | null };
      })
      .then(({ profile: nextProfile }) => {
        if (cancelled) return;
        setProfile(nextProfile);
        setLoadedArtist(currentArtist.name);
      })
      .catch((error) => {
        console.warn("Artist profile unavailable", error);
        if (!cancelled) {
          setProfile(null);
          setLoadedArtist(currentArtist.name);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [currentArtist, loadArtistData, saveArtistData]);

  if (view === "artists") {
    if (tracks.length === 0) {
      return <div className="empty"><div className="empty-orb" /><h3>Your library is empty</h3><p>Add songs to see their artists here.</p></div>;
    }
    if (!visibleArtists.length) {
      return <div className="empty"><div className="empty-orb" /><h3>No matches</h3><p>Try a different search term.</p></div>;
    }
    return (
      <div className={`artist-grid${listMode === "list" ? " list-mode" : ""}`}>
        {visibleArtists.map((artist) => {
          const key = artistKey(artist.name);
          const artistData = artistDataByName[key];
          const src = artistData?.picture;
          return (
            <article className={`artist-card${listMode === "list" ? " list-mode" : ""}`} key={artist.name}>
              <button
                className="artist-card-open"
                type="button"
                aria-label={`Open ${artist.name} page`}
                onClick={() => setView(`artist:${encodeURIComponent(artist.name)}`)}
              >
                {src ? (
                  <img
                    className="artist-card-photo"
                    src={src}
                    alt=""
                    onError={() => {
                      setArtistDataByName((current) => {
                        const data = current[key];
                        return data
                          ? { ...current, [key]: { ...data, picture: null } }
                          : current;
                      });
                    }}
                  />
                ) : (
                  <span className={`artist-card-photo${artistData ? " artist-card-photo-empty" : " artist-card-photo-loading"}`} aria-hidden="true" />
                )}
                <span className="artist-card-name">{artist.name}</span>
                <span className="artist-card-count">{artist.tracks.length} song{artist.tracks.length === 1 ? "" : "s"}</span>
              </button>
              <button
                className="artist-card-play"
                type="button"
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  const firstTrack = artist.tracks[0];
                  if (firstTrack) onPlay(artist.tracks, firstTrack.id);
                }}
              >▶ Play</button>
            </article>
          );
        })}
      </div>
    );
  }

  if (!currentArtist) {
    return <div className="empty"><div className="empty-orb" /><h3>Artist not found</h3><p>This artist no longer has songs in your library.</p><button className="btn" type="button" onClick={() => setView("artists")}>Back to artists</button></div>;
  }

  const loading = loadedArtist !== currentArtist.name;
  const activeProfile = loading ? null : profile;
  const currentArtistData = artistDataByName[artistKey(currentArtist.name)];
  const heroSrc = currentArtistData?.picture ?? null;
  const fallbackBio = currentArtistData
    ? currentArtistData.fans !== null
      ? `${currentArtistData.name} is a music artist with ${new Intl.NumberFormat().format(currentArtistData.fans)} Deezer fans.`
      : `${currentArtistData.name} has an artist profile on Deezer.`
    : "Artist information is not available right now.";
  const facts = ([
    ["Genre", activeProfile?.genre],
    ["Style", activeProfile?.style],
    ["Mood", activeProfile?.mood],
    ["Formed", activeProfile?.formed_year],
    ["Label", activeProfile?.label],
    ["Deezer fans", activeProfile?.followers ?? currentArtistData?.fans],
    ["Popularity", activeProfile?.popularity],
  ] satisfies Array<[string, unknown]>).filter(
    (entry): entry is [string, unknown] => Boolean(entry[1]),
  );
  const sourceUrl = safeExternalUrl(activeProfile?.source_url);
  const websiteUrl = safeExternalUrl(activeProfile?.website);
  const websiteLabel = String(activeProfile?.website_label ?? "Official website");

  return (
    <div className="artist-page">
      <header className="artist-hero">
        {heroSrc ? (
          <img
            className="artist-photo"
            src={heroSrc}
            alt={currentArtist.name}
            onError={() => {
              const key = artistKey(currentArtist.name);
              setArtistDataByName((current) => {
                const data = current[key];
                return data
                  ? { ...current, [key]: { ...data, picture: null } }
                  : current;
              });
            }}
          />
        ) : (
          <span className={`artist-photo${currentArtistData ? " artist-photo-empty" : " artist-photo-loading"}`} aria-hidden="true" />
        )}
        <div className="artist-hero-meta">
          <div className="artist-kicker">Artist</div>
          <h1 className="artist-name">{currentArtist.name}</h1>
          <div className="artist-sub">{currentArtist.tracks.length} song{currentArtist.tracks.length === 1 ? "" : "s"} in your library · {currentArtist.albums.size} album{currentArtist.albums.size === 1 ? "" : "s"}</div>
          <button
            className="btn btn-primary artist-hero-play"
            type="button"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              const firstTrack = currentArtist.tracks[0];
              if (firstTrack) onPlay(currentArtist.tracks, firstTrack.id);
            }}
          >▶ Play artist</button>
        </div>
      </header>
      <section className="artist-library-info" aria-label="Library information">
        <div className="artist-library-stat"><span>Songs</span><strong>{currentArtist.tracks.length}</strong></div>
        <div className="artist-library-stat"><span>Albums</span><strong>{currentArtist.albums.size}</strong></div>
        {currentArtist.duration ? <div className="artist-library-stat"><span>Play time</span><strong>{formatDuration(currentArtist.duration)}</strong></div> : null}
      </section>
      <section className="artist-info" aria-busy={loading}>
        <h2>About</h2>
        <p className="artist-bio">{loading ? "Looking up artist details…" : String(activeProfile?.bio ?? fallbackBio)}</p>
        {facts.length ? <div className="artist-tags">{facts.map(([label, value]) => <span className="artist-tag" key={label}>{label}: {String(value)}</span>)}</div> : null}
        {websiteUrl ? <a className="artist-website" href={websiteUrl} target="_blank" rel="noopener noreferrer">{websiteLabel} ↗</a> : null}
        {sourceUrl ? <><p className="artist-source">Source: {String(activeProfile?.source ?? "Verified artist information")}</p><a className="artist-website" href={sourceUrl} target="_blank" rel="noopener noreferrer">Source page ↗</a></> : null}
        {currentArtistData?.url ? <><p className="artist-source">Artist data: Deezer</p><a className="artist-website" href={currentArtistData.url} target="_blank" rel="noopener noreferrer">Deezer artist profile ↗</a></> : null}
      </section>
      {artistTracks.length ? (
        listMode === "grid" ? (
          <div className="grid">
            {artistTracks.map((track, index) => renderTrack(track, index, artistTracks))}
          </div>
        ) : (
          <div className="list">
            <div className="list-head"><div /><div>Title</div><div>Album</div><div>Time</div><div /></div>
            {artistTracks.map((track, index) => renderTrack(track, index, artistTracks))}
          </div>
        )
      ) : (
        <div className="empty">
          <h3>No matches</h3>
          <p>Try a different search term.</p>
        </div>
      )}
    </div>
  );
}
