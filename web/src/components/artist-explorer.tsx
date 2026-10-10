"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { apiFetch } from "@/lib/api/client";
import { usePlayerStore, type ListMode, type TrackRecord } from "@/store/player-store";

interface Artist {
  name: string;
  tracks: TrackRecord[];
  albums: Set<string>;
  duration: number;
}

interface ArtistPhotoData {
  picture: string | null;
  nb_fan: number | null;
  lookupPending: boolean;
}

interface ArtistImagesResponse {
  artists: Array<{ name: string; image_url: string | null; lookup_pending: boolean }>;
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
  const [photoByArtist, setPhotoByArtist] = useState<Record<string, ArtistPhotoData>>({});
  const photoByArtistRef = useRef(photoByArtist);
  const [profileByArtist, setProfileByArtist] = useState<
    Record<string, Record<string, unknown> | null>
  >({});
  const [loadedProfiles, setLoadedProfiles] = useState<Record<string, boolean>>({});

  useEffect(() => {
    photoByArtistRef.current = photoByArtist;
  }, [photoByArtist]);

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
  const artistTracks = currentArtist?.tracks.filter((track) =>
    `${track.title} ${track.artist} ${track.album}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()),
  ) ?? [];

  useEffect(() => {
    if (view !== "artists") return;
    const needsRefresh = artists.some((artist) => {
      const cached = photoByArtistRef.current[artistKey(artist.name)];
      return !cached || cached.lookupPending;
    });
    if (!needsRefresh) return;

    let cancelled = false;
    let refreshTimer: ReturnType<typeof setTimeout> | undefined;
    const refresh = async () => {
      try {
        const response = await apiFetch("/api/artists");
        if (!response.ok) throw new Error(`Artist image lookup failed (${response.status})`);
        const payload = (await response.json()) as ArtistImagesResponse;
        if (cancelled) return;
        setPhotoByArtist((current) => {
          const next = { ...current };
          for (const artist of payload.artists) {
            next[artistKey(artist.name)] = {
              picture: artist.image_url,
              nb_fan: null,
              lookupPending: artist.lookup_pending,
            };
          }
          return next;
        });
        if (payload.artists.some((artist) => artist.lookup_pending)) {
          refreshTimer = setTimeout(() => void refresh(), 2500);
        }
      } catch (error) {
        console.warn("Artist images unavailable", error);
      }
    };
    void refresh();
    return () => {
      cancelled = true;
      if (refreshTimer) clearTimeout(refreshTimer);
    };
  }, [artists, view]);

  useEffect(() => {
    if (!currentArtist) return;
    const key = artistKey(currentArtist.name);
    if (loadedProfiles[key]) return;
    let cancelled = false;
    const query = new URLSearchParams({ name: currentArtist.name });
    void apiFetch(`/api/artists/profile?${query}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`Profile lookup failed (${response.status})`);
        return (await response.json()) as { profile: Record<string, unknown> | null };
      })
      .then(({ profile: nextProfile }) => {
        if (cancelled) return;
        setProfileByArtist((current) => ({ ...current, [key]: nextProfile }));
        setLoadedProfiles((current) => ({ ...current, [key]: true }));
      })
      .catch((error) => {
        console.warn("Artist profile unavailable", error);
        if (!cancelled) {
          setProfileByArtist((current) => ({ ...current, [key]: null }));
          setLoadedProfiles((current) => ({ ...current, [key]: true }));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [currentArtist, loadedProfiles]);

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
          const artistPhoto = photoByArtist[key];
          const src = artistPhoto
            ? artistPhoto.picture
            : artist.tracks.find((track) => track.artistImageUrl)?.artistImageUrl ?? null;
          return (
            <article
              className={`artist-card${listMode === "list" ? " list-mode" : ""}`}
              key={artist.name}
              data-artist-name={artist.name}
            >
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
                    width={128}
                    height={128}
                    loading="lazy"
                    decoding="async"
                    referrerPolicy="no-referrer"
                    onError={() => {
                      setPhotoByArtist((current) => {
                        const data = current[key];
                        return data?.picture
                          ? { ...current, [key]: { ...data, picture: null } }
                          : current;
                      });
                    }}
                  />
                ) : (
                  <span className={`artist-card-photo${artistPhoto ? " artist-card-photo-empty" : " artist-card-photo-loading"}`} aria-hidden="true">{artist.name.charAt(0).toLocaleUpperCase()}</span>
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

  const currentArtistKey = artistKey(currentArtist.name);
  const loading = !loadedProfiles[currentArtistKey];
  const activeProfile = loading ? null : profileByArtist[currentArtistKey];
  const currentArtistPhoto = photoByArtist[currentArtistKey];
  const heroSrc = currentArtistPhoto?.picture;
  const facts = ([
    ["Genre", activeProfile?.genre],
    ["Style", activeProfile?.style],
    ["Mood", activeProfile?.mood],
    ["Formed", activeProfile?.formed_year],
    ["Label", activeProfile?.label],
    ["Followers", activeProfile?.followers],
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
            width={320}
            height={320}
            loading="lazy"
            decoding="async"
            referrerPolicy="no-referrer"
            onError={() => {
              const key = artistKey(currentArtist.name);
              setPhotoByArtist((current) => {
                const data = current[key];
                return data
                  ? { ...current, [key]: { ...data, picture: null } }
                  : current;
              });
            }}
          />
        ) : (
          <span className={`artist-photo${currentArtistPhoto ? " artist-photo-empty" : " artist-photo-loading"}`} aria-hidden="true">{currentArtist.name.charAt(0).toLocaleUpperCase()}</span>
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
        <p className="artist-bio">{loading ? "Looking up artist details…" : String(activeProfile?.bio ?? "No verified artist information is available yet.")}</p>
        {facts.length ? <div className="artist-tags">{facts.map(([label, value]) => <span className="artist-tag" key={label}>{label}: {String(value)}</span>)}</div> : null}
        {websiteUrl ? <a className="artist-website" href={websiteUrl} target="_blank" rel="noopener noreferrer">{websiteLabel} ↗</a> : null}
        {sourceUrl ? <><p className="artist-source">Source: {String(activeProfile?.source ?? "Verified artist information")}</p><a className="artist-website" href={sourceUrl} target="_blank" rel="noopener noreferrer">Source page ↗</a></> : null}
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
