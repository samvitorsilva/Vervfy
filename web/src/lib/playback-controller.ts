"use client";

import { apiFetch, expectOk } from "@/lib/api/client";
import { usePlayerStore, type TrackRecord } from "@/store/player-store";

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
  automaticTransition: boolean;
  retryableNetworkFailure: boolean;
  recovering: boolean;
  recoveryPosition: number | null;
  signedUrlRefreshed: boolean;
  listenedSeconds: number;
  lastListenPosition: number | null;
  listenRecorded: boolean;
}

const MAX_PLAYBACK_RETRIES = 3;
const PLAYBACK_STALL_TIMEOUT_MS = 5_000;
const PLAYBACK_START_TIMEOUT_MS = 15_000;
const SKIP_DEBOUNCE_MS = 400;

function logAudioFailure(
  context: string,
  audio: HTMLAudioElement,
  error: unknown,
): void {
  const errorName =
    error instanceof Error
      ? error.name
      : error &&
          typeof error === "object" &&
          "name" in error &&
          typeof error.name === "string"
        ? error.name
        : "UnknownError";
  console.warn(`[audio] ${context}`, {
    name: errorName,
    code: audio.error?.code ?? null,
    networkState: audio.networkState,
    readyState: audio.readyState,
  });
}

export interface PlaybackUiCallbacks {
  notify: (message: string) => void;
  listeningUpdated: () => void;
}

export class PlaybackController {
  private attempt: PlaybackAttempt | null = null;
  private startTimer: number | null = null;
  private endTransitionPending = false;
  private automaticFailureSkips = 0;
  private sleepTimerEndsAt: number | null = null;
  private sleepTimer: number | null = null;
  private shufflePlayed = new Set<number>();
  private playlistId: string | null = null;
  private lastPlaybackTime: number;
  private activeTrack: TrackRecord | null = null;
  private uiCallbacks: PlaybackUiCallbacks | null = null;
  private unsubscribeStore: (() => void) | null = null;
  private readonly mediaSession: MediaSession | null;

  constructor(private readonly audio: HTMLAudioElement) {
    this.lastPlaybackTime = audio.currentTime;
    this.mediaSession = navigator.mediaSession ?? null;

    audio.addEventListener("timeupdate", this.onTimeUpdate);
    audio.addEventListener("loadedmetadata", this.onMetadata);
    audio.addEventListener("durationchange", this.onMetadata);
    audio.addEventListener("seeked", this.onSeeked);
    audio.addEventListener("playing", this.onPlaying);
    audio.addEventListener("waiting", this.onBuffering);
    audio.addEventListener("stalled", this.onBuffering);
    audio.addEventListener("play", this.onPlay);
    audio.addEventListener("pause", this.onPause);
    audio.addEventListener("ended", this.onEnded);
    audio.addEventListener("error", this.onError);
    document.addEventListener("visibilitychange", this.onVisibilityChange);
    window.addEventListener("pageshow", this.onVisibilityChange);
    window.addEventListener("online", this.onOnline);

    this.installMediaSessionActions();
    this.unsubscribeStore = usePlayerStore.subscribe((state) => {
      const activeId = state.queue[state.queueIndex];
      const track = state.tracks.find((item) => item.id === activeId) ?? null;
      if (track !== this.activeTrack) {
        this.activeTrack = track;
        this.updateMediaMetadata();
      }
      if (state.sleepTimerEndsAt !== this.sleepTimerEndsAt) {
        this.sleepTimerEndsAt = state.sleepTimerEndsAt;
        this.scheduleSleepTimer();
      }
    });
    const state = usePlayerStore.getState();
    this.activeTrack =
      state.tracks.find((item) => item.id === state.queue[state.queueIndex]) ?? null;
    this.sleepTimerEndsAt = state.sleepTimerEndsAt;
    this.updateMediaMetadata();
    this.scheduleSleepTimer();
  }

  setUiCallbacks(callbacks: PlaybackUiCallbacks | null): void {
    this.uiCallbacks = callbacks;
  }

  setPlaylistContext(playlistId: string | null): void {
    this.playlistId = playlistId;
  }

  setInitialShuffleHistory(index: number): void {
    this.shufflePlayed = new Set([index]);
  }

  clearShuffleHistory(): void {
    this.shufflePlayed.clear();
  }

