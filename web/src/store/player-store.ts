"use client";

import { create } from "zustand";

export type RepeatMode = "off" | "all" | "one";
export type LibraryView =
  | "library"
  | "favorites"
  | "playlists"
  | "artists"
  | "account"
  | `playlist:${string}`
  | `artist:${string}`;
export type ListMode = "grid" | "list";

export interface TrackRecord {
  id: string;
  title: string;
  artist: string;
  album: string;
  duration: number;
  coverUrl: string;
  streamUrl: string;
  offlineUrl?: string | null;
  offline?: boolean;
  remoteCoverUrl?: string;
  favorite: boolean;
  customLyrics?: string | null;
}

export interface PlaylistRecord {
  id: string;
  name: string;
  trackIds: string[];
}

interface PlayerStore {
  audioElement: HTMLAudioElement | null;
  tracks: TrackRecord[];
  playlists: PlaylistRecord[];
  queue: string[];
  queueIndex: number;
  view: LibraryView;
  listMode: ListMode;
  repeat: RepeatMode;
  shuffle: boolean;
  isPlaying: boolean;
  setAudioElement: (audioElement: HTMLAudioElement | null) => void;
  setTracks: (tracks: TrackRecord[]) => void;
  setLibraryMeta: (favorites: string[], playlists: PlaylistRecord[]) => void;
  setQueue: (queue: string[], queueIndex: number) => void;
  setQueueIndex: (queueIndex: number) => void;
  setView: (view: LibraryView) => void;
  setListMode: (listMode: ListMode) => void;
  setRepeat: (repeat: RepeatMode) => void;
  setShuffle: (shuffle: boolean) => void;
  setPlaying: (isPlaying: boolean) => void;
  toggleFavorite: (trackId: string) => void;
  setPlaylists: (playlists: PlaylistRecord[]) => void;
  setTrackLyrics: (trackId: string, lyrics: string) => void;
}

export const usePlayerStore = create<PlayerStore>((set) => ({
  audioElement: null,
  tracks: [],
  playlists: [],
  queue: [],
  queueIndex: -1,
  view: "library",
  listMode: "grid",
  repeat: "off",
  shuffle: false,
  isPlaying: false,
  setAudioElement: (audioElement) => set({ audioElement }),
  setTracks: (tracks) => set({ tracks }),
  setLibraryMeta: (favorites, playlists) => {
    const favoriteIds = new Set(favorites);
    set((state) => ({
      tracks: state.tracks.map((track) => ({
        ...track,
        favorite: favoriteIds.has(track.id),
      })),
      playlists,
    }));
  },
  setQueue: (queue, queueIndex) => set({ queue, queueIndex }),
  setQueueIndex: (queueIndex) => set({ queueIndex }),
  setView: (view) => set({ view }),
  setListMode: (listMode) => {
    set({ listMode });
    if (typeof window !== "undefined") {
      window.localStorage.setItem("vervfy:list-mode", listMode);
    }
  },
  setRepeat: (repeat) => set({ repeat }),
  setShuffle: (shuffle) => set({ shuffle }),
  setPlaying: (isPlaying) => set({ isPlaying }),
  toggleFavorite: (trackId) =>
    set((state) => ({
      tracks: state.tracks.map((track) =>
        track.id === trackId ? { ...track, favorite: !track.favorite } : track,
      ),
    })),
  setPlaylists: (playlists) => set({ playlists }),
  setTrackLyrics: (trackId, customLyrics) =>
    set((state) => ({
      tracks: state.tracks.map((track) =>
        track.id === trackId ? { ...track, customLyrics } : track,
      ),
    })),
}));
