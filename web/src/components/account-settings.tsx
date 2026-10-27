"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent, type PointerEvent as ReactPointerEvent } from "react";
import { apiFetch, expectOk } from "@/lib/api/client";
import type { Account } from "@/lib/api/types";
import LogoutButton from "@/components/auth/logout-button";
import { artistNames } from "@/components/artist-explorer";
import { usePlayerStore, type LibraryView } from "@/store/player-store";
import { LanguageSelect, useLanguage } from "@/lib/i18n";

function dateLabel(timestamp: number, language: string): string {
  if (!timestamp) return "—";
  return new Date(timestamp * 1000).toLocaleDateString(language, {
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
  active,
  onToast,
  onPhotoChange,
}: {
  active: boolean;
  onToast: (message: string) => void;
  onPhotoChange: (photoUrl: string | null) => void;
}) {
  const { language, t } = useLanguage();
  const tracks = usePlayerStore((state) => state.tracks);
  const playlists = usePlayerStore((state) => state.playlists);
  const setView = usePlayerStore((state) => state.setView);
  const [account, setAccount] = useState<Account | null>(null);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [emailPassword, setEmailPassword] = useState("");
  const [emailMessage, setEmailMessage] = useState("");
  const [emailEditorOpen, setEmailEditorOpen] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState("");
  const [passwordEditorOpen, setPasswordEditorOpen] = useState(false);
  const [photoMessage, setPhotoMessage] = useState("");
  const [photoEditorOpen, setPhotoEditorOpen] = useState(false);
  const [photoDraftUrl, setPhotoDraftUrl] = useState<string | null>(null);
  const [photoRemoved, setPhotoRemoved] = useState(false);
  const [photoImageLoaded, setPhotoImageLoaded] = useState(false);
  const [photoZoom, setPhotoZoom] = useState(1);
  const [photoOffset, setPhotoOffset] = useState({ x: 0, y: 0 });
  const [photoSaving, setPhotoSaving] = useState(false);
  const [deleteMessage, setDeleteMessage] = useState("");
  const [deleteEditorOpen, setDeleteEditorOpen] = useState(false);
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
    if (!active || account) return;
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
        if (!cancelled) setError(reason instanceof Error ? reason.message : t("Could not load account."));
      });
    return () => {
      cancelled = true;
    };
  }, [account, active, onPhotoChange, t]);

  async function saveEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setEmailMessage(t("Saving email…"));
    try {
      const data = await sendJson("/api/account/email", "PUT", {
        email: email.trim(),
        current_password: emailPassword,
      });
      const nextEmail = typeof data.email === "string" ? data.email : null;
      setAccount((current) => current ? { ...current, email: nextEmail } : current);
      setEmail(nextEmail ?? "");
      setEmailPassword("");
      setEmailMessage(nextEmail ? t("Email saved to your account.") : t("Email removed."));
    } catch (reason) {
      setEmailMessage(reason instanceof Error ? reason.message : t("Could not update email."));
    }
  }

  async function savePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    setPasswordMessage(t("Updating…"));
    try {
      await sendJson("/api/account/password", "POST", {
        current_password: String(formData.get("current_password") ?? ""),
        new_password: String(formData.get("new_password") ?? ""),
      });
      form.reset();
      setPasswordMessage(t("Password updated."));
    } catch (reason) {
      setPasswordMessage(reason instanceof Error ? reason.message : t("Could not update password."));
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
      setPhotoMessage(t("Choose a JPEG, PNG, WebP, or GIF image."));
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setPhotoMessage(t("Profile photo must be 5 MB or smaller."));
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
    setPhotoMessage(photoRemoved ? t("Removing…") : t("Saving…"));
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
        onToast(t("Profile photo removed."));
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
      onToast(t("Profile photo saved."));
    } catch (reason) {
      setPhotoMessage(reason instanceof Error ? reason.message : t("Could not save profile photo."));
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
      onToast(reason instanceof Error ? reason.message : t("Could not sign out of all devices."));
    }
  }

  async function deleteAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    setDeleteMessage(t("Deleting account…"));
    setPending(true);
    try {
      await sendJson("/api/account", "DELETE", {
        current_password: String(formData.get("current_password") ?? ""),
        confirmation: String(formData.get("confirmation") ?? ""),
      });
      window.location.assign("/login?account_deleted=1");
    } catch (reason) {
      setPending(false);
      setDeleteMessage(reason instanceof Error ? reason.message : t("Could not delete account."));
    }
  }

  const likedCount = tracks.filter((track) => track.favorite).length;
  const artistCount = new Set(tracks.flatMap(artistNames)).size;
  const cards: Array<{ label: string; count: number; subtitle: string; view: LibraryView }> = [
    { label: t("Music files"), count: tracks.length, subtitle: t("tracks in your library"), view: "library" },
    { label: t("Liked songs"), count: likedCount, subtitle: t("saved favorites"), view: "favorites" },
    { label: t("Artists"), count: artistCount, subtitle: t("in your library"), view: "artists" },
    { label: t("Playlists"), count: playlists.length, subtitle: t("saved playlists"), view: "playlists" },
  ];
  const memberSince = new Date(account?.created_at ? account.created_at * 1000 : 0);

  if (!account) {
    return <div className="account-view acct-loading">{error || t("Loading account…")}</div>;
  }

  return (
    <div className="account-view">
      <section className="acct-card">
        <button className={`acct-avatar${account.photo_url ? " has-photo" : ""}`} type="button" title={t("Edit profile photo")} aria-label={t("Edit profile photo")} onClick={openPhotoEditor}>
          {account.photo_url ? <img src={account.photo_url} alt="" /> : <span className="acct-avatar-monogram">{account.username.slice(0, 1).toUpperCase()}</span>}
        </button>
        <div className="acct-profile-copy">
          <div className="acct-profile-kicker">
            <span className="acct-profile-wave" aria-hidden="true"><i /><i /><i /><i /><i /></span>
            <span>{t("Profile")}</span>
          </div>
          <h1 className="acct-name">{account.username}</h1>
          <p className="acct-member">
            <span>{t("Member since")}</span>
            <time dateTime={memberSince.toISOString()}>{dateLabel(account.created_at, language)}</time>
          </p>
        </div>
      </section>

      <section className="acct-library-section" aria-labelledby="account-library-title">
        <h2 className="acct-section-heading" id="account-library-title">{t("Your library")}</h2>
        <div className="acct-grid">
          {cards.map((card) => (
            <button type="button" className="acct-panel" key={card.label} onClick={() => setView(card.view)}>
              <span className="acct-panel-head"><span>{card.label}</span><span className="acct-count">{card.count}</span></span>
              <span className="acct-panel-sub">{card.subtitle}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="acct-settings acct-settings-group" aria-labelledby="account-preferences-title">
        <h2 className="acct-section-heading" id="account-preferences-title">{t("Preferences")}</h2>
        <div className="acct-setting-row">
          <div className="acct-setting-copy">
            <h3>{t("Language")}</h3>
            <p>{t("Choose the language used by Vervfy.")}</p>
          </div>
          <LanguageSelect className="acct-language-select" />
        </div>
        <div className="acct-setting-row">
          <div className="acct-setting-copy">
            <h3>{t("Credits")}</h3>
            <p>{t("Credits and data sources")}</p>
          </div>
          <Link className="acct-link" href="/credits">{t("View credits")}</Link>
        </div>
      </section>

      <section className="acct-settings acct-settings-group" aria-labelledby="account-security-title">
        <h2 className="acct-section-heading" id="account-security-title">{t("Sign-in & security")}</h2>
        <div className="acct-security-item">
          <div className="acct-setting-copy">
            <h3>{t("Email address")}</h3>
            <p>{t("Email is account information only; sign in with your username.")}</p>
            <p className="acct-current-value">{account.email ?? t("No email on file")}</p>
          </div>
          <div className="acct-security-action">
            <button
              className="btn"
              type="button"
              aria-expanded={emailEditorOpen}
              onClick={() => {
                setEmail(account.email ?? "");
                setEmailPassword("");
                setEmailMessage("");
                setEmailEditorOpen((open) => !open);
              }}
            >
              {t(emailEditorOpen ? "Cancel" : "Edit")}
            </button>
            {emailEditorOpen ? (
              <form className="acct-form acct-inline-editor" id="account-email-editor" onSubmit={saveEmail}>
                <label className="acct-field">
                  <span>{t("Email address")}</span>
                  <input type="email" autoComplete="email" maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} />
                </label>
                <label className="acct-field">
                  <span>{t("Current password")}</span>
                  <input type="password" autoComplete="current-password" required value={emailPassword} onChange={(event) => setEmailPassword(event.target.value)} />
                </label>
                <div className="acct-form-actions">
                  <button className="btn btn-primary" type="submit">{t("Save email")}</button>
                </div>
                <div className={`acct-form-msg${emailMessage.includes("salvo") || emailMessage.includes("removido") || emailMessage.includes("saved") || emailMessage.includes("removed") ? " ok" : emailMessage && !emailMessage.includes("Salvando") && !emailMessage.includes("Saving") ? " error" : ""}`} role="status" aria-live="polite">
                  {emailMessage}
                </div>
              </form>
            ) : null}
          </div>
        </div>
        <div className="acct-security-item">
          <div className="acct-setting-copy">
            <h3>{t("Password")}</h3>
          </div>
          <div className="acct-security-action">
            <button
              className="btn"
              type="button"
              aria-expanded={passwordEditorOpen}
              onClick={() => {
                setPasswordMessage("");
                setPasswordEditorOpen((open) => !open);
              }}
            >
              {t(passwordEditorOpen ? "Cancel" : "Change password")}
            </button>
            {passwordEditorOpen ? (
              <form className="acct-form acct-inline-editor" id="account-password-editor" onSubmit={savePassword}>
                <label className="acct-field">
                  <span>{t("Current password")}</span>
                  <input name="current_password" type="password" autoComplete="current-password" required />
                </label>
                <label className="acct-field">
                  <span>{t("New password (min 8 characters)")}</span>
                  <input name="new_password" type="password" autoComplete="new-password" minLength={8} required />
                </label>
                <button className="btn btn-primary" type="submit">{t("Update password")}</button>
                <div className={`acct-form-msg${passwordMessage === t("Password updated.") ? " ok" : passwordMessage && passwordMessage !== t("Updating…") ? " error" : ""}`} role="status" aria-live="polite">{passwordMessage}</div>
              </form>
            ) : null}
          </div>
        </div>
      </section>

      <section className="acct-settings acct-session" aria-labelledby="account-session-title">
        <h2 className="acct-section-heading" id="account-session-title">{t("Session")}</h2>
        <div className="acct-session-actions">
          <LogoutButton className="btn" />
          <button className="btn" type="button" disabled={pending} onClick={() => void logoutAll()}>{t("Sign out of all devices")}</button>
        </div>
      </section>

      <section className="acct-settings acct-danger-zone" aria-labelledby="account-delete-title">
        <h2 className="acct-section-heading" id="account-delete-title">{t("Delete account")}</h2>
        <p className="acct-danger-copy">{t("Permanently removes your profile, music files, playlists, favorites, and saved lyrics. This cannot be undone.")}</p>
        <div className="acct-delete-editor">
          <button
            className={`btn${deleteEditorOpen ? "" : " btn-danger"}`}
            type="button"
            aria-expanded={deleteEditorOpen}
            onClick={() => {
              setDeleteMessage("");
              setDeleteEditorOpen((open) => !open);
            }}
          >
            {t(deleteEditorOpen ? "Cancel" : "Delete account")}
          </button>
          {deleteEditorOpen ? (
            <form className="acct-form acct-delete-form" onSubmit={deleteAccount}>
              <label className="acct-field">
                <span>{t("Current password")}</span>
                <input name="current_password" type="password" autoComplete="current-password" required />
              </label>
              <label className="acct-field">
                <span>{t("Type DELETE to confirm")}</span>
                <input name="confirmation" type="text" autoComplete="off" required />
              </label>
              <div className="acct-form-actions">
                <button className="btn btn-danger" type="submit" disabled={pending}>{t("Delete account")}</button>
              </div>
              <div className={`acct-form-msg${deleteMessage && !deleteMessage.includes("Deleting") ? " error" : ""}`} role="status" aria-live="polite">{deleteMessage}</div>
            </form>
          ) : null}
        </div>
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
                <h3 id="photo-editor-title">{t("Profile photo")}</h3>
                <p>{t("Choose a photo, adjust its zoom and position, then save.")}</p>
              </div>
              <button className="btn" type="button" aria-label={t("Close photo editor")} disabled={photoSaving} onClick={closePhotoEditor}>{t("Close")}</button>
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
                aria-label={t("Photo crop preview; drag to reposition")}
              >
                <img
                  ref={photoImageRef}
                  src={photoDraftUrl}
                  alt=""
                  draggable={false}
                  onLoad={() => setPhotoImageLoaded(true)}
                  onError={() => {
                    setPhotoImageLoaded(false);
                    setPhotoMessage(t("Could not load this photo."));
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
                {photoRemoved ? t("Photo will be removed when you save.") : t("Choose a photo to get started.")}
              </div>
            )}

            {photoDraftUrl && !photoRemoved ? (
              <label className="photo-editor-zoom">
                <span>{t("Zoom")}</span>
                <input
                  type="range"
                  min="1"
                  max="3"
                  step="0.05"
                  value={photoZoom}
                  aria-label={t("Photo zoom")}
                  disabled={!photoImageLoaded || photoSaving}
                  onChange={(event) => setZoom(Number(event.currentTarget.value))}
                />
                <span>{photoZoom.toFixed(1)}×</span>
              </label>
            ) : null}

            <div className="photo-editor-actions">
              <button className="btn" type="button" disabled={photoSaving} onClick={() => photoInputRef.current?.click()}>
                {account.photo_url ? t("Choose another photo") : t("Choose photo")}
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