  startTrack(
    trackId: string,
    debounceSkip = false,
    automaticTransition = false,
  ): void {
    if (this.startTimer !== null) {
      window.clearTimeout(this.startTimer);
      this.startTimer = null;
    }

    if (debounceSkip) {
      this.cancelAttempt();
      this.audio.pause();
      this.audio.removeAttribute("src");
      this.audio.load();
      this.startTimer = window.setTimeout(() => {
        this.startTimer = null;
        this.beginTrack(trackId, automaticTransition);
      }, SKIP_DEBOUNCE_MS);
      return;
    }
    this.beginTrack(trackId, automaticTransition);
  }

  playQueueIndex(
    index: number,
    debounceSkip = false,
    automaticTransition = false,
  ): void {
    const trackId = usePlayerStore.getState().queue[index];
    if (!trackId) return;
    usePlayerStore.getState().setQueueIndex(index);
    this.startTrack(trackId, debounceSkip, automaticTransition);
  }

  playNext(automatic: boolean, skipFailedTrack = false): void {
    const state = usePlayerStore.getState();
    if (!state.queue.length) return;

    if (automatic && state.repeat === "one" && !skipFailedTrack) {
      this.audio.currentTime = 0;
      if (this.attempt) {
        this.attempt.wantsPlayback = true;
        this.attempt.failed = false;
        this.attempt.recovering = false;
        this.attempt.recoveryPosition = null;
      }
      void this.audio.play().catch((error: unknown) => {
        if (this.attempt) {
          this.handlePlaybackFailure(
            this.attempt,
            error,
            "The track could not restart. Please try again.",
          );
        } else {
          this.notify("The track could not restart. Please try again.");
        }
      });
      return;
    }

    let nextIndex = state.queueIndex + 1;
    if (state.shuffle) {
      this.shufflePlayed.add(state.queueIndex);
      let choices = state.queue
        .map((_, index) => index)
        .filter((index) => index !== state.queueIndex);
      if (automatic && state.repeat === "off") {
        choices = choices.filter((index) => !this.shufflePlayed.has(index));
        if (!choices.length) {
          this.pauseAtQueueEnd();
          return;
        }
      } else if (
        automatic &&
        state.repeat === "all" &&
        !choices.some((index) => !this.shufflePlayed.has(index))
      ) {
        this.shufflePlayed = new Set([state.queueIndex]);
      }
      if (!choices.length) choices = [state.queueIndex];
      nextIndex = choices[Math.floor(Math.random() * choices.length)];
      this.shufflePlayed.add(nextIndex);
    } else if (nextIndex >= state.queue.length) {
      // Match prior library behavior: wrap the queue even when repeat is off.
      // Shuffle + repeat-off still stops after every track has played once.
      nextIndex = 0;
    }
    this.playQueueIndex(nextIndex, !automatic, automatic);
  }

  playPrevious(): void {
    const state = usePlayerStore.getState();
    if (!state.queue.length) return;
    if (this.audio.currentTime > 3) {
      this.audio.currentTime = 0;
      return;
    }
    this.playQueueIndex(Math.max(0, state.queueIndex - 1), true);
  }

  togglePlayback(trackId: string | null): void {
    if (!trackId) return;
    if (!this.audio.paused) {
      this.pause();
      return;
    }
    this.startTrack(trackId);
  }

  pause(): void {
    if (this.attempt) {
      this.attempt.wantsPlayback = false;
      this.attempt.recovering = false;
      this.attempt.requestId += 1;
      this.clearAttemptTimers(this.attempt);
    }
    this.audio.pause();
    const state = usePlayerStore.getState();
    state.setPlaying(false);
    state.setPlaybackStatus("paused");
  }

  stop(): void {
    this.cancelAttempt();
    this.audio.pause();
    this.audio.removeAttribute("src");
    this.audio.load();
    const state = usePlayerStore.getState();
    state.setPlaying(false);
    state.setPlaybackStatus("paused");
  }

