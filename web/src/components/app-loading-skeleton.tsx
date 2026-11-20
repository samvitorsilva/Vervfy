"use client";

import type { LibraryView, ListMode } from "@/store/player-store";

export default function AppLoadingSkeleton({
  view,
  listMode,
  label,
  compact = false,
}: {
  view: LibraryView;
  listMode: ListMode;
  label: string;
  compact?: boolean;
}) {
  const trackRows = Array.from({ length: 8 }, (_, index) => (
    <div className="app-skeleton-list-row" key={index} aria-hidden="true">
      <span className="app-skeleton-block app-skeleton-index" />
      <span className="app-skeleton-track-copy">
        <span className="app-skeleton-block app-skeleton-cover" />
        <span className="app-skeleton-track-lines">
          <span className="app-skeleton-block app-skeleton-line" />
          <span className="app-skeleton-block app-skeleton-line short" />
        </span>
      </span>
      <span className="app-skeleton-block app-skeleton-line album" />
      <span className="app-skeleton-block app-skeleton-line time" />
      <span className="app-skeleton-actions">
        <span className="app-skeleton-block app-skeleton-action" />
        <span className="app-skeleton-block app-skeleton-action" />
      </span>
    </div>
  ));
  const trackGrid = (
    <div className="grid app-skeleton-track-grid" aria-hidden="true">
      {Array.from({ length: 12 }, (_, index) => (
        <div className="app-skeleton-track-card" key={index}>
          <span className="app-skeleton-block app-skeleton-square" />
          <span className="app-skeleton-block app-skeleton-line" />
          <span className="app-skeleton-block app-skeleton-line short" />
        </div>
      ))}
    </div>
  );
  const trackList = (
    <div className="list app-skeleton-track-list" aria-hidden="true">
      <div className="list-head"><div /><div /><div /><div /><div /></div>
      {trackRows}
    </div>
  );
  const playlistCards = (
    <div className={`pl-grid app-skeleton-playlists${listMode === "list" ? " list-mode" : ""}`} aria-hidden="true">
      {Array.from({ length: 6 }, (_, index) => (
        <div className="pl-card app-skeleton-playlist-card" key={index}>
          <span className="app-skeleton-block app-skeleton-playlist-cover" />
          <span className="app-skeleton-playlist-copy">
            <span className="app-skeleton-block app-skeleton-line" />
            <span className="app-skeleton-block app-skeleton-line short" />
          </span>
        </div>
      ))}
    </div>
  );
  const artistCards = (
    <div className={`artist-grid app-skeleton-artists${listMode === "list" ? " list-mode" : ""}`} aria-hidden="true">
      {Array.from({ length: 8 }, (_, index) => (
        <div className={`artist-card app-skeleton-artist-card${listMode === "list" ? " list-mode" : ""}`} key={index}>
          <span className="app-skeleton-block app-skeleton-artist-avatar" />
          <span className="app-skeleton-block app-skeleton-line" />
          <span className="app-skeleton-block app-skeleton-line short" />
        </div>
      ))}
    </div>
  );
  const recap = (
    <div className="recap-page app-skeleton-recap" aria-hidden="true">
      {!compact ? <div className="recap-overview"><div className="app-skeleton-recap-intro"><span className="app-skeleton-block app-skeleton-line heading" /><span className="app-skeleton-block app-skeleton-line" /></div></div> : null}
      <div className="recap-periods">{[0, 1].map((period) => <section className="recap-period app-skeleton-recap-card" key={period}>
        <span className="app-skeleton-block app-skeleton-line short" /><span className="app-skeleton-block app-skeleton-line heading" />
        <span className="app-skeleton-block app-skeleton-recap-total" />
        <div className="recap-top-tracks">{Array.from({ length: 5 }, (_, index) => <div className="recap-track app-skeleton-recap-track" key={index}><span className="app-skeleton-block app-skeleton-index" /><span className="app-skeleton-block app-skeleton-cover" /><span className="app-skeleton-track-lines"><span className="app-skeleton-block app-skeleton-line" /><span className="app-skeleton-block app-skeleton-line short" /></span><span className="app-skeleton-block app-skeleton-line time" /></div>)}</div>
        <div className="recap-artists"><span className="app-skeleton-block app-skeleton-line short" /><div className="app-skeleton-artist-chips">{[0, 1, 2].map((index) => <span className="app-skeleton-block app-skeleton-artist-chip" key={index} />)}</div></div>
      </section>)}</div>
    </div>
  );
  const account = (
    <div className="account-view app-skeleton-account" aria-hidden="true">
      <section className="acct-card">
        <span className="app-skeleton-block app-skeleton-account-avatar" />
        <div className="app-skeleton-account-profile">
          <span className="app-skeleton-block app-skeleton-line short" />
          <span className="app-skeleton-block app-skeleton-line heading" />
          <span className="app-skeleton-block app-skeleton-line" />
        </div>
      </section>
      <section className="acct-library-section">
        <span className="app-skeleton-block app-skeleton-line heading" />
        <div className="acct-grid">
          {Array.from({ length: 4 }, (_, index) => (
            <div className="acct-panel" key={index}>
              <span className="app-skeleton-block app-skeleton-line" />
              <span className="app-skeleton-block app-skeleton-line short" />
            </div>
          ))}
        </div>
      </section>
      {[3, 5, 2, 1].map((rows, section) => <section className={`acct-settings acct-settings-group${section === 3 ? " acct-danger-zone" : ""}`} key={section}>
        <span className="app-skeleton-block app-skeleton-line heading" />
        {Array.from({ length: rows }, (_, row) => <div className="acct-setting-row" key={row}><span className="app-skeleton-setting-copy"><span className="app-skeleton-block app-skeleton-line" /><span className="app-skeleton-block app-skeleton-line short" /></span><span className="app-skeleton-block app-skeleton-setting-control" /></div>)}
      </section>)}
    </div>
  );
  const artistProfile = (
    <div className="artist-page app-skeleton-artist-profile" aria-hidden="true">
      <header className="artist-hero">
        <span className="app-skeleton-block app-skeleton-profile-avatar" />
        <div className="app-skeleton-profile-copy">
          <span className="app-skeleton-block app-skeleton-line short" />
          <span className="app-skeleton-block app-skeleton-line heading" />
          <span className="app-skeleton-block app-skeleton-line" />
          <span className="app-skeleton-block app-skeleton-profile-button" />
        </div>
      </header>
      <section className="artist-info">
        <span className="app-skeleton-block app-skeleton-line heading" />
        <span className="app-skeleton-block app-skeleton-line" />
        <span className="app-skeleton-block app-skeleton-line" />
        <span className="app-skeleton-block app-skeleton-line short" />
      </section>
      {listMode === "grid" ? trackGrid : trackList}
    </div>
  );
  const isPlaylistDetail = view.startsWith("playlist:");

  return (
    <div className="app-loading-skeleton" role="status" aria-label={label} aria-busy="true">
      {view === "recap" ? recap
        : view === "account" ? account
          : view === "playlists" ? playlistCards
            : view === "artists" ? artistCards
              : view.startsWith("artist:") ? artistProfile
                : (
                  <>
                    {isPlaylistDetail ? (
                      <div className="app-skeleton-playlist-detail" aria-hidden="true">
                        <div className="playlist-hero">
                          <span className="app-skeleton-block app-skeleton-detail-cover" />
                          <div className="app-skeleton-detail-copy">
                            <span className="app-skeleton-block app-skeleton-line short" />
                            <span className="app-skeleton-block app-skeleton-line heading" />
                            <span className="app-skeleton-block app-skeleton-line" />
                            <span className="app-skeleton-block app-skeleton-profile-button" />
                          </div>
                        </div>
                      </div>
                    ) : null}
                    {listMode === "grid" ? trackGrid : trackList}
                  </>
                )}
    </div>
  );
}

