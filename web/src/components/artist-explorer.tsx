"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { apiFetch } from "@/lib/api/client";
import { usePlayerStore, type ListMode, type TrackRecord } from "@/store/player-store";
import { useLanguage } from "@/lib/i18n";

interface Artist {
  name: string;
  tracks: TrackRecord[];
  albums: Set<string>;
  duration: number;
}

export function artistNames(track: TrackRecord): string[] {
  const names = track.artist
    .split(/\s*(?:,|;|\/|\bfeat(?:uring)?\.?|\bft\.?|\bwith\b)\s*/i)
    .flatMap((part) =>
      part
        .split(/\s+and\s+/i)
        .flatMap((name) => name.split(/\s+x\s+/)),
    )
    .map((part) => part.trim())
    .filter(Boolean);
  return [...new Set(names)];
}

interface ArtistImageInfo {
  audiodb_id: string | null;
  image_url: string | null;
  banner_url: string | null;
  status: "found" | "not_found" | "pending";
  user_photo_url: string | null;
  pending: boolean;
}

function coverUrlsForArtist(artist: Artist): string[] {
  const covers: string[] = [];
  const seen = new Set<string>();
  for (const track of artist.tracks) {
    if (
      !track.coverUrl ||
      (!track.hasCover &&
        !["embedded", "upload", "user", "musicbrainz", "audiodb"].includes(
          track.coverSource ?? "",
        ))
    ) continue;
    const album = track.album.trim().toLocaleLowerCase();
    const key = album && !/^unknown album$/i.test(album)
      ? `album:${album}`
      : `track:${track.coverUrl}`;
    if (seen.has(key)) continue;
    seen.add(key);
    covers.push(track.coverUrl);
    if (covers.length === 4) break;
  }
  return covers;
}

function formatDuration(seconds: number, t: (text: string) => string): string {
  const minutes = Math.round(seconds / 60);
  const hours = Math.floor(minutes / 60);
  return hours === 0
    ? `${minutes} ${t("min")}`
    : `${hours} ${t("hr")}${minutes % 60 ? ` ${minutes % 60} ${t("min")}` : ""}`;
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

function artistImageKey(name: string): string {
  return name
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]/gu, "");
}

function artistInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length > 1) return `${parts[0][0]}${parts.at(-1)?.[0]}`.toLocaleUpperCase();
  return (parts[0]?.slice(0, 2) || "?").toLocaleUpperCase();
}

function artistPhotoUrl(name: string, version = 0): string {
  const query = new URLSearchParams({ name });
  if (version) query.set("v", String(version));
  return `/api/artists/photo?${query}`;
}

function smallArtistImageUrl(value: unknown): string | null {
  const url = safeExternalUrl(value);
  if (!url) return null;
  try {
    const parsed = new URL(url);
    parsed.pathname = `${parsed.pathname.replace(/\/+$/, "")}/small`;
    return parsed.href;
  } catch {
    return null;
  }
}