  dispose(): void {
    if (this.startTimer !== null) window.clearTimeout(this.startTimer);
    this.startTimer = null;
    if (this.sleepTimer !== null) window.clearTimeout(this.sleepTimer);
    this.sleepTimer = null;
    this.cancelAttempt();
    this.audio.removeEventListener("timeupdate", this.onTimeUpdate);
    this.audio.removeEventListener("loadedmetadata", this.onMetadata);
    this.audio.removeEventListener("durationchange", this.onMetadata);
    this.audio.removeEventListener("seeked", this.onSeeked);
    this.audio.removeEventListener("playing", this.onPlaying);
    this.audio.removeEventListener("waiting", this.onBuffering);
    this.audio.removeEventListener("stalled", this.onBuffering);
    this.audio.removeEventListener("play", this.onPlay);
    this.audio.removeEventListener("pause", this.onPause);
    this.audio.removeEventListener("ended", this.onEnded);
    this.audio.removeEventListener("error", this.onError);
    document.removeEventListener("visibilitychange", this.onVisibilityChange);
    window.removeEventListener("pageshow", this.onVisibilityChange);
    window.removeEventListener("online", this.onOnline);
    this.unsubscribeStore?.();
    this.unsubscribeStore = null;
    for (const action of this.mediaActions) {
      try {
        this.mediaSession?.setActionHandler(action, null);
      } catch {
        // Unsupported actions are ignored by the browser.
      }
    }
  }

  private readonly mediaActions: MediaSessionAction[] = [
    "play",
    "pause",
    "previoustrack",
    "nexttrack",
    "seekbackward",
    "seekforward",
    "seekto",
  ];

  private installMediaSessionActions(): void {
    if (!this.mediaSession) return;
    const actions: Array<[MediaSessionAction, MediaSessionActionHandler]> = [
      ["play", () => this.togglePlayback(this.currentTrackId())],
      ["pause", () => this.pause()],
      ["previoustrack", () => this.playPrevious()],
      ["nexttrack", () => this.playNext(false)],
      ["seekbackward", (details) =>
        this.seek(-(Number(details.seekOffset) || 10))],
      ["seekforward", (details) =>
        this.seek(Number(details.seekOffset) || 10)],
      ["seekto", (details) => {
        if (Number.isFinite(details.seekTime)) {
          this.audio.currentTime = Math.max(
            0,
            Math.min(this.audio.duration || Infinity, details.seekTime ?? 0),
          );
        }
      }],
    ];
    for (const [action, handler] of actions) {
      try {
        this.mediaSession.setActionHandler(action, handler);
      } catch {
        // Unsupported actions are ignored by the browser.
      }
    }
  }

  private updateMediaMetadata(): void {
    if (!this.mediaSession) return;
    const track = this.activeTrack;
    if (!track) {
      this.mediaSession.metadata = null;
      this.mediaSession.playbackState = "none";
      return;
    }
    this.mediaSession.playbackState = this.audio.paused ? "paused" : "playing";
    if (!("MediaMetadata" in window)) return;
    try {
      this.mediaSession.metadata = new MediaMetadata({
        title: track.title || "Unknown title",
        artist: track.artist || "Unknown artist",
        album: track.album || "",
        artwork: [96, 128, 192, 256, 384, 512].map((size) => ({
          src: new URL(track.coverUrl, window.location.href).href,
          sizes: `${size}x${size}`,
          type: "image/jpeg",
        })),
      });
    } catch (error) {
      console.warn("Could not set system media metadata", error);
    }
  }

  private updateMediaPosition(): void {
    if (
      !this.mediaSession?.setPositionState ||
      !Number.isFinite(this.audio.duration) ||
      this.audio.duration <= 0 ||
      !Number.isFinite(this.audio.currentTime)
    ) {
      return;
    }
    try {
      this.mediaSession.setPositionState({
        duration: this.audio.duration,
        position: Math.max(0, Math.min(this.audio.currentTime, this.audio.duration)),
        playbackRate: this.audio.playbackRate || 1,
      });
    } catch {
      // Browsers may reject position updates before media metadata is ready.
    }
  }

  private currentTrackId(): string | null {
    const state = usePlayerStore.getState();
    return state.queue[state.queueIndex] ?? null;
  }

  private seek(offset: number): void {
    if (!Number.isFinite(this.audio.duration)) return;
    this.audio.currentTime = Math.max(
      0,
      Math.min(this.audio.duration, this.audio.currentTime + offset),
    );
  }

  private notify(message: string): void {
    if (this.uiCallbacks) this.uiCallbacks.notify(message);
    else console.warn(`[audio] ${message}`);
  }

