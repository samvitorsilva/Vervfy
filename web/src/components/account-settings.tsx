"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type FormEvent, type PointerEvent as ReactPointerEvent } from "react";
import { ApiError, apiFetch, expectOk } from "@/lib/api/client";
import {
  isPasskeyBrowserSupported,
  issueRecoveryCodes,
  loadPasskeySecurity,
  registerPasskey,
  verifyPasskeyAction,
  type PasskeyEnrollmentEligibility,
  type PasskeySecurityStatus,
} from "@/lib/passkey-client";
import type { Account } from "@/lib/api/types";
import LogoutButton from "@/components/auth/logout-button";
import { artistNames } from "@/components/artist-explorer";
import { usePlayerStore, type LibraryView } from "@/store/player-store";
import { LanguageSelect, useLanguage } from "@/lib/i18n";

function dateLabel(timestamp: number, language: string): string {
  if (!timestamp) return "Not available";
  return new Date(timestamp * 1000).toLocaleDateString(language, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function subscribeToBrowserSupport() {
  return () => {};
}

function getPasskeyBrowserSupport() {
  return isPasskeyBrowserSupported();
}

function getServerPasskeyBrowserSupport() {
  return false;
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

function clearCachedLyrics() {
  try {
    for (let index = window.localStorage.length - 1; index >= 0; index -= 1) {
      const key = window.localStorage.key(index);
      if (key?.startsWith("vervfy:lrclib:v4:")) {
        window.localStorage.removeItem(key);
      }
    }
  } catch (reason) {
    console.warn("Could not clear cached lyrics after account deletion.", reason);
  }
}

function clearOfflineTracks(accountId: string): Promise<void> {
  if (typeof indexedDB === "undefined") return Promise.resolve();

  return new Promise((resolve, reject) => {
    const request = indexedDB.open("auralis-db", 2);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains("kv")) database.createObjectStore("kv");
      if (!database.objectStoreNames.contains("handles")) database.createObjectStore("handles");
      if (!database.objectStoreNames.contains("offlineTracks")) {
        database.createObjectStore("offlineTracks", { keyPath: "id" });
      }
    };
    request.onerror = () => reject(request.error ?? new Error("Could not open offline storage."));
    request.onblocked = () => reject(new Error("Offline storage is busy in another browser tab."));
    request.onsuccess = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains("offlineTracks")) {
        database.close();
        resolve();
        return;
      }

      let transaction: IDBTransaction;
      try {
        transaction = database.transaction("offlineTracks", "readwrite");
        const cursorRequest = transaction.objectStore("offlineTracks").openCursor();
        cursorRequest.onsuccess = () => {
          try {
            const cursor = cursorRequest.result;
            if (!cursor) return;
            const value: unknown = cursor.value;
            if (
              typeof value === "object" &&
              value !== null &&
              "accountId" in value &&
              value.accountId === accountId
            ) {
              cursor.delete();
            }
            cursor.continue();
          } catch (reason) {
            try {
              transaction.abort();
            } catch {
              // The transaction may already have completed.
            }
            database.close();
            reject(reason instanceof Error ? reason : new Error("Could not clear offline storage."));
          }
        };
        cursorRequest.onerror = () => {
          database.close();
          reject(cursorRequest.error ?? new Error("Could not clear offline storage."));
        };
      } catch (reason) {
        database.close();
        reject(reason instanceof Error ? reason : new Error("Could not clear offline storage."));
        return;
      }
      transaction.oncomplete = () => {
        database.close();
        resolve();
      };
      transaction.onerror = () => {
        database.close();
        reject(transaction.error ?? new Error("Could not clear offline storage."));
      };
      transaction.onabort = () => {
        database.close();
        reject(transaction.error ?? new Error("Could not clear offline storage."));
      };
    };
  });
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
  const { language, t, translateError } = useLanguage();
  const router = useRouter();
  const tracks = usePlayerStore((state) => state.tracks);
  const playlists = usePlayerStore((state) => state.playlists);
  const setView = usePlayerStore((state) => state.setView);
  const [account, setAccount] = useState<Account | null>(null);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [emailPassword, setEmailPassword] = useState("");
  const emailInputRef = useRef<HTMLInputElement>(null);
  const [emailMessage, setEmailMessage] = useState("");
  const [emailEditorOpen, setEmailEditorOpen] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState("");
  const [passwordEditorOpen, setPasswordEditorOpen] = useState(false);
  const [googleMessage, setGoogleMessage] = useState("");
  const [googleLinkEditorOpen, setGoogleLinkEditorOpen] = useState(false);
  const [googleLinkPassword, setGoogleLinkPassword] = useState("");
  const [googleUnlinkEditorOpen, setGoogleUnlinkEditorOpen] = useState(false);
  const [googleUnlinkPassword, setGoogleUnlinkPassword] = useState("");
  const [logoutEditorOpen, setLogoutEditorOpen] = useState(false);
  const [logoutPassword, setLogoutPassword] = useState("");
  const [logoutMessage, setLogoutMessage] = useState("");
  const [passkeyFeatureState, setPasskeyFeatureState] = useState<
    "loading" | "enabled" | "disabled" | "error"
  >("loading");
  const [passkeyMethods, setPasskeyMethods] =
    useState<PasskeySecurityStatus | null>(null);
  const [passkeyEligibility, setPasskeyEligibility] =
    useState<PasskeyEnrollmentEligibility | null>(null);
  const [passkeyMessage, setPasskeyMessage] = useState("");
  const [passkeyPassword, setPasskeyPassword] = useState("");
  const [passkeyBusy, setPasskeyBusy] = useState(false);
  const passkeyBrowserSupported = useSyncExternalStore(
    subscribeToBrowserSupport,
    getPasskeyBrowserSupport,
    getServerPasskeyBrowserSupport,
  );
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const passwordFormRef = useRef<HTMLFormElement>(null);
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
  const [emailPasskeyBusy, setEmailPasskeyBusy] = useState(false);
  const [passwordPasskeyBusy, setPasswordPasskeyBusy] = useState(false);
  const [logoutPasskeyBusy, setLogoutPasskeyBusy] = useState(false);
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

  const refreshPasskeySecurity = useCallback(async () => {
    try {
      const status = await loadPasskeySecurity();
      setPasskeyMethods(status.methods);
      setPasskeyEligibility(status.enrollment);
      setPasskeyFeatureState("enabled");
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 404) {
        setPasskeyMethods(null);
        setPasskeyEligibility(null);
        setPasskeyFeatureState("disabled");
        return;
      }
      setPasskeyFeatureState("error");
      setPasskeyMessage(
        translateError(
          reason instanceof Error ? reason.message : "",
          "Could not load passkey settings.",
        ),
      );
    }
  }, [translateError]);

  useEffect(() => {
    if (!active || !account) return;
    let cancelled = false;
    void loadPasskeySecurity().then((status) => {
      if (cancelled) return;
      setPasskeyMethods(status.methods);
      setPasskeyEligibility(status.enrollment);
      setPasskeyFeatureState("enabled");
    }).catch((reason: unknown) => {
      if (cancelled) return;
      if (reason instanceof ApiError && reason.status === 404) {
        setPasskeyMethods(null);
        setPasskeyEligibility(null);
        setPasskeyFeatureState("disabled");
        return;
      }
      setPasskeyFeatureState("error");
      setPasskeyMessage(
        translateError(
          reason instanceof Error ? reason.message : "",
          "Could not load passkey settings.",
        ),
      );
    });
    return () => {
      cancelled = true;
    };
  }, [active, account, translateError]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const url = new URL(window.location.href);
      const linkStatus = url.searchParams.get("google_link");
      const reauthStatus = url.searchParams.get("google_reauth");
      const action = url.searchParams.get("google_action");
      if (linkStatus === "success") {
        setGoogleMessage(t("Google account linked."));
      } else if (linkStatus === "failed") {
        setGoogleMessage(t("Google account could not be linked. Try again."));
      } else if (reauthStatus === "success") {
        setGoogleMessage(t("Google verification complete. Repeat your action now."));
        if (action === "email_change") setEmailEditorOpen(true);
        if (action === "password_add") setPasswordEditorOpen(true);
        if (action === "account_delete") setDeleteEditorOpen(true);
        if (action === "logout_all") setLogoutEditorOpen(true);
      } else if (reauthStatus === "failed") {
        setGoogleMessage(t("Google verification failed. Try again."));
      } else {
        return;
      }
      url.searchParams.delete("google_link");
      url.searchParams.delete("google_reauth");
      url.searchParams.delete("google_action");
      window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [t]);

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
        if (!cancelled) setError(translateError(reason instanceof Error ? reason.message : "", "Could not load account."));
      });
    return () => {
      cancelled = true;
    };
  }, [account, active, onPhotoChange, translateError]);

  async function saveEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setEmailMessage(t("Saving email…"));
    try {
      const data = await sendJson("/api/account/email", "PUT", {
        email: email.trim(),
        ...(account?.has_password ? { current_password: emailPassword } : {}),
      });
      const nextEmail = typeof data.email === "string" ? data.email : null;
      setAccount((current) => current ? { ...current, email: nextEmail } : current);
      setEmail(nextEmail ?? "");
      setEmailPassword("");
      setEmailMessage(nextEmail ? t("Email saved to your account.") : t("Email removed."));
    } catch (reason) {
      setEmailMessage(translateError(reason instanceof Error ? reason.message : "", "Could not update email."));
    }
  }

  function passkeyErrorMessage(reason: unknown): string {
    if (reason instanceof DOMException && reason.name === "NotAllowedError") {
      return t("Passkey request cancelled or timed out. Start again.");
    }
    if (
      reason instanceof Error &&
      reason.message.includes("not supported")
    ) {
      return t("Passkeys are not supported in this browser or connection.");
    }
    if (reason instanceof ApiError && reason.status === 400) {
      return t("Passkey verification failed or expired. Start a new attempt.");
    }
    return translateError(
      reason instanceof Error ? reason.message : "",
      "Passkey verification failed. Try again.",
    );
  }

  async function saveEmailWithPasskey() {
    if (!emailInputRef.current?.reportValidity()) return;
    setEmailPasskeyBusy(true);
    setEmailMessage(t("Verifying with your passkey…"));
    try {
      const proof = await verifyPasskeyAction("email_change", {
        email: email.trim(),
      });
      const data = await sendJson("/api/account/email", "PUT", {
        email: email.trim(),
        ...proof,
      });
      const nextEmail = typeof data.email === "string" ? data.email : null;
      setAccount((current) => current ? { ...current, email: nextEmail } : current);
      setEmail(nextEmail ?? "");
      setEmailPassword("");
      setEmailMessage(nextEmail ? t("Email saved to your account.") : t("Email removed."));
    } catch (reason) {
      setEmailMessage(passkeyErrorMessage(reason));
    } finally {
      setEmailPasskeyBusy(false);
    }
  }

  async function savePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    setPasswordMessage(t("Updating…"));
    try {
      await sendJson("/api/account/password", "POST", {
        ...(account?.has_password
          ? { current_password: String(formData.get("current_password") ?? "") }
          : {}),
        new_password: String(formData.get("new_password") ?? ""),
      });
      form.reset();
      setAccount((current) => current ? { ...current, has_password: true } : current);
      setPasswordMessage(t("Password updated."));
    } catch (reason) {
      setPasswordMessage(translateError(reason instanceof Error ? reason.message : "", "Could not update password."));
    }
  }

  async function createPasswordWithPasskey() {
    if (!passwordFormRef.current?.reportValidity()) return;
    const formData = passwordFormRef.current
      ? new FormData(passwordFormRef.current)
      : null;
    const newPassword = String(formData?.get("new_password") ?? "");
    setPasswordPasskeyBusy(true);
    setPasswordMessage(t("Verifying with your passkey…"));
    try {
      const proof = await verifyPasskeyAction("password_add", {
        new_password: newPassword,
      });
      await sendJson("/api/account/password", "POST", {
        new_password: newPassword,
        ...proof,
      });
      passwordFormRef.current?.reset();
      setAccount((current) => current ? { ...current, has_password: true } : current);
      setPasswordMessage(t("Password updated."));
      await refreshPasskeySecurity();
    } catch (reason) {
      setPasswordMessage(passkeyErrorMessage(reason));
    } finally {
      setPasswordPasskeyBusy(false);
    }
  }

  async function enrollPasskey() {
    setPasskeyBusy(true);
    setPasskeyMessage(t("Starting passkey setup…"));
    try {
      await registerPasskey(passkeyPassword);
      setPasskeyPassword("");
      setPasskeyMessage(t("Passkey added. Your session was refreshed."));
      await refreshPasskeySecurity();
    } catch (reason) {
      setPasskeyMessage(passkeyErrorMessage(reason));
    } finally {
      setPasskeyBusy(false);
    }
  }

  async function setupRecoveryCodes() {
    setPasskeyBusy(true);
    setPasskeyMessage(t("Verifying with your passkey…"));
    try {
      const codes = await issueRecoveryCodes();
      setRecoveryCodes(codes);
      setPasskeyMessage(t("Recovery codes created. Save them now; they will not be shown again."));
      await refreshPasskeySecurity();
    } catch (reason) {
      setPasskeyMessage(passkeyErrorMessage(reason));
    } finally {
      setPasskeyBusy(false);
    }
  }

  async function logoutAllWithPasskey() {
    setLogoutPasskeyBusy(true);
    setLogoutMessage(t("Verifying with your passkey…"));
    try {
      const proof = await verifyPasskeyAction("logout_all");
      await sendJson("/api/account/logout-all", "POST", proof);
      router.replace("/login");
    } catch (reason) {
      setLogoutMessage(passkeyErrorMessage(reason));
      setLogoutPasskeyBusy(false);
    }
  }

  async function redirectToGoogle(path: string, payload: unknown) {
    setPending(true);
    setGoogleMessage(t("Opening Google verification…"));
    try {
      const data = await sendJson(path, "POST", payload);
      const target = typeof data.authorization_url === "string"
        ? new URL(data.authorization_url)
        : null;
      if (!target || target.origin !== "https://accounts.google.com") {
        throw new Error("Could not start Google verification.");
      }
      window.location.assign(target.href);
    } catch (reason) {
      setPending(false);
      setGoogleMessage(
        translateError(
          reason instanceof Error ? reason.message : "",
          "Could not start Google verification.",
        ),
      );
    }
  }

  async function linkGoogle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await redirectToGoogle("/api/account/google/link/start", {
      current_password: googleLinkPassword,
    });
  }

  async function startGoogleReauthentication(
    purpose: "password_add" | "email_change" | "account_delete" | "logout_all",
  ) {
    await redirectToGoogle("/api/account/google/reauth/start", { purpose });
  }

  async function unlinkGoogle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setGoogleMessage(t("Unlinking Google…"));
    try {
      await sendJson("/api/account/google", "DELETE", {
        current_password: googleUnlinkPassword,
      });
      setAccount((current) => current ? { ...current, google_linked: false } : current);
      setGoogleUnlinkPassword("");
      setGoogleUnlinkEditorOpen(false);
      setGoogleMessage(t("Google account unlinked."));
    } catch (reason) {
      setGoogleMessage(translateError(reason instanceof Error ? reason.message : "", "Could not unlink Google."));
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
      setPhotoMessage(translateError(reason instanceof Error ? reason.message : "", "Could not save profile photo."));
    } finally {
      setPhotoSaving(false);
    }
  }

  async function logoutAll() {
    setPending(true);
    try {
      await sendJson("/api/account/logout-all", "POST", {
        ...(account?.has_password ? { current_password: logoutPassword } : {}),
      });
      window.location.assign("/login");
    } catch (reason) {
      setPending(false);
      setLogoutMessage(translateError(reason instanceof Error ? reason.message : "", "Could not sign out of all devices."));
    }
  }

  async function deleteAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const accountId = account?.id;
    if (!accountId) {
      setDeleteMessage(t("Could not delete account."));
      return;
    }
    const formData = new FormData(event.currentTarget);
    setDeleteMessage(t("Deleting account…"));
    setPending(true);
    try {
      await sendJson("/api/account", "DELETE", {
        ...(account?.has_password
          ? { current_password: String(formData.get("current_password") ?? "") }
          : {}),
        confirmation: String(formData.get("confirmation") ?? ""),
      });
      clearCachedLyrics();
      try {
        await clearOfflineTracks(accountId);
      } catch (reason) {
        console.error("Could not clear offline downloads after account deletion.", reason);
        window.alert(
          t("Your account was deleted, but offline downloads could not be removed from this browser. Clear this site's browser storage manually."),
        );
      }
      window.location.assign("/login?account_deleted=1");
    } catch (reason) {
      setPending(false);
      setDeleteMessage(translateError(reason instanceof Error ? reason.message : "", "Could not delete account."));
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
    if (error) return <div className="account-view acct-loading" role="alert">{error}</div>;
    return (
      <div className="account-view app-skeleton-account" aria-label={t("Loading account…")} aria-busy="true">
        <section className="acct-card" aria-hidden="true">
          <span className="app-skeleton-block app-skeleton-account-avatar" />
          <div className="app-skeleton-account-profile">
            <span className="app-skeleton-block app-skeleton-line short" />
            <span className="app-skeleton-block app-skeleton-line heading" />
            <span className="app-skeleton-block app-skeleton-line" />
          </div>
        </section>
        <section className="acct-library-section" aria-hidden="true">
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
      </div>
    );
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
        <div className="acct-setting-row">
          <div className="acct-setting-copy">
            <h3>{t("Privacy & data requests")}</h3>
            <p>{t("Access, correct, or request deletion of your personal data.")}</p>
          </div>
          <Link className="acct-link" href="/privacy">{t("View privacy options")}</Link>
        </div>
      </section>

      <section className="acct-settings acct-settings-group" aria-labelledby="account-security-title">
        <h2 className="acct-section-heading" id="account-security-title">{t("Sign-in & security")}</h2>
        {googleMessage ? <p className="acct-form-msg" role="status" aria-live="polite">{googleMessage}</p> : null}
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
                  <input ref={emailInputRef} type="email" autoComplete="email" maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} />
                </label>
                <label className="acct-field">
                  {account.has_password ? (
                    <>
                      <span>{t("Current password")}</span>
                      <input type="password" autoComplete="current-password" required value={emailPassword} onChange={(event) => setEmailPassword(event.target.value)} />
                    </>
                  ) : (
                    <span>{t("Verify your Google account before saving.")}</span>
                  )}
                </label>
                <div className="acct-form-actions">
                  {passkeyFeatureState === "enabled" && passkeyBrowserSupported && passkeyMethods?.passkey_count ? (
                    <button className="btn" type="button" disabled={emailPasskeyBusy || pending} onClick={() => void saveEmailWithPasskey()}>
                      {t(emailPasskeyBusy ? "Verifying with your passkey…" : "Save email with passkey")}
                    </button>
                  ) : null}
                  {!account.has_password && account.google_oauth_enabled ? (
                    <button className="btn" type="button" disabled={pending} onClick={() => void startGoogleReauthentication("email_change")}>
                      {t("Verify with Google")}
                    </button>
                  ) : null}
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
              <form ref={passwordFormRef} className="acct-form acct-inline-editor" id="account-password-editor" onSubmit={savePassword}>
                {account.has_password ? (
                  <label className="acct-field">
                    <span>{t("Current password")}</span>
                    <input name="current_password" type="password" autoComplete="current-password" required />
                  </label>
                ) : account.google_oauth_enabled ? (
                  <button className="btn" type="button" disabled={pending} onClick={() => void startGoogleReauthentication("password_add")}>
                    {t("Verify with Google")}
                  </button>
                ) : <p className="acct-form-msg">{t("Google sign-in is currently unavailable.")}</p>}
                <label className="acct-field">
                  <span>{t(account.has_password ? "New password (min 8 characters)" : "Create password (min 8 characters)")}</span>
                  <input name="new_password" type="password" autoComplete="new-password" minLength={8} required />
                </label>
                {!account.has_password && passkeyFeatureState === "enabled" && passkeyBrowserSupported && passkeyMethods?.passkey_count ? (
                  <button className="btn" type="button" disabled={passwordPasskeyBusy || pending} onClick={() => void createPasswordWithPasskey()}>
                    {t(passwordPasskeyBusy ? "Verifying with your passkey…" : "Create password with passkey")}
                  </button>
                ) : null}
                <button className="btn btn-primary" type="submit">{t(account.has_password ? "Update password" : "Add password")}</button>
                <div className={`acct-form-msg${passwordMessage === t("Password updated.") ? " ok" : passwordMessage && passwordMessage !== t("Updating…") ? " error" : ""}`} role="status" aria-live="polite">{passwordMessage}</div>
              </form>
            ) : null}
          </div>
        </div>
        {account.google_oauth_enabled || account.google_linked ? (
          <div className="acct-security-item">
            <div className="acct-setting-copy">
              <h3>{t("Google account")}</h3>
              <p>{t(account.google_linked ? "Google is linked to this account." : "Google is not linked.")}</p>
            </div>
            <div className="acct-security-action">
              {account.google_linked && account.has_password ? (
                <button className="btn" type="button" aria-expanded={googleUnlinkEditorOpen} onClick={() => {
                  setGoogleUnlinkEditorOpen((open) => !open);
                  setGoogleMessage("");
                }}>
                  {t(googleUnlinkEditorOpen ? "Cancel" : "Unlink Google")}
                </button>
              ) : null}
              {!account.google_linked && account.google_oauth_enabled ? (
                <button className="btn" type="button" aria-expanded={googleLinkEditorOpen} onClick={() => {
                  setGoogleLinkEditorOpen((open) => !open);
                  setGoogleMessage("");
                }}>
                  {t(googleLinkEditorOpen ? "Cancel" : "Link Google")}
                </button>
              ) : null}
              {account.google_linked && !account.has_password ? (
                <p className="acct-form-msg">{t("Add a password before unlinking Google.")}</p>
              ) : null}
              {googleLinkEditorOpen ? (
                <form className="acct-form acct-inline-editor" onSubmit={linkGoogle}>
                  <label className="acct-field">
                    <span>{t("Current password")}</span>
                    <input type="password" autoComplete="current-password" required value={googleLinkPassword} onChange={(event) => setGoogleLinkPassword(event.target.value)} />
                  </label>
                  <p className="acct-form-msg">{t("Google will ask you to verify your account before linking.")}</p>
                  <button className="btn btn-primary" type="submit" disabled={pending}>{t("Continue with Google")}</button>
                </form>
              ) : null}
              {googleUnlinkEditorOpen ? (
                <form className="acct-form acct-inline-editor" onSubmit={unlinkGoogle}>
                  <label className="acct-field">
                    <span>{t("Current password")}</span>
                    <input type="password" autoComplete="current-password" required value={googleUnlinkPassword} onChange={(event) => setGoogleUnlinkPassword(event.target.value)} />
                  </label>
                  <p className="acct-form-msg">{t("You must keep at least one sign-in method.")}</p>
                  <button className="btn btn-danger" type="submit">{t("Unlink Google")}</button>
                </form>
              ) : null}
            </div>
          </div>
        ) : null}
        <div className="acct-security-item" aria-labelledby="account-passkeys-title">
          <div className="acct-setting-copy">
            <h3 id="account-passkeys-title">{t("Passkeys")}</h3>
            <p>{t("Use a device screen lock or security key to verify sensitive account changes.")}</p>
            {passkeyFeatureState === "enabled" && passkeyMethods ? (
              <>
                <p>{t("Available verification methods")}: {passkeyMethods.passkey_count > 0 ? t("Passkey") : passkeyMethods.has_password ? t("Password") : passkeyMethods.google_linked ? t("Google account") : t("No additional verification method")}</p>
                <p>{t("Passkeys enrolled")}: {passkeyMethods.passkey_count}</p>
                {passkeyMethods.recovery_codes_remaining > 0 ? (
                  <p>{t("Unused recovery codes")}: {passkeyMethods.recovery_codes_remaining}</p>
                ) : null}
              </>
            ) : passkeyFeatureState === "disabled" ? (
              <p>{t("Passkeys are not enabled for this service.")}</p>
            ) : passkeyFeatureState === "loading" ? (
              <p aria-live="polite">{t("Loading passkey settings…")}</p>
            ) : null}
            {!passkeyBrowserSupported && passkeyFeatureState === "enabled" ? (
              <p role="status">{t("Passkeys are not supported in this browser or connection.")}</p>
            ) : null}
            {passkeyEligibility && !passkeyEligibility.eligible ? (
              <p>{t("Passkey setup is unavailable")}: {t(passkeyEligibility.reason === "password_verification_required" ? "A current password is required to add a passkey." : "The maximum number of passkeys has been reached.")}</p>
            ) : null}
          </div>
          <div className="acct-security-action">
            {passkeyFeatureState === "enabled" && passkeyEligibility?.eligible && passkeyBrowserSupported ? (
              <>
                <label className="acct-field">
                  <span>{t("Current password")}</span>
                  <input
                    type="password"
                    autoComplete="current-password"
                    value={passkeyPassword}
                    onChange={(event) => setPasskeyPassword(event.target.value)}
                    disabled={passkeyBusy}
                  />
                </label>
                <button
                  className="btn btn-primary"
                  type="button"
                  disabled={passkeyBusy || pending || !passkeyPassword}
                  onClick={() => void enrollPasskey()}
                >
                  {t(passkeyBusy ? "Setting up passkey…" : "Add a passkey")}
                </button>
              </>
            ) : null}
            {passkeyFeatureState === "enabled" && passkeyMethods?.passkey_count ? (
              passkeyMethods.recovery_codes_remaining === 0 ? (
                <button
                  className="btn"
                  type="button"
                  disabled={passkeyBusy || pending || !passkeyBrowserSupported}
                  onClick={() => void setupRecoveryCodes()}
                >
                  {t(passkeyBusy ? "Verifying with your passkey…" : "Set up recovery codes")}
                </button>
              ) : (
                <p className="acct-form-msg">{t("Recovery-code regeneration and credential replacement are not available.")}</p>
              )
            ) : null}
            {passkeyFeatureState === "error" && passkeyMessage ? (
              <p className="acct-form-msg error" role="alert">{passkeyMessage}</p>
            ) : null}
          </div>
          {passkeyMessage && passkeyFeatureState !== "error" ? (
            <p className="acct-form-msg" role="status" aria-live="polite">{passkeyMessage}</p>
          ) : null}
          {recoveryCodes ? (
            <div className="acct-recovery-codes" aria-labelledby="recovery-codes-title">
              <h4 id="recovery-codes-title">{t("Recovery codes")}</h4>
              <p>{t("Save these codes somewhere private. They are shown only once and cannot replace a passkey or sign-in method.")}</p>
              <ol>
                {recoveryCodes.map((code) => <li key={code}><code>{code}</code></li>)}
              </ol>
              <button
                className="btn"
                type="button"
                onClick={() => setRecoveryCodes(null)}
              >
                {t("Hide and clear codes")}
              </button>
            </div>
          ) : null}
        </div>
      </section>

      <section className="acct-settings acct-session" aria-labelledby="account-session-title">
        <h2 className="acct-section-heading" id="account-session-title">{t("Session")}</h2>
        <div className="acct-session-actions">
          <LogoutButton className="btn" />
          <button className="btn" type="button" disabled={pending} aria-expanded={logoutEditorOpen} onClick={() => setLogoutEditorOpen((open) => !open)}>{t("Sign out of all devices")}</button>
        </div>
        {logoutEditorOpen ? (
          <div className="acct-form acct-inline-editor">
            {account.has_password ? (
              <label className="acct-field">
                <span>{t("Current password")}</span>
                <input type="password" autoComplete="current-password" required value={logoutPassword} onChange={(event) => setLogoutPassword(event.target.value)} />
              </label>
            ) : account.google_oauth_enabled ? (
              <button className="btn" type="button" disabled={pending} onClick={() => void startGoogleReauthentication("logout_all")}>{t("Verify with Google")}</button>
            ) : <p className="acct-form-msg">{t("Google sign-in is currently unavailable.")}</p>}
            {passkeyFeatureState === "enabled" && passkeyBrowserSupported && passkeyMethods?.passkey_count ? (
              <button className="btn" type="button" disabled={logoutPasskeyBusy || pending} onClick={() => void logoutAllWithPasskey()}>
                {t(logoutPasskeyBusy ? "Verifying with your passkey…" : "Sign out of all devices with passkey")}
              </button>
            ) : null}
            <button className="btn btn-primary" type="button" disabled={pending} onClick={() => void logoutAll()}>{t("Sign out of all devices")}</button>
            <div className="acct-form-msg" role="status" aria-live="polite">{logoutMessage}</div>
          </div>
        ) : null}
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
                {account.has_password ? (
                  <>
                    <span>{t("Current password")}</span>
                    <input name="current_password" type="password" autoComplete="current-password" required />
                  </>
                ) : (
                  <span>{t("Google reauthentication is required before deletion.")}</span>
                )}
              </label>
              {!account.has_password && account.google_oauth_enabled ? (
                <button className="btn" type="button" disabled={pending} onClick={() => void startGoogleReauthentication("account_delete")}>{t("Verify with Google")}</button>
              ) : null}
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