function ArtistAvatar({
  name,
  className,
  userPhotoUrl,
  artistImageUrl,
  coverUrls,
}: {
  name: string;
  className: string;
  userPhotoUrl?: string | null;
  artistImageUrl?: string | null;
  coverUrls: string[];
}) {
  const candidates = useMemo(
    () =>
      [
        ...(userPhotoUrl ? [{ kind: "image" as const, url: userPhotoUrl }] : []),
        ...(artistImageUrl ? [{ kind: "image" as const, url: artistImageUrl }] : []),
        ...(coverUrls.length
          ? [{ kind: "covers" as const, url: coverUrls.join("|") }]
          : []),
      ],
    [artistImageUrl, coverUrls, userPhotoUrl],
  );
  const signature = candidates.map((candidate) => `${candidate.kind}:${candidate.url}`).join("\n");
  const [imageState, setImageState] = useState<{
    signature: string;
    failed: string[];
    loaded: string[];
  }>({ signature: "", failed: [], loaded: [] });
  const failed = imageState.signature === signature ? imageState.failed : [];
  const loaded = imageState.signature === signature ? imageState.loaded : [];
  const markLoaded = (url: string) => {
    setImageState((current) => ({
      signature,
      failed: current.signature === signature ? current.failed : [],
      loaded: current.signature === signature && current.loaded.includes(url)
        ? current.loaded
        : [...(current.signature === signature ? current.loaded : []), url],
    }));
  };
  const markFailed = (url: string) => {
    setImageState((current) => ({
      signature,
      failed: current.signature === signature && current.failed.includes(url)
        ? current.failed
        : [...(current.signature === signature ? current.failed : []), url],
      loaded: current.signature === signature ? current.loaded : [],
    }));
  };
  const active = candidates.find((candidate) => !failed.includes(candidate.url));
  let hash = 2_166_136_261;
  for (const character of name) {
    hash = Math.imul(hash ^ character.codePointAt(0)!, 16_777_619);
  }
  const hue = (hash >>> 0) % 360;
  const style = {
    "--artist-avatar-start": `hsl(${hue} 72% 28%)`,
    "--artist-avatar-end": `hsl(${(hue + 52) % 360} 76% 36%)`,
  } as CSSProperties;
  if (active?.kind === "image") {
    return (
      <img
        className={`${className} artist-avatar-image${loaded.includes(active.url) ? " is-loaded" : ""}`}
        src={active.url}
        alt={name}
        loading="lazy"
        decoding="async"
        onLoad={() => markLoaded(active.url)}
        onError={() => markFailed(active.url)}
      />
    );
  }
  if (active?.kind === "covers") {
    const covers = active.url.split("|");
    const mosaicClass = covers.length > 1
      ? ` artist-avatar-mosaic artist-avatar-mosaic-${covers.length}`
      : "";
    return (
      <span
        className={`${className} artist-avatar-covers${mosaicClass}`}
        role="img"
        aria-label={name}
      >
        {covers.slice(0, 4).map((url) => (
          <img
            className={`artist-avatar-image${loaded.includes(url) ? " is-loaded" : ""}`}
            src={url}
            alt=""
            key={url}
            loading="lazy"
            decoding="async"
            onLoad={() => markLoaded(url)}
            onError={() => markFailed(active.url)}
          />
        ))}
      </span>
    );
  }
  return (
    <span className={`${className} artist-avatar`} style={style} role="img" aria-label={name}>
      {artistInitials(name)}
    </span>
  );
}

