"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useLanguage } from "@/lib/i18n";
import { usePlayerStore, type LibraryView } from "@/store/player-store";

export default function CommandMenu({ onPlay, onUpload, onShortcuts }: {
  onPlay: (id: string) => void;
  onUpload: () => void;
  onShortcuts: () => void;
}) {
  const { t } = useLanguage();
  const tracks = usePlayerStore((state) => state.tracks);
  const setView = usePlayerStore((state) => state.setView);
  const dialog = useRef<HTMLDialogElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const id = useId();
  const navigation: [string, LibraryView][] = [["Library", "library"], ["Favorites", "favorites"], ["Artists", "artists"], ["Playlists", "playlists"], ["Offline", "offline"], ["Recap", "recap"], ["Account", "account"]];
  const actions = [
    ...navigation.map(([label, view]) => ({ id: view, label: t(label), run: () => setView(view) })),
    { id: "upload", label: t("Add music"), run: onUpload },
    { id: "shortcuts", label: t("Keyboard shortcuts"), run: onShortcuts },
    ...tracks.map((track) => ({ id: `track:${track.id}`, label: `${track.title} · ${track.artist}`, run: () => onPlay(track.id) })),
  ].filter((action) => action.label.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())).slice(0, 30);
  const activeIndex = Math.min(selected, Math.max(0, actions.length - 1));
  const close = () => dialog.current?.close();
  const open = () => {
    if (dialog.current?.open) { close(); return; }
    returnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setQuery("");
    setSelected(0);
    dialog.current?.showModal();
  };
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLowerCase() === "k") {
        // Do not open over a password, account confirmation, or other modal form.
        if (!dialog.current?.open && [...document.querySelectorAll<HTMLElement>('dialog[open], [role="dialog"][aria-modal="true"]')].some((element) => element.getClientRects().length > 0)) return;
        event.preventDefault();
        open();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });
  useEffect(() => {
    dialog.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);
  return <>
    <button className="btn command-trigger" type="button" aria-label={t("Open command menu")} aria-haspopup="dialog" aria-keyshortcuts="Meta+K Control+K" onClick={open}>
      <span>{t("Commands")}</span><kbd>⌘ / Ctrl K</kbd>
    </button>
    <dialog ref={dialog} className="command-menu" aria-label={t("Command menu")} onClose={() => returnFocus.current?.focus()} onClick={(event) => { if (event.target === event.currentTarget) close(); }} onKeyDown={(event) => {
      if (event.key === "Escape") { event.stopPropagation(); return; }
      event.stopPropagation();
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        setSelected((activeIndex + (event.key === "ArrowDown" ? 1 : -1) + actions.length) % Math.max(1, actions.length));
      }
      if (event.key === "Enter") {
        event.preventDefault();
        const action = actions[activeIndex];
        if (action) { close(); action.run(); }
      }
    }}>
      <div className="command-search">
        <input autoFocus role="combobox" aria-autocomplete="list" aria-label={t("Search commands and songs")} aria-expanded="true" aria-controls={`${id}-results`} aria-activedescendant={actions.length ? `${id}-${activeIndex}` : undefined} autoComplete="off" placeholder={t("Search commands and songs")} value={query} onChange={(event) => { setQuery(event.target.value); setSelected(0); }} />
        <button className="icon-btn" type="button" aria-label={t("Close")} onClick={close}>×</button>
      </div>
      <div id={`${id}-results`} role="listbox" aria-label={t("Commands")} className="command-results">
        {actions.map((action, index) => <div role="option" aria-selected={activeIndex === index} id={`${id}-${index}`} key={action.id} onPointerMove={() => setSelected(index)}>
          <button tabIndex={-1} type="button" onClick={() => { close(); action.run(); }}>{action.label}</button>
        </div>)}
        {!actions.length && <p role="status">{t("No matches")}</p>}
      </div>
      <p className="command-hint"><kbd>↑ ↓</kbd> {t("Navigate")} <kbd>Enter</kbd> {t("Select")} <kbd>Esc</kbd> {t("Close")}</p>
    </dialog>
  </>;
}