  private async recordListen(trackId: string): Promise<void> {
    try {
      await expectOk(
        await apiFetch(
          "/api/library/listening",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ trackId }),
          },
          { csrf: true, retryCsrfOnForbidden: true },
        ),
      );
      this.uiCallbacks?.listeningUpdated();
    } catch (error) {
      console.error("Could not save listening history.", error);
    }

    const playlistId = this.playlistId;
    if (!playlistId) return;
    this.playlistId = null;
    try {
      const response = await expectOk(
        await apiFetch(
          `/api/library/playlists/${encodeURIComponent(playlistId)}/listening`,
          { method: "POST" },
          { csrf: true, retryCsrfOnForbidden: true },
        ),
      );
      const result: unknown = await response.json();
      if (
        !result ||
        typeof result !== "object" ||
        !("playlistId" in result) ||
        result.playlistId !== playlistId ||
        !("lastPlayedAt" in result) ||
        typeof result.lastPlayedAt !== "number" ||
        !Number.isFinite(result.lastPlayedAt)
      ) {
        throw new Error("The server returned invalid playlist listening data.");
      }
      const state = usePlayerStore.getState();
      state.setPlaylists(
        state.playlists.map((playlist) =>
          playlist.id === playlistId
            ? { ...playlist, lastPlayedAt: result.lastPlayedAt as number }
            : playlist,
        ),
      );
    } catch (error) {
      console.error("Could not save playlist listening history.", error);
    }
  }

  private readonly onTimeUpdate = (): void => {
    const currentTime = this.audio.currentTime;
    const madeProgress = currentTime > this.lastPlaybackTime + 0.05;
    this.lastPlaybackTime = currentTime;
    this.updateMediaPosition();
    if (!madeProgress) return;

    this.endTransitionPending = false;
    const attempt = this.attempt;
    if (attempt?.wantsPlayback && !this.audio.paused) {
      const listenDelta =
        attempt.lastListenPosition === null
          ? 0
          : currentTime - attempt.lastListenPosition;
      if (listenDelta > 0 && listenDelta <= 5) {
        attempt.listenedSeconds += listenDelta;
      }
      attempt.lastListenPosition = currentTime;
      const listenThreshold =
        this.audio.duration > 0 ? Math.min(30, this.audio.duration / 2) : 30;
      if (!attempt.listenRecorded && attempt.listenedSeconds >= listenThreshold) {
        attempt.listenRecorded = true;
        void this.recordListen(attempt.trackId);
      }
    }
    this.clearStallTimer(attempt);
    if (
      attempt?.wantsPlayback &&
      !this.audio.paused &&
      this.audio.readyState >= HTMLMediaElement.HAVE_FUTURE_DATA
    ) {
      usePlayerStore.getState().setPlaybackStatus("playing");
    }
  };

  private readonly onMetadata = (): void => {
    this.lastPlaybackTime = this.audio.currentTime;
    this.updateMediaPosition();
  };

  private readonly onSeeked = (): void => {
    this.lastPlaybackTime = this.audio.currentTime;
    if (this.attempt) this.attempt.lastListenPosition = this.audio.currentTime;
    this.updateMediaPosition();
  };

  private readonly onPlaying = (): void => {
    const attempt = this.attempt;
    if (attempt) {
      attempt.hasPlayed = true;
      attempt.retryableNetworkFailure = false;
      attempt.lastListenPosition = this.audio.currentTime;
      attempt.recovering = false;
      attempt.retryCount = 0;
      attempt.signedUrlRefreshed = false;
      attempt.retrySource = this.audio.currentSrc || attempt.retrySource;
    }
    this.automaticFailureSkips = 0;
    this.clearStallTimer(attempt);
    const state = usePlayerStore.getState();
    state.setPlaying(true);
    state.setPlaybackStatus("playing");
    if (this.mediaSession) this.mediaSession.playbackState = "playing";
  };

  private readonly onBuffering = (): void => {
    const attempt = this.attempt;
    if (!attempt?.wantsPlayback || this.audio.paused) return;
    usePlayerStore.getState().setPlaybackStatus("buffering");
    if (attempt.stallTimer !== null) return;

    const stalledAt = this.audio.currentTime;
    attempt.stallTimer = window.setTimeout(() => {
      attempt.stallTimer = null;
      if (
        this.attempt === attempt &&
        attempt.wantsPlayback &&
        !this.audio.paused &&
        !this.audio.ended &&
        this.audio.currentTime <= stalledAt + 0.1
      ) {
        this.handlePlaybackFailure(
          attempt,
          new Error("Playback made no progress after a buffer event"),
          "Playback stopped while buffering. Check your connection and try again.",
          "stalled",
        );
      }
    }, attempt.hasPlayed ? PLAYBACK_STALL_TIMEOUT_MS : PLAYBACK_START_TIMEOUT_MS);
  };

  private readonly onPlay = (): void => {
    const state = usePlayerStore.getState();
    state.setPlaying(true);
    state.setPlaybackStatus("buffering");
    if (this.mediaSession) this.mediaSession.playbackState = "playing";
  };

  private readonly onPause = (): void => {
    const attempt = this.attempt;
    if (
      attempt?.recovering ||
      (attempt?.wantsPlayback &&
        this.audio.error !== null &&
        this.audio.error !== undefined)
    ) {
      return;
    }
    if (
      document.visibilityState === "hidden" &&
      attempt?.wantsPlayback &&
      !this.audio.ended
    ) {
      usePlayerStore.getState().setPlaybackStatus("buffering");
      return;
    }
    this.clearStallTimer(attempt);
    if (attempt) {
      attempt.wantsPlayback = false;
      attempt.lastListenPosition = null;
    }
    const state = usePlayerStore.getState();
    state.setPlaying(false);
    state.setPlaybackStatus(attempt?.failed ? "failed" : "paused");
    if (this.mediaSession) this.mediaSession.playbackState = "paused";
  };

  private readonly onEnded = (): void => {
    if (this.endTransitionPending) return;
    this.endTransitionPending = true;
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
    this.playNext(true);
  };

  private readonly onVisibilityChange = (): void => {
    if (document.visibilityState !== "visible") return;
    this.restorePlayback();
  };

  private readonly onOnline = (): void => {
    const attempt = this.attempt;
    if (!attempt?.failed || !attempt.retryableNetworkFailure) return;
    this.restoreFailedNetworkAttempt(attempt);
  };

  private readonly onError = (): void => {
    const attempt = this.attempt;
    if (
      !attempt ||
      (this.audio.src !== attempt.src && this.audio.src !== attempt.retrySource) ||
      (attempt.recovering &&
        this.audio.error?.code === MediaError.MEDIA_ERR_ABORTED)
    ) {
      return;
    }
    const error = new Error("Audio element emitted a media error");
    error.name =
      this.audio.error?.code === MediaError.MEDIA_ERR_NETWORK
        ? "NetworkError"
        : this.audio.error?.code === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED
          ? "NotSupportedError"
          : "MediaError";
    logAudioFailure("audio error event", this.audio, error);
    this.handlePlaybackFailure(
      attempt,
      error,
      "This track could not be played. Check the file format or your connection.",
    );
  };

  private restorePlayback(): void {
    if (this.checkSleepTimer()) return;
    if (this.audio.ended) {
      this.onEnded();
      return;
    }
    const attempt = this.attempt;
    if (attempt?.failed && attempt.retryableNetworkFailure) {
      this.restoreFailedNetworkAttempt(attempt);
      return;
    }
    if (
      attempt?.wantsPlayback &&
      !attempt.failed &&
      this.audio.paused &&
      attempt.retryTimer === null
    ) {
      this.runPlaybackAttempt(attempt);
    }
  }

  private restoreFailedNetworkAttempt(attempt: PlaybackAttempt): void {
    attempt.failed = false;
    attempt.wantsPlayback = true;
    attempt.retryCount = 0;
    attempt.retryableNetworkFailure = false;
    attempt.recoveryPosition = Number.isFinite(this.audio.currentTime)
      ? this.audio.currentTime
      : null;
    this.runPlaybackAttempt(attempt);
  }

  private beginTrack(trackId: string, automaticTransition: boolean): void {
    const state = usePlayerStore.getState();
    const track = state.tracks.find((item) => item.id === trackId);
    if (!track) return;
    if (!automaticTransition) this.automaticFailureSkips = 0;

    const src = new URL(
      track.offlineUrl || track.streamUrl,
      window.location.href,
    ).href;
    const currentAttempt = this.attempt;
    if (
      currentAttempt?.src === src &&
      !currentAttempt.failed &&
      currentAttempt.wantsPlayback &&
      (currentAttempt.loading || !this.audio.paused)
    ) {
      return;
    }

    this.cancelAttempt();
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
      automaticTransition,
      retryableNetworkFailure: false,
      recovering: false,
      recoveryPosition: null,
      signedUrlRefreshed: false,
      listenedSeconds: 0,
      lastListenPosition: null,
      listenRecorded: false,
    };
    this.attempt = attempt;
    this.runPlaybackAttempt(attempt);
  }

  private runPlaybackAttempt(attempt: PlaybackAttempt): void {
    if (this.attempt !== attempt) return;
    const requestId = ++attempt.requestId;
    const source = attempt.retrySource ?? attempt.src;
    attempt.loading = true;
    const needsLoad =
      this.audio.src !== source ||
      this.audio.error !== null ||
      this.audio.networkState === HTMLMediaElement.NETWORK_NO_SOURCE;
    if (needsLoad) {
      attempt.recovering = true;
      if (this.audio.src !== source) {
        this.audio.pause();
        this.audio.removeAttribute("src");
        this.audio.load();
      }
      this.audio.src = source;
      this.audio.load();
    }
    const state = usePlayerStore.getState();
    state.setPlaying(true);
    state.setPlaybackStatus("buffering");

    const startPlayback = () => {
      attempt.restoreMetadataListener = null;
      if (
        this.attempt !== attempt ||
        attempt.requestId !== requestId ||
        !attempt.wantsPlayback
      ) {
        return;
      }
      if (attempt.recoveryPosition !== null && attempt.recoveryPosition > 0) {
        const duration = this.audio.duration;
        this.audio.currentTime =
          Number.isFinite(duration) && duration > 0
            ? Math.min(attempt.recoveryPosition, duration)
            : attempt.recoveryPosition;
      }
      attempt.recoveryPosition = null;
      void this.audio.play().then(
        () => {
          if (this.attempt === attempt && attempt.requestId === requestId) {
            attempt.loading = false;
          }
        },
        (error: unknown) => {
          if (
            this.attempt !== attempt ||
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
          logAudioFailure("play() rejected", this.audio, error);
          this.handlePlaybackFailure(
            attempt,
            error,
            "The track could not start. Please try again.",
          );
        },
      );
    };

    if (
      attempt.recoveryPosition !== null &&
      attempt.recoveryPosition > 0 &&
      this.audio.readyState < HTMLMediaElement.HAVE_METADATA
    ) {
      const onMetadata = () => {
        if (attempt.restoreMetadataListener === onMetadata) {
          attempt.restoreMetadataListener = null;
        }
        startPlayback();
      };
      attempt.restoreMetadataListener = onMetadata;
      this.audio.addEventListener("loadedmetadata", onMetadata, { once: true });
      return;
    }
    startPlayback();
  }

  private handlePlaybackFailure(
    attempt: PlaybackAttempt,
    error: unknown,
    message: string,
    failureKind: "media" | "stalled" = "media",
  ): void {
    if (
      this.attempt !== attempt ||
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
    if (
      document.visibilityState === "hidden" &&
      (errorName === "NotAllowedError" || errorName === "AbortError")
    ) {
      attempt.loading = false;
      attempt.recovering = false;
      attempt.failed = false;
      attempt.retryableNetworkFailure = false;
      this.clearAttemptTimers(attempt);
      const state = usePlayerStore.getState();
      state.setPlaying(false);
      state.setPlaybackStatus("buffering");
      return;
    }
    const mediaErrorCode = this.audio.error?.code;
    const retryableNetworkError =
      failureKind === "stalled" ||
      errorName === "NetworkError" ||
      mediaErrorCode === MediaError.MEDIA_ERR_ABORTED ||
      mediaErrorCode === MediaError.MEDIA_ERR_NETWORK;
    const unsupportedMediaError =
      errorName === "NotSupportedError" ||
      mediaErrorCode === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED;
    // Unsupported media may be a stale signed URL once; after that, stop retrying.
    const retryable =
      retryableNetworkError ||
      (unsupportedMediaError && !attempt.signedUrlRefreshed);

    if (!retryable || attempt.retryCount >= MAX_PLAYBACK_RETRIES) {
      attempt.failed = true;
      attempt.wantsPlayback = false;
      attempt.retryableNetworkFailure = retryableNetworkError;
      attempt.recovering = false;
      this.clearAttemptTimers(attempt);
      this.audio.pause();
      const state = usePlayerStore.getState();
      state.setPlaying(false);
      state.setPlaybackStatus("failed");
      this.notify(errorName === "NotAllowedError" ? "Press play to start." : message);
      if (
        attempt.automaticTransition &&
        this.automaticFailureSkips < state.queue.length - 1
      ) {
        this.automaticFailureSkips += 1;
        this.playNext(true, true);
      }
      return;
    }

    if (attempt.restoreMetadataListener) {
      this.audio.removeEventListener("loadedmetadata", attempt.restoreMetadataListener);
      attempt.restoreMetadataListener = null;
    }
    attempt.recoveryPosition = Number.isFinite(this.audio.currentTime)
      ? this.audio.currentTime
      : null;
    attempt.recovering = true;
    const reusableSignedSource =
      [this.audio.currentSrc, attempt.retrySource].find(
        (candidate) => candidate && candidate !== attempt.src,
      ) ?? null;
    const refreshSignedUrl =
      !attempt.signedUrlRefreshed &&
      (attempt.retryCount > 0 || reusableSignedSource === null);
    if (refreshSignedUrl) attempt.signedUrlRefreshed = true;
    attempt.retrySource = refreshSignedUrl ? null : reusableSignedSource;
    attempt.retryCount += 1;
    usePlayerStore.getState().setPlaybackStatus("buffering");
    logAudioFailure("retrying playback", this.audio, error);

    const delay = Math.min(500 * 2 ** (attempt.retryCount - 1), 4_000);
    attempt.retryTimer = window.setTimeout(() => {
      attempt.retryTimer = null;
      if (this.attempt !== attempt || !attempt.wantsPlayback) return;
      this.audio.pause();
      this.runPlaybackAttempt(attempt);
    }, delay);
  }

  private pauseAtQueueEnd(): void {
    this.audio.pause();
    const state = usePlayerStore.getState();
    state.setPlaying(false);
    state.setPlaybackStatus("paused");
  }

  private scheduleSleepTimer(): void {
    if (this.sleepTimer !== null) window.clearTimeout(this.sleepTimer);
    this.sleepTimer = null;
    if (this.sleepTimerEndsAt === null) return;
    const delay = Math.max(0, this.sleepTimerEndsAt - Date.now());
    this.sleepTimer = window.setTimeout(() => {
      this.sleepTimer = null;
      this.checkSleepTimer();
    }, delay);
  }

  private checkSleepTimer(): boolean {
    const endsAt = this.sleepTimerEndsAt;
    if (endsAt === null || endsAt > Date.now()) return false;
    const state = usePlayerStore.getState();
    if (state.sleepTimerEndsAt !== endsAt) return false;
    this.sleepTimerEndsAt = null;
    this.audio.pause();
    state.setSleepTimer(null, null);
    state.setPlaying(false);
    state.setPlaybackStatus("paused");
    return true;
  }

  private cancelAttempt(): void {
    const attempt = this.attempt;
    if (!attempt) return;
    attempt.wantsPlayback = false;
    attempt.recovering = false;
    attempt.requestId += 1;
    this.clearAttemptTimers(attempt);
    if (attempt.restoreMetadataListener) {
      this.audio.removeEventListener("loadedmetadata", attempt.restoreMetadataListener);
      attempt.restoreMetadataListener = null;
    }
    this.attempt = null;
  }

  private clearAttemptTimers(attempt: PlaybackAttempt): void {
    if (attempt.retryTimer !== null) {
      window.clearTimeout(attempt.retryTimer);
      attempt.retryTimer = null;
    }
    this.clearStallTimer(attempt);
  }

  private clearStallTimer(attempt: PlaybackAttempt | null): void {
    if (attempt?.stallTimer !== null && attempt?.stallTimer !== undefined) {
      window.clearTimeout(attempt.stallTimer);
      attempt.stallTimer = null;
    }
  }
}

let activeController: PlaybackController | null = null;

export function installPlaybackController(audio: HTMLAudioElement): () => void {
  activeController?.dispose();
  const controller = new PlaybackController(audio);
  activeController = controller;
  return () => {
    if (activeController === controller) activeController = null;
    controller.dispose();
  };
}

export function getPlaybackController(): PlaybackController | null {
  return activeController;
}