function ArtistCardPhoto({
  name,
  t,
  userPhotoUrl,
  artistImageUrl,
  coverUrls,
  onOpen,
}: {
  name: string;
  t: (text: string) => string;
  userPhotoUrl?: string | null;
  artistImageUrl?: string | null;
  coverUrls: string[];
  onOpen: () => void;
}) {
  return (
    <button
      className="artist-card-photo-open"
      type="button"
      aria-label={`${t("Open artist page")}: ${name}`}
      onClick={onOpen}
    >
      <ArtistAvatar
        name={name}
        className="artist-card-photo"
        userPhotoUrl={userPhotoUrl}
        artistImageUrl={artistImageUrl}
        coverUrls={coverUrls}
      />
    </button>
  );
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
  const { language, t } = useLanguage();
  const tracks = usePlayerStore((state) => state.tracks);
  const setView = usePlayerStore((state) => state.setView);
  const [profileByArtist, setProfileByArtist] = useState<
    Record<string, Record<string, unknown> | null>
  >({});
  const [loadedProfiles, setLoadedProfiles] = useState<Record<string, boolean>>({});
  const [artistImageByKey, setArtistImageByKey] = useState<
    Record<string, ArtistImageInfo>
  >({});
  const [photoEditorOpen, setPhotoEditorOpen] = useState(false);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [photoPending, setPhotoPending] = useState(false);
  const [photoError, setPhotoError] = useState("");
  const [photoVersion, setPhotoVersion] = useState(0);
  const photoFileInputRef = useRef<HTMLInputElement>(null);
  const photoPreviewUrlRef = useRef<string | null>(null);

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

  const shouldLoadArtistImages = view === "artists" || view.startsWith("artist:");
  useEffect(() => {
    if (!shouldLoadArtistImages) return;
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | null = null;
    const loadImages = async () => {
      controller = new AbortController();
      const timeout = setTimeout(() => controller?.abort(), 10_000);
      try {
        const response = await apiFetch("/api/artists/images", {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error(`Artist image lookup failed (${response.status})`);
        const payload = (await response.json()) as {
          artists?: Record<string, ArtistImageInfo>;
        };
        if (cancelled) return;
        const nextImages = payload.artists ?? {};
        setArtistImageByKey((current) => ({ ...current, ...nextImages }));
        if (Object.values(nextImages).some((item) => item.pending)) {
          retryTimer = setTimeout(() => void loadImages(), 5_000);
        }
      } catch (error) {
        if (cancelled) return;
        console.warn("Artist images unavailable", error);
        retryTimer = setTimeout(() => void loadImages(), 15_000);
      } finally {
        clearTimeout(timeout);
      }
    };
    void loadImages();
    return () => {
      cancelled = true;
      controller?.abort();
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [shouldLoadArtistImages]);

  useEffect(() => {
    if (!currentArtist) return;
    const key = `${artistKey(currentArtist.name)}:${language}`;
    if (loadedProfiles[key]) return;
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let activeController: AbortController | null = null;
    const query = new URLSearchParams({ name: currentArtist.name, language });
    const loadProfile = async (attempt: number) => {
      activeController = new AbortController();
      const timeout = setTimeout(() => activeController?.abort(), 8_000);
      try {
        const response = await apiFetch(`/api/artists/profile?${query}`, {
          signal: activeController.signal,
        });
        if (!response.ok) throw new Error(`Profile lookup failed (${response.status})`);
        const { profile: nextProfile } = (await response.json()) as {
          profile: Record<string, unknown> | null;
        };
        if (cancelled) return;
        setProfileByArtist((current) => ({
          ...current,
          [key]: nextProfile ?? null,
        }));
        setLoadedProfiles((current) => ({ ...current, [key]: true }));
      } catch (error) {
        if (cancelled) return;
        console.warn("Artist profile unavailable", error);
        if (attempt < 2) {
          retryTimer = setTimeout(() => void loadProfile(attempt + 1), 1_000 * (attempt + 1));
        } else {
          setProfileByArtist((current) => ({ ...current, [key]: null }));
        }
      } finally {
        clearTimeout(timeout);
      }
    };
    void loadProfile(0);
    return () => {
      cancelled = true;
      activeController?.abort();
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [currentArtist, language, loadedProfiles]);

  if (view === "artists") {
    if (tracks.length === 0) {
      return <div className="empty"><div className="empty-orb" /><h3>{t("Your library is empty")}</h3><p>{t("Add songs to see their artists here.")}</p></div>;
    }
    if (!visibleArtists.length) {
      return <div className="empty"><div className="empty-orb" /><h3>{t("No matches")}</h3><p>{t("Try a different search term.")}</p></div>;
    }
    return (
      <div className={`artist-grid${listMode === "list" ? " list-mode" : ""}`}>
        {visibleArtists.map((artist) => {
          const openArtist = () =>
            setView(`artist:${encodeURIComponent(artist.name)}`);
          const imageInfo = artistImageByKey[artistImageKey(artist.name)];
          return (
            <article
              className={`artist-card${listMode === "list" ? " list-mode" : ""}`}
              key={artist.name}
              data-artist-name={artist.name}
            >
              <ArtistCardPhoto
                name={artist.name}
                t={t}
                userPhotoUrl={
                  imageInfo?.user_photo_url
                    ? artistPhotoUrl(artist.name, photoVersion)
                    : null
                }
                artistImageUrl={smallArtistImageUrl(imageInfo?.image_url)}
                coverUrls={coverUrlsForArtist(artist)}
                onOpen={openArtist}
              />
              <button
                className="artist-card-open"
                type="button"
                onClick={openArtist}
              >
                <span className="artist-card-name">{artist.name}</span>
                <span className="artist-card-count">
                  {artist.tracks.length} {t(artist.tracks.length === 1 ? "song" : "songs")}
                </span>
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
              >▶ {t("Play")}</button>
            </article>
          );
        })}
      </div>
    );
  }

  if (!currentArtist) {
    return <div className="empty"><div className="empty-orb" /><h3>{t("Artist not found")}</h3><p>{t("This artist no longer has songs in your library.")}</p><button className="btn" type="button" onClick={() => setView("artists")}>{t("Back to artists")}</button></div>;
  }

  const currentProfileKey = `${artistKey(currentArtist.name)}:${language}`;
  const artistName = currentArtist.name;
  const loading = !loadedProfiles[currentProfileKey];
  const activeProfile = loading ? null : profileByArtist[currentProfileKey];
  const imageInfo = artistImageByKey[artistImageKey(currentArtist.name)];
  const userPhotoUrl = imageInfo?.user_photo_url
    ? artistPhotoUrl(currentArtist.name, photoVersion)
    : null;
  const audioDbPhotoUrl = safeExternalUrl(imageInfo?.image_url);
  const artistCovers = coverUrlsForArtist(currentArtist);
  const facts = ([
    [t("Genre"), activeProfile?.genre],
    [t("Style"), activeProfile?.style],
    [t("Mood"), activeProfile?.mood],
    [t("Formed"), activeProfile?.formed_year],
    [t("Label"), activeProfile?.label],
  ] satisfies Array<[string, unknown]>).filter(
    (entry): entry is [string, unknown] => Boolean(entry[1]),
  );
  const sourceUrl = safeExternalUrl(activeProfile?.source_url);
  const wikipediaSource =
    activeProfile?.source === "Wikipedia" || activeProfile?.source === "Wikipédia";
  const websiteUrl = safeExternalUrl(activeProfile?.website);
  const websiteLabel = t(String(activeProfile?.website_label ?? "Official website"));
  const songLabel = t(currentArtist.tracks.length === 1 ? "song" : "songs");
  const albumLabel = t(currentArtist.albums.size === 1 ? "album" : "albums");

  function closePhotoEditor() {
    if (photoPreviewUrlRef.current) URL.revokeObjectURL(photoPreviewUrlRef.current);
    photoPreviewUrlRef.current = null;
    setPhotoPreview(null);
    setPhotoFile(null);
    setPhotoError("");
    setPhotoEditorOpen(false);
  }

  async function saveArtistPhoto() {
    if (!photoFile) {
      setPhotoError(t("Choose an artist photo."));
      return;
    }
    setPhotoPending(true);
    setPhotoError("");
    try {
      const form = new FormData();
      form.append("name", artistName);
      form.append("file", photoFile);
      const response = await apiFetch(
        "/api/artists/photo",
        { method: "PUT", body: form },
        { csrf: true, retryCsrfOnForbidden: true },
      );
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as
          | { detail?: string }
          | null;
        throw new Error(payload?.detail ?? t("Could not update artist photo."));
      }
      closePhotoEditor();
      const photoUrl = artistPhotoUrl(artistName, photoVersion + 1);
      setPhotoVersion((version) => version + 1);
      setArtistImageByKey((current) => ({
        ...current,
        [artistImageKey(artistName)]: {
          ...(current[artistImageKey(artistName)] ?? {
            audiodb_id: null,
            image_url: null,
            banner_url: null,
            status: "pending",
            pending: true,
          }),
          user_photo_url: photoUrl,
        },
      }));
    } catch (error) {
      setPhotoError(error instanceof Error ? error.message : t("Could not update artist photo."));
    } finally {
      setPhotoPending(false);
    }
  }

  async function removeArtistPhoto() {
    setPhotoPending(true);
    setPhotoError("");
    try {
      const query = new URLSearchParams({ name: artistName });
      const response = await apiFetch(
        `/api/artists/photo?${query}`,
        { method: "DELETE" },
        { csrf: true, retryCsrfOnForbidden: true },
      );
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as
          | { detail?: string }
          | null;
        throw new Error(payload?.detail ?? t("Could not remove artist photo."));
      }
      setPhotoVersion((version) => version + 1);
      setArtistImageByKey((current) => ({
        ...current,
        [artistImageKey(artistName)]: {
          ...(current[artistImageKey(artistName)] ?? {
            audiodb_id: null,
            image_url: null,
            banner_url: null,
            status: "pending",
            pending: true,
          }),
          user_photo_url: null,
        },
      }));
    } catch (error) {
      setPhotoError(error instanceof Error ? error.message : t("Could not remove artist photo."));
    } finally {
      setPhotoPending(false);
    }
  }

  return (
    <div className="artist-page">
      <header className="artist-hero">
        <figure className="artist-photo-wrap">
          <ArtistAvatar
            name={currentArtist.name}
            className="artist-photo"
            userPhotoUrl={photoPreview ?? userPhotoUrl}
            artistImageUrl={audioDbPhotoUrl}
            coverUrls={artistCovers}
          />
        </figure>
        <div className="artist-hero-meta">
          <div className="artist-kicker">{t("Artist")}</div>
          <h1 className="artist-name">{currentArtist.name}</h1>
          <div className="artist-sub">
            {currentArtist.tracks.length} {songLabel} {t("in your library")} · {currentArtist.albums.size} {albumLabel}
          </div>
          <button
            className="btn btn-primary artist-hero-play"
            type="button"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              const firstTrack = currentArtist.tracks[0];
              if (firstTrack) onPlay(currentArtist.tracks, firstTrack.id);
            }}
          >▶ {t("Play artist")}</button>
          <div className="artist-photo-actions">
            <button
              className="btn"
              type="button"
              onClick={() => {
                setPhotoError("");
                setPhotoEditorOpen(true);
              }}
            >
              {t("Change image")}
            </button>
            {userPhotoUrl ? (
              <button
                className="btn btn-danger"
                type="button"
                onClick={() => void removeArtistPhoto()}
                disabled={photoPending}
              >
                {t("Remove photo")}
              </button>
            ) : null}
          </div>
        </div>
      </header>
      {photoError && !photoEditorOpen ? (
        <p className="artist-photo-error" role="alert">{photoError}</p>
      ) : null}
      <section className="artist-library-info" aria-label={t("Library information")}>
        <div className="artist-library-stat"><span>{t("Songs")}</span><strong>{currentArtist.tracks.length}</strong></div>
        <div className="artist-library-stat"><span>{t("Albums")}</span><strong>{currentArtist.albums.size}</strong></div>
        {currentArtist.duration ? <div className="artist-library-stat"><span>{t("Play time")}</span><strong>{formatDuration(currentArtist.duration, t)}</strong></div> : null}
      </section>
      <section className="artist-info" aria-busy={loading}>
        <h2>{t("About")}</h2>
        <p className="artist-bio">{loading ? t("Looking up artist details…") : String(activeProfile?.bio ?? t("No artist information is available yet."))}</p>
        {sourceUrl && wikipediaSource ? (
          <p className="artist-source">
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
              {t("Source: Wikipedia")}
            </a>
            {" · "}
            <a
              href="https://creativecommons.org/licenses/by-sa/4.0/"
              target="_blank"
              rel="noopener noreferrer"
            >
              CC BY-SA 4.0
            </a>
            {activeProfile?.source_modified === "true"
              ? ` · ${t("Shortened or adapted")}`
              : ""}
          </p>
        ) : null}
        {facts.length ? <div className="artist-tags">{facts.map(([label, value]) => <span className="artist-tag" key={label}>{label}: {String(value)}</span>)}</div> : null}
        {websiteUrl ? <a className="artist-website" href={websiteUrl} target="_blank" rel="noopener noreferrer">{websiteLabel} ↗</a> : null}
        {sourceUrl && !wikipediaSource ? <><p className="artist-source">{t("Source")}: {t(String(activeProfile?.source ?? t("Artist profile")))}</p><a className="artist-website" href={sourceUrl} target="_blank" rel="noopener noreferrer">{t("Source page ↗")}</a></> : null}
      </section>
      {artistTracks.length ? (
        listMode === "grid" ? (
          <div className="grid">
            {artistTracks.map((track, index) => renderTrack(track, index, artistTracks))}
          </div>
        ) : (
          <div className="list">
            <div className="list-head"><div /><div>{t("Title")}</div><div>{t("Album")}</div><div>{t("Time")}</div><div /></div>
            {artistTracks.map((track, index) => renderTrack(track, index, artistTracks))}
          </div>
        )
      ) : (
        <div className="empty">
          <h3>{t("No matches")}</h3>
          <p>{t("Try a different search term.")}</p>
        </div>
      )}
      {photoEditorOpen ? (
        <div
          className="queue-picker-overlay open"
          role="dialog"
          aria-modal="true"
          aria-labelledby="artistPhotoEditorTitle"
          onClick={(event) => {
            if (event.target === event.currentTarget && !photoPending) closePhotoEditor();
          }}
        >
          <section className="queue-picker-card track-editor-card artist-photo-editor">
            <div className="queue-picker-head">
              <h3 id="artistPhotoEditorTitle">{t("Photo for")} {currentArtist.name}</h3>
              <button
                className="icon-btn"
                type="button"
                aria-label={t("Close")}
                onClick={closePhotoEditor}
                disabled={photoPending}
              >×</button>
            </div>
            <ArtistAvatar
              name={currentArtist.name}
              className="artist-photo-preview"
              userPhotoUrl={photoPreview ?? userPhotoUrl}
              artistImageUrl={audioDbPhotoUrl}
              coverUrls={artistCovers}
            />
            <p className="track-editor-help">{t("JPEG, PNG, or WebP; up to 5 MB.")}</p>
            <input
              ref={photoFileInputRef}
              className="hidden-input"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(event) => {
                const selected = event.currentTarget.files?.[0] ?? null;
                event.currentTarget.value = "";
                if (!selected) return;
                if (selected.size > 5 * 1024 * 1024) {
                  setPhotoFile(null);
                  setPhotoPreview(null);
                  if (photoPreviewUrlRef.current) URL.revokeObjectURL(photoPreviewUrlRef.current);
                  photoPreviewUrlRef.current = null;
                  setPhotoError(t("Artist photo must be 5 MB or smaller."));
                  return;
                }
                if (!["image/jpeg", "image/png", "image/webp"].includes(selected.type)) {
                  setPhotoFile(null);
                  setPhotoPreview(null);
                  if (photoPreviewUrlRef.current) URL.revokeObjectURL(photoPreviewUrlRef.current);
                  photoPreviewUrlRef.current = null;
                  setPhotoError(t("Choose a JPEG, PNG, or WebP image."));
                  return;
                }
                if (photoPreviewUrlRef.current) URL.revokeObjectURL(photoPreviewUrlRef.current);
                const previewUrl = URL.createObjectURL(selected);
                photoPreviewUrlRef.current = previewUrl;
                setPhotoFile(selected);
                setPhotoPreview(previewUrl);
                setPhotoError("");
              }}
            />
            <div className="track-editor-error" role="alert">{photoError}</div>
            <div className="playlist-name-actions">
              <button
                className="btn"
                type="button"
                onClick={() => photoFileInputRef.current?.click()}
                disabled={photoPending}
              >{t("Choose photo")}</button>
              <button
                className="btn btn-primary"
                type="button"
                onClick={() => void saveArtistPhoto()}
                disabled={photoPending || !photoFile}
              >
                {photoPending ? t("Saving photo…") : t("Save photo")}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
