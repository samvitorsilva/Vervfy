"use client";

import { useEffect, useRef, useState, type FormEvent, type PointerEvent as ReactPointerEvent } from "react";
import { apiFetch, expectOk } from "@/lib/api/client";
import type { Account } from "@/lib/api/types";
import LogoutButton from "@/components/auth/logout-button";
import { artistNames } from "@/components/artist-explorer";
import { usePlayerStore, type LibraryView } from "@/store/player-store";

function dateLabel(timestamp: number): string {
  if (!timestamp) return "—";
  return new Date(timestamp * 1000).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

async function sendJson(path: string, method: string, payload: unknown) {
  const response = await apiFetch(
    path,
    {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    { csrf: true, retryCsrfOnForbidden: true },
  );
  await expectOk(response);
  return response.json() as Promise<Record<string, unknown>>;
}

export default function AccountSettings({
  onToast,
  onPhotoChange,
}: {
  onToast: (message: string) => void;
  onPhotoChange: (photoUrl: string | null) => void;
}) {
  const tracks = usePlayerStore((state) => state.tracks);
  const playlists = usePlayerStore((state) => state.playlists);
  const setView = usePlayerStore((state) => state.setView);
  const [account, setAccount] = useState<Account | null>(null);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [emailPassword, setEmailPassword] = useState("");
  const [emailMessage, setEmailMessage] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");
  const [photoMessage, setPhotoMessage] = useState("");
  const [photoEditorOpen, setPhotoEditorOpen] = useState(false);
  const [photoDraftUrl, setPhotoDraftUrl] = useState<string | null>(null);
  const [photoRemoved, setPhotoRemoved] = useState(false);
  const [photoImageLoaded, setPhotoImageLoaded] = useState(false);
  const [photoZoom, setPhotoZoom] = useState(1);
  const [photoOffset, setPhotoOffset] = useState({ x: 0, y: 0 });
  const [photoSaving, setPhotoSaving] = useState(false);
  const [deleteMessage, setDeleteMessage] = useState("");
  const [pending, setPending] = useState(false);
  const photoInputRef = useRef<HTMLInputElement>(null);
  const photoImageRef = useRef<HTMLImageElement>(null);
  const photoStageRef = useRef<HTMLDivElement>(null);
  const photoObjectUrlRef = useRef<string | null>(null);
  const photoDragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    offsetX: number;
    offsetY: number;
  } | null>(null);

  useEffect(
    () => () => {
      if (photoObjectUrlRef.current) URL.revokeObjectURL(photoObjectUrlRef.current);
    },
    [],
  );

  useEffect(() => {
    if (!photoEditorOpen || photoSaving) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") closePhotoEditor();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [photoEditorOpen, photoSaving]);

  useEffect(() => {
    let cancelled = false;
    apiFetch("/api/me")
      .then(async (response) => {
        await expectOk(response);
        return response.json() as Promise<Account>;
      })
      .then((data) => {
        if (!cancelled) {
          setAccount(data);
          setEmail(data.email ?? "");
          onPhotoChange(data.photo_url);
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load account.");
      });
    return () => {
      cancelled = true;
    };
  }, [onPhotoChange]);

  async function saveEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setEmailMessage("Saving email…");
    try {
      const data = await sendJson("/api/account/email", "PUT", {
        email: email.trim(),
        current_password: emailPassword,
      });
      const nextEmail = typeof data.email === "string" ? data.email : null;
      setAccount((current) => current ? { ...current, email: nextEmail } : current);
      setEmail(nextEmail ?? "");
      setEmailPassword("");
      setEmailMessage(nextEmail ? "Email saved to your account." : "Email removed.");
    } catch (reason) {
      setEmailMessage(reason instanceof Error ? reason.message : "Could not update email.");
    }
  }

  async function savePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    setPasswordMessage("Updating…");
    try {
      await sendJson("/api/account/password", "POST", {
        current_password: String(formData.get("current_password") ?? ""),
        new_password: String(formData.get("new_password") ?? ""),
      });
      form.reset();
      setPasswordMessage("Password updated.");
    } catch (reason) {
      setPasswordMessage(reason instanceof Error ? reason.message : "Could not update password.");
    }
  }

  function openPhotoEditor() {
    setPhotoDraftUrl(account?.photo_url ?? null);
    setPhotoRemoved(false);
    setPhotoImageLoaded(false);
    setPhotoZoom(1);
    setPhotoOffset({ x: 0, y: 0 });
    setPhotoMessage("");
    setPhotoEditorOpen(true);
  }

  function closePhotoEditor() {
    if (photoObjectUrlRef.current) {
      URL.revokeObjectURL(photoObjectUrlRef.current);
      photoObjectUrlRef.current = null;
    }
    setPhotoEditorOpen(false);
    setPhotoDraftUrl(null);
    setPhotoRemoved(false);
    setPhotoImageLoaded(false);
    setPhotoOffset({ x: 0, y: 0 });
  }

  function choosePhoto(file: File | undefined) {
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp", "image/gif"].includes(file.type)) {
      setPhotoMessage("Choose a JPEG, PNG, WebP, or GIF image.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setPhotoMessage("Profile photo must be 5 MB or smaller.");
      return;
    }
    if (photoObjectUrlRef.current) URL.revokeObjectURL(photoObjectUrlRef.current);
    const objectUrl = URL.createObjectURL(file);
    photoObjectUrlRef.current = objectUrl;
    setPhotoDraftUrl(objectUrl);
    setPhotoRemoved(false);
    setPhotoImageLoaded(false);
    setPhotoZoom(1);
    setPhotoOffset({ x: 0, y: 0 });
    setPhotoMessage("");
  }

  function clampPhotoOffset(x: number, y: number, zoom: number) {
    const image = photoImageRef.current;
    const stage = photoStageRef.current;
    if (!image || !stage || !image.naturalWidth || !image.naturalHeight) {
      return { x: 0, y: 0 };
    }
    const stageSize = stage.clientWidth;
    const baseScale = stageSize / Math.min(image.naturalWidth, image.naturalHeight);
    const maxX = Math.max(0, (image.naturalWidth * baseScale * zoom - stageSize) / 2);
    const maxY = Math.max(0, (image.naturalHeight * baseScale * zoom - stageSize) / 2);
    return {
      x: Math.max(-maxX, Math.min(maxX, x)),
      y: Math.max(-maxY, Math.min(maxY, y)),
    };
  }

  function movePhoto(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = photoDragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    setPhotoOffset(
      clampPhotoOffset(
        drag.offsetX + event.clientX - drag.startX,
        drag.offsetY + event.clientY - drag.startY,
        photoZoom,
      ),
    );
  }

  function setZoom(value: number) {
    setPhotoZoom(value);
    setPhotoOffset((current) => clampPhotoOffset(current.x, current.y, value));
  }

  function handlePhotoDragStart(event: ReactPointerEvent<HTMLDivElement>) {
    if (!photoImageLoaded || photoRemoved) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    photoDragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      offsetX: photoOffset.x,
      offsetY: photoOffset.y,
    };
  }

  async function savePhoto() {
    setPhotoSaving(true);
    setPhotoMessage(photoRemoved ? "Removing…" : "Saving…");
    try {
      if (photoRemoved) {
        await expectOk(
          await apiFetch(
            "/api/account/photo",
            { method: "DELETE" },
            { csrf: true, retryCsrfOnForbidden: true },
          ),
        );
        setAccount((current) => current ? { ...current, photo_url: null } : current);
        onPhotoChange(null);
        closePhotoEditor();
        onToast("Profile photo removed.");
        return;
      }

      const image = photoImageRef.current;
      const stage = photoStageRef.current;
      if (!image?.naturalWidth || !image.naturalHeight || !stage) {
        throw new Error("Choose a photo before saving.");
      }
      const outputSize = 512;
      const cropSize = Math.min(image.naturalWidth, image.naturalHeight) / photoZoom;
      const stageSize = stage.clientWidth;
      const baseScale = stageSize / Math.min(image.naturalWidth, image.naturalHeight);
      const centerX = image.naturalWidth / 2 - photoOffset.x / (baseScale * photoZoom);
      const centerY = image.naturalHeight / 2 - photoOffset.y / (baseScale * photoZoom);
      const cropX = Math.max(0, Math.min(image.naturalWidth - cropSize, centerX - cropSize / 2));
      const cropY = Math.max(0, Math.min(image.naturalHeight - cropSize, centerY - cropSize / 2));
      const canvas = document.createElement("canvas");
      canvas.width = outputSize;
      canvas.height = outputSize;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Your browser could not prepare the photo.");
      context.drawImage(image, cropX, cropY, cropSize, cropSize, 0, 0, outputSize, outputSize);
      const photo = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob(
          (blob) => (blob ? resolve(blob) : reject(new Error("Could not prepare this photo."))),
          "image/jpeg",
          0.92,
        );
      });
      const body = new FormData();
      body.append("file", photo, "profile-photo.jpg");
      const response = await apiFetch(
        "/api/account/photo",
        { method: "POST", body },
        { csrf: true, retryCsrfOnForbidden: true },
      );
      await expectOk(response);
      const data = (await response.json()) as { photo_url: string };
      const photoUrl = `${data.photo_url}?v=${Date.now()}`;
      setAccount((current) => current ? { ...current, photo_url: photoUrl } : current);
      onPhotoChange(photoUrl);
      closePhotoEditor();
      onToast("Profile photo saved.");
    } catch (reason) {
      setPhotoMessage(reason instanceof Error ? reason.message : "Could not save profile photo.");
    } finally {
      setPhotoSaving(false);
    }
  }

  async function logoutAll() {
    setPending(true);
    try {
      await sendJson("/api/account/logout-all", "POST", {});
      window.location.assign("/login");
    } catch (reason) {
      setPending(false);
      onToast(reason instanceof Error ? reason.message : "Could not sign out of all devices.");
    }
  }

  async function deleteAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!window.confirm("Delete your account and all of its music data permanently?")) return;
    const formData = new FormData(event.currentTarget);
    setDeleteMessage("Deleting account…");
    setPending(true);
    try {
      await sendJson("/api/account", "DELETE", {
        current_password: String(formData.get("current_password") ?? ""),
        confirmation: String(formData.get("confirmation") ?? ""),
      });
      window.location.assign("/login?account_deleted=1");
    } catch (reason) {
      setPending(false);
      setDeleteMessage(reason instanceof Error ? reason.message : "Could not delete account.");
    }
  }

  const likedCount = tracks.filter((track) => track.favorite).length;
  const artistCount = new Set(tracks.flatMap(artistNames)).size;
  const cards: Array<{ label: string; count: number; subtitle: string; view: LibraryView }> = [
    { label: "Music files", count: tracks.length, subtitle: "tracks in your library", view: "library" },
    { label: "Liked songs", count: likedCount, subtitle: "saved favorites", view: "favorites" },
    { label: "Artists", count: artistCount, subtitle: "in your library", view: "artists" },
    { label: "Playlists", count: playlists.length, subtitle: "saved playlists", view: "playlists" },
  ];

  if (!account) {
    return <div className="account-view acct-loading">{error || "Loading account…"}</div>;
  }

  return (
    <div className="account-view">
      <section className="acct-card">
        <button className="acct-avatar" type="button" title="Edit profile photo" aria-label="Edit profile photo" onClick={openPhotoEditor}>
          {account.photo_url ? <img src={account.photo_url} alt="Profile photo" /> : account.username.slice(0, 1).toUpperCase()}
        </button>
        <div><div className="acct-name">{account.username}</div><div className="acct-sub">{account.email ?? "No email on file"} · Member since {dateLabel(account.created_at)}</div></div>
      </section>

      <div className="acct-grid">
        {cards.map((card) => <button type="button" className="acct-panel" key={card.label} onClick={() => setView(card.view)}><span className="acct-panel-head"><span>{card.label}</span><span className="acct-count">{card.count}</span></span><span className="acct-panel-sub">{card.subtitle}</span></button>)}
      </div>

      <section className="acct-settings">
        <div className="acct-settings-title">Email address</div>
        <form className="acct-form" onSubmit={saveEmail}>
          <input type="email" placeholder="you@example.com" autoComplete="email" maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} />
          <input type="password" placeholder="Current password" autoComplete="current-password" required value={emailPassword} onChange={(event) => setEmailPassword(event.target.value)} />
          <button className="btn btn-primary" type="submit">Save email</button>
          {account.email ? <button className="btn" type="button" onClick={() => setEmail("")}>Clear email</button> : null}
          <div className={`acct-form-msg${emailMessage.includes("saved") || emailMessage.includes("removed") ? " ok" : emailMessage && !emailMessage.includes("Saving") ? " error" : ""}`}>{emailMessage || "Email is account information only; sign in with your username."}</div>
        </form>
      </section>

      <section className="acct-settings">
        <div className="acct-settings-title">Change password</div>
        <form className="acct-form" onSubmit={savePassword}>
          <input name="current_password" type="password" placeholder="Current password" autoComplete="current-password" required />
          <input name="new_password" type="password" placeholder="New password (min 8 characters)" autoComplete="new-password" minLength={8} required />
          <button className="btn btn-primary" type="submit">Update password</button>
          <div className={`acct-form-msg${passwordMessage === "Password updated." ? " ok" : passwordMessage && passwordMessage !== "Updating…" ? " error" : ""}`}>{passwordMessage}</div>
        </form>
      </section>

      <section className="acct-settings">
        <div className="acct-settings-title">Session</div>
        <div className="acct-form"><LogoutButton /><button className="btn" type="button" disabled={pending} onClick={() => void logoutAll()}>Sign out of all devices</button></div>
      </section>

      <section className="acct-settings acct-danger-zone">
        <div className="acct-settings-title">Delete account</div>
        <p className="acct-danger-copy">Permanently removes your profile, music files, playlists, favorites, and saved lyrics. This cannot be undone.</p>
        <form className="acct-form" onSubmit={deleteAccount}>
          <input name="current_password" type="password" placeholder="Current password" autoComplete="current-password" required />
          <input name="confirmation" type="text" placeholder="Type DELETE to confirm" autoComplete="off" required />
          <button className="btn btn-danger" type="submit" disabled={pending}>Delete account</button>
          <div className={`acct-form-msg${deleteMessage && !deleteMessage.includes("Deleting") ? " error" : ""}`}>{deleteMessage}</div>
        </form>
      </section>

      {photoEditorOpen ? (
        <div
          className="photo-editor-overlay open"
          onClick={(event) => {
            if (event.target === event.currentTarget && !photoSaving) closePhotoEditor();
          }}
        >
          <section className="photo-editor-card" role="dialog" aria-modal="true" aria-labelledby="photo-editor-title">
            <div className="photo-editor-head">
              <div>
                <h3 id="photo-editor-title">Profile photo</h3>
                <p>Choose a photo, adjust its zoom and position, then save.</p>
              </div>
              <button className="btn" type="button" aria-label="Close photo editor" disabled={photoSaving} onClick={closePhotoEditor}>Close</button>
            </div>

            <input
              ref={photoInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              hidden
              onChange={(event) => {
                choosePhoto(event.currentTarget.files?.[0]);
                event.currentTarget.value = "";
              }}
            />

            {photoDraftUrl && !photoRemoved ? (
              <div
                className="photo-editor-stage"
                ref={photoStageRef}
                onPointerDown={handlePhotoDragStart}
                onPointerMove={movePhoto}
                onPointerUp={() => { photoDragRef.current = null; }}
                onPointerCancel={() => { photoDragRef.current = null; }}
                role="img"
                aria-label="Photo crop preview; drag to reposition"
              >
                <img
                  ref={photoImageRef}
                  src={photoDraftUrl}
                  alt=""
                  draggable={false}
                  onLoad={() => setPhotoImageLoaded(true)}
                  onError={() => {
                    setPhotoImageLoaded(false);
                    setPhotoMessage("Could not load this photo.");
                  }}
                  style={{
                    width: photoImageRef.current?.naturalWidth && photoStageRef.current
                      ? `${photoImageRef.current.naturalWidth * photoStageRef.current.clientWidth / Math.min(photoImageRef.current.naturalWidth, photoImageRef.current.naturalHeight) * photoZoom}px`
                      : undefined,
                    height: photoImageRef.current?.naturalHeight && photoStageRef.current
                      ? `${photoImageRef.current.naturalHeight * photoStageRef.current.clientWidth / Math.min(photoImageRef.current.naturalWidth, photoImageRef.current.naturalHeight) * photoZoom}px`
                      : undefined,
                    left: `calc(50% + ${photoOffset.x}px)`,
                    top: `calc(50% + ${photoOffset.y}px)`,
                    transform: "translate(-50%, -50%)",
                  }}
                />
              </div>
            ) : (
              <div className="photo-editor-stage photo-editor-empty" aria-live="polite">
                {photoRemoved ? "Photo will be removed when you save." : "Choose a photo to get started."}
              </div>
            )}

            {photoDraftUrl && !photoRemoved ? (
              <label className="photo-editor-zoom">
                <span>Zoom</span>
                <input
                  type="range"
                  min="1"
                  max="3"
                  step="0.05"
                  value={photoZoom}
                  aria-label="Photo zoom"
                  disabled={!photoImageLoaded || photoSaving}
                  onChange={(event) => setZoom(Number(event.currentTarget.value))}
                />
                <span>{photoZoom.toFixed(1)}×</span>
              </label>
            ) : null}

            <div className="photo-editor-actions">
              <button className="btn" type="button" disabled={photoSaving} onClick={() => photoInputRef.current?.click()}>
                {account.photo_url ? "Choose another photo" : "Choose photo"}
              </button>
              {account.photo_url ? (
                <button
                  className={photoRemoved ? "btn" : "btn btn-danger"}
                  type="button"
                  disabled={photoSaving}
                  onClick={() => {
                    setPhotoRemoved((removed) => !removed);
                    setPhotoMessage("");
                  }}
                >
                  {photoRemoved ? "Keep current photo" : "Remove photo"}
                </button>
              ) : null}
              <button className="btn btn-primary" type="button" disabled={photoSaving || (!photoRemoved && !photoImageLoaded)} onClick={() => void savePhoto()}>
                {photoSaving ? "Saving…" : "Save"}
              </button>
            </div>
            <div className={`acct-form-msg${photoMessage && !photoMessage.includes("Saving") && !photoMessage.includes("Removing") ? " error" : ""}`} role="status">
              {photoMessage || "JPEG, PNG, WebP, or GIF up to 5 MB."}
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
