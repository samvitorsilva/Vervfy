(globalThis["TURBOPACK"] || (globalThis["TURBOPACK"] = [])).push([typeof document === "object" ? document.currentScript : undefined,
"[project]/src/components/account-settings.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>AccountSettings
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$client$2f$app$2d$dir$2f$link$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/client/app-dir/link.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/api/client.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$auth$2f$logout$2d$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/components/auth/logout-button.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$artist$2d$explorer$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/components/artist-explorer.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/store/player-store.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/i18n.tsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
"use client";
;
;
;
;
;
;
;
function dateLabel(timestamp, language) {
    if (!timestamp) return "—";
    return new Date(timestamp * 1000).toLocaleDateString(language, {
        year: "numeric",
        month: "long",
        day: "numeric"
    });
}
async function sendJson(path, method, payload) {
    const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])(path, {
        method,
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
    }, {
        csrf: true,
        retryCsrfOnForbidden: true
    });
    await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(response);
    return response.json();
}
function AccountSettings({ active, onToast, onPhotoChange }) {
    _s();
    const { language, t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"])();
    const tracks = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "AccountSettings.usePlayerStore[tracks]": (state)=>state.tracks
    }["AccountSettings.usePlayerStore[tracks]"]);
    const playlists = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "AccountSettings.usePlayerStore[playlists]": (state)=>state.playlists
    }["AccountSettings.usePlayerStore[playlists]"]);
    const setView = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "AccountSettings.usePlayerStore[setView]": (state)=>state.setView
    }["AccountSettings.usePlayerStore[setView]"]);
    const [account, setAccount] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [error, setError] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [email, setEmail] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [emailPassword, setEmailPassword] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [emailMessage, setEmailMessage] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [passwordMessage, setPasswordMessage] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [photoMessage, setPhotoMessage] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [photoEditorOpen, setPhotoEditorOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [photoDraftUrl, setPhotoDraftUrl] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [photoRemoved, setPhotoRemoved] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [photoImageLoaded, setPhotoImageLoaded] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [photoZoom, setPhotoZoom] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(1);
    const [photoOffset, setPhotoOffset] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])({
        x: 0,
        y: 0
    });
    const [photoSaving, setPhotoSaving] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [deleteMessage, setDeleteMessage] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [pending, setPending] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const photoInputRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const photoImageRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const photoStageRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const photoObjectUrlRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const photoDragRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "AccountSettings.useEffect": ()=>({
                "AccountSettings.useEffect": ()=>{
                    if (photoObjectUrlRef.current) URL.revokeObjectURL(photoObjectUrlRef.current);
                }
            })["AccountSettings.useEffect"]
    }["AccountSettings.useEffect"], []);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "AccountSettings.useEffect": ()=>{
            if (!photoEditorOpen || photoSaving) return;
            function handleKeyDown(event) {
                if (event.key === "Escape") closePhotoEditor();
            }
            document.addEventListener("keydown", handleKeyDown);
            return ({
                "AccountSettings.useEffect": ()=>document.removeEventListener("keydown", handleKeyDown)
            })["AccountSettings.useEffect"];
        }
    }["AccountSettings.useEffect"], [
        photoEditorOpen,
        photoSaving
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "AccountSettings.useEffect": ()=>{
            if (!active || account) return;
            let cancelled = false;
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])("/api/me").then({
                "AccountSettings.useEffect": async (response)=>{
                    await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(response);
                    return response.json();
                }
            }["AccountSettings.useEffect"]).then({
                "AccountSettings.useEffect": (data)=>{
                    if (!cancelled) {
                        setAccount(data);
                        setEmail(data.email ?? "");
                        onPhotoChange(data.photo_url);
                    }
                }
            }["AccountSettings.useEffect"]).catch({
                "AccountSettings.useEffect": (reason)=>{
                    if (!cancelled) setError(reason instanceof Error ? reason.message : t("Could not load account."));
                }
            }["AccountSettings.useEffect"]);
            return ({
                "AccountSettings.useEffect": ()=>{
                    cancelled = true;
                }
            })["AccountSettings.useEffect"];
        }
    }["AccountSettings.useEffect"], [
        account,
        active,
        onPhotoChange,
        t
    ]);
    async function saveEmail(event) {
        event.preventDefault();
        setEmailMessage(t("Saving email…"));
        try {
            const data = await sendJson("/api/account/email", "PUT", {
                email: email.trim(),
                current_password: emailPassword
            });
            const nextEmail = typeof data.email === "string" ? data.email : null;
            setAccount((current)=>current ? {
                    ...current,
                    email: nextEmail
                } : current);
            setEmail(nextEmail ?? "");
            setEmailPassword("");
            setEmailMessage(nextEmail ? t("Email saved to your account.") : t("Email removed."));
        } catch (reason) {
            setEmailMessage(reason instanceof Error ? reason.message : t("Could not update email."));
        }
    }
    async function savePassword(event) {
        event.preventDefault();
        const form = event.currentTarget;
        const formData = new FormData(form);
        setPasswordMessage(t("Updating…"));
        try {
            await sendJson("/api/account/password", "POST", {
                current_password: String(formData.get("current_password") ?? ""),
                new_password: String(formData.get("new_password") ?? "")
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
        setPhotoOffset({
            x: 0,
            y: 0
        });
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
        setPhotoOffset({
            x: 0,
            y: 0
        });
    }
    function choosePhoto(file) {
        if (!file) return;
        if (![
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/gif"
        ].includes(file.type)) {
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
        setPhotoOffset({
            x: 0,
            y: 0
        });
        setPhotoMessage("");
    }
    function clampPhotoOffset(x, y, zoom) {
        const image = photoImageRef.current;
        const stage = photoStageRef.current;
        if (!image || !stage || !image.naturalWidth || !image.naturalHeight) {
            return {
                x: 0,
                y: 0
            };
        }
        const stageSize = stage.clientWidth;
        const baseScale = stageSize / Math.min(image.naturalWidth, image.naturalHeight);
        const maxX = Math.max(0, (image.naturalWidth * baseScale * zoom - stageSize) / 2);
        const maxY = Math.max(0, (image.naturalHeight * baseScale * zoom - stageSize) / 2);
        return {
            x: Math.max(-maxX, Math.min(maxX, x)),
            y: Math.max(-maxY, Math.min(maxY, y))
        };
    }
    function movePhoto(event) {
        const drag = photoDragRef.current;
        if (!drag || drag.pointerId !== event.pointerId) return;
        setPhotoOffset(clampPhotoOffset(drag.offsetX + event.clientX - drag.startX, drag.offsetY + event.clientY - drag.startY, photoZoom));
    }
    function setZoom(value) {
        setPhotoZoom(value);
        setPhotoOffset((current)=>clampPhotoOffset(current.x, current.y, value));
    }
    function handlePhotoDragStart(event) {
        if (!photoImageLoaded || photoRemoved) return;
        event.currentTarget.setPointerCapture(event.pointerId);
        photoDragRef.current = {
            pointerId: event.pointerId,
            startX: event.clientX,
            startY: event.clientY,
            offsetX: photoOffset.x,
            offsetY: photoOffset.y
        };
    }
    async function savePhoto() {
        setPhotoSaving(true);
        setPhotoMessage(photoRemoved ? t("Removing…") : t("Saving…"));
        try {
            if (photoRemoved) {
                await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])("/api/account/photo", {
                    method: "DELETE"
                }, {
                    csrf: true,
                    retryCsrfOnForbidden: true
                }));
                setAccount((current)=>current ? {
                        ...current,
                        photo_url: null
                    } : current);
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
            const photo = await new Promise((resolve, reject)=>{
                canvas.toBlob((blob)=>blob ? resolve(blob) : reject(new Error("Could not prepare this photo.")), "image/jpeg", 0.92);
            });
            const body = new FormData();
            body.append("file", photo, "profile-photo.jpg");
            const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])("/api/account/photo", {
                method: "POST",
                body
            }, {
                csrf: true,
                retryCsrfOnForbidden: true
            });
            await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(response);
            const data = await response.json();
            const photoUrl = `${data.photo_url}?v=${Date.now()}`;
            setAccount((current)=>current ? {
                    ...current,
                    photo_url: photoUrl
                } : current);
            onPhotoChange(photoUrl);
            closePhotoEditor();
            onToast(t("Profile photo saved."));
        } catch (reason) {
            setPhotoMessage(reason instanceof Error ? reason.message : t("Could not save profile photo."));
        } finally{
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
    async function deleteAccount(event) {
        event.preventDefault();
        if (!window.confirm(t("Delete your account and all of its music data permanently?"))) return;
        const formData = new FormData(event.currentTarget);
        setDeleteMessage(t("Deleting account…"));
        setPending(true);
        try {
            await sendJson("/api/account", "DELETE", {
                current_password: String(formData.get("current_password") ?? ""),
                confirmation: String(formData.get("confirmation") ?? "")
            });
            window.location.assign("/login?account_deleted=1");
        } catch (reason) {
            setPending(false);
            setDeleteMessage(reason instanceof Error ? reason.message : t("Could not delete account."));
        }
    }
    const likedCount = tracks.filter((track)=>track.favorite).length;
    const artistCount = new Set(tracks.flatMap(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$artist$2d$explorer$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["artistNames"])).size;
    const cards = [
        {
            label: t("Music files"),
            count: tracks.length,
            subtitle: t("tracks in your library"),
            view: "library"
        },
        {
            label: t("Liked songs"),
            count: likedCount,
            subtitle: t("saved favorites"),
            view: "favorites"
        },
        {
            label: t("Artists"),
            count: artistCount,
            subtitle: t("in your library"),
            view: "artists"
        },
        {
            label: t("Playlists"),
            count: playlists.length,
            subtitle: t("saved playlists"),
            view: "playlists"
        }
    ];
    if (!account) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "account-view acct-loading",
            children: error || t("Loading account…")
        }, void 0, false, {
            fileName: "[project]/src/components/account-settings.tsx",
            lineNumber: 343,
            columnNumber: 12
        }, this);
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "account-view",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                className: "acct-card",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "acct-avatar",
                        type: "button",
                        title: t("Edit profile photo"),
                        "aria-label": t("Edit profile photo"),
                        onClick: openPhotoEditor,
                        children: account.photo_url ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                            src: account.photo_url,
                            alt: t("Profile photo")
                        }, void 0, false, {
                            fileName: "[project]/src/components/account-settings.tsx",
                            lineNumber: 350,
                            columnNumber: 32
                        }, this) : account.username.slice(0, 1).toUpperCase()
                    }, void 0, false, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 349,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "acct-name",
                                children: account.username
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 352,
                                columnNumber: 14
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "acct-sub",
                                children: [
                                    account.email ?? t("No email on file"),
                                    " · ",
                                    t("Member since"),
                                    " ",
                                    dateLabel(account.created_at, language)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 352,
                                columnNumber: 65
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 352,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/account-settings.tsx",
                lineNumber: 348,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "acct-grid",
                children: cards.map((card)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        type: "button",
                        className: "acct-panel",
                        onClick: ()=>setView(card.view),
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                className: "acct-panel-head",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        children: card.label
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/account-settings.tsx",
                                        lineNumber: 356,
                                        columnNumber: 161
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        className: "acct-count",
                                        children: card.count
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/account-settings.tsx",
                                        lineNumber: 356,
                                        columnNumber: 186
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 356,
                                columnNumber: 127
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                className: "acct-panel-sub",
                                children: card.subtitle
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 356,
                                columnNumber: 241
                            }, this)
                        ]
                    }, card.label, true, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 356,
                        columnNumber: 30
                    }, this))
            }, void 0, false, {
                fileName: "[project]/src/components/account-settings.tsx",
                lineNumber: 355,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                className: "acct-settings",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "acct-settings-title",
                        children: t("Language")
                    }, void 0, false, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 360,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        className: "acct-danger-copy",
                        children: t("Choose the language used by Vervfy.")
                    }, void 0, false, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 361,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["LanguageSelect"], {}, void 0, false, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 362,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/account-settings.tsx",
                lineNumber: 359,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                className: "acct-settings",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "acct-settings-title",
                        children: t("Credits")
                    }, void 0, false, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 366,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$client$2f$app$2d$dir$2f$link$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                        className: "artist-website",
                        href: "/credits",
                        children: [
                            t("Credits and data sources"),
                            " ↗"
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 367,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/account-settings.tsx",
                lineNumber: 365,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                className: "acct-settings",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "acct-settings-title",
                        children: t("Email address")
                    }, void 0, false, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 371,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("form", {
                        className: "acct-form",
                        onSubmit: saveEmail,
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                type: "email",
                                placeholder: "you@example.com",
                                autoComplete: "email",
                                maxLength: 320,
                                value: email,
                                onChange: (event)=>setEmail(event.target.value)
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 373,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                type: "password",
                                placeholder: t("Current password"),
                                autoComplete: "current-password",
                                required: true,
                                value: emailPassword,
                                onChange: (event)=>setEmailPassword(event.target.value)
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 374,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "btn btn-primary",
                                type: "submit",
                                children: t("Save email")
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 375,
                                columnNumber: 11
                            }, this),
                            account.email ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "btn",
                                type: "button",
                                onClick: ()=>setEmail(""),
                                children: t("Clear email")
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 376,
                                columnNumber: 28
                            }, this) : null,
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: `acct-form-msg${emailMessage.includes("salvo") || emailMessage.includes("removido") || emailMessage.includes("saved") || emailMessage.includes("removed") ? " ok" : emailMessage && !emailMessage.includes("Salvando") && !emailMessage.includes("Saving") ? " error" : ""}`,
                                children: emailMessage || t("Email is account information only; sign in with your username.")
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 377,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 372,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/account-settings.tsx",
                lineNumber: 370,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                className: "acct-settings",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "acct-settings-title",
                        children: t("Change password")
                    }, void 0, false, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 382,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("form", {
                        className: "acct-form",
                        onSubmit: savePassword,
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                name: "current_password",
                                type: "password",
                                placeholder: t("Current password"),
                                autoComplete: "current-password",
                                required: true
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 384,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                name: "new_password",
                                type: "password",
                                placeholder: t("New password (min 8 characters)"),
                                autoComplete: "new-password",
                                minLength: 8,
                                required: true
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 385,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "btn btn-primary",
                                type: "submit",
                                children: t("Update password")
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 386,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: `acct-form-msg${passwordMessage === t("Password updated.") ? " ok" : passwordMessage && passwordMessage !== t("Updating…") ? " error" : ""}`,
                                children: passwordMessage
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 387,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 383,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/account-settings.tsx",
                lineNumber: 381,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                className: "acct-settings",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "acct-settings-title",
                        children: t("Session")
                    }, void 0, false, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 392,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "acct-form",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$auth$2f$logout$2d$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {}, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 393,
                                columnNumber: 36
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "btn",
                                type: "button",
                                disabled: pending,
                                onClick: ()=>void logoutAll(),
                                children: t("Sign out of all devices")
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 393,
                                columnNumber: 52
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 393,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/account-settings.tsx",
                lineNumber: 391,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                className: "acct-settings acct-danger-zone",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "acct-settings-title",
                        children: t("Delete account")
                    }, void 0, false, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 397,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        className: "acct-danger-copy",
                        children: t("Permanently removes your profile, music files, playlists, favorites, and saved lyrics. This cannot be undone.")
                    }, void 0, false, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 398,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("form", {
                        className: "acct-form",
                        onSubmit: deleteAccount,
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                name: "current_password",
                                type: "password",
                                placeholder: t("Current password"),
                                autoComplete: "current-password",
                                required: true
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 400,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                name: "confirmation",
                                type: "text",
                                placeholder: t("Type DELETE to confirm"),
                                autoComplete: "off",
                                required: true
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 401,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "btn btn-danger",
                                type: "submit",
                                disabled: pending,
                                children: t("Delete account")
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 402,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: `acct-form-msg${deleteMessage && !deleteMessage.includes("Deleting") ? " error" : ""}`,
                                children: deleteMessage
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 403,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/account-settings.tsx",
                        lineNumber: 399,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/account-settings.tsx",
                lineNumber: 396,
                columnNumber: 7
            }, this),
            photoEditorOpen ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "photo-editor-overlay open",
                onClick: (event)=>{
                    if (event.target === event.currentTarget && !photoSaving) closePhotoEditor();
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                    className: "photo-editor-card",
                    role: "dialog",
                    "aria-modal": "true",
                    "aria-labelledby": "photo-editor-title",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "photo-editor-head",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                            id: "photo-editor-title",
                                            children: t("Profile photo")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/account-settings.tsx",
                                            lineNumber: 417,
                                            columnNumber: 17
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                            children: t("Choose a photo, adjust its zoom and position, then save.")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/account-settings.tsx",
                                            lineNumber: 418,
                                            columnNumber: 17
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/account-settings.tsx",
                                    lineNumber: 416,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn",
                                    type: "button",
                                    "aria-label": t("Close photo editor"),
                                    disabled: photoSaving,
                                    onClick: closePhotoEditor,
                                    children: t("Close")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/account-settings.tsx",
                                    lineNumber: 420,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/account-settings.tsx",
                            lineNumber: 415,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                            ref: photoInputRef,
                            type: "file",
                            accept: "image/jpeg,image/png,image/webp,image/gif",
                            hidden: true,
                            onChange: (event)=>{
                                choosePhoto(event.currentTarget.files?.[0]);
                                event.currentTarget.value = "";
                            }
                        }, void 0, false, {
                            fileName: "[project]/src/components/account-settings.tsx",
                            lineNumber: 423,
                            columnNumber: 13
                        }, this),
                        photoDraftUrl && !photoRemoved ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "photo-editor-stage",
                            ref: photoStageRef,
                            onPointerDown: handlePhotoDragStart,
                            onPointerMove: movePhoto,
                            onPointerUp: ()=>{
                                photoDragRef.current = null;
                            },
                            onPointerCancel: ()=>{
                                photoDragRef.current = null;
                            },
                            role: "img",
                            "aria-label": t("Photo crop preview; drag to reposition"),
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                ref: photoImageRef,
                                src: photoDraftUrl,
                                alt: "",
                                draggable: false,
                                onLoad: ()=>setPhotoImageLoaded(true),
                                onError: ()=>{
                                    setPhotoImageLoaded(false);
                                    setPhotoMessage(t("Could not load this photo."));
                                },
                                style: {
                                    width: photoImageRef.current?.naturalWidth && photoStageRef.current ? `${photoImageRef.current.naturalWidth * photoStageRef.current.clientWidth / Math.min(photoImageRef.current.naturalWidth, photoImageRef.current.naturalHeight) * photoZoom}px` : undefined,
                                    height: photoImageRef.current?.naturalHeight && photoStageRef.current ? `${photoImageRef.current.naturalHeight * photoStageRef.current.clientWidth / Math.min(photoImageRef.current.naturalWidth, photoImageRef.current.naturalHeight) * photoZoom}px` : undefined,
                                    left: `calc(50% + ${photoOffset.x}px)`,
                                    top: `calc(50% + ${photoOffset.y}px)`,
                                    transform: "translate(-50%, -50%)"
                                }
                            }, void 0, false, {
                                fileName: "[project]/src/components/account-settings.tsx",
                                lineNumber: 445,
                                columnNumber: 17
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/src/components/account-settings.tsx",
                            lineNumber: 435,
                            columnNumber: 15
                        }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "photo-editor-stage photo-editor-empty",
                            "aria-live": "polite",
                            children: photoRemoved ? t("Photo will be removed when you save.") : t("Choose a photo to get started.")
                        }, void 0, false, {
                            fileName: "[project]/src/components/account-settings.tsx",
                            lineNumber: 469,
                            columnNumber: 15
                        }, this),
                        photoDraftUrl && !photoRemoved ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                            className: "photo-editor-zoom",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                    children: t("Zoom")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/account-settings.tsx",
                                    lineNumber: 476,
                                    columnNumber: 17
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                    type: "range",
                                    min: "1",
                                    max: "3",
                                    step: "0.05",
                                    value: photoZoom,
                                    "aria-label": t("Photo zoom"),
                                    disabled: !photoImageLoaded || photoSaving,
                                    onChange: (event)=>setZoom(Number(event.currentTarget.value))
                                }, void 0, false, {
                                    fileName: "[project]/src/components/account-settings.tsx",
                                    lineNumber: 477,
                                    columnNumber: 17
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                    children: [
                                        photoZoom.toFixed(1),
                                        "×"
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/account-settings.tsx",
                                    lineNumber: 487,
                                    columnNumber: 17
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/account-settings.tsx",
                            lineNumber: 475,
                            columnNumber: 15
                        }, this) : null,
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "photo-editor-actions",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn",
                                    type: "button",
                                    disabled: photoSaving,
                                    onClick: ()=>photoInputRef.current?.click(),
                                    children: account.photo_url ? t("Choose another photo") : t("Choose photo")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/account-settings.tsx",
                                    lineNumber: 492,
                                    columnNumber: 15
                                }, this),
                                account.photo_url ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: photoRemoved ? "btn" : "btn btn-danger",
                                    type: "button",
                                    disabled: photoSaving,
                                    onClick: ()=>{
                                        setPhotoRemoved((removed)=>!removed);
                                        setPhotoMessage("");
                                    },
                                    children: photoRemoved ? "Keep current photo" : "Remove photo"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/account-settings.tsx",
                                    lineNumber: 496,
                                    columnNumber: 17
                                }, this) : null,
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn btn-primary",
                                    type: "button",
                                    disabled: photoSaving || !photoRemoved && !photoImageLoaded,
                                    onClick: ()=>void savePhoto(),
                                    children: photoSaving ? "Saving…" : "Save"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/account-settings.tsx",
                                    lineNumber: 508,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/account-settings.tsx",
                            lineNumber: 491,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: `acct-form-msg${photoMessage && !photoMessage.includes("Saving") && !photoMessage.includes("Removing") ? " error" : ""}`,
                            role: "status",
                            children: photoMessage || "JPEG, PNG, WebP, or GIF up to 5 MB."
                        }, void 0, false, {
                            fileName: "[project]/src/components/account-settings.tsx",
                            lineNumber: 512,
                            columnNumber: 13
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/account-settings.tsx",
                    lineNumber: 414,
                    columnNumber: 11
                }, this)
            }, void 0, false, {
                fileName: "[project]/src/components/account-settings.tsx",
                lineNumber: 408,
                columnNumber: 9
            }, this) : null
        ]
    }, void 0, true, {
        fileName: "[project]/src/components/account-settings.tsx",
        lineNumber: 347,
        columnNumber: 5
    }, this);
}
_s(AccountSettings, "X/bWDIYO7EmXixBxruGu7awzRcY=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"]
    ];
});
_c = AccountSettings;
var _c;
__turbopack_context__.k.register(_c, "AccountSettings");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/src/components/artist-explorer.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "artistNames",
    ()=>artistNames,
    "default",
    ()=>ArtistExplorer
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/api/client.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/store/player-store.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/i18n.tsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature(), _s1 = __turbopack_context__.k.signature();
"use client";
;
;
;
;
function artistNames(track) {
    const names = track.artist.split(/\s*(?:,|;|\/|&|\bfeat(?:uring)?\.?|\bft\.?|\bwith\b)\s*/i).flatMap((part)=>part.split(/\s+and\s+/i).flatMap((name)=>name.split(/\s+x\s+/))).map((part)=>part.trim()).filter(Boolean);
    return [
        ...new Set(names)
    ];
}
function coverUrlsForArtist(artist) {
    const covers = [];
    const seen = new Set();
    for (const track of artist.tracks){
        if (!track.coverUrl || !track.hasCover && ![
            "embedded",
            "upload",
            "user",
            "musicbrainz",
            "audiodb"
        ].includes(track.coverSource ?? "")) continue;
        const album = track.album.trim().toLocaleLowerCase();
        const key = album && !/^unknown album$/i.test(album) ? `album:${album}` : `track:${track.coverUrl}`;
        if (seen.has(key)) continue;
        seen.add(key);
        covers.push(track.coverUrl);
        if (covers.length === 4) break;
    }
    return covers;
}
function formatDuration(seconds, t) {
    const minutes = Math.round(seconds / 60);
    const hours = Math.floor(minutes / 60);
    return hours === 0 ? `${minutes} ${t("min")}` : `${hours} ${t("hr")}${minutes % 60 ? ` ${minutes % 60} ${t("min")}` : ""}`;
}
function safeExternalUrl(value) {
    if (typeof value !== "string") return null;
    try {
        const url = new URL(value);
        return url.protocol === "https:" ? url.href : null;
    } catch  {
        return null;
    }
}
function artistKey(name) {
    return name.toLocaleLowerCase();
}
function artistImageKey(name) {
    return name.normalize("NFKD").replace(/\p{M}/gu, "").toLocaleLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}
function artistInitials(name) {
    const parts = name.trim().split(/\s+/).filter(Boolean);
    if (parts.length > 1) return `${parts[0][0]}${parts.at(-1)?.[0]}`.toLocaleUpperCase();
    return (parts[0]?.slice(0, 2) || "?").toLocaleUpperCase();
}
function artistPhotoUrl(name, version = 0) {
    const query = new URLSearchParams({
        name
    });
    if (version) query.set("v", String(version));
    return `/api/artists/photo?${query}`;
}
function smallArtistImageUrl(value) {
    const url = safeExternalUrl(value);
    if (!url) return null;
    try {
        const parsed = new URL(url);
        parsed.pathname = `${parsed.pathname.replace(/\/+$/, "")}/small`;
        return parsed.href;
    } catch  {
        return null;
    }
}
function ArtistAvatar({ name, className, userPhotoUrl, artistImageUrl, coverUrls }) {
    _s();
    const candidates = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "ArtistAvatar.useMemo[candidates]": ()=>[
                ...userPhotoUrl ? [
                    {
                        kind: "image",
                        url: userPhotoUrl
                    }
                ] : [],
                ...artistImageUrl ? [
                    {
                        kind: "image",
                        url: artistImageUrl
                    }
                ] : [],
                ...coverUrls.length ? [
                    {
                        kind: "covers",
                        url: coverUrls.join("|")
                    }
                ] : []
            ]
    }["ArtistAvatar.useMemo[candidates]"], [
        artistImageUrl,
        coverUrls,
        userPhotoUrl
    ]);
    const signature = candidates.map((candidate)=>`${candidate.kind}:${candidate.url}`).join("\n");
    const [imageState, setImageState] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])({
        signature: "",
        failed: [],
        loaded: []
    });
    const failed = imageState.signature === signature ? imageState.failed : [];
    const loaded = imageState.signature === signature ? imageState.loaded : [];
    const markLoaded = (url)=>{
        setImageState((current)=>({
                signature,
                failed: current.signature === signature ? current.failed : [],
                loaded: current.signature === signature && current.loaded.includes(url) ? current.loaded : [
                    ...current.signature === signature ? current.loaded : [],
                    url
                ]
            }));
    };
    const markFailed = (url)=>{
        setImageState((current)=>({
                signature,
                failed: current.signature === signature && current.failed.includes(url) ? current.failed : [
                    ...current.signature === signature ? current.failed : [],
                    url
                ],
                loaded: current.signature === signature ? current.loaded : []
            }));
    };
    const active = candidates.find((candidate)=>!failed.includes(candidate.url));
    let hash = 2_166_136_261;
    for (const character of name){
        hash = Math.imul(hash ^ character.codePointAt(0), 16_777_619);
    }
    const hue = (hash >>> 0) % 360;
    const style = {
        "--artist-avatar-start": `hsl(${hue} 72% 28%)`,
        "--artist-avatar-end": `hsl(${(hue + 52) % 360} 76% 36%)`
    };
    if (active?.kind === "image") {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
            className: `${className} artist-avatar-image${loaded.includes(active.url) ? " is-loaded" : ""}`,
            src: active.url,
            alt: name,
            loading: "lazy",
            decoding: "async",
            onLoad: ()=>markLoaded(active.url),
            onError: ()=>markFailed(active.url)
        }, void 0, false, {
            fileName: "[project]/src/components/artist-explorer.tsx",
            lineNumber: 177,
            columnNumber: 7
        }, this);
    }
    if (active?.kind === "covers") {
        const covers = active.url.split("|");
        const mosaicClass = covers.length > 1 ? ` artist-avatar-mosaic artist-avatar-mosaic-${covers.length}` : "";
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
            className: `${className} artist-avatar-covers${mosaicClass}`,
            role: "img",
            "aria-label": name,
            children: covers.slice(0, 4).map((url)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                    className: `artist-avatar-image${loaded.includes(url) ? " is-loaded" : ""}`,
                    src: url,
                    alt: "",
                    loading: "lazy",
                    decoding: "async",
                    onLoad: ()=>markLoaded(url),
                    onError: ()=>markFailed(active.url)
                }, url, false, {
                    fileName: "[project]/src/components/artist-explorer.tsx",
                    lineNumber: 200,
                    columnNumber: 11
                }, this))
        }, void 0, false, {
            fileName: "[project]/src/components/artist-explorer.tsx",
            lineNumber: 194,
            columnNumber: 7
        }, this);
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
        className: `${className} artist-avatar`,
        style: style,
        role: "img",
        "aria-label": name,
        children: artistInitials(name)
    }, void 0, false, {
        fileName: "[project]/src/components/artist-explorer.tsx",
        lineNumber: 215,
        columnNumber: 5
    }, this);
}
_s(ArtistAvatar, "aa+A4/XL6LogpmMDViqiSE9VSnk=");
_c = ArtistAvatar;
function ArtistCardPhoto({ name, t, userPhotoUrl, artistImageUrl, coverUrls, onOpen }) {
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
        className: "artist-card-photo-open",
        type: "button",
        "aria-label": `${t("Open artist page")}: ${name}`,
        onClick: onOpen,
        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(ArtistAvatar, {
            name: name,
            className: "artist-card-photo",
            userPhotoUrl: userPhotoUrl,
            artistImageUrl: artistImageUrl,
            coverUrls: coverUrls
        }, void 0, false, {
            fileName: "[project]/src/components/artist-explorer.tsx",
            lineNumber: 243,
            columnNumber: 7
        }, this)
    }, void 0, false, {
        fileName: "[project]/src/components/artist-explorer.tsx",
        lineNumber: 237,
        columnNumber: 5
    }, this);
}
_c1 = ArtistCardPhoto;
function ArtistExplorer({ view, search, listMode, onPlay, renderTrack }) {
    _s1();
    const { language, t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"])();
    const tracks = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "ArtistExplorer.usePlayerStore[tracks]": (state)=>state.tracks
    }["ArtistExplorer.usePlayerStore[tracks]"]);
    const setView = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "ArtistExplorer.usePlayerStore[setView]": (state)=>state.setView
    }["ArtistExplorer.usePlayerStore[setView]"]);
    const [profileByArtist, setProfileByArtist] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])({});
    const [loadedProfiles, setLoadedProfiles] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])({});
    const [artistImageByKey, setArtistImageByKey] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])({});
    const [photoEditorOpen, setPhotoEditorOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [photoFile, setPhotoFile] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [photoPreview, setPhotoPreview] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [photoPending, setPhotoPending] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [photoError, setPhotoError] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [photoVersion, setPhotoVersion] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(0);
    const photoFileInputRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const photoPreviewUrlRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const artists = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "ArtistExplorer.useMemo[artists]": ()=>{
            const map = new Map();
            for (const track of tracks){
                for (const name of artistNames(track)){
                    const key = artistKey(name);
                    const existing = map.get(key);
                    if (existing) {
                        if (!existing.tracks.some({
                            "ArtistExplorer.useMemo[artists]": (item)=>item.id === track.id
                        }["ArtistExplorer.useMemo[artists]"])) existing.tracks.push(track);
                        if (track.album && !/^unknown album$/i.test(track.album)) existing.albums.add(track.album.toLocaleLowerCase());
                        if (track.duration > 0) existing.duration += track.duration;
                        continue;
                    }
                    map.set(key, {
                        name,
                        tracks: [
                            track
                        ],
                        albums: new Set(track.album && !/^unknown album$/i.test(track.album) ? [
                            track.album.toLocaleLowerCase()
                        ] : []),
                        duration: Math.max(0, track.duration)
                    });
                }
            }
            return [
                ...map.values()
            ].sort({
                "ArtistExplorer.useMemo[artists]": (left, right)=>left.name.localeCompare(right.name)
            }["ArtistExplorer.useMemo[artists]"]);
        }
    }["ArtistExplorer.useMemo[artists]"], [
        tracks
    ]);
    const decodedArtist = view.startsWith("artist:") ? decodeURIComponent(view.slice("artist:".length)) : null;
    const currentArtist = decodedArtist ? artists.find((artist)=>artistKey(artist.name) === artistKey(decodedArtist)) ?? null : null;
    const visibleArtists = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "ArtistExplorer.useMemo[visibleArtists]": ()=>artists.filter({
                "ArtistExplorer.useMemo[visibleArtists]": (artist)=>artist.name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())
            }["ArtistExplorer.useMemo[visibleArtists]"])
    }["ArtistExplorer.useMemo[visibleArtists]"], [
        artists,
        search
    ]);
    const artistTracks = currentArtist?.tracks.filter((track)=>`${track.title} ${track.artist} ${track.album}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())) ?? [];
    const shouldLoadArtistImages = view === "artists" || view.startsWith("artist:");
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "ArtistExplorer.useEffect": ()=>{
            if (!shouldLoadArtistImages) return;
            let cancelled = false;
            let retryTimer;
            let controller = null;
            const loadImages = {
                "ArtistExplorer.useEffect.loadImages": async ()=>{
                    controller = new AbortController();
                    const timeout = setTimeout({
                        "ArtistExplorer.useEffect.loadImages.timeout": ()=>controller?.abort()
                    }["ArtistExplorer.useEffect.loadImages.timeout"], 10_000);
                    try {
                        const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])("/api/artists/images", {
                            signal: controller.signal
                        });
                        if (!response.ok) throw new Error(`Artist image lookup failed (${response.status})`);
                        const payload = await response.json();
                        if (cancelled) return;
                        const nextImages = payload.artists ?? {};
                        setArtistImageByKey({
                            "ArtistExplorer.useEffect.loadImages": (current)=>({
                                    ...current,
                                    ...nextImages
                                })
                        }["ArtistExplorer.useEffect.loadImages"]);
                        if (Object.values(nextImages).some({
                            "ArtistExplorer.useEffect.loadImages": (item)=>item.pending
                        }["ArtistExplorer.useEffect.loadImages"])) {
                            retryTimer = setTimeout({
                                "ArtistExplorer.useEffect.loadImages": ()=>void loadImages()
                            }["ArtistExplorer.useEffect.loadImages"], 5_000);
                        }
                    } catch (error) {
                        if (cancelled) return;
                        console.warn("Artist images unavailable", error);
                        retryTimer = setTimeout({
                            "ArtistExplorer.useEffect.loadImages": ()=>void loadImages()
                        }["ArtistExplorer.useEffect.loadImages"], 15_000);
                    } finally{
                        clearTimeout(timeout);
                    }
                }
            }["ArtistExplorer.useEffect.loadImages"];
            void loadImages();
            return ({
                "ArtistExplorer.useEffect": ()=>{
                    cancelled = true;
                    controller?.abort();
                    if (retryTimer) clearTimeout(retryTimer);
                }
            })["ArtistExplorer.useEffect"];
        }
    }["ArtistExplorer.useEffect"], [
        shouldLoadArtistImages
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "ArtistExplorer.useEffect": ()=>{
            if (!currentArtist) return;
            const key = `${artistKey(currentArtist.name)}:${language}`;
            if (loadedProfiles[key]) return;
            let cancelled = false;
            let retryTimer;
            let activeController = null;
            const query = new URLSearchParams({
                name: currentArtist.name,
                language
            });
            const loadProfile = {
                "ArtistExplorer.useEffect.loadProfile": async (attempt)=>{
                    activeController = new AbortController();
                    const timeout = setTimeout({
                        "ArtistExplorer.useEffect.loadProfile.timeout": ()=>activeController?.abort()
                    }["ArtistExplorer.useEffect.loadProfile.timeout"], 8_000);
                    try {
                        const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])(`/api/artists/profile?${query}`, {
                            signal: activeController.signal
                        });
                        if (!response.ok) throw new Error(`Profile lookup failed (${response.status})`);
                        const { profile: nextProfile } = await response.json();
                        if (cancelled) return;
                        setProfileByArtist({
                            "ArtistExplorer.useEffect.loadProfile": (current)=>({
                                    ...current,
                                    [key]: nextProfile ?? null
                                })
                        }["ArtistExplorer.useEffect.loadProfile"]);
                        setLoadedProfiles({
                            "ArtistExplorer.useEffect.loadProfile": (current)=>({
                                    ...current,
                                    [key]: true
                                })
                        }["ArtistExplorer.useEffect.loadProfile"]);
                    } catch (error) {
                        if (cancelled) return;
                        console.warn("Artist profile unavailable", error);
                        if (attempt < 2) {
                            retryTimer = setTimeout({
                                "ArtistExplorer.useEffect.loadProfile": ()=>void loadProfile(attempt + 1)
                            }["ArtistExplorer.useEffect.loadProfile"], 1_000 * (attempt + 1));
                        } else {
                            setProfileByArtist({
                                "ArtistExplorer.useEffect.loadProfile": (current)=>({
                                        ...current,
                                        [key]: null
                                    })
                            }["ArtistExplorer.useEffect.loadProfile"]);
                        }
                    } finally{
                        clearTimeout(timeout);
                    }
                }
            }["ArtistExplorer.useEffect.loadProfile"];
            void loadProfile(0);
            return ({
                "ArtistExplorer.useEffect": ()=>{
                    cancelled = true;
                    activeController?.abort();
                    if (retryTimer) clearTimeout(retryTimer);
                }
            })["ArtistExplorer.useEffect"];
        }
    }["ArtistExplorer.useEffect"], [
        currentArtist,
        language,
        loadedProfiles
    ]);
    if (view === "artists") {
        if (tracks.length === 0) {
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "empty",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "empty-orb"
                    }, void 0, false, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 412,
                        columnNumber: 37
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                        children: t("Your library is empty")
                    }, void 0, false, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 412,
                        columnNumber: 66
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        children: t("Add songs to see their artists here.")
                    }, void 0, false, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 412,
                        columnNumber: 103
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/artist-explorer.tsx",
                lineNumber: 412,
                columnNumber: 14
            }, this);
        }
        if (!visibleArtists.length) {
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "empty",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "empty-orb"
                    }, void 0, false, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 415,
                        columnNumber: 37
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                        children: t("No matches")
                    }, void 0, false, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 415,
                        columnNumber: 66
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        children: t("Try a different search term.")
                    }, void 0, false, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 415,
                        columnNumber: 92
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/artist-explorer.tsx",
                lineNumber: 415,
                columnNumber: 14
            }, this);
        }
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: `artist-grid${listMode === "list" ? " list-mode" : ""}`,
            children: visibleArtists.map((artist)=>{
                const openArtist = ()=>setView(`artist:${encodeURIComponent(artist.name)}`);
                const imageInfo = artistImageByKey[artistImageKey(artist.name)];
                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("article", {
                    className: `artist-card${listMode === "list" ? " list-mode" : ""}`,
                    "data-artist-name": artist.name,
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(ArtistCardPhoto, {
                            name: artist.name,
                            t: t,
                            userPhotoUrl: imageInfo?.user_photo_url ? artistPhotoUrl(artist.name, photoVersion) : null,
                            artistImageUrl: smallArtistImageUrl(imageInfo?.image_url),
                            coverUrls: coverUrlsForArtist(artist),
                            onOpen: openArtist
                        }, void 0, false, {
                            fileName: "[project]/src/components/artist-explorer.tsx",
                            lineNumber: 429,
                            columnNumber: 15
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                            className: "artist-card-open",
                            type: "button",
                            onClick: openArtist,
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                    className: "artist-card-name",
                                    children: artist.name
                                }, void 0, false, {
                                    fileName: "[project]/src/components/artist-explorer.tsx",
                                    lineNumber: 446,
                                    columnNumber: 17
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                    className: "artist-card-count",
                                    children: [
                                        artist.tracks.length,
                                        " ",
                                        t(artist.tracks.length === 1 ? "song" : "songs")
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/artist-explorer.tsx",
                                    lineNumber: 447,
                                    columnNumber: 17
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/artist-explorer.tsx",
                            lineNumber: 441,
                            columnNumber: 15
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                            className: "artist-card-play",
                            type: "button",
                            onClick: (event)=>{
                                event.preventDefault();
                                event.stopPropagation();
                                const firstTrack = artist.tracks[0];
                                if (firstTrack) onPlay(artist.tracks, firstTrack.id);
                            },
                            children: [
                                "▶ ",
                                t("Play")
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/artist-explorer.tsx",
                            lineNumber: 451,
                            columnNumber: 15
                        }, this)
                    ]
                }, artist.name, true, {
                    fileName: "[project]/src/components/artist-explorer.tsx",
                    lineNumber: 424,
                    columnNumber: 13
                }, this);
            })
        }, void 0, false, {
            fileName: "[project]/src/components/artist-explorer.tsx",
            lineNumber: 418,
            columnNumber: 7
        }, this);
    }
    if (!currentArtist) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "empty",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "empty-orb"
                }, void 0, false, {
                    fileName: "[project]/src/components/artist-explorer.tsx",
                    lineNumber: 469,
                    columnNumber: 35
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                    children: t("Artist not found")
                }, void 0, false, {
                    fileName: "[project]/src/components/artist-explorer.tsx",
                    lineNumber: 469,
                    columnNumber: 64
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                    children: t("This artist no longer has songs in your library.")
                }, void 0, false, {
                    fileName: "[project]/src/components/artist-explorer.tsx",
                    lineNumber: 469,
                    columnNumber: 96
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                    className: "btn",
                    type: "button",
                    onClick: ()=>setView("artists"),
                    children: t("Back to artists")
                }, void 0, false, {
                    fileName: "[project]/src/components/artist-explorer.tsx",
                    lineNumber: 469,
                    columnNumber: 158
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/artist-explorer.tsx",
            lineNumber: 469,
            columnNumber: 12
        }, this);
    }
    const currentProfileKey = `${artistKey(currentArtist.name)}:${language}`;
    const artistName = currentArtist.name;
    const loading = !loadedProfiles[currentProfileKey];
    const activeProfile = loading ? null : profileByArtist[currentProfileKey];
    const imageInfo = artistImageByKey[artistImageKey(currentArtist.name)];
    const userPhotoUrl = imageInfo?.user_photo_url ? artistPhotoUrl(currentArtist.name, photoVersion) : null;
    const audioDbPhotoUrl = safeExternalUrl(imageInfo?.image_url);
    const artistCovers = coverUrlsForArtist(currentArtist);
    const facts = [
        [
            t("Genre"),
            activeProfile?.genre
        ],
        [
            t("Style"),
            activeProfile?.style
        ],
        [
            t("Mood"),
            activeProfile?.mood
        ],
        [
            t("Formed"),
            activeProfile?.formed_year
        ],
        [
            t("Label"),
            activeProfile?.label
        ]
    ].filter((entry)=>Boolean(entry[1]));
    const sourceUrl = safeExternalUrl(activeProfile?.source_url);
    const wikipediaSource = activeProfile?.source === "Wikipedia" || activeProfile?.source === "Wikipédia";
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
            const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])("/api/artists/photo", {
                method: "PUT",
                body: form
            }, {
                csrf: true,
                retryCsrfOnForbidden: true
            });
            if (!response.ok) {
                const payload = await response.json().catch(()=>null);
                throw new Error(payload?.detail ?? t("Could not update artist photo."));
            }
            closePhotoEditor();
            const photoUrl = artistPhotoUrl(artistName, photoVersion + 1);
            setPhotoVersion((version)=>version + 1);
            setArtistImageByKey((current)=>({
                    ...current,
                    [artistImageKey(artistName)]: {
                        ...current[artistImageKey(artistName)] ?? {
                            audiodb_id: null,
                            image_url: null,
                            banner_url: null,
                            status: "pending",
                            pending: true
                        },
                        user_photo_url: photoUrl
                    }
                }));
        } catch (error) {
            setPhotoError(error instanceof Error ? error.message : t("Could not update artist photo."));
        } finally{
            setPhotoPending(false);
        }
    }
    async function removeArtistPhoto() {
        setPhotoPending(true);
        setPhotoError("");
        try {
            const query = new URLSearchParams({
                name: artistName
            });
            const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])(`/api/artists/photo?${query}`, {
                method: "DELETE"
            }, {
                csrf: true,
                retryCsrfOnForbidden: true
            });
            if (!response.ok) {
                const payload = await response.json().catch(()=>null);
                throw new Error(payload?.detail ?? t("Could not remove artist photo."));
            }
            setPhotoVersion((version)=>version + 1);
            setArtistImageByKey((current)=>({
                    ...current,
                    [artistImageKey(artistName)]: {
                        ...current[artistImageKey(artistName)] ?? {
                            audiodb_id: null,
                            image_url: null,
                            banner_url: null,
                            status: "pending",
                            pending: true
                        },
                        user_photo_url: null
                    }
                }));
        } catch (error) {
            setPhotoError(error instanceof Error ? error.message : t("Could not remove artist photo."));
        } finally{
            setPhotoPending(false);
        }
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "artist-page",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("header", {
                className: "artist-hero",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("figure", {
                        className: "artist-photo-wrap",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(ArtistAvatar, {
                            name: currentArtist.name,
                            className: "artist-photo",
                            userPhotoUrl: photoPreview ?? userPhotoUrl,
                            artistImageUrl: audioDbPhotoUrl,
                            coverUrls: artistCovers
                        }, void 0, false, {
                            fileName: "[project]/src/components/artist-explorer.tsx",
                            lineNumber: 594,
                            columnNumber: 11
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 593,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "artist-hero-meta",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "artist-kicker",
                                children: t("Artist")
                            }, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 603,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h1", {
                                className: "artist-name",
                                children: currentArtist.name
                            }, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 604,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "artist-sub",
                                children: [
                                    currentArtist.tracks.length,
                                    " ",
                                    songLabel,
                                    " ",
                                    t("in your library"),
                                    " · ",
                                    currentArtist.albums.size,
                                    " ",
                                    albumLabel
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 605,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "btn btn-primary artist-hero-play",
                                type: "button",
                                onClick: (event)=>{
                                    event.preventDefault();
                                    event.stopPropagation();
                                    const firstTrack = currentArtist.tracks[0];
                                    if (firstTrack) onPlay(currentArtist.tracks, firstTrack.id);
                                },
                                children: [
                                    "▶ ",
                                    t("Play artist")
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 608,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "artist-photo-actions",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "btn",
                                        type: "button",
                                        onClick: ()=>{
                                            setPhotoError("");
                                            setPhotoEditorOpen(true);
                                        },
                                        children: t("Change image")
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/artist-explorer.tsx",
                                        lineNumber: 619,
                                        columnNumber: 13
                                    }, this),
                                    userPhotoUrl ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "btn btn-danger",
                                        type: "button",
                                        onClick: ()=>void removeArtistPhoto(),
                                        disabled: photoPending,
                                        children: t("Remove photo")
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/artist-explorer.tsx",
                                        lineNumber: 630,
                                        columnNumber: 15
                                    }, this) : null
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 618,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 602,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/artist-explorer.tsx",
                lineNumber: 592,
                columnNumber: 7
            }, this),
            photoError && !photoEditorOpen ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                className: "artist-photo-error",
                role: "alert",
                children: photoError
            }, void 0, false, {
                fileName: "[project]/src/components/artist-explorer.tsx",
                lineNumber: 643,
                columnNumber: 9
            }, this) : null,
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                className: "artist-library-info",
                "aria-label": t("Library information"),
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "artist-library-stat",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                children: t("Songs")
                            }, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 646,
                                columnNumber: 46
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("strong", {
                                children: currentArtist.tracks.length
                            }, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 646,
                                columnNumber: 71
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 646,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "artist-library-stat",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                children: t("Albums")
                            }, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 647,
                                columnNumber: 46
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("strong", {
                                children: currentArtist.albums.size
                            }, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 647,
                                columnNumber: 72
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 647,
                        columnNumber: 9
                    }, this),
                    currentArtist.duration ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "artist-library-stat",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                children: t("Play time")
                            }, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 648,
                                columnNumber: 72
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("strong", {
                                children: formatDuration(currentArtist.duration, t)
                            }, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 648,
                                columnNumber: 101
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 648,
                        columnNumber: 35
                    }, this) : null
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/artist-explorer.tsx",
                lineNumber: 645,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                className: "artist-info",
                "aria-busy": loading,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                        children: t("About")
                    }, void 0, false, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 651,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        className: "artist-bio",
                        children: loading ? t("Looking up artist details…") : String(activeProfile?.bio ?? t("No artist information is available yet."))
                    }, void 0, false, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 652,
                        columnNumber: 9
                    }, this),
                    sourceUrl && wikipediaSource ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        className: "artist-source",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("a", {
                                href: sourceUrl,
                                target: "_blank",
                                rel: "noopener noreferrer",
                                children: t("Source: Wikipedia")
                            }, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 655,
                                columnNumber: 13
                            }, this),
                            " · ",
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("a", {
                                href: "https://creativecommons.org/licenses/by-sa/4.0/",
                                target: "_blank",
                                rel: "noopener noreferrer",
                                children: "CC BY-SA 4.0"
                            }, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 659,
                                columnNumber: 13
                            }, this),
                            activeProfile?.source_modified === "true" ? ` · ${t("Shortened or adapted")}` : ""
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 654,
                        columnNumber: 11
                    }, this) : null,
                    facts.length ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "artist-tags",
                        children: facts.map(([label, value])=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                className: "artist-tag",
                                children: [
                                    label,
                                    ": ",
                                    String(value)
                                ]
                            }, label, true, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 671,
                                columnNumber: 85
                            }, this))
                    }, void 0, false, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 671,
                        columnNumber: 25
                    }, this) : null,
                    websiteUrl ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("a", {
                        className: "artist-website",
                        href: websiteUrl,
                        target: "_blank",
                        rel: "noopener noreferrer",
                        children: [
                            websiteLabel,
                            " ↗"
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 672,
                        columnNumber: 23
                    }, this) : null,
                    sourceUrl && !wikipediaSource ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                className: "artist-source",
                                children: [
                                    t("Source"),
                                    ": ",
                                    t(String(activeProfile?.source ?? t("Artist profile")))
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 673,
                                columnNumber: 44
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("a", {
                                className: "artist-website",
                                href: sourceUrl,
                                target: "_blank",
                                rel: "noopener noreferrer",
                                children: t("Source page ↗")
                            }, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 673,
                                columnNumber: 149
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 673,
                        columnNumber: 42
                    }, this) : null
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/artist-explorer.tsx",
                lineNumber: 650,
                columnNumber: 7
            }, this),
            artistTracks.length ? listMode === "grid" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "grid",
                children: artistTracks.map((track, index)=>renderTrack(track, index, artistTracks))
            }, void 0, false, {
                fileName: "[project]/src/components/artist-explorer.tsx",
                lineNumber: 677,
                columnNumber: 11
            }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "list",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "list-head",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {}, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 682,
                                columnNumber: 40
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                children: t("Title")
                            }, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 682,
                                columnNumber: 47
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                children: t("Album")
                            }, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 682,
                                columnNumber: 70
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                children: t("Time")
                            }, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 682,
                                columnNumber: 93
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {}, void 0, false, {
                                fileName: "[project]/src/components/artist-explorer.tsx",
                                lineNumber: 682,
                                columnNumber: 115
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 682,
                        columnNumber: 13
                    }, this),
                    artistTracks.map((track, index)=>renderTrack(track, index, artistTracks))
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/artist-explorer.tsx",
                lineNumber: 681,
                columnNumber: 11
            }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "empty",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                        children: t("No matches")
                    }, void 0, false, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 688,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        children: t("Try a different search term.")
                    }, void 0, false, {
                        fileName: "[project]/src/components/artist-explorer.tsx",
                        lineNumber: 689,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/artist-explorer.tsx",
                lineNumber: 687,
                columnNumber: 9
            }, this),
            photoEditorOpen ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "queue-picker-overlay open",
                role: "dialog",
                "aria-modal": "true",
                "aria-labelledby": "artistPhotoEditorTitle",
                onClick: (event)=>{
                    if (event.target === event.currentTarget && !photoPending) closePhotoEditor();
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                    className: "queue-picker-card track-editor-card artist-photo-editor",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "queue-picker-head",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                    id: "artistPhotoEditorTitle",
                                    children: [
                                        t("Photo for"),
                                        " ",
                                        currentArtist.name
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/artist-explorer.tsx",
                                    lineNumber: 704,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "icon-btn",
                                    type: "button",
                                    "aria-label": t("Close"),
                                    onClick: closePhotoEditor,
                                    disabled: photoPending,
                                    children: "×"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/artist-explorer.tsx",
                                    lineNumber: 705,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/artist-explorer.tsx",
                            lineNumber: 703,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(ArtistAvatar, {
                            name: currentArtist.name,
                            className: "artist-photo-preview",
                            userPhotoUrl: photoPreview ?? userPhotoUrl,
                            artistImageUrl: audioDbPhotoUrl,
                            coverUrls: artistCovers
                        }, void 0, false, {
                            fileName: "[project]/src/components/artist-explorer.tsx",
                            lineNumber: 713,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                            className: "track-editor-help",
                            children: t("JPEG, PNG, or WebP; up to 5 MB.")
                        }, void 0, false, {
                            fileName: "[project]/src/components/artist-explorer.tsx",
                            lineNumber: 720,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                            ref: photoFileInputRef,
                            className: "hidden-input",
                            type: "file",
                            accept: "image/jpeg,image/png,image/webp",
                            onChange: (event)=>{
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
                                if (![
                                    "image/jpeg",
                                    "image/png",
                                    "image/webp"
                                ].includes(selected.type)) {
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
                            }
                        }, void 0, false, {
                            fileName: "[project]/src/components/artist-explorer.tsx",
                            lineNumber: 721,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "track-editor-error",
                            role: "alert",
                            children: photoError
                        }, void 0, false, {
                            fileName: "[project]/src/components/artist-explorer.tsx",
                            lineNumber: 754,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "playlist-name-actions",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn",
                                    type: "button",
                                    onClick: ()=>photoFileInputRef.current?.click(),
                                    disabled: photoPending,
                                    children: t("Choose photo")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/artist-explorer.tsx",
                                    lineNumber: 756,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn btn-primary",
                                    type: "button",
                                    onClick: ()=>void saveArtistPhoto(),
                                    disabled: photoPending || !photoFile,
                                    children: photoPending ? t("Saving photo…") : t("Save photo")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/artist-explorer.tsx",
                                    lineNumber: 762,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/artist-explorer.tsx",
                            lineNumber: 755,
                            columnNumber: 13
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/artist-explorer.tsx",
                    lineNumber: 702,
                    columnNumber: 11
                }, this)
            }, void 0, false, {
                fileName: "[project]/src/components/artist-explorer.tsx",
                lineNumber: 693,
                columnNumber: 9
            }, this) : null
        ]
    }, void 0, true, {
        fileName: "[project]/src/components/artist-explorer.tsx",
        lineNumber: 591,
        columnNumber: 5
    }, this);
}
_s1(ArtistExplorer, "vHr1iukmGPaN6F7fkxCcicshY6A=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"]
    ];
});
_c2 = ArtistExplorer;
var _c, _c1, _c2;
__turbopack_context__.k.register(_c, "ArtistAvatar");
__turbopack_context__.k.register(_c1, "ArtistCardPhoto");
__turbopack_context__.k.register(_c2, "ArtistExplorer");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/src/components/auth/logout-button.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>LogoutButton
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/api/client.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/i18n.tsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
"use client";
;
;
;
function LogoutButton({ className = "auth-submit", children, ariaLabel }) {
    _s();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"])();
    const [error, setError] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [pending, setPending] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    async function logout() {
        setPending(true);
        setError(null);
        try {
            const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])("/logout", {
                method: "POST",
                redirect: "follow"
            }, {
                csrf: true
            });
            await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(response);
            window.location.assign("/login");
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : t("Could not log out."));
            setPending(false);
        }
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
        children: [
            error && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "auth-error",
                role: "alert",
                children: error
            }, void 0, false, {
                fileName: "[project]/src/components/auth/logout-button.tsx",
                lineNumber: 41,
                columnNumber: 17
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                className: className,
                type: "button",
                "aria-label": ariaLabel ? t(ariaLabel) : undefined,
                onClick: logout,
                disabled: pending,
                children: pending ? t("Logging out…") : children ?? t("Log out")
            }, void 0, false, {
                fileName: "[project]/src/components/auth/logout-button.tsx",
                lineNumber: 42,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/src/components/auth/logout-button.tsx",
        lineNumber: 40,
        columnNumber: 5
    }, this);
}
_s(LogoutButton, "i14I+PPVOsucIULXJvR0rOxkknw=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"]
    ];
});
_c = LogoutButton;
var _c;
__turbopack_context__.k.register(_c, "LogoutButton");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/src/components/library-app.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>LibraryApp
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react-dom/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/api/client.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$auth$2f$logout$2d$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/components/auth/logout-button.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$account$2d$settings$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/components/account-settings.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$artist$2d$explorer$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/components/artist-explorer.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$lyrics$2d$overlay$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/components/lyrics-overlay.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$visualizer$2d$overlay$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/components/visualizer-overlay.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/i18n.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/store/player-store.ts [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature(), _s1 = __turbopack_context__.k.signature(), _s2 = __turbopack_context__.k.signature(), _s3 = __turbopack_context__.k.signature(), _s4 = __turbopack_context__.k.signature();
"use client";
;
;
;
;
;
;
;
;
;
;
const OFFLINE_DATABASE = "auralis-db";
const OFFLINE_DATABASE_VERSION = 2;
const OFFLINE_STORE = "offlineTracks";
const AURA_PALETTE = [
    [
        "#8b7fff",
        "#54e8d4"
    ],
    [
        "#ff8fb1",
        "#8b7fff"
    ],
    [
        "#54e8d4",
        "#3aa0ff"
    ],
    [
        "#ffb86b",
        "#ff6b9d"
    ],
    [
        "#6bd6ff",
        "#8b7fff"
    ],
    [
        "#c084fc",
        "#54e8d4"
    ]
];
function hashCoverSeed(seed) {
    let hash = 0;
    for(let index = 0; index < seed.length; index += 1){
        hash = Math.imul(31, hash) + seed.charCodeAt(index) | 0;
    }
    return Math.abs(hash);
}
function logAudioFailure(context, audio, error) {
    const errorName = error instanceof Error ? error.name : error && typeof error === "object" && "name" in error && typeof error.name === "string" ? error.name : "UnknownError";
    const errorMessage = error instanceof Error ? error.message : error && typeof error === "object" && "message" in error && typeof error.message === "string" ? error.message : String(error);
    console.warn(`[audio] ${context}`, {
        name: errorName,
        message: errorMessage,
        code: audio.error?.code ?? null,
        networkState: audio.networkState,
        readyState: audio.readyState
    });
}
function generateAura(seed) {
    const hash = hashCoverSeed(seed);
    const [first, second] = AURA_PALETTE[hash % AURA_PALETTE.length];
    const angle = hash % 360 * (Math.PI / 180);
    const x = Math.round(50 + Math.cos(angle) * 15);
    const y = Math.round(50 + Math.sin(angle) * 15);
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300"><defs><radialGradient id="a" cx="${x}%" cy="${y}%" r="75%"><stop stop-color="${first}"/><stop offset=".5" stop-color="${second}" stop-opacity=".34"/><stop offset="1" stop-color="#0c0e14" stop-opacity="0"/></radialGradient><radialGradient id="b" cx="${100 - x}%" cy="${100 - y}%" r="60%"><stop stop-color="${second}"/><stop offset="1" stop-color="#0c0e14" stop-opacity="0"/></radialGradient></defs><rect width="300" height="300" fill="#12151e"/><rect width="300" height="300" fill="url(#a)" opacity=".9"/><rect width="300" height="300" fill="url(#b)" opacity=".55"/></svg>`;
    return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}
function GeneratedAura({ seed, className = "" }) {
    _s();
    const hash = hashCoverSeed(seed);
    const id = `aura-${(0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useId"])().replace(/:/g, "")}`;
    const [first, second] = AURA_PALETTE[hash % AURA_PALETTE.length];
    const angle = hash % 360 * (Math.PI / 180);
    const x = Math.round(50 + Math.cos(angle) * 15);
    const y = Math.round(50 + Math.sin(angle) * 15);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
        className: `generated-aura ${className}`,
        viewBox: "0 0 300 300",
        "aria-hidden": "true",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("defs", {
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("radialGradient", {
                        id: `${id}-a`,
                        cx: `${x}%`,
                        cy: `${y}%`,
                        r: "75%",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("stop", {
                                stopColor: first
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 133,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("stop", {
                                offset: ".5",
                                stopColor: second,
                                stopOpacity: ".34"
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 134,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("stop", {
                                offset: "1",
                                stopColor: "#0c0e14",
                                stopOpacity: "0"
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 135,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 132,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("radialGradient", {
                        id: `${id}-b`,
                        cx: `${100 - x}%`,
                        cy: `${100 - y}%`,
                        r: "60%",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("stop", {
                                stopColor: second
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 138,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("stop", {
                                offset: "1",
                                stopColor: "#0c0e14",
                                stopOpacity: "0"
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 139,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 137,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 131,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("rect", {
                width: "300",
                height: "300",
                fill: "#12151e"
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 142,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("rect", {
                className: "generated-aura-first",
                width: "300",
                height: "300",
                fill: `url(#${id}-a)`,
                opacity: ".9"
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 143,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("rect", {
                className: "generated-aura-second",
                width: "300",
                height: "300",
                fill: `url(#${id}-b)`,
                opacity: ".55"
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 144,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/src/components/library-app.tsx",
        lineNumber: 130,
        columnNumber: 5
    }, this);
}
_s(GeneratedAura, "xfMyHNFebGjSN1/YPqrD8z5EdLc=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useId"]
    ];
});
_c = GeneratedAura;
const FALLBACK_ART = generateAura("Unknown song");
function coverUrlForTrack(track) {
    const source = track.cover_source ?? "unknown";
    const hasGeneratedCover = [
        "generated",
        "placeholder",
        "unknown"
    ].includes(source);
    if (!track.has_cover && hasGeneratedCover) {
        return generateAura(`${track.artist}|${track.album}|${track.title}`);
    }
    return track.cover_url || generateAura(`${track.artist}|${track.album}|${track.title}`);
}
function normalizeMeta(value) {
    return {
        favorites: [
            ...new Set(value.favorites.filter((id)=>typeof id === "string"))
        ].sort(),
        playlists: value.playlists.map((playlist)=>({
                id: playlist.id,
                name: playlist.name,
                trackIds: [
                    ...new Set(playlist.trackIds)
                ]
            }))
    };
}
function activePreviewLine(lines, timeMs) {
    let low = 0;
    let high = lines.length - 1;
    let active = -1;
    while(low <= high){
        const middle = low + high >> 1;
        if (lines[middle].time <= timeMs) {
            active = middle;
            low = middle + 1;
        } else {
            high = middle - 1;
        }
    }
    return active;
}
const LoadedTrackImage = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["memo"])(_s1(function LoadedTrackImage({ src, fallbackSrc = FALLBACK_ART, className = "" }) {
    _s1();
    const [loaded, setLoaded] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
        className: `${className} media-image${loaded ? " media-image-ready" : ""}`,
        src: src,
        alt: "",
        loading: "lazy",
        decoding: "async",
        onLoad: ()=>setLoaded(true),
        onError: (event)=>{
            if (event.currentTarget.src !== new URL(fallbackSrc, window.location.href).href) {
                event.currentTarget.src = fallbackSrc;
            } else {
                setLoaded(true);
            }
        }
    }, void 0, false, {
        fileName: "[project]/src/components/library-app.tsx",
        lineNumber: 200,
        columnNumber: 5
    }, this);
}, "5HkI/FtSFoHY/ZszUPbNWJy51d0="));
_c1 = LoadedTrackImage;
const TrackImage = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["memo"])(function TrackImage({ track, className = "" }) {
    if (!track.hasCover && [
        "generated",
        "placeholder",
        "unknown"
    ].includes(track.coverSource ?? "unknown")) {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(GeneratedAura, {
            seed: `${track.artist}|${track.album}|${track.title}`,
            className: className
        }, void 0, false, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 230,
            columnNumber: 7
        }, this);
    }
    const fallback = generateAura(`${track.artist}|${track.album}|${track.title}`);
    const src = track.coverUrl || fallback;
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(LoadedTrackImage, {
        src: src,
        fallbackSrc: fallback,
        className: className
    }, `${track.id}:${src}`, false, {
        fileName: "[project]/src/components/library-app.tsx",
        lineNumber: 238,
        columnNumber: 10
    }, this);
});
_c2 = TrackImage;
function PlaybackSeek({ audioElement, duration, onSeek, onResume, className = "", variant }) {
    _s2();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"])();
    const [currentTime, setCurrentTime] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(0);
    const [scrubbingTime, setScrubbingTime] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const dragRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "PlaybackSeek.useEffect": ()=>{
            if (!audioElement) return;
            const update = {
                "PlaybackSeek.useEffect.update": ()=>setCurrentTime(audioElement.currentTime || 0)
            }["PlaybackSeek.useEffect.update"];
            audioElement.addEventListener("timeupdate", update);
            audioElement.addEventListener("loadedmetadata", update);
            audioElement.addEventListener("durationchange", update);
            audioElement.addEventListener("seeked", update);
            update();
            return ({
                "PlaybackSeek.useEffect": ()=>{
                    audioElement.removeEventListener("timeupdate", update);
                    audioElement.removeEventListener("loadedmetadata", update);
                    audioElement.removeEventListener("durationchange", update);
                    audioElement.removeEventListener("seeked", update);
                }
            })["PlaybackSeek.useEffect"];
        }
    }["PlaybackSeek.useEffect"], [
        audioElement
    ]);
    const displayedTime = scrubbingTime ?? currentTime;
    const progress = duration ? Math.min(100, displayedTime / duration * 100) : 0;
    function timeAtPosition(clientX, element) {
        const bounds = element.getBoundingClientRect();
        const ratio = bounds.width ? Math.max(0, Math.min(1, (clientX - bounds.left) / bounds.width)) : 0;
        return ratio * duration;
    }
    function beginSeek(event) {
        if (!audioElement || !duration || !event.isPrimary || event.button !== 0) return;
        event.preventDefault();
        dragRef.current = {
            pointerId: event.pointerId,
            wasPlaying: !audioElement.paused
        };
        event.currentTarget.setPointerCapture(event.pointerId);
        setScrubbingTime(timeAtPosition(event.clientX, event.currentTarget));
        if (!audioElement.paused) audioElement.pause();
    }
    function continueSeek(event) {
        if (dragRef.current?.pointerId !== event.pointerId) return;
        setScrubbingTime(timeAtPosition(event.clientX, event.currentTarget));
    }
    function finishSeek(event) {
        const drag = dragRef.current;
        if (!audioElement || !drag || drag.pointerId !== event.pointerId) return;
        onSeek(timeAtPosition(event.clientX, event.currentTarget));
        dragRef.current = null;
        setScrubbingTime(null);
        if (drag.wasPlaying) onResume();
    }
    const seekBar = /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: `seek${variant === "mobile" ? " mobile-seek" : ""}`,
        role: "slider",
        tabIndex: duration ? 0 : -1,
        "aria-label": t("Track progress"),
        "aria-valuemin": 0,
        "aria-valuemax": duration,
        "aria-valuenow": displayedTime,
        "aria-valuetext": `${formatTime(displayedTime)} of ${formatTime(duration)}`,
        onPointerDown: beginSeek,
        onPointerMove: continueSeek,
        onPointerUp: finishSeek,
        onPointerCancel: finishSeek,
        onKeyDown: (event)=>{
            if (!audioElement || !duration) return;
            const offsets = {
                ArrowRight: 5,
                ArrowLeft: -5,
                Home: -duration,
                End: duration
            };
            const offset = offsets[event.key];
            if (offset === undefined) return;
            event.preventDefault();
            seekAudio(audioElement, offset);
        },
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "seek-track",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "seek-fill",
                    style: {
                        width: `${progress}%`
                    }
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 335,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 334,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "seek-thumb",
                style: {
                    left: `${progress}%`
                }
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 337,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/src/components/library-app.tsx",
        lineNumber: 307,
        columnNumber: 5
    }, this);
    if (variant === "mobile") {
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "mobile-seek-row",
            children: [
                seekBar,
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "mobile-times",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                            children: formatTime(displayedTime)
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 346,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                            children: formatTime(duration)
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 347,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 345,
                    columnNumber: 9
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 343,
            columnNumber: 7
        }, this);
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: `seek-row${className ? ` ${className}` : ""}`,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                className: "time",
                children: formatTime(displayedTime)
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 354,
                columnNumber: 7
            }, this),
            seekBar,
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                className: "time right",
                children: formatTime(duration)
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 356,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/src/components/library-app.tsx",
        lineNumber: 353,
        columnNumber: 5
    }, this);
}
_s2(PlaybackSeek, "ADc7dV12PEvfbveXHQR/7zooXqM=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"]
    ];
});
_c3 = PlaybackSeek;
function parseLegacyMeta(value) {
    let parsed = value;
    if (typeof parsed === "string") {
        try {
            parsed = JSON.parse(parsed);
        } catch  {
            return null;
        }
    }
    if (typeof parsed !== "object" || parsed === null) return null;
    const record = parsed;
    const favorites = Array.isArray(record.favorites) ? record.favorites.filter((id)=>typeof id === "string") : [];
    const playlists = Array.isArray(record.playlists) ? record.playlists.flatMap((value)=>{
        if (typeof value !== "object" || value === null) return [];
        const playlist = value;
        if (typeof playlist.id !== "string" || typeof playlist.name !== "string") return [];
        const rawTrackIds = Array.isArray(playlist.trackIds) ? playlist.trackIds : Array.isArray(playlist.fingerprints) ? playlist.fingerprints : [];
        return [
            {
                id: playlist.id,
                name: playlist.name,
                trackIds: [
                    ...new Set(rawTrackIds.filter((id)=>typeof id === "string"))
                ]
            }
        ];
    }) : [];
    return {
        favorites: [
            ...new Set(favorites)
        ].sort(),
        playlists
    };
}
async function readLegacyMeta() {
    if (typeof indexedDB === "undefined") return null;
    return new Promise((resolve)=>{
        let settled = false;
        let database = null;
        const finish = (result)=>{
            if (settled) return;
            settled = true;
            database?.close();
            resolve(result);
        };
        const request = indexedDB.open("auralis-db", 2);
        request.onupgradeneeded = ()=>{
            const db = request.result;
            if (!db.objectStoreNames.contains("kv")) db.createObjectStore("kv");
            if (!db.objectStoreNames.contains("handles")) db.createObjectStore("handles");
            if (!db.objectStoreNames.contains("offlineTracks")) {
                db.createObjectStore("offlineTracks", {
                    keyPath: "id"
                });
            }
        };
        request.onerror = ()=>finish(null);
        request.onblocked = ()=>finish(null);
        request.onsuccess = ()=>{
            database = request.result;
            if (!database.objectStoreNames.contains("kv")) {
                finish(null);
                return;
            }
            const transaction = database.transaction("kv", "readonly");
            const valueRequest = transaction.objectStore("kv").get("auralis:library");
            valueRequest.onsuccess = ()=>finish(parseLegacyMeta(valueRequest.result));
            valueRequest.onerror = ()=>finish(null);
            transaction.onerror = ()=>finish(null);
        };
    });
}
function openOfflineDatabase() {
    if (typeof indexedDB === "undefined") {
        return Promise.reject(new Error("Offline storage is not available in this browser."));
    }
    return new Promise((resolve, reject)=>{
        const request = indexedDB.open(OFFLINE_DATABASE, OFFLINE_DATABASE_VERSION);
        request.onupgradeneeded = ()=>{
            const database = request.result;
            if (!database.objectStoreNames.contains("kv")) database.createObjectStore("kv");
            if (!database.objectStoreNames.contains("handles")) database.createObjectStore("handles");
            if (!database.objectStoreNames.contains(OFFLINE_STORE)) {
                database.createObjectStore(OFFLINE_STORE, {
                    keyPath: "id"
                });
            }
        };
        request.onsuccess = ()=>resolve(request.result);
        request.onerror = ()=>reject(request.error ?? new Error("Could not open offline storage."));
        request.onblocked = ()=>reject(new Error("Offline storage is busy in another browser tab."));
    });
}
async function readOfflineTracks(accountId) {
    const database = await openOfflineDatabase();
    return new Promise((resolve, reject)=>{
        const transaction = database.transaction(OFFLINE_STORE, "readonly");
        const request = transaction.objectStore(OFFLINE_STORE).getAll();
        request.onsuccess = ()=>{
            resolve(request.result.filter((record)=>record.accountId === accountId && typeof record.trackId === "string" && record.audio instanceof Blob));
        };
        request.onerror = ()=>reject(request.error ?? new Error("Could not read offline tracks."));
        transaction.oncomplete = ()=>database.close();
        transaction.onabort = ()=>{
            database.close();
            reject(transaction.error ?? new Error("Could not read offline tracks."));
        };
    });
}
async function writeOfflineTrack(record) {
    const database = await openOfflineDatabase();
    return new Promise((resolve, reject)=>{
        const transaction = database.transaction(OFFLINE_STORE, "readwrite");
        transaction.objectStore(OFFLINE_STORE).put(record);
        transaction.oncomplete = ()=>{
            database.close();
            resolve();
        };
        transaction.onerror = ()=>reject(transaction.error ?? new Error("Could not save the offline track."));
        transaction.onabort = ()=>{
            database.close();
            reject(transaction.error ?? new Error("Could not save the offline track."));
        };
    });
}
async function deleteOfflineTrack(accountId, trackId) {
    const database = await openOfflineDatabase();
    return new Promise((resolve, reject)=>{
        const transaction = database.transaction(OFFLINE_STORE, "readwrite");
        transaction.objectStore(OFFLINE_STORE).delete(`${accountId}:${trackId}`);
        transaction.oncomplete = ()=>{
            database.close();
            resolve();
        };
        transaction.onerror = ()=>reject(transaction.error ?? new Error("Could not remove the offline track."));
        transaction.onabort = ()=>{
            database.close();
            reject(transaction.error ?? new Error("Could not remove the offline track."));
        };
    });
}
function sameMeta(left, right) {
    return JSON.stringify(left) === JSON.stringify(right);
}
function mergeUnsavedMeta(remote, baseline, local) {
    const mergedFavorites = new Set(remote.favorites);
    const baselineFavorites = new Set(baseline.favorites);
    const localFavorites = new Set(local.favorites);
    for (const id of new Set([
        ...baselineFavorites,
        ...localFavorites
    ])){
        if (baselineFavorites.has(id) === localFavorites.has(id)) continue;
        if (localFavorites.has(id)) mergedFavorites.add(id);
        else mergedFavorites.delete(id);
    }
    const baselinePlaylists = new Map(baseline.playlists.map((item)=>[
            item.id,
            item
        ]));
    const localPlaylists = new Map(local.playlists.map((item)=>[
            item.id,
            item
        ]));
    const mergedPlaylists = new Map(remote.playlists.map((item)=>[
            item.id,
            item
        ]));
    for (const id of new Set([
        ...baselinePlaylists.keys(),
        ...localPlaylists.keys()
    ])){
        if (JSON.stringify(baselinePlaylists.get(id)) === JSON.stringify(localPlaylists.get(id))) {
            continue;
        }
        const localPlaylist = localPlaylists.get(id);
        if (localPlaylist) mergedPlaylists.set(id, localPlaylist);
        else mergedPlaylists.delete(id);
    }
    return {
        favorites: [
            ...mergedFavorites
        ].sort(),
        playlists: [
            ...mergedPlaylists.values()
        ]
    };
}
function formatTime(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) seconds = 0;
    return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}
function seekAudio(audio, offset) {
    if (!audio) return;
    const duration = Number.isFinite(audio.duration) ? audio.duration : Infinity;
    audio.currentTime = Math.max(0, Math.min(duration, audio.currentTime + offset));
}
function viewName(view, playlists) {
    if (view === "library") return "Library";
    if (view === "offline") return "Offline";
    if (view === "favorites") return "Favorites";
    if (view === "playlists") return "Playlists";
    if (view === "artists") return "Artists";
    if (view === "account") return "Account";
    if (view.startsWith("artist:")) return decodeURIComponent(view.slice("artist:".length));
    return playlists.find((playlist)=>`playlist:${playlist.id}` === view)?.name ?? "Playlist";
}
function getMetaFromStore() {
    const state = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState();
    return {
        favorites: state.tracks.filter((track)=>track.favorite).map((track)=>track.id).sort(),
        playlists: state.playlists.map((playlist)=>({
                ...playlist,
                trackIds: [
                    ...playlist.trackIds
                ]
            }))
    };
}
function Icon({ name }) {
    const paths = {
        library: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("rect", {
                    x: "3.5",
                    y: "3.5",
                    width: "7",
                    height: "7",
                    rx: "2"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 590,
                    columnNumber: 16
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("rect", {
                    x: "13.5",
                    y: "3.5",
                    width: "7",
                    height: "7",
                    rx: "2"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 590,
                    columnNumber: 67
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("rect", {
                    x: "3.5",
                    y: "13.5",
                    width: "7",
                    height: "7",
                    rx: "2"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 590,
                    columnNumber: 119
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("rect", {
                    x: "13.5",
                    y: "13.5",
                    width: "7",
                    height: "7",
                    rx: "2"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 590,
                    columnNumber: 171
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 590,
            columnNumber: 14
        }, this),
        playlists: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M4 7h12M4 12h12M4 17h8"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 591,
                    columnNumber: 18
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M18 8v8.2"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 591,
                    columnNumber: 52
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "18",
                    cy: "17.5",
                    r: "1.8"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 591,
                    columnNumber: 73
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 591,
            columnNumber: 16
        }, this),
        heart: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
            d: "M12 20s-7-4.35-9.4-8.9C.8 7.5 3.1 4.2 6.6 4.2c1.9 0 3.3 1.05 4.4 2.55 1.1-1.5 2.5-2.55 4.4-2.55 3.5 0 5.8 3.3 4 6.9C17 15.65 12 20 12 20Z"
        }, void 0, false, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 592,
            columnNumber: 12
        }, this),
        logout: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 593,
                    columnNumber: 15
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "m16 17 5-5-5-5M21 12H9"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 593,
                    columnNumber: 66
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 593,
            columnNumber: 13
        }, this),
        search: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "11",
                    cy: "11",
                    r: "6.5"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 594,
                    columnNumber: 15
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "m20 20-3.8-3.8"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 594,
                    columnNumber: 48
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 594,
            columnNumber: 13
        }, this),
        play: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
            d: "M8 5v14l11-7z",
            fill: "currentColor",
            stroke: "none"
        }, void 0, false, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 595,
            columnNumber: 11
        }, this),
        pause: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                d: "M8 6h3v12H8zM15 6h3v12h-3z",
                fill: "currentColor",
                stroke: "none"
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 596,
                columnNumber: 14
            }, this)
        }, void 0, false, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 596,
            columnNumber: 12
        }, this),
        prev: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
            d: "M6.5 6.5h2.2v11H6.5zM19.5 6.8 9.8 12l9.7 5.2z",
            fill: "currentColor",
            stroke: "none"
        }, void 0, false, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 597,
            columnNumber: 11
        }, this),
        next: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
            d: "M15.3 6.5h2.2v11h-2.2zM4.5 6.8 14.2 12l-9.7 5.2z",
            fill: "currentColor",
            stroke: "none"
        }, void 0, false, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 598,
            columnNumber: 11
        }, this),
        shuffle: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                d: "M3 6.5h3.2l7.2 11H21M17.5 4.5 21 6.5l-3.5 2M3 17.5h3.2l3.2-4.9M17.5 19.5 21 17.5l-3.5-2"
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 599,
                columnNumber: 16
            }, this)
        }, void 0, false, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 599,
            columnNumber: 14
        }, this),
        repeat: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                d: "m17 3.5 3.5 3.5-3.5 3.5M4 11.5V9.2a3.7 3.7 0 0 1 3.7-3.7h12.8M7 20.5 3.5 17 7 13.5M20 12.5v2.3a3.7 3.7 0 0 1-3.7 3.7H3.5"
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 600,
                columnNumber: 15
            }, this)
        }, void 0, false, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 600,
            columnNumber: 13
        }, this),
        queue: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                d: "M4.5 7h15M4.5 12h9.5M4.5 17h9.5"
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 601,
                columnNumber: 14
            }, this)
        }, void 0, false, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 601,
            columnNumber: 12
        }, this),
        plus: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                d: "M12 5v14M5 12h14"
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 602,
                columnNumber: 13
            }, this)
        }, void 0, false, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 602,
            columnNumber: 11
        }, this),
        close: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                d: "m7 7 10 10M17 7 7 17"
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 603,
                columnNumber: 14
            }, this)
        }, void 0, false, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 603,
            columnNumber: 12
        }, this),
        list: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                d: "M4.5 7h15M4.5 12h15M4.5 17h15"
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 604,
                columnNumber: 13
            }, this)
        }, void 0, false, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 604,
            columnNumber: 11
        }, this),
        grid: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("rect", {
                    x: "3.5",
                    y: "3.5",
                    width: "7",
                    height: "7",
                    rx: "1.8"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 605,
                    columnNumber: 13
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("rect", {
                    x: "13.5",
                    y: "3.5",
                    width: "7",
                    height: "7",
                    rx: "1.8"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 605,
                    columnNumber: 66
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("rect", {
                    x: "3.5",
                    y: "13.5",
                    width: "7",
                    height: "7",
                    rx: "1.8"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 605,
                    columnNumber: 120
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("rect", {
                    x: "13.5",
                    y: "13.5",
                    width: "7",
                    height: "7",
                    rx: "1.8"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 605,
                    columnNumber: 174
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 605,
            columnNumber: 11
        }, this),
        more: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "5",
                    cy: "12",
                    r: "1.4",
                    fill: "currentColor"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 606,
                    columnNumber: 13
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "12",
                    cy: "12",
                    r: "1.4",
                    fill: "currentColor"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 606,
                    columnNumber: 65
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "19",
                    cy: "12",
                    r: "1.4",
                    fill: "currentColor"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 606,
                    columnNumber: 118
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 606,
            columnNumber: 11
        }, this),
        artist: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "12",
                    cy: "8",
                    r: "3.2"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 607,
                    columnNumber: 15
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M5.5 19.2c0-3.2 2.9-5.5 6.5-5.5s6.5 2.3 6.5 5.5"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 607,
                    columnNumber: 47
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "18.2",
                    cy: "9.2",
                    r: "2.1"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 607,
                    columnNumber: 106
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M19.5 19.2c0-2.1-1.3-3.8-3.2-4.6"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 607,
                    columnNumber: 142
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 607,
            columnNumber: 13
        }, this),
        offline: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M12 4v11"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 608,
                    columnNumber: 16
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "m8 11 4 4 4-4M5 20h14"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 608,
                    columnNumber: 36
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 608,
            columnNumber: 14
        }, this),
        account: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "12",
                    cy: "8",
                    r: "3.4"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 609,
                    columnNumber: 16
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M5 20c0-3.6 3.1-6.2 7-6.2s7 2.6 7 6.2"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 609,
                    columnNumber: 48
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 609,
            columnNumber: 14
        }, this),
        help: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "12",
                    cy: "12",
                    r: "8.25"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 610,
                    columnNumber: 13
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M9.6 9.4a2.4 2.4 0 1 1 3.1 2.25c-.85.35-1.2.8-1.2 1.7"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 610,
                    columnNumber: 47
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "12",
                    cy: "16.6",
                    r: ".7",
                    fill: "currentColor",
                    stroke: "none"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 610,
                    columnNumber: 112
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 610,
            columnNumber: 11
        }, this),
        import: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M12 4v11"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 611,
                    columnNumber: 15
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "m8.5 11.5 3.5 3.5 3.5-3.5M5 18.5h14"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 611,
                    columnNumber: 35
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 611,
            columnNumber: 13
        }, this),
        volume: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M4 10v4h3l4 3V7l-4 3H4Z"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 612,
                    columnNumber: 15
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M15 9a5 5 0 0 1 0 6M17.5 6.5a8.5 8.5 0 0 1 0 11"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 612,
                    columnNumber: 50
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 612,
            columnNumber: 13
        }, this),
        "volume-muted": /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M4 10v4h3l4 3V7l-4 3H4Z"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 613,
                    columnNumber: 23
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "m16 9 5 6m0-6-5 6"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 613,
                    columnNumber: 58
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 613,
            columnNumber: 21
        }, this),
        lyrics: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M6 3.75h8l4 4V20.25H6z"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 614,
                    columnNumber: 15
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M14 3.75v4h4M9 12h6M9 15.5h6"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 614,
                    columnNumber: 49
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 614,
            columnNumber: 13
        }, this),
        visualizer: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M5 14v5M5 5v5M12 10v9M12 5v2M19 15v4M19 5v7"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 615,
                    columnNumber: 19
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M3 10h4M10 7h4M17 12h4"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 615,
                    columnNumber: 74
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 615,
            columnNumber: 17
        }, this),
        info: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "12",
                    cy: "12",
                    r: "9"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 616,
                    columnNumber: 13
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M12 11v5"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 616,
                    columnNumber: 44
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                    d: "M12 8h.01"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 616,
                    columnNumber: 64
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 616,
            columnNumber: 11
        }, this),
        drag: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "9",
                    cy: "5",
                    r: "1",
                    fill: "currentColor",
                    stroke: "none"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 617,
                    columnNumber: 13
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "15",
                    cy: "5",
                    r: "1",
                    fill: "currentColor",
                    stroke: "none"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 617,
                    columnNumber: 76
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "9",
                    cy: "12",
                    r: "1",
                    fill: "currentColor",
                    stroke: "none"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 617,
                    columnNumber: 140
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "15",
                    cy: "12",
                    r: "1",
                    fill: "currentColor",
                    stroke: "none"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 617,
                    columnNumber: 204
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "9",
                    cy: "19",
                    r: "1",
                    fill: "currentColor",
                    stroke: "none"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 617,
                    columnNumber: 269
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("circle", {
                    cx: "15",
                    cy: "19",
                    r: "1",
                    fill: "currentColor",
                    stroke: "none"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 617,
                    columnNumber: 333
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 617,
            columnNumber: 11
        }, this)
    };
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        strokeWidth: "1.8",
        strokeLinecap: "round",
        strokeLinejoin: "round",
        "aria-hidden": "true",
        children: paths[name]
    }, void 0, false, {
        fileName: "[project]/src/components/library-app.tsx",
        lineNumber: 621,
        columnNumber: 5
    }, this);
}
_c4 = Icon;
function TrackMenuPortal({ track, position, view, playlists, offlinePendingId, expandedPlayerOpen, onPlayNext, onAddToQueue, onAddToPlaylist, onToggleOffline, onToggleFavorite, onViewArtist, onShare, onRemoveFromPlaylist, onAddOrChangeCover, onRetryCover, onCoverInfo, onEditDetails, onRemove }) {
    _s3();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"])();
    const playlistId = view.startsWith("playlist:") ? view.slice("playlist:".length) : null;
    const playlist = playlists.find((item)=>item.id === playlistId);
    const inPlaylist = playlist?.trackIds.includes(track.id) ?? false;
    const hasPlaceholderCover = [
        "placeholder",
        "unknown",
        "generated"
    ].includes(track.coverSource ?? "unknown");
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createPortal"])(/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "menu track-context-menu",
        role: "menu",
        "aria-label": `${t("Options for")} ${track.title}`,
        style: {
            top: position.top,
            left: position.left
        },
        onClick: (event)=>event.stopPropagation(),
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                className: "menu-item",
                role: "menuitem",
                type: "button",
                onClick: onPlayNext,
                children: t("Play next")
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 692,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                className: "menu-item",
                role: "menuitem",
                type: "button",
                onClick: onAddToQueue,
                children: t("Add to queue")
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 693,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                className: "menu-item",
                role: "menuitem",
                type: "button",
                onClick: onAddToPlaylist,
                children: t("Add to playlist")
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 694,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                className: "menu-item",
                role: "menuitem",
                type: "button",
                disabled: offlinePendingId !== null,
                onClick: onToggleOffline,
                children: offlinePendingId === track.id ? t("Saving offline…") : track.offlineUrl ? t("Remove offline download") : t("Download for offline")
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 695,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                className: "menu-item",
                role: "menuitemcheckbox",
                type: "button",
                "aria-checked": track.favorite,
                onClick: onToggleFavorite,
                children: track.favorite ? t("Remove from liked songs") : t("Save to liked songs")
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 708,
                columnNumber: 7
            }, this),
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$artist$2d$explorer$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["artistNames"])(track).map((name)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                    className: "menu-item",
                    role: "menuitem",
                    type: "button",
                    onClick: ()=>onViewArtist(name),
                    children: [
                        "View artist: ",
                        name
                    ]
                }, name, true, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 718,
                    columnNumber: 9
                }, this)),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                className: "menu-item",
                role: "menuitem",
                type: "button",
                onClick: onShare,
                children: t("Share song")
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 728,
                columnNumber: 7
            }, this),
            inPlaylist && playlist ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                className: "menu-item",
                role: "menuitem",
                type: "button",
                onClick: onRemoveFromPlaylist,
                children: t("Remove from this playlist")
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 730,
                columnNumber: 9
            }, this) : null,
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "menu-sep"
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 734,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                className: `menu-item${hasPlaceholderCover ? " cover-menu-item" : ""}`,
                role: "menuitem",
                type: "button",
                onClick: onAddOrChangeCover,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                        children: t(hasPlaceholderCover ? "Add cover" : "Change cover")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 736,
                        columnNumber: 9
                    }, this),
                    hasPlaceholderCover ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("small", {
                        children: t("Generated placeholder")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 737,
                        columnNumber: 32
                    }, this) : null
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 735,
                columnNumber: 7
            }, this),
            track.coverSource !== "upload" && track.coverSource !== "user" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                className: "menu-item",
                role: "menuitem",
                type: "button",
                onClick: onRetryCover,
                children: t("Retry cover")
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 740,
                columnNumber: 9
            }, this) : null,
            expandedPlayerOpen && track.coverSource === "musicbrainz" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                className: "menu-item",
                role: "menuitem",
                type: "button",
                "aria-haspopup": "dialog",
                onClick: onCoverInfo,
                children: t("Cover art info")
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 745,
                columnNumber: 9
            }, this) : null,
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                className: "menu-item",
                role: "menuitem",
                type: "button",
                onClick: onEditDetails,
                children: t("Edit track details")
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 749,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "menu-sep"
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 752,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                className: "menu-item",
                role: "menuitem",
                type: "button",
                onClick: onRemove,
                children: t("Remove from library")
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 753,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/src/components/library-app.tsx",
        lineNumber: 685,
        columnNumber: 5
    }, this), document.body, `track-menu-${track.id}`);
}
_s3(TrackMenuPortal, "ot2YhC7pP10gRrIouBKIa40vomw=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"]
    ];
});
_c5 = TrackMenuPortal;
function LibraryApp() {
    _s4();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"])();
    const audioElement = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[audioElement]": (state)=>state.audioElement
    }["LibraryApp.usePlayerStore[audioElement]"]);
    const tracks = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[tracks]": (state)=>state.tracks
    }["LibraryApp.usePlayerStore[tracks]"]);
    const playlists = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[playlists]": (state)=>state.playlists
    }["LibraryApp.usePlayerStore[playlists]"]);
    const queue = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[queue]": (state)=>state.queue
    }["LibraryApp.usePlayerStore[queue]"]);
    const queueIndex = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[queueIndex]": (state)=>state.queueIndex
    }["LibraryApp.usePlayerStore[queueIndex]"]);
    const view = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[view]": (state)=>state.view
    }["LibraryApp.usePlayerStore[view]"]);
    const listMode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[listMode]": (state)=>state.listMode
    }["LibraryApp.usePlayerStore[listMode]"]);
    const repeat = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[repeat]": (state)=>state.repeat
    }["LibraryApp.usePlayerStore[repeat]"]);
    const shuffle = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[shuffle]": (state)=>state.shuffle
    }["LibraryApp.usePlayerStore[shuffle]"]);
    const isPlaying = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[isPlaying]": (state)=>state.isPlaying
    }["LibraryApp.usePlayerStore[isPlaying]"]);
    const setTracks = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[setTracks]": (state)=>state.setTracks
    }["LibraryApp.usePlayerStore[setTracks]"]);
    const setLibraryMeta = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[setLibraryMeta]": (state)=>state.setLibraryMeta
    }["LibraryApp.usePlayerStore[setLibraryMeta]"]);
    const setQueue = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[setQueue]": (state)=>state.setQueue
    }["LibraryApp.usePlayerStore[setQueue]"]);
    const setQueueIndex = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[setQueueIndex]": (state)=>state.setQueueIndex
    }["LibraryApp.usePlayerStore[setQueueIndex]"]);
    const setView = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[setView]": (state)=>state.setView
    }["LibraryApp.usePlayerStore[setView]"]);
    const setListMode = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[setListMode]": (state)=>state.setListMode
    }["LibraryApp.usePlayerStore[setListMode]"]);
    const setRepeat = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[setRepeat]": (state)=>state.setRepeat
    }["LibraryApp.usePlayerStore[setRepeat]"]);
    const setShuffle = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[setShuffle]": (state)=>state.setShuffle
    }["LibraryApp.usePlayerStore[setShuffle]"]);
    const setPlaying = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[setPlaying]": (state)=>state.setPlaying
    }["LibraryApp.usePlayerStore[setPlaying]"]);
    const lyricsByTrack = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[lyricsByTrack]": (state)=>state.lyricsByTrack
    }["LibraryApp.usePlayerStore[lyricsByTrack]"]);
    const setCachedLyrics = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[setCachedLyrics]": (state)=>state.setCachedLyrics
    }["LibraryApp.usePlayerStore[setCachedLyrics]"]);
    const toggleFavorite = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[toggleFavorite]": (state)=>state.toggleFavorite
    }["LibraryApp.usePlayerStore[toggleFavorite]"]);
    const setPlaylists = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LibraryApp.usePlayerStore[setPlaylists]": (state)=>state.setPlaylists
    }["LibraryApp.usePlayerStore[setPlaylists]"]);
    const playbackAttemptRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const runPlaybackAttemptRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])({
        "LibraryApp.useRef[runPlaybackAttemptRef]": ()=>{}
    }["LibraryApp.useRef[runPlaybackAttemptRef]"]);
    const coverInfoButtonRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const coverInfoPopoverRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const coverInfoReturnFocusRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const mobilePlayerMenuButtonRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const [search, setSearch] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [loading, setLoading] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(true);
    const [loadError, setLoadError] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [profile, setProfile] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [toast, setToast] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [queueOpen, setQueueOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [lyricsOpen, setLyricsOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [coverInfoTrackId, setCoverInfoTrackId] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [visualizerOpen, setVisualizerOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [shortcutsOpen, setShortcutsOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [queuePickerOpen, setQueuePickerOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [queueSearch, setQueueSearch] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [playlistAddTarget, setPlaylistAddTarget] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [trackMenu, setTrackMenu] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [offlinePendingId, setOfflinePendingId] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [queueDragIndex, setQueueDragIndex] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [queueDragOverIndex, setQueueDragOverIndex] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const queuePointerDragRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const previewLineRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const [playlistModal, setPlaylistModal] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [playlistName, setPlaylistName] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [playlistPicker, setPlaylistPicker] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [coverEditorTrack, setCoverEditorTrack] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [coverFile, setCoverFile] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [coverPreview, setCoverPreview] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [coverPending, setCoverPending] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [coverError, setCoverError] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [applyCoverToAlbum, setApplyCoverToAlbum] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [replaceAlbumUserCovers, setReplaceAlbumUserCovers] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [metadataEditorTrack, setMetadataEditorTrack] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [metadataDraft, setMetadataDraft] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])({
        title: "",
        artist: "",
        album: ""
    });
    const [metadataPending, setMetadataPending] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [metadataError, setMetadataError] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [expandedPlayerOpen, setExpandedPlayerOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [playingFromView, setPlayingFromView] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [currentTime, setCurrentTime] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(0);
    const [lyricsLookupFailedTrackId, setLyricsLookupFailedTrackId] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [previewLineState, setPreviewLineState] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [duration, setDuration] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(0);
    const [volume, setVolume] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(0.7);
    const [muted, setMuted] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [uploadStatus, setUploadStatus] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [isDraggingFiles, setIsDraggingFiles] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const fileInputRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const folderInputRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const playlistNameInputRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const coverFileInputRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const coverPreviewUrlRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const expandedPlayerCloseRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const expandedPlayerReturnFocusRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const queuePanelRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const baselineRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])({
        favorites: [],
        playlists: []
    });
    const etagRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const dirtyRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(false);
    const saveQueueRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(Promise.resolve());
    const shufflePlayedRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(new Set());
    const nextRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])({
        "LibraryApp.useRef[nextRef]": ()=>undefined
    }["LibraryApp.useRef[nextRef]"]);
    const toastTimeoutRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const offlineObjectUrlsRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(new Set());
    const trackCoverPollRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const refreshTrackCoversRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])({
        "LibraryApp.useRef[refreshTrackCoversRef]": async ()=>undefined
    }["LibraryApp.useRef[refreshTrackCoversRef]"]);
    const updateProfilePhoto = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[updateProfilePhoto]": (photoUrl)=>{
            setProfile({
                "LibraryApp.useCallback[updateProfilePhoto]": (current)=>current ? {
                        ...current,
                        photo_url: photoUrl
                    } : current
            }["LibraryApp.useCallback[updateProfilePhoto]"]);
        }
    }["LibraryApp.useCallback[updateProfilePhoto]"], []);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            const shell = document.querySelector("#app > .shell");
            if (!shell) return;
            shell.inert = expandedPlayerOpen;
            return ({
                "LibraryApp.useEffect": ()=>{
                    shell.inert = false;
                }
            })["LibraryApp.useEffect"];
        }
    }["LibraryApp.useEffect"], [
        expandedPlayerOpen
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            const savedMode = window.localStorage.getItem("vervfy:list-mode");
            if (savedMode === "grid" || savedMode === "list") setListMode(savedMode);
        }
    }["LibraryApp.useEffect"], [
        setListMode
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            if (expandedPlayerOpen) {
                expandedPlayerCloseRef.current?.focus();
            } else {
                expandedPlayerReturnFocusRef.current?.focus();
                expandedPlayerReturnFocusRef.current = null;
            }
        }
    }["LibraryApp.useEffect"], [
        expandedPlayerOpen
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            if (!expandedPlayerOpen) return;
            document.body.classList.add("expanded-player-open");
            return ({
                "LibraryApp.useEffect": ()=>document.body.classList.remove("expanded-player-open")
            })["LibraryApp.useEffect"];
        }
    }["LibraryApp.useEffect"], [
        expandedPlayerOpen
    ]);
    const activeTrackId = queueIndex >= 0 ? queue[queueIndex] ?? null : null;
    const currentTrack = tracks.find((track)=>track.id === activeTrackId) ?? null;
    const coverInfoOpen = coverInfoTrackId === currentTrack?.id && currentTrack?.coverSource === "musicbrainz";
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            if (coverInfoOpen) coverInfoPopoverRef.current?.focus();
        }
    }["LibraryApp.useEffect"], [
        coverInfoOpen
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            if (!coverInfoOpen) return;
            const onPointerDown = {
                "LibraryApp.useEffect.onPointerDown": (event)=>{
                    const target = event.target;
                    if (target instanceof Node && !coverInfoPopoverRef.current?.contains(target) && !coverInfoButtonRef.current?.contains(target)) {
                        setCoverInfoTrackId(null);
                    }
                }
            }["LibraryApp.useEffect.onPointerDown"];
            document.addEventListener("pointerdown", onPointerDown);
            return ({
                "LibraryApp.useEffect": ()=>document.removeEventListener("pointerdown", onPointerDown)
            })["LibraryApp.useEffect"];
        }
    }["LibraryApp.useEffect"], [
        coverInfoOpen
    ]);
    const cachedLyrics = currentTrack ? lyricsByTrack[currentTrack.id] : undefined;
    const previewLyrics = currentTrack?.customLyrics ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$lyrics$2d$overlay$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["parseLyricsText"])(currentTrack.customLyrics, "custom") : cachedLyrics;
    const previewLines = previewLyrics?.lines;
    const previewLineIndex = currentTrack && previewLines ? previewLineState?.trackId === currentTrack.id ? previewLineState.index : activePreviewLine(previewLines, currentTime * 1000) : -1;
    const previewCurrentLineIndex = previewLines?.length ? Math.max(0, Math.min(previewLineIndex < 0 ? 0 : previewLineIndex, previewLines.length - 1)) : -1;
    const previewNextLineIndex = previewLineIndex < 0 ? 1 : previewCurrentLineIndex + 1;
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            if (!expandedPlayerOpen || !currentTrack || cachedLyrics || currentTrack.customLyrics) return;
            let cancelled = false;
            const controller = new AbortController();
            const timeout = setTimeout({
                "LibraryApp.useEffect.timeout": ()=>controller.abort()
            }["LibraryApp.useEffect.timeout"], 6000);
            void (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$lyrics$2d$overlay$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["lookupLyrics"])(currentTrack, controller.signal).then({
                "LibraryApp.useEffect": (lyrics)=>{
                    if (!cancelled) setCachedLyrics(currentTrack.id, lyrics);
                }
            }["LibraryApp.useEffect"]).catch({
                "LibraryApp.useEffect": ()=>{
                    if (!cancelled) setLyricsLookupFailedTrackId(currentTrack.id);
                }
            }["LibraryApp.useEffect"]).finally({
                "LibraryApp.useEffect": ()=>clearTimeout(timeout)
            }["LibraryApp.useEffect"]);
            return ({
                "LibraryApp.useEffect": ()=>{
                    cancelled = true;
                    controller.abort();
                    clearTimeout(timeout);
                }
            })["LibraryApp.useEffect"];
        }
    }["LibraryApp.useEffect"], [
        cachedLyrics,
        currentTrack,
        expandedPlayerOpen,
        setCachedLyrics
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            if (!expandedPlayerOpen || !currentTrack || !previewLines?.length) return;
            let frame = 0;
            const update = {
                "LibraryApp.useEffect.update": ()=>{
                    const time = audioElement?.currentTime ?? currentTime;
                    const next = {
                        trackId: currentTrack.id,
                        index: activePreviewLine(previewLines, time * 1000)
                    };
                    const previous = previewLineRef.current;
                    if (previous?.trackId !== next.trackId || previous.index !== next.index) {
                        previewLineRef.current = next;
                        setPreviewLineState(next);
                    }
                    frame = requestAnimationFrame(update);
                }
            }["LibraryApp.useEffect.update"];
            frame = requestAnimationFrame(update);
            return ({
                "LibraryApp.useEffect": ()=>cancelAnimationFrame(frame)
            })["LibraryApp.useEffect"];
        }
    }["LibraryApp.useEffect"], [
        audioElement,
        currentTime,
        currentTrack,
        expandedPlayerOpen,
        previewLines
    ]);
    const tracksById = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "LibraryApp.useMemo[tracksById]": ()=>new Map(tracks.map({
                "LibraryApp.useMemo[tracksById]": (track)=>[
                        track.id,
                        track
                    ]
            }["LibraryApp.useMemo[tracksById]"]))
    }["LibraryApp.useMemo[tracksById]"], [
        tracks
    ]);
    const trackMenuTrack = trackMenu ? tracksById.get(trackMenu.trackId) ?? null : null;
    const title = t(viewName(view, playlists));
    const playlistForView = view.startsWith("playlist:") ? playlists.find((playlist)=>`playlist:${playlist.id}` === view) : null;
    const visibleTracks = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "LibraryApp.useMemo[visibleTracks]": ()=>{
            let list = tracks;
            if (view === "offline") list = list.filter({
                "LibraryApp.useMemo[visibleTracks]": (track)=>track.offline
            }["LibraryApp.useMemo[visibleTracks]"]);
            if (view === "favorites") list = list.filter({
                "LibraryApp.useMemo[visibleTracks]": (track)=>track.favorite
            }["LibraryApp.useMemo[visibleTracks]"]);
            if (view.startsWith("playlist:")) {
                const playlist = playlists.find({
                    "LibraryApp.useMemo[visibleTracks].playlist": (item)=>`playlist:${item.id}` === view
                }["LibraryApp.useMemo[visibleTracks].playlist"]);
                const ids = new Set(playlist?.trackIds ?? []);
                list = list.filter({
                    "LibraryApp.useMemo[visibleTracks]": (track)=>ids.has(track.id)
                }["LibraryApp.useMemo[visibleTracks]"]);
            }
            const query = search.trim().toLocaleLowerCase();
            if (query) {
                list = list.filter({
                    "LibraryApp.useMemo[visibleTracks]": (track)=>`${track.title} ${track.artist} ${track.album}`.toLocaleLowerCase().includes(query)
                }["LibraryApp.useMemo[visibleTracks]"]);
            }
            if (view.startsWith("artist:")) {
                const artistName = decodeURIComponent(view.slice("artist:".length)).toLocaleLowerCase();
                list = list.filter({
                    "LibraryApp.useMemo[visibleTracks]": (track)=>track.artist.toLocaleLowerCase().includes(artistName)
                }["LibraryApp.useMemo[visibleTracks]"]);
            }
            return list;
        }
    }["LibraryApp.useMemo[visibleTracks]"], [
        playlists,
        search,
        tracks,
        view
    ]);
    const filteredPlaylists = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "LibraryApp.useMemo[filteredPlaylists]": ()=>{
            const query = search.trim().toLocaleLowerCase();
            return query ? playlists.filter({
                "LibraryApp.useMemo[filteredPlaylists]": (playlist)=>playlist.name.toLocaleLowerCase().includes(query)
            }["LibraryApp.useMemo[filteredPlaylists]"]) : playlists;
        }
    }["LibraryApp.useMemo[filteredPlaylists]"], [
        playlists,
        search
    ]);
    const notify = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[notify]": (message)=>{
            setToast(message);
            if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
            toastTimeoutRef.current = setTimeout({
                "LibraryApp.useCallback[notify]": ()=>setToast("")
            }["LibraryApp.useCallback[notify]"], 2600);
        }
    }["LibraryApp.useCallback[notify]"], []);
    const reloadTracks = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[reloadTracks]": async ()=>{
            const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fetchWithRetry"])("/api/tracks", {
                cache: "no-store"
            }, 3));
            const payload = await response.json();
            const previousTracks = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().tracks;
            const previousById = new Map(previousTracks.map({
                "LibraryApp.useCallback[reloadTracks]": (track)=>[
                        track.id,
                        track
                    ]
            }["LibraryApp.useCallback[reloadTracks]"]));
            const nextTracks = payload.tracks.map({
                "LibraryApp.useCallback[reloadTracks].nextTracks": (track)=>{
                    const previous = previousById.get(track.id);
                    const keepCachedImage = previous?.coverSource === "audiodb" && !track.has_cover && (track.cover_source === "placeholder" || track.cover_source === "generated");
                    const fallback = coverUrlForTrack(track);
                    return {
                        id: track.id,
                        title: track.title || "Unknown title",
                        artist: track.artist || "Unknown artist",
                        album: track.album || "Unknown album",
                        duration: track.duration || 0,
                        hasCover: track.has_cover,
                        coverUrl: keepCachedImage ? previous.coverUrl : fallback,
                        remoteCoverUrl: keepCachedImage ? previous.remoteCoverUrl : fallback,
                        streamUrl: track.stream_url,
                        coverSource: keepCachedImage ? "audiodb" : track.cover_source ?? "unknown",
                        offlineUrl: previous?.offlineUrl ?? null,
                        offline: previous?.offline ?? false,
                        favorite: previous?.favorite ?? false,
                        customLyrics: track.custom_lyrics ?? previous?.customLyrics ?? null
                    };
                }
            }["LibraryApp.useCallback[reloadTracks].nextTracks"]);
            setTracks(nextTracks);
            void refreshTrackCoversRef.current();
        }
    }["LibraryApp.useCallback[reloadTracks]"], [
        setTracks
    ]);
    const refreshTrackCovers = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[refreshTrackCovers]": async ()=>{
            try {
                const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fetchWithRetry"])("/api/tracks/covers", {
                    cache: "no-store"
                }, 2));
                const payload = await response.json();
                const cached = payload.covers ?? {};
                setTracks(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().tracks.map({
                    "LibraryApp.useCallback[refreshTrackCovers]": (track)=>{
                        const result = cached[track.id];
                        if (!result?.cover_url || track.offline || track.hasCover || track.coverSource === "embedded" || track.coverSource === "upload" || track.coverSource === "user" || track.coverSource === "musicbrainz" || track.coverSource === "audiodb") {
                            return track;
                        }
                        const coverUrl = coverUrlForTrack({
                            ...track,
                            has_cover: track.hasCover ?? false,
                            cover_url: result.cover_url,
                            cover_source: result.cover_source ?? "generated"
                        });
                        return {
                            ...track,
                            coverUrl,
                            remoteCoverUrl: coverUrl,
                            coverSource: result.cover_source ?? "generated"
                        };
                    }
                }["LibraryApp.useCallback[refreshTrackCovers]"]));
                if (trackCoverPollRef.current) clearTimeout(trackCoverPollRef.current);
                if (payload.pending) {
                    trackCoverPollRef.current = setTimeout({
                        "LibraryApp.useCallback[refreshTrackCovers]": ()=>void refreshTrackCoversRef.current()
                    }["LibraryApp.useCallback[refreshTrackCovers]"], 12_000);
                }
            } catch (error) {
                console.warn("[covers] Could not refresh TheAudioDB track covers.", error);
                if (trackCoverPollRef.current) clearTimeout(trackCoverPollRef.current);
                trackCoverPollRef.current = setTimeout({
                    "LibraryApp.useCallback[refreshTrackCovers]": ()=>void refreshTrackCoversRef.current()
                }["LibraryApp.useCallback[refreshTrackCovers]"], 30_000);
            }
        }
    }["LibraryApp.useCallback[refreshTrackCovers]"], [
        setTracks
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            refreshTrackCoversRef.current = refreshTrackCovers;
        }
    }["LibraryApp.useEffect"], [
        refreshTrackCovers
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>({
                "LibraryApp.useEffect": ()=>{
                    if (trackCoverPollRef.current) clearTimeout(trackCoverPollRef.current);
                }
            })["LibraryApp.useEffect"]
    }["LibraryApp.useEffect"], []);
    function openCoverEditor(track) {
        setTrackMenu(null);
        setExpandedPlayerOpen(false);
        setCoverFile(null);
        setCoverError("");
        setApplyCoverToAlbum(false);
        setReplaceAlbumUserCovers(false);
        setCoverEditorTrack(track);
    }
    function closeCoverEditor() {
        if (coverPreviewUrlRef.current) URL.revokeObjectURL(coverPreviewUrlRef.current);
        coverPreviewUrlRef.current = null;
        setCoverPreview(null);
        setCoverFile(null);
        setCoverError("");
        setApplyCoverToAlbum(false);
        setReplaceAlbumUserCovers(false);
        setCoverEditorTrack(null);
    }
    function openMetadataEditor(track) {
        setTrackMenu(null);
        setExpandedPlayerOpen(false);
        setMetadataDraft({
            title: track.title,
            artist: track.artist,
            album: track.album
        });
        setMetadataError("");
        setMetadataEditorTrack(track);
    }
    async function saveCover() {
        if (!coverEditorTrack || !coverFile) {
            setCoverError(t("Choose cover image."));
            return;
        }
        setCoverPending(true);
        setCoverError("");
        try {
            const form = new FormData();
            form.append("file", coverFile);
            form.append("apply_to_album", String(applyCoverToAlbum));
            form.append("replace_user_covers", String(applyCoverToAlbum && replaceAlbumUserCovers));
            await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])(`/api/tracks/${encodeURIComponent(coverEditorTrack.id)}/cover`, {
                method: "PUT",
                body: form
            }, {
                csrf: true,
                retryCsrfOnForbidden: true
            }));
            await reloadTracks();
            notify(t("Cover updated."));
            closeCoverEditor();
        } catch (error) {
            setCoverError(error instanceof Error ? error.message : t("Could not update cover."));
        } finally{
            setCoverPending(false);
        }
    }
    async function removeCover() {
        if (!coverEditorTrack) return;
        setCoverPending(true);
        setCoverError("");
        try {
            await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])(`/api/tracks/${encodeURIComponent(coverEditorTrack.id)}/cover`, {
                method: "DELETE"
            }, {
                csrf: true,
                retryCsrfOnForbidden: true
            }));
            await reloadTracks();
            notify(t("Cover removed."));
            closeCoverEditor();
        } catch (error) {
            setCoverError(error instanceof Error ? error.message : t("Could not remove cover."));
        } finally{
            setCoverPending(false);
        }
    }
    async function saveTrackDetails(event) {
        event.preventDefault();
        if (!metadataEditorTrack) return;
        setMetadataPending(true);
        setMetadataError("");
        try {
            await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])(`/api/tracks/${encodeURIComponent(metadataEditorTrack.id)}`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    title: metadataDraft.title.trim(),
                    artist: metadataDraft.artist.trim(),
                    album: metadataDraft.album.trim()
                })
            }, {
                csrf: true,
                retryCsrfOnForbidden: true
            }));
            await reloadTracks();
            setMetadataEditorTrack(null);
            notify(t("Track details saved."));
        } catch (error) {
            setMetadataError(error instanceof Error ? error.message : t("Could not update track details."));
        } finally{
            setMetadataPending(false);
        }
    }
    const uploadFiles = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[uploadFiles]": async (selectedFiles)=>{
            const files = Array.from(selectedFiles).filter({
                "LibraryApp.useCallback[uploadFiles].files": (file)=>file.type.startsWith("audio/") || /\.(mp3|m4a|mp4|wav|flac|ogg|oga|aac|opus|weba)$/i.test(file.name)
            }["LibraryApp.useCallback[uploadFiles].files"]);
            if (files.length === 0) {
                notify("No audio files found in that selection.");
                return;
            }
            let added = 0;
            let failed = 0;
            let firstFailure = "";
            let rateLimited = false;
            let nextFileIndex = 0;
            let completedFiles = 0;
            const knownTrackIds = new Set(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().tracks.map({
                "LibraryApp.useCallback[uploadFiles]": (track)=>track.id
            }["LibraryApp.useCallback[uploadFiles]"]));
            setUploadStatus(`Uploading 0/${files.length}…`);
            const uploadNext = {
                "LibraryApp.useCallback[uploadFiles].uploadNext": async ()=>{
                    while(!rateLimited){
                        const index = nextFileIndex;
                        nextFileIndex += 1;
                        if (index >= files.length) return;
                        const file = files[index];
                        try {
                            const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["uploadWithRetry"])("/api/library/upload", file);
                            const uploadResult = await response.json();
                            let uploadedTrack;
                            let resolvedFromReload = false;
                            if ("status" in uploadResult && uploadResult.status === "processing") {
                                for(let attempt = 0; attempt < 60; attempt += 1){
                                    await new Promise({
                                        "LibraryApp.useCallback[uploadFiles].uploadNext": (resolve)=>setTimeout(resolve, 1000)
                                    }["LibraryApp.useCallback[uploadFiles].uploadNext"]);
                                    const statusResponse = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])(`/api/library/upload/${encodeURIComponent(uploadResult.id)}`));
                                    const status = await statusResponse.json();
                                    if (status.status === "completed") {
                                        uploadedTrack = status.track;
                                        if (!uploadedTrack) {
                                            await reloadTracks();
                                            const refreshedTrack = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().tracks.find({
                                                "LibraryApp.useCallback[uploadFiles].uploadNext.refreshedTrack": (track)=>track.id === status.track_id
                                            }["LibraryApp.useCallback[uploadFiles].uploadNext.refreshedTrack"]);
                                            if (!refreshedTrack) {
                                                throw new Error("Upload completed but the track is not available yet.");
                                            }
                                            resolvedFromReload = true;
                                        }
                                        break;
                                    }
                                    if (status.status === "failed") {
                                        throw new Error(status.error || "Upload processing failed.");
                                    }
                                }
                                if (!uploadedTrack && !resolvedFromReload) {
                                    throw new Error("Upload is still processing; refresh the library shortly.");
                                }
                            } else if ("title" in uploadResult && "stream_url" in uploadResult) {
                                uploadedTrack = uploadResult;
                            } else {
                                throw new Error("The upload response was not recognized.");
                            }
                            if (uploadedTrack) {
                                if (!knownTrackIds.has(uploadedTrack.id)) {
                                    knownTrackIds.add(uploadedTrack.id);
                                    added += 1;
                                }
                            } else if (resolvedFromReload) {
                                added += 1;
                            }
                        } catch (error) {
                            failed += 1;
                            firstFailure = firstFailure || (error instanceof Error ? error.message : "Upload failed.");
                            if (error && typeof error === "object" && "status" in error && error.status === 429) {
                                rateLimited = true;
                                return;
                            }
                        } finally{
                            completedFiles += 1;
                            if (completedFiles % 4 === 0 || completedFiles === files.length) {
                                setUploadStatus(`Uploading ${completedFiles}/${files.length}…`);
                            }
                        }
                    }
                }
            }["LibraryApp.useCallback[uploadFiles].uploadNext"];
            await Promise.all(Array.from({
                length: Math.min(3, files.length)
            }, {
                "LibraryApp.useCallback[uploadFiles]": ()=>uploadNext()
            }["LibraryApp.useCallback[uploadFiles]"]));
            if (added > 0) await reloadTracks();
            setUploadStatus("");
            if (rateLimited) {
                notify(`${added} uploaded; the rest were rate limited. Try again later.`);
            } else if (added > 0 && failed > 0) {
                notify(`Saved ${added}; ${failed} failed: ${firstFailure}`);
            } else if (added > 0) {
                notify(`Saved ${added} track${added === 1 ? "" : "s"} to your library.`);
            } else if (failed > 0) {
                notify(`${files.length === 1 ? "Upload failed" : `${failed} uploads failed`}: ${firstFailure}`);
            } else {
                notify("Those tracks were already in your library.");
            }
        }
    }["LibraryApp.useCallback[uploadFiles]"], [
        notify,
        reloadTracks
    ]);
    async function retryCoverLookup(track) {
        setTrackMenu(null);
        try {
            await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])(`/api/tracks/${encodeURIComponent(track.id)}/cover/retry`, {
                method: "POST"
            }, {
                csrf: true,
                retryCsrfOnForbidden: true
            }));
            notify(t("Cover lookup queued."));
            window.setTimeout(()=>{
                void reloadTracks();
            }, 2500);
        } catch (error) {
            notify(error instanceof Error ? error.message : t("Could not retry cover lookup."));
        }
    }
    const applyMeta = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[applyMeta]": (meta)=>{
            const trackIds = new Set(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().tracks.map({
                "LibraryApp.useCallback[applyMeta]": (track)=>track.id
            }["LibraryApp.useCallback[applyMeta]"]));
            const filtered = {
                favorites: meta.favorites.filter({
                    "LibraryApp.useCallback[applyMeta]": (id)=>trackIds.has(id)
                }["LibraryApp.useCallback[applyMeta]"]),
                playlists: meta.playlists.map({
                    "LibraryApp.useCallback[applyMeta]": (playlist)=>({
                            ...playlist,
                            trackIds: playlist.trackIds.filter({
                                "LibraryApp.useCallback[applyMeta]": (id)=>trackIds.has(id)
                            }["LibraryApp.useCallback[applyMeta]"])
                        })
                }["LibraryApp.useCallback[applyMeta]"])
            };
            setLibraryMeta(filtered.favorites, filtered.playlists);
        }
    }["LibraryApp.useCallback[applyMeta]"], [
        setLibraryMeta
    ]);
    const saveMeta = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[saveMeta]": ()=>{
            dirtyRef.current = true;
            const save = {
                "LibraryApp.useCallback[saveMeta].save": async ()=>{
                    let snapshot = getMetaFromStore();
                    if (!etagRef.current) return;
                    let conflictRetries = 0;
                    while(true){
                        const etag = etagRef.current;
                        if (!etag) return;
                        const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])("/api/library/state", {
                            method: "PUT",
                            headers: {
                                "Content-Type": "application/json",
                                "If-Match": etag
                            },
                            body: JSON.stringify(snapshot)
                        }, {
                            csrf: true,
                            retryCsrfOnForbidden: true
                        });
                        if (response.status === 409 && conflictRetries < 2) {
                            const latestResponse = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fetchWithRetry"])("/api/library/state", {
                                cache: "no-store"
                            }, 3));
                            const remote = normalizeMeta(await latestResponse.json());
                            const latestLocal = getMetaFromStore();
                            const merged = mergeUnsavedMeta(remote, baselineRef.current, latestLocal);
                            etagRef.current = latestResponse.headers.get("ETag");
                            baselineRef.current = remote;
                            applyMeta(merged);
                            snapshot = merged;
                            conflictRetries += 1;
                            continue;
                        }
                        await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(response);
                        etagRef.current = response.headers.get("ETag") ?? etagRef.current;
                        baselineRef.current = normalizeMeta(await response.json());
                        dirtyRef.current = !sameMeta(getMetaFromStore(), snapshot);
                        return;
                    }
                }
            }["LibraryApp.useCallback[saveMeta].save"];
            const queuedSave = saveQueueRef.current.then(save, save);
            saveQueueRef.current = queuedSave.catch({
                "LibraryApp.useCallback[saveMeta]": (error)=>{
                    dirtyRef.current = true;
                    notify(error instanceof Error ? `Library changes could not be synced: ${error.message}` : "Library changes could not be synced. Please try again.");
                }
            }["LibraryApp.useCallback[saveMeta]"]);
            return saveQueueRef.current;
        }
    }["LibraryApp.useCallback[saveMeta]"], [
        applyMeta,
        notify
    ]);
    const handlePlaybackFailure = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[handlePlaybackFailure]": (attempt, audio, error, message, refreshSignedUrl = false)=>{
            if (playbackAttemptRef.current !== attempt || attempt.failed || attempt.retryTimer !== null) {
                return;
            }
            attempt.loading = false;
            const errorName = error && typeof error === "object" && "name" in error && typeof error.name === "string" ? error.name : "";
            if (errorName === "AbortError") {
                return;
            }
            if (errorName !== "NotAllowedError" && attempt.retryCount === 0 && (refreshSignedUrl || errorName === "NetworkError" || audio.error?.code === MediaError.MEDIA_ERR_ABORTED || audio.error?.code === MediaError.MEDIA_ERR_NETWORK)) {
                attempt.retryCount += 1;
                attempt.retryTimer = window.setTimeout({
                    "LibraryApp.useCallback[handlePlaybackFailure]": ()=>{
                        attempt.retryTimer = null;
                        if (playbackAttemptRef.current === attempt && audio.src === attempt.src) {
                            runPlaybackAttemptRef.current(attempt);
                        }
                    }
                }["LibraryApp.useCallback[handlePlaybackFailure]"], 300);
                return;
            }
            attempt.failed = true;
            setPlaying(false);
            notify(errorName === "NotAllowedError" ? "Press play to start." : message);
        }
    }["LibraryApp.useCallback[handlePlaybackFailure]"], [
        notify,
        setPlaying
    ]);
    const runPlaybackAttempt = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[runPlaybackAttempt]": (attempt)=>{
            const audio = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement;
            if (!audio || playbackAttemptRef.current !== attempt) return;
            const requestId = ++attempt.requestId;
            attempt.loading = true;
            if (audio.src !== attempt.src || audio.error !== null || audio.networkState === HTMLMediaElement.NETWORK_NO_SOURCE) {
                audio.src = attempt.src;
                audio.load();
            }
            setPlaying(true);
            void audio.play().then({
                "LibraryApp.useCallback[runPlaybackAttempt]": ()=>{
                    if (playbackAttemptRef.current === attempt && attempt.requestId === requestId) {
                        attempt.loading = false;
                    }
                }
            }["LibraryApp.useCallback[runPlaybackAttempt]"], {
                "LibraryApp.useCallback[runPlaybackAttempt]": (error)=>{
                    if (playbackAttemptRef.current !== attempt || attempt.requestId !== requestId || audio.src !== attempt.src) {
                        return;
                    }
                    attempt.loading = false;
                    if (error && typeof error === "object" && "name" in error && error.name === "AbortError") {
                        setPlaying(false);
                        return;
                    }
                    logAudioFailure("play() rejected", audio, error);
                    handlePlaybackFailure(attempt, audio, error, "The track could not start. Please try again.");
                }
            }["LibraryApp.useCallback[runPlaybackAttempt]"]);
        }
    }["LibraryApp.useCallback[runPlaybackAttempt]"], [
        handlePlaybackFailure,
        setPlaying
    ]);
    const startTrack = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[startTrack]": (trackId)=>{
            const track = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().tracks.find({
                "LibraryApp.useCallback[startTrack].track": (item)=>item.id === trackId
            }["LibraryApp.useCallback[startTrack].track"]);
            const audio = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement;
            if (!track || !audio) return;
            const src = new URL(track.offlineUrl || track.streamUrl, window.location.href).href;
            const currentAttempt = playbackAttemptRef.current;
            if (currentAttempt?.src === src && !currentAttempt.failed && (currentAttempt.loading || !audio.paused)) {
                return;
            }
            const previousAttempt = playbackAttemptRef.current;
            if (previousAttempt?.retryTimer !== null && previousAttempt?.retryTimer !== undefined) {
                window.clearTimeout(previousAttempt.retryTimer);
            }
            const attempt = {
                src,
                retryCount: 0,
                retryTimer: null,
                requestId: 0,
                loading: false,
                failed: false
            };
            playbackAttemptRef.current = attempt;
            runPlaybackAttemptRef.current = runPlaybackAttempt;
            runPlaybackAttempt(attempt);
        }
    }["LibraryApp.useCallback[startTrack]"], [
        runPlaybackAttempt
    ]);
    const handleAudioError = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[handleAudioError]": (audio)=>{
            const error = new Error(audio.error?.message || "Audio element emitted an error");
            error.name = "MediaError";
            logAudioFailure("audio error event", audio, error);
            const attempt = playbackAttemptRef.current;
            if (!attempt || audio.src !== attempt.src) {
                return;
            }
            handlePlaybackFailure(attempt, audio, error, "This track could not be played. Check the file format or your connection.", true);
        }
    }["LibraryApp.useCallback[handleAudioError]"], [
        handlePlaybackFailure
    ]);
    const playFromList = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[playFromList]": (list, trackId)=>{
            const ids = list.map({
                "LibraryApp.useCallback[playFromList].ids": (track)=>track.id
            }["LibraryApp.useCallback[playFromList].ids"]);
            const index = ids.indexOf(trackId);
            if (index < 0) return;
            setPlayingFromView(view);
            shufflePlayedRef.current = new Set([
                index
            ]);
            setQueue(ids, index);
            startTrack(trackId);
        }
    }["LibraryApp.useCallback[playFromList]"], [
        setQueue,
        startTrack,
        view
    ]);
    const playQueueIndex = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[playQueueIndex]": (index)=>{
            const state = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState();
            const trackId = state.queue[index];
            if (!trackId) return;
            setQueueIndex(index);
            startTrack(trackId);
        }
    }["LibraryApp.useCallback[playQueueIndex]"], [
        setQueueIndex,
        startTrack
    ]);
    const playNext = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[playNext]": (automatic)=>{
            const state = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState();
            const audio = state.audioElement;
            if (!audio || state.queue.length === 0) return;
            if (automatic && state.repeat === "one") {
                audio.currentTime = 0;
                void audio.play().catch({
                    "LibraryApp.useCallback[playNext]": ()=>notify("The track could not restart. Please try again.")
                }["LibraryApp.useCallback[playNext]"]);
                return;
            }
            let nextIndex = state.queueIndex + 1;
            if (state.shuffle) {
                shufflePlayedRef.current.add(state.queueIndex);
                let choices = state.queue.map({
                    "LibraryApp.useCallback[playNext].choices": (_, index)=>index
                }["LibraryApp.useCallback[playNext].choices"]).filter({
                    "LibraryApp.useCallback[playNext].choices": (index)=>index !== state.queueIndex
                }["LibraryApp.useCallback[playNext].choices"]);
                if (automatic && state.repeat === "off") {
                    choices = choices.filter({
                        "LibraryApp.useCallback[playNext]": (index)=>!shufflePlayedRef.current.has(index)
                    }["LibraryApp.useCallback[playNext]"]);
                    if (choices.length === 0) {
                        audio.pause();
                        return;
                    }
                } else if (automatic && state.repeat === "all" && !choices.some({
                    "LibraryApp.useCallback[playNext]": (index)=>!shufflePlayedRef.current.has(index)
                }["LibraryApp.useCallback[playNext]"])) {
                    shufflePlayedRef.current = new Set([
                        state.queueIndex
                    ]);
                }
                if (choices.length === 0) choices = [
                    state.queueIndex
                ];
                nextIndex = choices[Math.floor(Math.random() * choices.length)];
                shufflePlayedRef.current.add(nextIndex);
            } else if (nextIndex >= state.queue.length) {
                nextIndex = 0;
            }
            playQueueIndex(nextIndex);
        }
    }["LibraryApp.useCallback[playNext]"], [
        notify,
        playQueueIndex
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            nextRef.current = playNext;
        }
    }["LibraryApp.useEffect"], [
        playNext
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            const panel = queuePanelRef.current;
            if (!panel) return;
            panel.inert = !queueOpen;
            if (queueOpen) panel.removeAttribute("aria-hidden");
            else panel.setAttribute("aria-hidden", "true");
        }
    }["LibraryApp.useEffect"], [
        queueOpen
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            if (!trackMenu) return;
            const onPointerDown = {
                "LibraryApp.useEffect.onPointerDown": (event)=>{
                    if (!(event.target instanceof Element)) return;
                    if (event.target.closest(".track-context-menu") || event.target.closest("[data-track-menu-trigger]")) {
                        return;
                    }
                    setTrackMenu(null);
                }
            }["LibraryApp.useEffect.onPointerDown"];
            document.addEventListener("pointerdown", onPointerDown);
            return ({
                "LibraryApp.useEffect": ()=>document.removeEventListener("pointerdown", onPointerDown)
            })["LibraryApp.useEffect"];
        }
    }["LibraryApp.useEffect"], [
        trackMenu
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            if (playlistModal) playlistNameInputRef.current?.focus();
        }
    }["LibraryApp.useEffect"], [
        playlistModal
    ]);
    const playPrevious = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[playPrevious]": ()=>{
            const state = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState();
            const audio = state.audioElement;
            if (!audio || state.queue.length === 0) return;
            if (audio.currentTime > 3) {
                audio.currentTime = 0;
                return;
            }
            playQueueIndex(Math.max(0, state.queueIndex - 1));
        }
    }["LibraryApp.useCallback[playPrevious]"], [
        playQueueIndex
    ]);
    const togglePlayback = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[togglePlayback]": ()=>{
            if (!audioElement) return;
            if (!currentTrack) {
                if (visibleTracks[0]) playFromList(visibleTracks, visibleTracks[0].id);
                return;
            }
            if (audioElement.paused) {
                if (audioElement.getAttribute("src")) {
                    void audioElement.play().catch({
                        "LibraryApp.useCallback[togglePlayback]": ()=>startTrack(currentTrack.id)
                    }["LibraryApp.useCallback[togglePlayback]"]);
                } else {
                    startTrack(currentTrack.id);
                }
            } else {
                const attempt = playbackAttemptRef.current;
                if (attempt?.retryTimer !== null && attempt?.retryTimer !== undefined) {
                    window.clearTimeout(attempt.retryTimer);
                    attempt.retryTimer = null;
                }
                if (attempt) attempt.requestId += 1;
                audioElement.pause();
            }
        }
    }["LibraryApp.useCallback[togglePlayback]"], [
        audioElement,
        currentTrack,
        playFromList,
        startTrack,
        visibleTracks
    ]);
    const toggleCurrentFavorite = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "LibraryApp.useCallback[toggleCurrentFavorite]": ()=>{
            const state = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState();
            const trackId = state.queue[state.queueIndex];
            if (!trackId) return;
            state.toggleFavorite(trackId);
            void saveMeta();
        }
    }["LibraryApp.useCallback[toggleCurrentFavorite]"], [
        saveMeta
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            const mediaSession = navigator.mediaSession;
            if (!mediaSession) return;
            const active = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().tracks.find({
                "LibraryApp.useEffect.active": (track)=>track.id === __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().queue[__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().queueIndex]
            }["LibraryApp.useEffect.active"]);
            if (!active) {
                mediaSession.metadata = null;
                mediaSession.playbackState = "none";
                return;
            }
            mediaSession.playbackState = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement?.paused ? "paused" : "playing";
            if ("MediaMetadata" in window) {
                try {
                    mediaSession.metadata = new MediaMetadata({
                        title: active.title || "Unknown title",
                        artist: active.artist || "Unknown artist",
                        album: active.album || "",
                        artwork: [
                            96,
                            128,
                            192,
                            256,
                            384,
                            512
                        ].map({
                            "LibraryApp.useEffect": (size)=>({
                                    src: new URL(active.coverUrl, window.location.href).href,
                                    sizes: `${size}x${size}`,
                                    type: "image/jpeg"
                                })
                        }["LibraryApp.useEffect"])
                    });
                } catch (error) {
                    console.warn("Could not set system media metadata", error);
                }
            }
            const actions = [
                [
                    "play",
                    {
                        "LibraryApp.useEffect": ()=>togglePlayback()
                    }["LibraryApp.useEffect"]
                ],
                [
                    "pause",
                    {
                        "LibraryApp.useEffect": ()=>__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement?.pause()
                    }["LibraryApp.useEffect"]
                ],
                [
                    "previoustrack",
                    {
                        "LibraryApp.useEffect": ()=>playPrevious()
                    }["LibraryApp.useEffect"]
                ],
                [
                    "nexttrack",
                    {
                        "LibraryApp.useEffect": ()=>nextRef.current(false)
                    }["LibraryApp.useEffect"]
                ],
                [
                    "seekbackward",
                    {
                        "LibraryApp.useEffect": (details)=>seekAudio(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement, -(Number(details.seekOffset) || 10))
                    }["LibraryApp.useEffect"]
                ],
                [
                    "seekforward",
                    {
                        "LibraryApp.useEffect": (details)=>seekAudio(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement, Number(details.seekOffset) || 10)
                    }["LibraryApp.useEffect"]
                ],
                [
                    "seekto",
                    {
                        "LibraryApp.useEffect": (details)=>{
                            const audio = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement;
                            if (audio && Number.isFinite(details.seekTime)) {
                                audio.currentTime = Math.max(0, Math.min(audio.duration || Infinity, details.seekTime ?? 0));
                            }
                        }
                    }["LibraryApp.useEffect"]
                ]
            ];
            for (const [action, handler] of actions){
                try {
                    mediaSession.setActionHandler(action, handler);
                } catch  {
                // Unsupported actions are ignored by the browser.
                }
            }
            return ({
                "LibraryApp.useEffect": ()=>{
                    for (const [action] of actions){
                        try {
                            mediaSession.setActionHandler(action, null);
                        } catch  {
                        // Unsupported actions are ignored by the browser.
                        }
                    }
                }
            })["LibraryApp.useEffect"];
        }
    }["LibraryApp.useEffect"], [
        activeTrackId,
        playPrevious,
        togglePlayback
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            const onKeyDown = {
                "LibraryApp.useEffect.onKeyDown": (event)=>{
                    const target = event.target;
                    if (target instanceof HTMLElement && (target.isContentEditable || [
                        "INPUT",
                        "TEXTAREA",
                        "SELECT"
                    ].includes(target.tagName))) {
                        if (event.key === "Escape") target.blur();
                        return;
                    }
                    if (event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey) {
                        event.preventDefault();
                        document.querySelector(".search-wrap input")?.focus();
                        return;
                    }
                    if (event.key === "Escape") {
                        setExpandedPlayerOpen(false);
                        setLyricsOpen(false);
                        setCoverInfoTrackId(null);
                        if (coverInfoOpen) coverInfoButtonRef.current?.focus();
                        setVisualizerOpen(false);
                        setQueueOpen(false);
                        setPlaylistPicker(null);
                        setPlaylistModal(null);
                        setShortcutsOpen(false);
                        setTrackMenu(null);
                        return;
                    }
                    if (event.key === "?") {
                        setShortcutsOpen({
                            "LibraryApp.useEffect.onKeyDown": (current)=>!current
                        }["LibraryApp.useEffect.onKeyDown"]);
                        return;
                    }
                    switch(event.key){
                        case " ":
                            event.preventDefault();
                            togglePlayback();
                            break;
                        case "ArrowRight":
                            if (event.shiftKey) nextRef.current(false);
                            else seekAudio(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement, 5);
                            break;
                        case "ArrowLeft":
                            if (event.shiftKey) playPrevious();
                            else seekAudio(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement, -5);
                            break;
                        case "ArrowUp":
                            event.preventDefault();
                            setVolume({
                                "LibraryApp.useEffect.onKeyDown": (current)=>Math.min(1, current + 0.05)
                            }["LibraryApp.useEffect.onKeyDown"]);
                            break;
                        case "ArrowDown":
                            event.preventDefault();
                            setVolume({
                                "LibraryApp.useEffect.onKeyDown": (current)=>Math.max(0, current - 0.05)
                            }["LibraryApp.useEffect.onKeyDown"]);
                            break;
                        case "m":
                        case "M":
                            setMuted({
                                "LibraryApp.useEffect.onKeyDown": (current)=>!current
                            }["LibraryApp.useEffect.onKeyDown"]);
                            break;
                        case "f":
                        case "F":
                            toggleCurrentFavorite();
                            break;
                        case "l":
                        case "L":
                            setLyricsOpen({
                                "LibraryApp.useEffect.onKeyDown": (current)=>!current
                            }["LibraryApp.useEffect.onKeyDown"]);
                            break;
                        case "v":
                        case "V":
                            setVisualizerOpen({
                                "LibraryApp.useEffect.onKeyDown": (current)=>!current
                            }["LibraryApp.useEffect.onKeyDown"]);
                            break;
                    }
                }
            }["LibraryApp.useEffect.onKeyDown"];
            document.addEventListener("keydown", onKeyDown);
            return ({
                "LibraryApp.useEffect": ()=>document.removeEventListener("keydown", onKeyDown)
            })["LibraryApp.useEffect"];
        }
    }["LibraryApp.useEffect"], [
        coverInfoOpen,
        playPrevious,
        toggleCurrentFavorite,
        togglePlayback
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            let cancelled = false;
            async function loadLibrary() {
                setLoading(true);
                setLoadError(null);
                try {
                    const [tracksResponse, stateResponse, accountResponse] = await Promise.all([
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fetchWithRetry"])("/api/tracks", {
                            cache: "no-store"
                        }, 3),
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fetchWithRetry"])("/api/library/state", {
                            cache: "no-store"
                        }, 3),
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fetchWithRetry"])("/api/me", {
                            cache: "no-store"
                        }, 3)
                    ]);
                    await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(tracksResponse);
                    await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(stateResponse);
                    await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(accountResponse);
                    const payload = await tracksResponse.json();
                    const account = await accountResponse.json();
                    const nextTracks = payload.tracks.map({
                        "LibraryApp.useEffect.loadLibrary.nextTracks": (track)=>({
                                id: track.id,
                                title: track.title || "Unknown title",
                                artist: track.artist || "Unknown artist",
                                album: track.album || "Unknown album",
                                duration: track.duration || 0,
                                hasCover: track.has_cover,
                                coverUrl: coverUrlForTrack(track),
                                remoteCoverUrl: coverUrlForTrack(track),
                                streamUrl: track.stream_url,
                                coverSource: track.cover_source ?? "unknown",
                                favorite: false,
                                customLyrics: track.custom_lyrics ?? null
                            })
                    }["LibraryApp.useEffect.loadLibrary.nextTracks"]);
                    const remoteMeta = normalizeMeta(await stateResponse.json());
                    const legacyMeta = await readLegacyMeta();
                    let offlineRecords = [];
                    try {
                        offlineRecords = await readOfflineTracks(account.id);
                    } catch (error) {
                        console.error("Could not load saved offline tracks.", error);
                        notify("Saved offline tracks could not be loaded from this browser.");
                    }
                    const offlineById = new Map(offlineRecords.map({
                        "LibraryApp.useEffect.loadLibrary": (record)=>[
                                record.trackId,
                                record
                            ]
                    }["LibraryApp.useEffect.loadLibrary"]));
                    for (const track of nextTracks){
                        const record = offlineById.get(track.id);
                        if (!record) continue;
                        const offlineUrl = URL.createObjectURL(record.audio);
                        offlineObjectUrlsRef.current.add(offlineUrl);
                        track.offlineUrl = offlineUrl;
                        track.offline = true;
                        track.customLyrics = record.customLyrics ?? track.customLyrics;
                        if (record.cover instanceof Blob) {
                            const coverUrl = URL.createObjectURL(record.cover);
                            offlineObjectUrlsRef.current.add(coverUrl);
                            track.coverUrl = coverUrl;
                        }
                    }
                    const loadedTrackIds = new Set(nextTracks.map({
                        "LibraryApp.useEffect.loadLibrary": (track)=>track.id
                    }["LibraryApp.useEffect.loadLibrary"]));
                    for (const record of offlineRecords){
                        if (loadedTrackIds.has(record.trackId)) continue;
                        const offlineUrl = URL.createObjectURL(record.audio);
                        offlineObjectUrlsRef.current.add(offlineUrl);
                        const fallbackCover = generateAura(`${record.artist}|${record.album}|${record.title}`);
                        let coverUrl = fallbackCover;
                        if (record.cover instanceof Blob) {
                            coverUrl = URL.createObjectURL(record.cover);
                            offlineObjectUrlsRef.current.add(coverUrl);
                        }
                        nextTracks.push({
                            id: record.trackId,
                            title: record.title || "Unknown title",
                            artist: record.artist || "Unknown artist",
                            album: record.album || "Unknown album",
                            duration: record.duration || 0,
                            coverUrl,
                            remoteCoverUrl: fallbackCover,
                            streamUrl: "",
                            offlineUrl,
                            offline: true,
                            favorite: false,
                            customLyrics: record.customLyrics
                        });
                    }
                    if (cancelled) return;
                    setProfile(account);
                    setTracks(nextTracks);
                    void refreshTrackCoversRef.current();
                    void refreshTrackCoversRef.current();
                    baselineRef.current = remoteMeta;
                    etagRef.current = stateResponse.headers.get("ETag");
                    if (remoteMeta.favorites.length === 0 && remoteMeta.playlists.length === 0 && legacyMeta && (legacyMeta.favorites.length > 0 || legacyMeta.playlists.length > 0)) {
                        applyMeta(legacyMeta);
                        void saveMeta();
                    } else {
                        applyMeta(remoteMeta);
                    }
                } catch (error) {
                    if (!cancelled) {
                        setLoadError(error instanceof Error ? error.message : "Could not load your library.");
                    }
                } finally{
                    if (!cancelled) setLoading(false);
                }
            }
            void loadLibrary();
            return ({
                "LibraryApp.useEffect": ()=>{
                    cancelled = true;
                }
            })["LibraryApp.useEffect"];
        }
    }["LibraryApp.useEffect"], [
        applyMeta,
        notify,
        saveMeta,
        setTracks
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            if (!audioElement) return;
            const updatePlayback = {
                "LibraryApp.useEffect.updatePlayback": ()=>{
                    const nextDuration = Number.isFinite(audioElement.duration) ? audioElement.duration : 0;
                    setDuration({
                        "LibraryApp.useEffect.updatePlayback": (currentDuration)=>currentDuration === nextDuration ? currentDuration : nextDuration
                    }["LibraryApp.useEffect.updatePlayback"]);
                    const session = navigator.mediaSession;
                    if (session?.setPositionState && Number.isFinite(audioElement.duration) && audioElement.duration > 0 && Number.isFinite(audioElement.currentTime)) {
                        try {
                            session.setPositionState({
                                duration: audioElement.duration,
                                position: Math.max(0, Math.min(audioElement.currentTime, audioElement.duration)),
                                playbackRate: audioElement.playbackRate || 1
                            });
                        } catch  {
                        // Browsers may reject position updates before media metadata is ready.
                        }
                    }
                }
            }["LibraryApp.useEffect.updatePlayback"];
            const updatePlaybackPosition = {
                "LibraryApp.useEffect.updatePlaybackPosition": ()=>{
                    setCurrentTime(audioElement.currentTime || 0);
                    updatePlayback();
                }
            }["LibraryApp.useEffect.updatePlaybackPosition"];
            const onPlay = {
                "LibraryApp.useEffect.onPlay": ()=>{
                    setPlaying(true);
                    if (navigator.mediaSession) navigator.mediaSession.playbackState = "playing";
                }
            }["LibraryApp.useEffect.onPlay"];
            const onPause = {
                "LibraryApp.useEffect.onPause": ()=>{
                    updatePlaybackPosition();
                    setPlaying(false);
                    if (navigator.mediaSession) navigator.mediaSession.playbackState = "paused";
                }
            }["LibraryApp.useEffect.onPause"];
            const onEnded = {
                "LibraryApp.useEffect.onEnded": ()=>nextRef.current(true)
            }["LibraryApp.useEffect.onEnded"];
            const onError = {
                "LibraryApp.useEffect.onError": ()=>handleAudioError(audioElement)
            }["LibraryApp.useEffect.onError"];
            audioElement.addEventListener("timeupdate", updatePlayback);
            audioElement.addEventListener("loadedmetadata", updatePlaybackPosition);
            audioElement.addEventListener("durationchange", updatePlaybackPosition);
            audioElement.addEventListener("seeked", updatePlaybackPosition);
            audioElement.addEventListener("play", onPlay);
            audioElement.addEventListener("pause", onPause);
            audioElement.addEventListener("ended", onEnded);
            audioElement.addEventListener("error", onError);
            updatePlaybackPosition();
            return ({
                "LibraryApp.useEffect": ()=>{
                    audioElement.removeEventListener("timeupdate", updatePlayback);
                    audioElement.removeEventListener("loadedmetadata", updatePlaybackPosition);
                    audioElement.removeEventListener("durationchange", updatePlaybackPosition);
                    audioElement.removeEventListener("seeked", updatePlaybackPosition);
                    audioElement.removeEventListener("play", onPlay);
                    audioElement.removeEventListener("pause", onPause);
                    audioElement.removeEventListener("ended", onEnded);
                    audioElement.removeEventListener("error", onError);
                }
            })["LibraryApp.useEffect"];
        }
    }["LibraryApp.useEffect"], [
        audioElement,
        handleAudioError,
        setPlaying
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>{
            const audio = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement;
            if (!audio) return;
            audio.volume = volume;
            audio.muted = muted;
        }
    }["LibraryApp.useEffect"], [
        audioElement,
        muted,
        volume
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LibraryApp.useEffect": ()=>({
                "LibraryApp.useEffect": ()=>{
                    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
                    offlineObjectUrlsRef.current.forEach({
                        "LibraryApp.useEffect": (url)=>URL.revokeObjectURL(url)
                    }["LibraryApp.useEffect"]);
                    offlineObjectUrlsRef.current.clear();
                }
            })["LibraryApp.useEffect"]
    }["LibraryApp.useEffect"], []);
    function toggleFavoriteFor(track) {
        toggleFavorite(track.id);
        void saveMeta();
    }
    function createOrRenamePlaylist(event) {
        event.preventDefault();
        const name = playlistName.trim();
        if (!name) return;
        const state = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState();
        let nextPlaylists;
        if (playlistModal?.playlist) {
            nextPlaylists = state.playlists.map((playlist)=>playlist.id === playlistModal.playlist?.id ? {
                    ...playlist,
                    name
                } : playlist);
            notify(`Renamed playlist to “${name}”.`);
        } else {
            const playlist = {
                id: crypto.randomUUID().replaceAll("-", ""),
                name,
                trackIds: playlistModal?.trackId ? [
                    playlistModal.trackId
                ] : []
            };
            nextPlaylists = [
                ...state.playlists,
                playlist
            ];
            setView(`playlist:${playlist.id}`);
            notify(`Created “${name}”.`);
        }
        setPlaylists(nextPlaylists);
        setPlaylistModal(null);
        setPlaylistName("");
        void saveMeta();
    }
    function addTrackToPlaylist(playlistId, trackId) {
        const state = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState();
        const playlist = state.playlists.find((item)=>item.id === playlistId);
        if (!playlist || playlist.trackIds.includes(trackId)) return;
        setPlaylists(state.playlists.map((item)=>item.id === playlistId ? {
                ...item,
                trackIds: [
                    ...item.trackIds,
                    trackId
                ]
            } : item));
        void saveMeta();
    }
    async function toggleOfflineDownload(track) {
        if (!profile?.id) {
            notify("Your account is still loading. Try again shortly.");
            return;
        }
        setTrackMenu(null);
        setOfflinePendingId(track.id);
        try {
            if (track.offlineUrl) {
                await deleteOfflineTrack(profile.id, track.id);
                const state = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState();
                setTracks(state.tracks.map((item)=>item.id === track.id ? {
                        ...item,
                        offline: false,
                        offlineUrl: null,
                        coverUrl: item.remoteCoverUrl ?? item.coverUrl
                    } : item));
                notify(`Removed “${track.title}” from offline storage.`);
                return;
            }
            const audioResponse = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])(track.streamUrl, {
                cache: "no-store"
            }));
            const audio = await audioResponse.blob();
            if (!audio.size) throw new Error("The downloaded track was empty.");
            let cover = null;
            if (track.remoteCoverUrl?.startsWith("/api/tracks/")) {
                const coverResponse = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])(track.remoteCoverUrl, {
                    cache: "no-store"
                });
                if (coverResponse.ok) cover = await coverResponse.blob();
                else console.warn(`Could not save the cover for “${track.title}” offline.`);
            }
            await writeOfflineTrack({
                id: `${profile.id}:${track.id}`,
                accountId: profile.id,
                trackId: track.id,
                title: track.title,
                artist: track.artist,
                album: track.album,
                duration: track.duration,
                customLyrics: track.customLyrics ?? null,
                audio,
                cover,
                dateAdded: Date.now()
            });
            const offlineUrl = URL.createObjectURL(audio);
            offlineObjectUrlsRef.current.add(offlineUrl);
            let coverUrl;
            if (cover) {
                coverUrl = URL.createObjectURL(cover);
                offlineObjectUrlsRef.current.add(coverUrl);
            }
            const state = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState();
            setTracks(state.tracks.map((item)=>item.id === track.id ? {
                    ...item,
                    offline: true,
                    offlineUrl,
                    ...coverUrl ? {
                        coverUrl
                    } : {}
                } : item));
            notify(`Downloaded “${track.title}” for offline listening.`);
        } catch (error) {
            console.error("Could not save the offline track.", error);
            notify(error instanceof Error ? error.message : "Could not save this track offline.");
        } finally{
            setOfflinePendingId(null);
        }
    }
    async function removeTrack(track) {
        if (!window.confirm(`Remove “${track.title}” from your library? This deletes the file.`)) {
            return;
        }
        setTrackMenu(null);
        try {
            await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])(`/api/tracks/${encodeURIComponent(track.id)}`, {
                method: "DELETE"
            }, {
                csrf: true,
                retryCsrfOnForbidden: true
            }));
        } catch (error) {
            notify(error instanceof Error ? error.message : "Could not remove the track.");
            return;
        }
        const state = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState();
        const activeId = state.queue[state.queueIndex] ?? null;
        const nextTracks = state.tracks.filter((item)=>item.id !== track.id);
        const nextPlaylists = state.playlists.map((playlist)=>({
                ...playlist,
                trackIds: playlist.trackIds.filter((id)=>id !== track.id)
            }));
        const nextQueue = state.queue.filter((id)=>id !== track.id);
        setTracks(nextTracks);
        setPlaylists(nextPlaylists);
        if (activeId === track.id) {
            if (nextQueue.length) {
                const nextIndex = Math.min(state.queueIndex, nextQueue.length - 1);
                setQueue(nextQueue, nextIndex);
                startTrack(nextQueue[nextIndex]);
            } else {
                audioElement?.pause();
                if (audioElement) {
                    audioElement.removeAttribute("src");
                    audioElement.load();
                }
                setQueue([], -1);
                setPlaying(false);
            }
        } else {
            setQueue(nextQueue, activeId ? nextQueue.indexOf(activeId) : -1);
        }
        let offlineCleanupFailed = false;
        if (profile?.id) {
            try {
                await deleteOfflineTrack(profile.id, track.id);
            } catch (error) {
                offlineCleanupFailed = true;
                console.error("Could not remove the local offline copy.", error);
            }
        }
        void saveMeta();
        notify(offlineCleanupFailed ? `Removed “${track.title}” from your library, but its local offline copy could not be cleared.` : `Removed “${track.title}” from your library.`);
    }
    function removeTrackFromPlaylist(playlistId, track) {
        const state = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState();
        const playlist = state.playlists.find((item)=>item.id === playlistId);
        if (!playlist || !playlist.trackIds.includes(track.id)) return;
        setPlaylists(state.playlists.map((item)=>item.id === playlistId ? {
                ...item,
                trackIds: item.trackIds.filter((id)=>id !== track.id)
            } : item));
        setTrackMenu(null);
        void saveMeta();
        notify(`Removed “${track.title}” from “${playlist.name}”.`);
    }
    function openArtist(name) {
        setTrackMenu(null);
        setExpandedPlayerOpen(false);
        setLyricsOpen(false);
        setSearch("");
        setView(`artist:${encodeURIComponent(name)}`);
    }
    function openExpandedPlayer(trigger) {
        const activeElement = document.activeElement;
        expandedPlayerReturnFocusRef.current = trigger ?? (activeElement instanceof HTMLElement ? activeElement : null);
        setExpandedPlayerOpen(true);
    }
    async function shareTrack(track) {
        const text = `${track.title} — ${track.artist}`;
        if (navigator.share) {
            try {
                await navigator.share({
                    title: track.title,
                    text
                });
            } catch (error) {
                if (error instanceof DOMException && error.name === "AbortError") return;
                notify("Could not share this song.");
            }
            return;
        }
        try {
            await navigator.clipboard.writeText(`${text}\n${window.location.href}`);
            notify("Song details copied to clipboard.");
        } catch  {
            notify("Sharing is not available in this browser.");
        }
        setTrackMenu(null);
    }
    function addToQueue(track, playImmediatelyAfterCurrent = false) {
        const state = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState();
        const nextQueue = [
            ...state.queue
        ];
        if (playImmediatelyAfterCurrent) {
            const insertAt = state.queueIndex < 0 ? nextQueue.length : state.queueIndex + 1;
            nextQueue.splice(insertAt, 0, track.id);
            setQueue(nextQueue, state.queueIndex < 0 ? 0 : state.queueIndex);
            notify(`“${track.title}” will play next.`);
        } else {
            nextQueue.push(track.id);
            setQueue(nextQueue, state.queueIndex < 0 ? 0 : state.queueIndex);
            notify(`Added “${track.title}” to the queue.`);
        }
    }
    function seekTo(time) {
        const audio = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement;
        if (!audio || !duration) return;
        audio.currentTime = Math.max(0, Math.min(duration, time));
        setCurrentTime(audio.currentTime);
    }
    function updateVolume(event) {
        const rect = event.currentTarget.getBoundingClientRect();
        const nextVolume = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
        setPlayerVolume(nextVolume);
    }
    function setPlayerVolume(nextVolume) {
        const audio = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement;
        setVolume(nextVolume);
        setMuted(nextVolume === 0);
        if (audio) {
            audio.volume = nextVolume;
            audio.muted = nextVolume === 0;
        }
    }
    function toggleShuffle() {
        setShuffle(!shuffle);
        shufflePlayedRef.current.clear();
        notify(!shuffle ? "Shuffle on" : "Shuffle off");
    }
    function toggleRepeat() {
        const next = repeat === "off" ? "all" : repeat === "all" ? "one" : "off";
        setRepeat(next);
        notify(`Repeat: ${next}`);
    }
    function reorderQueue(fromIndex, targetIndex) {
        const state = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState();
        if (fromIndex < 0 || fromIndex >= state.queue.length || targetIndex < 0 || targetIndex >= state.queue.length || fromIndex === targetIndex) return;
        const nextQueue = [
            ...state.queue
        ];
        const [moved] = nextQueue.splice(fromIndex, 1);
        const insertAt = fromIndex < targetIndex ? targetIndex - 1 : targetIndex;
        nextQueue.splice(insertAt, 0, moved);
        let activeIndex = state.queueIndex;
        if (activeIndex === fromIndex) activeIndex = insertAt;
        else {
            if (fromIndex < activeIndex) activeIndex -= 1;
            if (insertAt <= activeIndex) activeIndex += 1;
        }
        setQueue(nextQueue, activeIndex);
    }
    function removeFromQueue(index) {
        const state = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState();
        const nextQueue = [
            ...state.queue
        ];
        nextQueue.splice(index, 1);
        let nextIndex = state.queueIndex;
        if (index < nextIndex) nextIndex -= 1;
        else if (index === nextIndex) {
            if (nextQueue.length === 0) {
                audioElement?.pause();
                nextIndex = -1;
            } else {
                nextIndex = Math.min(index, nextQueue.length - 1);
                startTrack(nextQueue[nextIndex]);
            }
        }
        setQueue(nextQueue, nextIndex);
    }
    const count = view === "playlists" ? filteredPlaylists.length : view === "artists" ? new Set(tracks.flatMap(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$artist$2d$explorer$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["artistNames"])).size : visibleTracks.length;
    const playlistCoverTracks = (playlist)=>playlist.trackIds.map((trackId)=>tracksById.get(trackId)).filter((track)=>Boolean(track)).slice(0, 4);
    const playlistViewCovers = playlistForView ? playlistCoverTracks(playlistForView) : [];
    const filteredQueueTracks = tracks.filter((track)=>`${track.title} ${track.artist}`.toLowerCase().includes(queueSearch.trim().toLowerCase()));
    const playlistTarget = playlists.find((playlist)=>playlist.id === playlistAddTarget);
    const tracksAvailableToAdd = playlistTarget ? tracks.filter((track)=>!playlistTarget.trackIds.includes(track.id)) : [];
    function toggleTrackMenu(track, event) {
        event.stopPropagation();
        const rect = event.currentTarget.getBoundingClientRect();
        const playlistId = view.startsWith("playlist:") ? view.slice("playlist:".length) : null;
        const inPlaylist = playlists.find((playlist)=>playlist.id === playlistId)?.trackIds.includes(track.id);
        const itemCount = 9 + (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$artist$2d$explorer$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["artistNames"])(track).length + (inPlaylist ? 1 : 0) + (expandedPlayerOpen && track.coverSource === "musicbrainz" ? 1 : 0);
        const menuHeight = Math.min(16 + itemCount * 38, window.innerHeight - 16);
        const top = Math.max(8, Math.min(rect.bottom + 6, window.innerHeight - menuHeight - 8));
        const left = Math.max(8, Math.min(rect.right - 204, window.innerWidth - 212));
        setTrackMenu((current)=>current?.trackId === track.id ? null : {
                trackId: track.id,
                top,
                left
            });
    }
    const renderTrack = (track, index, playList = visibleTracks)=>{
        const playing = activeTrackId === track.id;
        if (listMode === "grid") {
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("article", {
                className: `card${playing ? " playing" : ""}`,
                onClick: ()=>playFromList(playList, track.id),
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "card-art",
                        type: "button",
                        "aria-label": `Play ${track.title}`,
                        onClick: (event)=>{
                            event.stopPropagation();
                            playFromList(playList, track.id);
                        },
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(TrackImage, {
                                track: track
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2483,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                className: "card-play",
                                "aria-hidden": "true",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "play"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2484,
                                    columnNumber: 60
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2484,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2482,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "card-queue",
                        type: "button",
                        title: t("Add to queue"),
                        "aria-label": t("Add to queue"),
                        onClick: (event)=>{
                            event.stopPropagation();
                            addToQueue(track);
                        },
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                            name: "queue"
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 2496,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2486,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: `card-fav${track.favorite ? " on" : ""}`,
                        type: "button",
                        title: t(track.favorite ? "Remove favorite" : "Favorite"),
                        "aria-label": t(track.favorite ? "Remove favorite" : "Favorite"),
                        onClick: (event)=>{
                            event.stopPropagation();
                            toggleFavoriteFor(track);
                        },
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                            name: "heart"
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 2508,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2498,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "card-menu",
                        type: "button",
                        title: t("More options"),
                        "aria-label": `${t("More options for")} ${track.title}`,
                        "aria-haspopup": "menu",
                        "aria-expanded": trackMenu?.trackId === track.id,
                        "data-track-menu-trigger": true,
                        onClick: (event)=>{
                            event.stopPropagation();
                            toggleTrackMenu(track, event);
                        },
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                            name: "more"
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 2523,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2510,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "card-title",
                        children: track.title
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2525,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "card-sub",
                        children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$artist$2d$explorer$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["artistNames"])(track).map((name, artistIndex)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                                children: [
                                    artistIndex > 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        className: "artist-sep",
                                        children: ", "
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2529,
                                        columnNumber: 36
                                    }, this) : null,
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "artist-link",
                                        type: "button",
                                        onClick: (event)=>{
                                            event.stopPropagation();
                                            openArtist(name);
                                        },
                                        children: name
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2530,
                                        columnNumber: 17
                                    }, this)
                                ]
                            }, name, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2528,
                                columnNumber: 15
                            }, this))
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2526,
                        columnNumber: 11
                    }, this)
                ]
            }, `${track.id}-${index}`, true, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 2477,
                columnNumber: 9
            }, this);
        }
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: `row${playing ? " playing" : ""}`,
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "row-idx",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                            className: "num",
                            children: index + 1
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 2550,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                            className: "play-mini",
                            type: "button",
                            "aria-label": `Play ${track.title}`,
                            onClick: ()=>playFromList(playList, track.id),
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                name: "play"
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2552,
                                columnNumber: 13
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 2551,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                            className: "bars",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {}, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2554,
                                    columnNumber: 34
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {}, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2554,
                                    columnNumber: 42
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {}, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2554,
                                    columnNumber: 50
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 2554,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 2549,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "row-title-wrap",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(TrackImage, {
                            track: track,
                            className: "row-art"
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 2557,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                            className: "row-title-stack",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "row-title",
                                    type: "button",
                                    onClick: ()=>playFromList(playList, track.id),
                                    children: track.title
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2559,
                                    columnNumber: 13
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                    className: "row-meta",
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        className: "row-artist",
                                        children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$artist$2d$explorer$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["artistNames"])(track).map((name, artistIndex)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                                                children: [
                                                    artistIndex > 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                        className: "artist-sep",
                                                        children: ", "
                                                    }, void 0, false, {
                                                        fileName: "[project]/src/components/library-app.tsx",
                                                        lineNumber: 2563,
                                                        columnNumber: 38
                                                    }, this) : null,
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                        className: "artist-link",
                                                        type: "button",
                                                        onClick: ()=>openArtist(name),
                                                        children: name
                                                    }, void 0, false, {
                                                        fileName: "[project]/src/components/library-app.tsx",
                                                        lineNumber: 2564,
                                                        columnNumber: 19
                                                    }, this)
                                                ]
                                            }, name, true, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2562,
                                                columnNumber: 17
                                            }, this))
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2560,
                                        columnNumber: 40
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2560,
                                    columnNumber: 13
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 2558,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 2556,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "row-album-cell",
                    children: track.album
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 2572,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "row-time",
                    children: track.duration ? formatTime(track.duration) : "--:--"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 2573,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "row-actions",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                            type: "button",
                            title: t("Add to queue"),
                            "aria-label": t("Add to queue"),
                            onClick: (event)=>{
                                event.stopPropagation();
                                addToQueue(track);
                            },
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                name: "queue"
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2575,
                                columnNumber: 159
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 2575,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                            type: "button",
                            className: track.favorite ? "fav-on" : "",
                            title: t(track.favorite ? "Remove favorite" : "Favorite"),
                            "aria-label": t(track.favorite ? "Remove favorite" : "Favorite"),
                            "aria-pressed": track.favorite,
                            onClick: (event)=>{
                                event.stopPropagation();
                                toggleFavoriteFor(track);
                            },
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                name: "heart"
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2576,
                                columnNumber: 305
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 2576,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                            type: "button",
                            title: t("More options"),
                            "aria-label": `${t("More options for")} ${track.title}`,
                            "aria-haspopup": "menu",
                            "aria-expanded": trackMenu?.trackId === track.id,
                            "data-track-menu-trigger": true,
                            onClick: (event)=>toggleTrackMenu(track, event),
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                name: "more"
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2585,
                                columnNumber: 12
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 2577,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 2574,
                    columnNumber: 9
                }, this)
            ]
        }, `${track.id}-${index}`, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 2548,
            columnNumber: 7
        }, this);
    };
    const renderEmptyState = ()=>{
        if (search.trim()) {
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "empty",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "empty-orb"
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2595,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                        children: [
                            t("No matches for"),
                            " “",
                            search.trim(),
                            "”"
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2596,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        children: t("Try another title, artist, or album name.")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2597,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "btn",
                        type: "button",
                        onClick: ()=>setSearch(""),
                        children: t("Clear search")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2598,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 2594,
                columnNumber: 9
            }, this);
        }
        if (playlistForView) {
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "empty playlist-track-empty",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "empty-orb"
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2605,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                        children: t("This playlist is empty")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2606,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        children: tracks.length ? t("Add songs from your library to start building it.") : t("Add music to your library, then come back to build this playlist.")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2607,
                        columnNumber: 11
                    }, this),
                    tracks.length ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "btn btn-primary",
                        type: "button",
                        onClick: ()=>setPlaylistAddTarget(playlistForView.id),
                        children: t("Add from library")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2609,
                        columnNumber: 13
                    }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "btn btn-primary",
                        type: "button",
                        onClick: ()=>fileInputRef.current?.click(),
                        children: t("Add music")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2611,
                        columnNumber: 13
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 2604,
                columnNumber: 9
            }, this);
        }
        if (view === "offline") {
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "empty",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "empty-orb",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                            name: "offline"
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 2619,
                            columnNumber: 38
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2619,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                        children: t("No offline songs yet")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2620,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        children: t("Download songs from the library menu to listen without an internet connection.")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2621,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "btn btn-primary",
                        type: "button",
                        onClick: ()=>setView("library"),
                        children: t("Browse library")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2622,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 2618,
                columnNumber: 9
            }, this);
        }
        if (tracks.length === 0) {
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "empty",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "empty-orb"
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2629,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                        children: t("Your library is empty")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2630,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        children: t("Add songs or a folder. Vervfy saves them to your account so they are available on your other devices.")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2631,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        style: {
                            display: "flex",
                            gap: 10,
                            flexWrap: "wrap",
                            justifyContent: "center",
                            marginTop: 6
                        },
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "btn btn-primary",
                                type: "button",
                                onClick: ()=>fileInputRef.current?.click(),
                                children: t("Add music")
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2633,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "btn",
                                type: "button",
                                onClick: ()=>folderInputRef.current?.click(),
                                children: t("Add folder")
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2634,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2632,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 2628,
                columnNumber: 9
            }, this);
        }
        if (view === "favorites" && !tracks.some((track)=>track.favorite)) {
            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "empty",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "empty-orb"
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2642,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                        children: t("No favorites yet")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2643,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        children: t("Use the heart on any song to keep it close. Your favorites sync with your account.")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2644,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 2641,
                columnNumber: 9
            }, this);
        }
        return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
            className: "empty",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "empty-orb"
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 2650,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                    children: t("Nothing here yet")
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 2651,
                    columnNumber: 9
                }, this),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                    children: t("Your library will show up here when you add music.")
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 2652,
                    columnNumber: 9
                }, this)
            ]
        }, void 0, true, {
            fileName: "[project]/src/components/library-app.tsx",
            lineNumber: 2649,
            columnNumber: 7
        }, this);
    };
    const expandedPlayer = expandedPlayerOpen && currentTrack && typeof document !== "undefined" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createPortal"])(/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "mobile-player open",
        role: "dialog",
        "aria-modal": "true",
        "aria-label": t("Now playing"),
        onKeyDown: (event)=>{
            if (event.key === "Escape") {
                event.stopPropagation();
                setExpandedPlayerOpen(false);
            }
        },
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "mobile-player-bg",
                style: {
                    backgroundImage: `url("${currentTrack.coverUrl}")`
                },
                "aria-hidden": "true"
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 2671,
                columnNumber: 11
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("header", {
                className: "mobile-player-head",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "mobile-player-icon",
                        type: "button",
                        "aria-label": t("Close player"),
                        ref: expandedPlayerCloseRef,
                        onClick: ()=>setExpandedPlayerOpen(false),
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                            name: "close"
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 2684,
                            columnNumber: 15
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2677,
                        columnNumber: 13
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "mobile-player-context",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                children: t("PLAYING FROM")
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2687,
                                columnNumber: 15
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("strong", {
                                children: t(viewName(playingFromView ?? view, playlists))
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2688,
                                columnNumber: 15
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2686,
                        columnNumber: 13
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "mobile-player-icon",
                        type: "button",
                        "aria-label": `${t("More options for")} ${currentTrack.title}`,
                        "aria-haspopup": "menu",
                        "data-track-menu-trigger": true,
                        ref: mobilePlayerMenuButtonRef,
                        onClick: (event)=>toggleTrackMenu(currentTrack, event),
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                            name: "more"
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 2699,
                            columnNumber: 15
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2690,
                        columnNumber: 13
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 2676,
                columnNumber: 11
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("main", {
                className: "mobile-player-scroll",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "mobile-player-art",
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(TrackImage, {
                            track: currentTrack
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 2704,
                            columnNumber: 15
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2703,
                        columnNumber: 13
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                        className: "mobile-player-info",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "mobile-player-title-row",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                                                children: currentTrack.title
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2709,
                                                columnNumber: 19
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                                children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$artist$2d$explorer$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["artistNames"])(currentTrack).map((name, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                                                        children: [
                                                            index > 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                className: "artist-sep",
                                                                children: ", "
                                                            }, void 0, false, {
                                                                fileName: "[project]/src/components/library-app.tsx",
                                                                lineNumber: 2713,
                                                                columnNumber: 38
                                                            }, this) : null,
                                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                                className: "artist-link",
                                                                type: "button",
                                                                onClick: ()=>openArtist(name),
                                                                children: name
                                                            }, void 0, false, {
                                                                fileName: "[project]/src/components/library-app.tsx",
                                                                lineNumber: 2714,
                                                                columnNumber: 25
                                                            }, this)
                                                        ]
                                                    }, name, true, {
                                                        fileName: "[project]/src/components/library-app.tsx",
                                                        lineNumber: 2712,
                                                        columnNumber: 23
                                                    }, this))
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2710,
                                                columnNumber: 19
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2708,
                                        columnNumber: 17
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: `mobile-player-fav${currentTrack.favorite ? " on" : ""}`,
                                        type: "button",
                                        "aria-label": t(currentTrack.favorite ? "Remove favorite" : "Favorite"),
                                        "aria-pressed": currentTrack.favorite,
                                        onClick: ()=>toggleFavoriteFor(currentTrack),
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                            name: "heart"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2728,
                                            columnNumber: 19
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2721,
                                        columnNumber: 17
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2707,
                                columnNumber: 15
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(PlaybackSeek, {
                                audioElement: audioElement,
                                duration: duration,
                                onSeek: seekTo,
                                onResume: togglePlayback,
                                variant: "mobile"
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2731,
                                columnNumber: 15
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "mobile-transport",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: `mobile-control${shuffle ? " on" : ""}`,
                                        type: "button",
                                        "aria-label": t("Shuffle"),
                                        "aria-pressed": shuffle,
                                        onClick: toggleShuffle,
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                            name: "shuffle"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2745,
                                            columnNumber: 18
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2739,
                                        columnNumber: 17
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "mobile-control",
                                        type: "button",
                                        "aria-label": t("Previous track"),
                                        onClick: playPrevious,
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                            name: "prev"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2747,
                                            columnNumber: 19
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2746,
                                        columnNumber: 17
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "mobile-play",
                                        type: "button",
                                        "aria-label": t(isPlaying ? "Pause" : "Play"),
                                        onClick: togglePlayback,
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                            name: isPlaying ? "pause" : "play"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2750,
                                            columnNumber: 19
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2749,
                                        columnNumber: 17
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "mobile-control",
                                        type: "button",
                                        "aria-label": t("Next track"),
                                        onClick: ()=>playNext(false),
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                            name: "next"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2753,
                                            columnNumber: 19
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2752,
                                        columnNumber: 17
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: `mobile-control${repeat !== "off" ? " on" : ""}`,
                                        type: "button",
                                        "aria-label": t(`Repeat: ${repeat}`),
                                        "aria-pressed": repeat !== "off",
                                        onClick: toggleRepeat,
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                name: "repeat"
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2761,
                                                columnNumber: 18
                                            }, this),
                                            repeat === "one" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("small", {
                                                children: "1"
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2761,
                                                columnNumber: 60
                                            }, this) : null
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2755,
                                        columnNumber: 17
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2738,
                                columnNumber: 15
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "mobile-lyrics-preview",
                                type: "button",
                                "aria-label": t("Open full lyrics"),
                                onClick: ()=>{
                                    setExpandedPlayerOpen(false);
                                    setLyricsOpen(true);
                                },
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        className: "mobile-lyrics-heading",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                children: t("Lyrics")
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2773,
                                                columnNumber: 19
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                children: previewLines?.length ? t("Synced to playback") : previewLyrics?.text ? t("Plain lyrics") : t("Open full lyrics")
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2774,
                                                columnNumber: 19
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2772,
                                        columnNumber: 17
                                    }, this),
                                    previewLines?.length ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                        "aria-live": "polite",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                className: "lyric-active",
                                                children: previewLines[previewCurrentLineIndex]?.text
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2784,
                                                columnNumber: 21
                                            }, this),
                                            previewLines[previewNextLineIndex] ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                className: "lyric-next",
                                                children: previewLines[previewNextLineIndex].text
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2788,
                                                columnNumber: 23
                                            }, this) : null
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2783,
                                        columnNumber: 19
                                    }, this) : previewLyrics?.text ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                        children: previewLyrics.text.split(/\r?\n/).filter(Boolean).slice(0, 2).join("\n")
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2794,
                                        columnNumber: 19
                                    }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                        children: lyricsLookupFailedTrackId === currentTrack.id ? t("Couldn't load lyrics. Tap to retry.") : cachedLyrics?.source === "none" ? t("No lyrics found for this track.") : cachedLyrics?.source === "disabled" ? t("Paste your own lyrics.") : t("Finding lyrics…")
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2796,
                                        columnNumber: 19
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2763,
                                columnNumber: 15
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "mobile-secondary-actions",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "mobile-secondary",
                                        type: "button",
                                        onClick: ()=>{
                                            setExpandedPlayerOpen(false);
                                            setLyricsOpen(true);
                                        },
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                "aria-hidden": "true",
                                                children: "♫"
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2815,
                                                columnNumber: 18
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                children: t("Lyrics")
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2815,
                                                columnNumber: 51
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2808,
                                        columnNumber: 17
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "mobile-secondary",
                                        type: "button",
                                        "aria-pressed": queueOpen,
                                        onClick: ()=>{
                                            setExpandedPlayerOpen(false);
                                            setQueueOpen(true);
                                        },
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                name: "queue"
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2824,
                                                columnNumber: 18
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                children: t("Queue")
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2824,
                                                columnNumber: 39
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2816,
                                        columnNumber: 17
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2807,
                                columnNumber: 15
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2706,
                        columnNumber: 13
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 2702,
                columnNumber: 11
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/src/components/library-app.tsx",
        lineNumber: 2659,
        columnNumber: 9
    }, this), document.body) : null;
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        id: "app",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "shell",
                onDragEnter: (event)=>{
                    if (Array.from(event.dataTransfer.types).includes("Files")) setIsDraggingFiles(true);
                },
                onDragOver: (event)=>{
                    if (Array.from(event.dataTransfer.types).includes("Files")) event.preventDefault();
                },
                onDragLeave: (event)=>{
                    if (event.currentTarget === event.target) setIsDraggingFiles(false);
                },
                onDrop: (event)=>{
                    if (!Array.from(event.dataTransfer.types).includes("Files")) return;
                    event.preventDefault();
                    setIsDraggingFiles(false);
                    void uploadFiles(event.dataTransfer.files);
                },
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("nav", {
                        className: "rail",
                        "aria-label": t("Main navigation"),
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "logo-mark",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "logo-squircle",
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                            className: "brand-logo",
                                            src: "/gemini-svg.svg",
                                            alt: ""
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2849,
                                            columnNumber: 44
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2849,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "logo-word",
                                        children: "Vervfy"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2850,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2848,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: `rail-btn${view === "library" ? " active" : ""}`,
                                type: "button",
                                "data-view": "library",
                                "data-tip": t("Library"),
                                "aria-label": t("Library"),
                                "aria-current": view === "library" ? "page" : undefined,
                                onClick: ()=>setView("library"),
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "library"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2852,
                                    columnNumber: 254
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2852,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: `rail-btn${view === "offline" ? " active" : ""}`,
                                type: "button",
                                "data-view": "offline",
                                "data-tip": t("Offline"),
                                "aria-label": t("Offline"),
                                "aria-current": view === "offline" ? "page" : undefined,
                                onClick: ()=>setView("offline"),
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "offline"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2853,
                                    columnNumber: 254
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2853,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: `rail-btn${view === "playlists" || view.startsWith("playlist:") ? " active" : ""}`,
                                type: "button",
                                "data-view": "playlists",
                                "data-tip": t("Playlists"),
                                "aria-label": t("Playlists"),
                                "aria-current": view === "playlists" || view.startsWith("playlist:") ? "page" : undefined,
                                onClick: ()=>setView("playlists"),
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "playlists"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2854,
                                    columnNumber: 330
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2854,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: `rail-btn${view === "artists" || view.startsWith("artist:") ? " active" : ""}`,
                                type: "button",
                                "data-view": "artists",
                                "data-tip": t("Artists"),
                                "aria-label": t("Artists"),
                                "aria-current": view === "artists" || view.startsWith("artist:") ? "page" : undefined,
                                onClick: ()=>setView("artists"),
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "artist"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2855,
                                    columnNumber: 314
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2855,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: `rail-btn${view === "favorites" ? " active" : ""}`,
                                type: "button",
                                "data-view": "favorites",
                                "data-tip": t("Favorites"),
                                "aria-label": t("Favorites"),
                                "aria-current": view === "favorites" ? "page" : undefined,
                                onClick: ()=>setView("favorites"),
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "heart"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2856,
                                    columnNumber: 266
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2856,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: `rail-btn${view === "account" ? " active" : ""}`,
                                type: "button",
                                "data-view": "account",
                                "data-tip": t("Account"),
                                "aria-label": t("Account"),
                                "aria-current": view === "account" ? "page" : undefined,
                                onClick: ()=>setView("account"),
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "account"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2857,
                                    columnNumber: 254
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2857,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "rail-spacer"
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2858,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "rail-logout",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$auth$2f$logout$2d$button$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                    className: "rail-btn rail-logout-button",
                                    ariaLabel: "Log out",
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                        name: "logout"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2859,
                                        columnNumber: 114
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2859,
                                    columnNumber: 40
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2859,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "rail-btn rail-shortcuts-button",
                                type: "button",
                                "data-tip": t("Shortcuts (?)"),
                                "aria-label": t("Shortcuts"),
                                onClick: ()=>setShortcutsOpen(true),
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "help"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2860,
                                    columnNumber: 173
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2860,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "rail-btn rail-import-button",
                                type: "button",
                                "data-tip": t("Add music"),
                                "aria-label": t("Add music"),
                                onClick: ()=>fileInputRef.current?.click(),
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "import"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2861,
                                    columnNumber: 173
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2861,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2847,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "main",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "topbar",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "home-profile-avatar",
                                        type: "button",
                                        title: t("Account"),
                                        "aria-label": t("Open account"),
                                        onClick: ()=>setView("account"),
                                        children: profile?.photo_url ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                            src: profile.photo_url,
                                            alt: "",
                                            onError: ()=>setProfile((current)=>current ? {
                                                        ...current,
                                                        photo_url: null
                                                    } : null)
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2868,
                                            columnNumber: 19
                                        }, this) : profile?.username.slice(0, 1).toUpperCase() ?? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                            name: "account"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2869,
                                            columnNumber: 66
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2866,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "topbar-id",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                className: "view-title",
                                                children: title
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2872,
                                                columnNumber: 15
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                className: "view-count",
                                                children: tracks.length || view === "playlists" || view === "offline" || playlistForView ? `· ${count}` : ""
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2873,
                                                columnNumber: 15
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2871,
                                        columnNumber: 13
                                    }, this),
                                    view !== "account" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "view-toggle",
                                        role: "group",
                                        "aria-label": t("View mode"),
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                type: "button",
                                                className: listMode === "grid" ? "active" : "",
                                                "aria-pressed": listMode === "grid",
                                                title: t("Grid view"),
                                                "aria-label": t("Grid view"),
                                                onClick: ()=>setListMode("grid"),
                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                    name: "grid"
                                                }, void 0, false, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 2877,
                                                    columnNumber: 209
                                                }, this)
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2877,
                                                columnNumber: 17
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                type: "button",
                                                className: listMode === "list" ? "active" : "",
                                                "aria-pressed": listMode === "list",
                                                title: t("List view"),
                                                "aria-label": t("List view"),
                                                onClick: ()=>setListMode("list"),
                                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                    name: "list"
                                                }, void 0, false, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 2878,
                                                    columnNumber: 209
                                                }, this)
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2878,
                                                columnNumber: 17
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2876,
                                        columnNumber: 15
                                    }, this) : null,
                                    view !== "account" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                                        className: "search-wrap",
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                name: "search"
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2882,
                                                columnNumber: 15
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                                value: search,
                                                onChange: (event)=>setSearch(event.target.value),
                                                placeholder: t("Search"),
                                                autoComplete: "off",
                                                "aria-label": t(view === "playlists" ? "Search playlists" : "Search library")
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2883,
                                                columnNumber: 15
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                className: "kbd",
                                                children: "/"
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2884,
                                                columnNumber: 15
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2881,
                                        columnNumber: 35
                                    }, this) : null,
                                    view === "playlists" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "btn btn-primary",
                                        type: "button",
                                        onClick: ()=>{
                                            setPlaylistName("");
                                            setPlaylistModal({});
                                        },
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                name: "plus"
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2888,
                                                columnNumber: 17
                                            }, this),
                                            " ",
                                            t("New playlist")
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2887,
                                        columnNumber: 15
                                    }, this) : view === "account" || view === "artists" || view.startsWith("artist:") || playlistForView ? null : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "btn btn-primary",
                                        type: "button",
                                        onClick: ()=>fileInputRef.current?.click(),
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                name: "import"
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2892,
                                                columnNumber: 17
                                            }, this),
                                            " ",
                                            t("Add music")
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 2891,
                                        columnNumber: 15
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2865,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "content",
                                children: loading ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "library-skeleton",
                                    "aria-label": t("Loading library"),
                                    "aria-busy": "true",
                                    children: [
                                        0,
                                        1,
                                        2
                                    ].map((item)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "skeleton-row",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "skeleton-art"
                                                }, void 0, false, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 2900,
                                                    columnNumber: 83
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "skeleton-copy",
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("i", {}, void 0, false, {
                                                            fileName: "[project]/src/components/library-app.tsx",
                                                            lineNumber: 2900,
                                                            columnNumber: 148
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("i", {}, void 0, false, {
                                                            fileName: "[project]/src/components/library-app.tsx",
                                                            lineNumber: 2900,
                                                            columnNumber: 153
                                                        }, this)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 2900,
                                                    columnNumber: 116
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "skeleton-time"
                                                }, void 0, false, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 2900,
                                                    columnNumber: 165
                                                }, this)
                                            ]
                                        }, item, true, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2900,
                                            columnNumber: 42
                                        }, this))
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2899,
                                    columnNumber: 15
                                }, this) : loadError ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "empty",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "empty-orb"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2903,
                                            columnNumber: 38
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                            children: t("Music server unavailable")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2903,
                                            columnNumber: 67
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                            children: loadError
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2903,
                                            columnNumber: 107
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                            className: "btn btn-primary",
                                            type: "button",
                                            onClick: ()=>window.location.reload(),
                                            children: t("Retry connection")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2903,
                                            columnNumber: 125
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2903,
                                    columnNumber: 15
                                }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            hidden: view !== "account",
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$account$2d$settings$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                                active: view === "account",
                                                onToast: notify,
                                                onPhotoChange: updateProfilePhoto
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2907,
                                                columnNumber: 19
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2906,
                                            columnNumber: 17
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            hidden: view !== "artists" && !view.startsWith("artist:"),
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$artist$2d$explorer$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                                                view: view,
                                                search: search,
                                                listMode: listMode,
                                                renderTrack: renderTrack,
                                                onPlay: (list, trackId)=>{
                                                    const selectedTrack = trackId ?? list[0]?.id;
                                                    if (selectedTrack) playFromList(list, selectedTrack);
                                                }
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 2914,
                                                columnNumber: 19
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2913,
                                            columnNumber: 17
                                        }, this),
                                        view === "account" || view === "artists" || view.startsWith("artist:") ? null : view === "playlists" ? filteredPlaylists.length ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: `pl-grid${listMode === "list" ? " list-mode" : ""}`,
                                            children: filteredPlaylists.map((playlist)=>{
                                                const coverTracks = playlistCoverTracks(playlist);
                                                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                    className: "pl-card",
                                                    type: "button",
                                                    "aria-label": `Open playlist ${playlist.name}`,
                                                    onClick: ()=>setView(`playlist:${playlist.id}`),
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                            className: `playlist-cover${coverTracks.length === 1 ? " single" : ""}${coverTracks.length ? "" : " is-empty"}`,
                                                            "aria-hidden": "true",
                                                            children: [
                                                                coverTracks.length ? coverTracks.map((track)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(TrackImage, {
                                                                        track: track
                                                                    }, track.id, false, {
                                                                        fileName: "[project]/src/components/library-app.tsx",
                                                                        lineNumber: 2940,
                                                                        columnNumber: 58
                                                                    }, this)) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                                    name: "playlists"
                                                                }, void 0, false, {
                                                                    fileName: "[project]/src/components/library-app.tsx",
                                                                    lineNumber: 2941,
                                                                    columnNumber: 31
                                                                }, this),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                    className: "playlist-cover-play",
                                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                                        name: "play"
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/src/components/library-app.tsx",
                                                                        lineNumber: 2942,
                                                                        columnNumber: 65
                                                                    }, this)
                                                                }, void 0, false, {
                                                                    fileName: "[project]/src/components/library-app.tsx",
                                                                    lineNumber: 2942,
                                                                    columnNumber: 27
                                                                }, this)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/src/components/library-app.tsx",
                                                            lineNumber: 2938,
                                                            columnNumber: 25
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                            className: "pl-card-info",
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                    className: "pl-name",
                                                                    children: playlist.name
                                                                }, void 0, false, {
                                                                    fileName: "[project]/src/components/library-app.tsx",
                                                                    lineNumber: 2945,
                                                                    columnNumber: 27
                                                                }, this),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                    className: "pl-count",
                                                                    children: [
                                                                        playlist.trackIds.length,
                                                                        " ",
                                                                        playlist.trackIds.length === 1 ? "song" : "songs"
                                                                    ]
                                                                }, void 0, true, {
                                                                    fileName: "[project]/src/components/library-app.tsx",
                                                                    lineNumber: 2946,
                                                                    columnNumber: 27
                                                                }, this)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/src/components/library-app.tsx",
                                                            lineNumber: 2944,
                                                            columnNumber: 25
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                            className: "pl-card-arrow",
                                                            "aria-hidden": "true",
                                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                                name: "next"
                                                            }, void 0, false, {
                                                                fileName: "[project]/src/components/library-app.tsx",
                                                                lineNumber: 2948,
                                                                columnNumber: 76
                                                            }, this)
                                                        }, void 0, false, {
                                                            fileName: "[project]/src/components/library-app.tsx",
                                                            lineNumber: 2948,
                                                            columnNumber: 25
                                                        }, this)
                                                    ]
                                                }, playlist.id, true, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 2931,
                                                    columnNumber: 23
                                                }, this);
                                            })
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2927,
                                            columnNumber: 17
                                        }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "empty playlist-list-empty",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "empty-orb",
                                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                        name: search.trim() ? "search" : "playlists"
                                                    }, void 0, false, {
                                                        fileName: "[project]/src/components/library-app.tsx",
                                                        lineNumber: 2955,
                                                        columnNumber: 46
                                                    }, this)
                                                }, void 0, false, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 2955,
                                                    columnNumber: 19
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                                    children: search.trim() ? t("No playlists found") : t("Your playlists start here")
                                                }, void 0, false, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 2956,
                                                    columnNumber: 19
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                                    children: search.trim() ? t("Try a different name or clear your search.") : t("Collect songs into playlists for every mood and moment.")
                                                }, void 0, false, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 2957,
                                                    columnNumber: 19
                                                }, this),
                                                search.trim() ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                    className: "btn",
                                                    type: "button",
                                                    onClick: ()=>setSearch(""),
                                                    children: t("Clear search")
                                                }, void 0, false, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 2959,
                                                    columnNumber: 23
                                                }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                    className: "btn btn-primary",
                                                    type: "button",
                                                    onClick: ()=>{
                                                        setPlaylistName("");
                                                        setPlaylistModal({});
                                                    },
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                            name: "plus"
                                                        }, void 0, false, {
                                                            fileName: "[project]/src/components/library-app.tsx",
                                                            lineNumber: 2960,
                                                            columnNumber: 136
                                                        }, this),
                                                        " ",
                                                        t("Create playlist")
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 2960,
                                                    columnNumber: 23
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2954,
                                            columnNumber: 17
                                        }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                                            children: [
                                                playlistForView ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                    className: "playlist-detail",
                                                    children: [
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                            className: "playlist-back",
                                                            type: "button",
                                                            onClick: ()=>setView("playlists"),
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                                    name: "prev"
                                                                }, void 0, false, {
                                                                    fileName: "[project]/src/components/library-app.tsx",
                                                                    lineNumber: 2967,
                                                                    columnNumber: 106
                                                                }, this),
                                                                " ",
                                                                t("All playlists")
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/src/components/library-app.tsx",
                                                            lineNumber: 2967,
                                                            columnNumber: 21
                                                        }, this),
                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                                                            className: "playlist-hero",
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: `playlist-hero-cover${playlistViewCovers.length === 1 ? " single" : ""}${playlistViewCovers.length ? "" : " is-empty"}`,
                                                                    "aria-hidden": "true",
                                                                    children: playlistViewCovers.length ? playlistViewCovers.map((track)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(TrackImage, {
                                                                            track: track
                                                                        }, track.id, false, {
                                                                            fileName: "[project]/src/components/library-app.tsx",
                                                                            lineNumber: 2971,
                                                                            columnNumber: 63
                                                                        }, this)) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                                        name: "playlists"
                                                                    }, void 0, false, {
                                                                        fileName: "[project]/src/components/library-app.tsx",
                                                                        lineNumber: 2972,
                                                                        columnNumber: 29
                                                                    }, this)
                                                                }, void 0, false, {
                                                                    fileName: "[project]/src/components/library-app.tsx",
                                                                    lineNumber: 2969,
                                                                    columnNumber: 23
                                                                }, this),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "playlist-hero-copy",
                                                                    children: [
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                            className: "playlist-eyebrow",
                                                                            children: t("PLAYLIST")
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/src/components/library-app.tsx",
                                                                            lineNumber: 2975,
                                                                            columnNumber: 25
                                                                        }, this),
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h1", {
                                                                            children: playlistForView.name
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/src/components/library-app.tsx",
                                                                            lineNumber: 2976,
                                                                            columnNumber: 25
                                                                        }, this),
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                                                            children: [
                                                                                playlistForView.trackIds.length,
                                                                                " ",
                                                                                t(playlistForView.trackIds.length === 1 ? "song" : "songs"),
                                                                                " ",
                                                                                t("in this collection")
                                                                            ]
                                                                        }, void 0, true, {
                                                                            fileName: "[project]/src/components/library-app.tsx",
                                                                            lineNumber: 2977,
                                                                            columnNumber: 25
                                                                        }, this),
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                            className: "playlist-actions",
                                                                            children: [
                                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                                                    className: "btn btn-primary",
                                                                                    type: "button",
                                                                                    disabled: !visibleTracks.length,
                                                                                    onClick: ()=>{
                                                                                        const firstTrack = visibleTracks[0];
                                                                                        if (firstTrack) playFromList(visibleTracks, firstTrack.id);
                                                                                    },
                                                                                    children: [
                                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                                                            name: "play"
                                                                                        }, void 0, false, {
                                                                                            fileName: "[project]/src/components/library-app.tsx",
                                                                                            lineNumber: 2982,
                                                                                            columnNumber: 30
                                                                                        }, this),
                                                                                        " ",
                                                                                        t("Play")
                                                                                    ]
                                                                                }, void 0, true, {
                                                                                    fileName: "[project]/src/components/library-app.tsx",
                                                                                    lineNumber: 2979,
                                                                                    columnNumber: 27
                                                                                }, this),
                                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                                                    className: "btn",
                                                                                    type: "button",
                                                                                    onClick: ()=>setPlaylistAddTarget(playlistForView.id),
                                                                                    children: [
                                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                                                            name: "plus"
                                                                                        }, void 0, false, {
                                                                                            fileName: "[project]/src/components/library-app.tsx",
                                                                                            lineNumber: 2983,
                                                                                            columnNumber: 122
                                                                                        }, this),
                                                                                        " ",
                                                                                        t("Add songs")
                                                                                    ]
                                                                                }, void 0, true, {
                                                                                    fileName: "[project]/src/components/library-app.tsx",
                                                                                    lineNumber: 2983,
                                                                                    columnNumber: 27
                                                                                }, this),
                                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                                                    className: "btn",
                                                                                    type: "button",
                                                                                    onClick: ()=>{
                                                                                        setPlaylistName(playlistForView.name);
                                                                                        setPlaylistModal({
                                                                                            playlist: playlistForView
                                                                                        });
                                                                                    },
                                                                                    children: t("Rename")
                                                                                }, void 0, false, {
                                                                                    fileName: "[project]/src/components/library-app.tsx",
                                                                                    lineNumber: 2984,
                                                                                    columnNumber: 27
                                                                                }, this),
                                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                                                    className: "btn btn-danger",
                                                                                    type: "button",
                                                                                    onClick: ()=>{
                                                                                        if (!window.confirm(`Delete “${playlistForView.name}”?`)) return;
                                                                                        setPlaylists(playlists.filter((item)=>item.id !== playlistForView.id));
                                                                                        setView("playlists");
                                                                                        void saveMeta();
                                                                                    },
                                                                                    children: t("Delete")
                                                                                }, void 0, false, {
                                                                                    fileName: "[project]/src/components/library-app.tsx",
                                                                                    lineNumber: 2985,
                                                                                    columnNumber: 27
                                                                                }, this)
                                                                            ]
                                                                        }, void 0, true, {
                                                                            fileName: "[project]/src/components/library-app.tsx",
                                                                            lineNumber: 2978,
                                                                            columnNumber: 25
                                                                        }, this)
                                                                    ]
                                                                }, void 0, true, {
                                                                    fileName: "[project]/src/components/library-app.tsx",
                                                                    lineNumber: 2974,
                                                                    columnNumber: 23
                                                                }, this)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/src/components/library-app.tsx",
                                                            lineNumber: 2968,
                                                            columnNumber: 21
                                                        }, this)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 2966,
                                                    columnNumber: 19
                                                }, this) : null,
                                                visibleTracks.length ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                                                    children: [
                                                        playlistForView ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "playlist-track-heading",
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                                                                    children: t("Songs")
                                                                }, void 0, false, {
                                                                    fileName: "[project]/src/components/library-app.tsx",
                                                                    lineNumber: 3000,
                                                                    columnNumber: 25
                                                                }, this),
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                                    children: [
                                                                        visibleTracks.length,
                                                                        " ",
                                                                        t(visibleTracks.length === 1 ? "song" : "songs")
                                                                    ]
                                                                }, void 0, true, {
                                                                    fileName: "[project]/src/components/library-app.tsx",
                                                                    lineNumber: 3001,
                                                                    columnNumber: 25
                                                                }, this)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/src/components/library-app.tsx",
                                                            lineNumber: 2999,
                                                            columnNumber: 23
                                                        }, this) : null,
                                                        listMode === "grid" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "grid",
                                                            children: visibleTracks.map(renderTrack)
                                                        }, void 0, false, {
                                                            fileName: "[project]/src/components/library-app.tsx",
                                                            lineNumber: 3005,
                                                            columnNumber: 23
                                                        }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                            className: "list",
                                                            children: [
                                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                    className: "list-head",
                                                                    children: [
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {}, void 0, false, {
                                                                            fileName: "[project]/src/components/library-app.tsx",
                                                                            lineNumber: 3008,
                                                                            columnNumber: 52
                                                                        }, this),
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                            children: t("Title")
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/src/components/library-app.tsx",
                                                                            lineNumber: 3008,
                                                                            columnNumber: 59
                                                                        }, this),
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                            children: t("Album")
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/src/components/library-app.tsx",
                                                                            lineNumber: 3008,
                                                                            columnNumber: 82
                                                                        }, this),
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                                                            children: t("Time")
                                                                        }, void 0, false, {
                                                                            fileName: "[project]/src/components/library-app.tsx",
                                                                            lineNumber: 3008,
                                                                            columnNumber: 105
                                                                        }, this),
                                                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {}, void 0, false, {
                                                                            fileName: "[project]/src/components/library-app.tsx",
                                                                            lineNumber: 3008,
                                                                            columnNumber: 127
                                                                        }, this)
                                                                    ]
                                                                }, void 0, true, {
                                                                    fileName: "[project]/src/components/library-app.tsx",
                                                                    lineNumber: 3008,
                                                                    columnNumber: 25
                                                                }, this),
                                                                visibleTracks.map(renderTrack)
                                                            ]
                                                        }, void 0, true, {
                                                            fileName: "[project]/src/components/library-app.tsx",
                                                            lineNumber: 3007,
                                                            columnNumber: 23
                                                        }, this)
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 2997,
                                                    columnNumber: 19
                                                }, this) : renderEmptyState()
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 2964,
                                            columnNumber: 15
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 2905,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 2897,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 2864,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 2835,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                id: "nowbar",
                className: `nowbar${currentTrack ? "" : " hidden"}${lyricsOpen ? " lyrics-open" : ""}`,
                role: "region",
                "aria-label": t("Now playing"),
                "aria-hidden": !currentTrack || lyricsOpen || expandedPlayerOpen,
                inert: !currentTrack || lyricsOpen || expandedPlayerOpen,
                onClick: (event)=>{
                    if (event.target instanceof Element && event.target.closest("button, .seek")) return;
                    if (window.matchMedia("(max-width: 900px)").matches) {
                        setExpandedPlayerOpen(true);
                    }
                },
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "now-track",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                className: "now-art-wrap",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                    className: "now-art",
                                    children: currentTrack ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(TrackImage, {
                                        track: currentTrack
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3031,
                                        columnNumber: 84
                                    }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                        src: FALLBACK_ART,
                                        alt: ""
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3031,
                                        columnNumber: 122
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3031,
                                    columnNumber: 42
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3031,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                className: "now-meta",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "now-track-open",
                                        type: "button",
                                        "aria-label": currentTrack ? `Open player for ${currentTrack.title}` : "Open player",
                                        onClick: (event)=>{
                                            if (window.matchMedia("(max-width: 900px)").matches) {
                                                openExpandedPlayer(event.currentTarget);
                                            }
                                        },
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            className: "now-title",
                                            children: currentTrack?.title ?? "—"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3043,
                                            columnNumber: 15
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3033,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        className: "now-artist",
                                        children: currentTrack ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$artist$2d$explorer$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["artistNames"])(currentTrack).map((name, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                                                children: [
                                                    index > 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                        className: "artist-sep",
                                                        children: ", "
                                                    }, void 0, false, {
                                                        fileName: "[project]/src/components/library-app.tsx",
                                                        lineNumber: 3049,
                                                        columnNumber: 36
                                                    }, this) : null,
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                        className: "artist-link",
                                                        type: "button",
                                                        onClick: ()=>openArtist(name),
                                                        children: name
                                                    }, void 0, false, {
                                                        fileName: "[project]/src/components/library-app.tsx",
                                                        lineNumber: 3050,
                                                        columnNumber: 23
                                                    }, this)
                                                ]
                                            }, name, true, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 3048,
                                                columnNumber: 21
                                            }, this)) : "—"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3045,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3032,
                                columnNumber: 11
                            }, this),
                            currentTrack ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: `now-fav${currentTrack.favorite ? " on" : ""}`,
                                type: "button",
                                "aria-label": t(currentTrack.favorite ? "Remove favorite" : "Favorite"),
                                "aria-pressed": currentTrack.favorite,
                                onClick: ()=>toggleFavoriteFor(currentTrack),
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "heart"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3058,
                                    columnNumber: 264
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3058,
                                columnNumber: 27
                            }, this) : null
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 3030,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "transport",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "transport-btns",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: `tbtn${shuffle ? " on" : ""}`,
                                        type: "button",
                                        title: t("Shuffle"),
                                        "aria-label": t("Shuffle"),
                                        "aria-pressed": shuffle,
                                        onClick: toggleShuffle,
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                            name: "shuffle"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3062,
                                            columnNumber: 171
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3062,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "tbtn",
                                        type: "button",
                                        title: t("Previous track"),
                                        "aria-label": t("Previous track"),
                                        onClick: playPrevious,
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                            name: "prev"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3063,
                                            columnNumber: 136
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3063,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "tbtn tbtn-play",
                                        type: "button",
                                        title: t("Play or pause"),
                                        "aria-label": t(isPlaying ? "Pause" : "Play"),
                                        onClick: togglePlayback,
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                            name: isPlaying ? "pause" : "play"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3064,
                                            columnNumber: 159
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3064,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "tbtn",
                                        type: "button",
                                        title: t("Next track"),
                                        "aria-label": t("Next track"),
                                        onClick: ()=>playNext(false),
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                            name: "next"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3065,
                                            columnNumber: 137
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3065,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: `tbtn${repeat !== "off" ? " on" : ""}`,
                                        type: "button",
                                        title: t(`Repeat: ${repeat}`),
                                        "aria-label": t(`Repeat: ${repeat}`),
                                        "aria-pressed": repeat !== "off",
                                        onClick: toggleRepeat,
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                name: "repeat"
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 3066,
                                                columnNumber: 208
                                            }, this),
                                            repeat === "one" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("small", {
                                                children: "1"
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 3066,
                                                columnNumber: 250
                                            }, this) : null
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3066,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3061,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(PlaybackSeek, {
                                audioElement: audioElement,
                                duration: duration,
                                onSeek: seekTo,
                                onResume: togglePlayback,
                                variant: "player"
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3068,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 3060,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "now-extra",
                        children: [
                            currentTrack?.coverSource === "musicbrainz" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                ref: coverInfoButtonRef,
                                className: `icon-btn player-control-cover-info${coverInfoOpen ? " on" : ""}`,
                                type: "button",
                                title: t("Cover art info"),
                                "aria-label": t("Cover art info"),
                                "aria-haspopup": "dialog",
                                "aria-expanded": coverInfoOpen,
                                "aria-controls": "cover-art-info",
                                onClick: (event)=>{
                                    coverInfoReturnFocusRef.current = event.currentTarget;
                                    setCoverInfoTrackId(coverInfoOpen ? null : currentTrack?.id ?? null);
                                },
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "info"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3092,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3078,
                                columnNumber: 13
                            }, this) : null,
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: `icon-btn player-control-lyrics${lyricsOpen ? " on" : ""}`,
                                type: "button",
                                title: t("Lyrics (L)"),
                                "aria-label": t("Lyrics"),
                                "aria-pressed": lyricsOpen,
                                onClick: ()=>setLyricsOpen(true),
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "lyrics"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3095,
                                    columnNumber: 215
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3095,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: `icon-btn player-control-visualizer${visualizerOpen ? " on" : ""}`,
                                type: "button",
                                title: t("Visualizer (V)"),
                                "aria-label": t("Visualizer"),
                                "aria-pressed": visualizerOpen,
                                onClick: ()=>setVisualizerOpen(true),
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "visualizer"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3096,
                                    columnNumber: 239
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3096,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: `icon-btn player-control-queue${queueOpen ? " on" : ""}`,
                                type: "button",
                                title: t("Queue"),
                                "aria-label": t("Queue"),
                                "aria-pressed": queueOpen,
                                onClick: ()=>setQueueOpen(!queueOpen),
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "queue"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3097,
                                    columnNumber: 211
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3097,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: `icon-btn player-control-offline${currentTrack?.offlineUrl ? " on" : ""}`,
                                type: "button",
                                title: t(currentTrack?.offlineUrl ? "Remove offline download" : "Download for offline listening"),
                                "aria-label": t(currentTrack?.offlineUrl ? "Remove offline download" : "Download for offline listening"),
                                "aria-pressed": Boolean(currentTrack?.offlineUrl),
                                "aria-busy": offlinePendingId === currentTrack?.id,
                                disabled: !currentTrack || offlinePendingId !== null,
                                onClick: ()=>{
                                    if (currentTrack) void toggleOfflineDownload(currentTrack);
                                },
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "offline"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3110,
                                    columnNumber: 13
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3098,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: `icon-btn player-control-mute${muted ? " on" : ""}`,
                                type: "button",
                                title: muted ? "Unmute" : "Mute",
                                "aria-label": muted ? "Unmute" : "Mute",
                                "aria-pressed": muted,
                                onClick: ()=>{
                                    const audio = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement;
                                    if (!audio) return;
                                    const nextMuted = !muted;
                                    setMuted(nextMuted);
                                    audio.muted = nextMuted;
                                },
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: muted || volume === 0 ? "volume-muted" : "volume"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3118,
                                    columnNumber: 14
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3112,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "vol-wrap",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "vol-track",
                                    role: "slider",
                                    tabIndex: 0,
                                    "aria-label": t("Volume"),
                                    "aria-valuemin": 0,
                                    "aria-valuemax": 100,
                                    "aria-valuenow": Math.round((muted ? 0 : volume) * 100),
                                    "aria-valuetext": `${Math.round((muted ? 0 : volume) * 100)}%`,
                                    onClick: updateVolume,
                                    onKeyDown: (event)=>{
                                        if (event.key !== "ArrowRight" && event.key !== "ArrowUp" && event.key !== "ArrowLeft" && event.key !== "ArrowDown") return;
                                        event.preventDefault();
                                        const direction = event.key === "ArrowRight" || event.key === "ArrowUp" ? 1 : -1;
                                        setVolume((current)=>Math.max(0, Math.min(1, current + direction * 0.05)));
                                        setMuted(false);
                                    },
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "vol-fill",
                                        style: {
                                            width: `${(muted ? 0 : volume) * 100}%`
                                        }
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3125,
                                        columnNumber: 14
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3119,
                                    columnNumber: 37
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3119,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 3076,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3022,
                columnNumber: 7
            }, this),
            coverInfoOpen && currentTrack?.coverSource === "musicbrainz" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createPortal"])(/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                id: "cover-art-info",
                ref: coverInfoPopoverRef,
                className: "cover-info-popover",
                role: "dialog",
                tabIndex: -1,
                "aria-label": t("Cover art information"),
                onClick: (event)=>event.stopPropagation(),
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "cover-info-heading",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                className: "cover-info-icon",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "info"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3141,
                                    columnNumber: 47
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3141,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                        children: t("NOW PLAYING")
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3143,
                                        columnNumber: 15
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h2", {
                                        children: t("Cover art source")
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3144,
                                        columnNumber: 15
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3142,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "icon-btn",
                                type: "button",
                                "aria-label": t("Close cover art information"),
                                onClick: ()=>{
                                    setCoverInfoTrackId(null);
                                    const returnFocusTarget = coverInfoReturnFocusRef.current ?? coverInfoButtonRef.current;
                                    returnFocusTarget?.focus();
                                    coverInfoReturnFocusRef.current = null;
                                },
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "close"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3157,
                                    columnNumber: 15
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3146,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 3140,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        className: "cover-info-copy",
                        children: t("This cover is provided through MusicBrainz and the Cover Art Archive.")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 3160,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        className: "cover-info-note",
                        children: t("Vervfy links to the image instead of storing a copy.")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 3163,
                        columnNumber: 11
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "cover-info-links",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("a", {
                                href: "https://musicbrainz.org/",
                                target: "_blank",
                                rel: "noopener noreferrer",
                                children: [
                                    "MusicBrainz ",
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        "aria-hidden": "true",
                                        children: "↗"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3168,
                                        columnNumber: 27
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3167,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("a", {
                                href: "https://coverartarchive.org/",
                                target: "_blank",
                                rel: "noopener noreferrer",
                                children: [
                                    "Cover Art Archive ",
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        "aria-hidden": "true",
                                        children: "↗"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3171,
                                        columnNumber: 33
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3170,
                                columnNumber: 13
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("a", {
                                href: "/credits",
                                children: [
                                    t("View all credits"),
                                    " ",
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        "aria-hidden": "true",
                                        children: "→"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3173,
                                        columnNumber: 56
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3173,
                                columnNumber: 13
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 3166,
                        columnNumber: 11
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3131,
                columnNumber: 11
            }, this), document.body) : null,
            expandedPlayer,
            trackMenu && trackMenuTrack ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(TrackMenuPortal, {
                track: trackMenuTrack,
                position: {
                    top: trackMenu.top,
                    left: trackMenu.left
                },
                view: view,
                playlists: playlists,
                offlinePendingId: offlinePendingId,
                expandedPlayerOpen: expandedPlayerOpen,
                onPlayNext: ()=>{
                    addToQueue(trackMenuTrack, true);
                    setTrackMenu(null);
                },
                onAddToQueue: ()=>{
                    addToQueue(trackMenuTrack);
                    setTrackMenu(null);
                },
                onAddToPlaylist: ()=>{
                    setExpandedPlayerOpen(false);
                    setPlaylistPicker(trackMenuTrack.id);
                    setTrackMenu(null);
                },
                onToggleOffline: ()=>void toggleOfflineDownload(trackMenuTrack),
                onToggleFavorite: ()=>{
                    toggleFavoriteFor(trackMenuTrack);
                    setTrackMenu(null);
                },
                onViewArtist: openArtist,
                onShare: ()=>{
                    setTrackMenu(null);
                    void shareTrack(trackMenuTrack);
                },
                onRemoveFromPlaylist: view.startsWith("playlist:") ? ()=>removeTrackFromPlaylist(view.slice("playlist:".length), trackMenuTrack) : undefined,
                onAddOrChangeCover: ()=>openCoverEditor(trackMenuTrack),
                onRetryCover: ()=>void retryCoverLookup(trackMenuTrack),
                onCoverInfo: ()=>{
                    coverInfoReturnFocusRef.current = mobilePlayerMenuButtonRef.current;
                    setCoverInfoTrackId(trackMenuTrack.id);
                    setTrackMenu(null);
                },
                onEditDetails: ()=>openMetadataEditor(trackMenuTrack),
                onRemove: ()=>{
                    setExpandedPlayerOpen(false);
                    void removeTrack(trackMenuTrack);
                }
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3182,
                columnNumber: 9
            }, this) : null,
            lyricsOpen && currentTrack ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$lyrics$2d$overlay$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                track: currentTrack,
                currentTime: currentTime,
                onClose: ()=>setLyricsOpen(false),
                onOpenArtist: openArtist,
                onToast: notify,
                onPrevious: playPrevious,
                onNext: ()=>playNext(false),
                onTogglePlayback: togglePlayback,
                onToggleShuffle: toggleShuffle,
                onToggleRepeat: toggleRepeat,
                shuffle: shuffle,
                repeat: repeat
            }, currentTrack.id, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3232,
                columnNumber: 9
            }, this) : null,
            visualizerOpen ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$visualizer$2d$overlay$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"], {
                onClose: ()=>setVisualizerOpen(false)
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3248,
                columnNumber: 25
            }, this) : null,
            shortcutsOpen ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "queue-picker-overlay open",
                role: "dialog",
                "aria-modal": "true",
                "aria-label": t("Keyboard shortcuts"),
                onClick: ()=>setShortcutsOpen(false),
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                    className: "queue-picker-card shortcuts-dialog",
                    onClick: (event)=>event.stopPropagation(),
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "queue-picker-head",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                    children: t("Keyboard shortcuts")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3251,
                                    columnNumber: 46
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "icon-btn",
                                    type: "button",
                                    "aria-label": t("Close shortcuts"),
                                    onClick: ()=>setShortcutsOpen(false),
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                        name: "close"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3251,
                                        columnNumber: 197
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3251,
                                    columnNumber: 80
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3251,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "queue-picker-list",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("kbd", {
                                            children: t("Space")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 49
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            children: t("Play / pause")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 72
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3252,
                                    columnNumber: 46
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("kbd", {
                                            children: "Shift + ← / →"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 111
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            children: t("Previous / next track")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 135
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3252,
                                    columnNumber: 108
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("kbd", {
                                            children: "← / →"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 183
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            children: t("Seek 5 seconds")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 199
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3252,
                                    columnNumber: 180
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("kbd", {
                                            children: "↑ / ↓"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 240
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            children: t("Volume")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 256
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3252,
                                    columnNumber: 237
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("kbd", {
                                            children: "M"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 289
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            children: t("Mute")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 301
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3252,
                                    columnNumber: 286
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("kbd", {
                                            children: "F"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 332
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            children: t("Favorite current track")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 344
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3252,
                                    columnNumber: 329
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("kbd", {
                                            children: "L"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 393
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            children: t("Lyrics")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 405
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3252,
                                    columnNumber: 390
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("kbd", {
                                            children: "V"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 438
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            children: t("Visualizer")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 450
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3252,
                                    columnNumber: 435
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("kbd", {
                                            children: "/"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 487
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            children: t("Search")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 499
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3252,
                                    columnNumber: 484
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("kbd", {
                                            children: "?"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 532
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            children: t("Shortcuts")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 544
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3252,
                                    columnNumber: 529
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("kbd", {
                                            children: "Esc"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 580
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            children: t("Close panels")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3252,
                                            columnNumber: 594
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3252,
                                    columnNumber: 577
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3252,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 3250,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3249,
                columnNumber: 24
            }, this) : null,
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("aside", {
                ref: queuePanelRef,
                className: `side-panel${queueOpen ? " open" : ""}`,
                "aria-label": t("Up next"),
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "side-head",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                children: t("Up next")
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3257,
                                columnNumber: 36
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "side-head-actions",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "icon-btn",
                                        type: "button",
                                        title: t("Add from library"),
                                        onClick: ()=>setQueuePickerOpen(true),
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                            name: "plus"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3257,
                                            columnNumber: 208
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3257,
                                        columnNumber: 94
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "icon-btn",
                                        type: "button",
                                        title: t("Close queue"),
                                        onClick: ()=>setQueueOpen(false),
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                            name: "close"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3257,
                                            columnNumber: 341
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3257,
                                        columnNumber: 237
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3257,
                                columnNumber: 59
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 3257,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "side-body",
                        children: queue.length === 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "side-empty",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    children: t("Your queue is empty.")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3259,
                                    columnNumber: 61
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn",
                                    type: "button",
                                    onClick: ()=>setQueuePickerOpen(true),
                                    children: t("Add from library")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3259,
                                    columnNumber: 95
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3259,
                            columnNumber: 33
                        }, this) : queue.map((trackId, index)=>{
                            const track = tracks.find((item)=>item.id === trackId);
                            if (!track) return null;
                            return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: `q-row${index === queueIndex ? " playing" : ""}${queueDragIndex === index ? " dragging" : ""}${queueDragOverIndex === index ? " drag-over" : ""}`,
                                "data-queue-index": index,
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "q-drag",
                                        type: "button",
                                        title: `Drag to reorder ${track.title}`,
                                        "aria-label": `Drag to reorder ${track.title}`,
                                        onPointerDown: (event)=>{
                                            if (!event.isPrimary || event.button !== 0) return;
                                            event.preventDefault();
                                            queuePointerDragRef.current = {
                                                pointerId: event.pointerId,
                                                fromIndex: index
                                            };
                                            event.currentTarget.setPointerCapture(event.pointerId);
                                            setQueueDragIndex(index);
                                        },
                                        onPointerMove: (event)=>{
                                            const drag = queuePointerDragRef.current;
                                            if (!drag || drag.pointerId !== event.pointerId) return;
                                            const row = document.elementFromPoint(event.clientX, event.clientY)?.closest(".q-row[data-queue-index]");
                                            const overIndex = row ? Number(row.dataset.queueIndex) : null;
                                            setQueueDragOverIndex(overIndex !== null && Number.isInteger(overIndex) ? overIndex : null);
                                        },
                                        onPointerUp: (event)=>{
                                            const drag = queuePointerDragRef.current;
                                            if (!drag || drag.pointerId !== event.pointerId) return;
                                            const row = document.elementFromPoint(event.clientX, event.clientY)?.closest(".q-row[data-queue-index]");
                                            const targetIndex = row ? Number(row.dataset.queueIndex) : null;
                                            queuePointerDragRef.current = null;
                                            setQueueDragIndex(null);
                                            setQueueDragOverIndex(null);
                                            if (targetIndex !== null && Number.isInteger(targetIndex)) {
                                                reorderQueue(drag.fromIndex, targetIndex);
                                            }
                                        },
                                        onPointerCancel: (event)=>{
                                            if (queuePointerDragRef.current?.pointerId !== event.pointerId) return;
                                            queuePointerDragRef.current = null;
                                            setQueueDragIndex(null);
                                            setQueueDragOverIndex(null);
                                        },
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                            name: "drag"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3305,
                                            columnNumber: 14
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3266,
                                        columnNumber: 14
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(TrackImage, {
                                        track: track
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3305,
                                        columnNumber: 43
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "q-meta",
                                        type: "button",
                                        onClick: ()=>playQueueIndex(index),
                                        children: [
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                className: "q-title",
                                                children: track.title
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 3305,
                                                columnNumber: 150
                                            }, this),
                                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                className: "q-artist",
                                                children: track.artist
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 3305,
                                                columnNumber: 196
                                            }, this)
                                        ]
                                    }, void 0, true, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3305,
                                        columnNumber: 71
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                        className: "icon-btn q-remove",
                                        type: "button",
                                        title: t("Remove from queue"),
                                        "aria-label": `${t("Remove from queue")}: ${track.title}`,
                                        onClick: ()=>removeFromQueue(index),
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                            name: "close"
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3305,
                                            columnNumber: 432
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3305,
                                        columnNumber: 253
                                    }, this)
                                ]
                            }, `${trackId}-${index}`, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3262,
                                columnNumber: 20
                            }, this);
                        })
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 3258,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3256,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: `queue-picker-overlay${queuePickerOpen ? " open" : ""}`,
                role: "dialog",
                "aria-modal": "true",
                "aria-label": t("Add from library"),
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "queue-picker-card",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "queue-picker-head",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                    children: t("Add from library")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3312,
                                    columnNumber: 46
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "icon-btn",
                                    type: "button",
                                    title: t("Close"),
                                    onClick: ()=>setQueuePickerOpen(false),
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                        name: "close"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3312,
                                        columnNumber: 182
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3312,
                                    columnNumber: 78
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3312,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                            className: "queue-picker-search",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                    name: "search"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3313,
                                    columnNumber: 50
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                    value: queueSearch,
                                    onChange: (event)=>setQueueSearch(event.target.value),
                                    placeholder: t("Search library"),
                                    "aria-label": t("Search library")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3313,
                                    columnNumber: 72
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3313,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "queue-picker-list",
                            children: filteredQueueTracks.length ? filteredQueueTracks.map((track)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "qp-row",
                                    type: "button",
                                    onClick: (event)=>{
                                        event.stopPropagation();
                                        addToQueue(track);
                                        setQueuePickerOpen(true);
                                    },
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(TrackImage, {
                                            track: track
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3318,
                                            columnNumber: 14
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            className: "qp-meta",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "qp-title",
                                                    children: track.title
                                                }, void 0, false, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 3318,
                                                    columnNumber: 68
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "qp-artist",
                                                    children: track.artist
                                                }, void 0, false, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 3318,
                                                    columnNumber: 115
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3318,
                                            columnNumber: 42
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            className: "qp-add",
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                name: "plus"
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 3318,
                                                columnNumber: 196
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3318,
                                            columnNumber: 171
                                        }, this)
                                    ]
                                }, track.id, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3314,
                                    columnNumber: 111
                                }, this)) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "queue-picker-empty",
                                children: tracks.length ? t("No tracks match your search.") : t("Your library is empty")
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3318,
                                columnNumber: 236
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3314,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 3311,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3310,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: `queue-picker-overlay playlist-name-overlay${playlistModal ? " open" : ""}`,
                role: "dialog",
                "aria-modal": "true",
                "aria-labelledby": "playlistNameTitle",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("form", {
                    className: "queue-picker-card playlist-name-card",
                    onSubmit: createOrRenamePlaylist,
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "queue-picker-head",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                    id: "playlistNameTitle",
                                    children: playlistModal?.playlist ? t("Rename playlist") : t("New playlist")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3324,
                                    columnNumber: 46
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "icon-btn",
                                    type: "button",
                                    title: t("Close"),
                                    onClick: ()=>setPlaylistModal(null),
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                        name: "close"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3324,
                                        columnNumber: 247
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3324,
                                    columnNumber: 146
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3324,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                            className: "playlist-name-label",
                            htmlFor: "playlistNameInput",
                            children: t("Playlist name")
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3325,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                            ref: playlistNameInputRef,
                            className: "playlist-name-input",
                            id: "playlistNameInput",
                            maxLength: 200,
                            value: playlistName,
                            onChange: (event)=>setPlaylistName(event.target.value)
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3326,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "playlist-name-actions",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn",
                                    type: "button",
                                    onClick: ()=>setPlaylistModal(null),
                                    children: t("Cancel")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3327,
                                    columnNumber: 50
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn btn-primary",
                                    type: "submit",
                                    children: playlistModal?.playlist ? t("Save") : t("Create")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3327,
                                    columnNumber: 149
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3327,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 3323,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3322,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: `queue-picker-overlay${playlistPicker ? " open" : ""}`,
                role: "dialog",
                "aria-modal": "true",
                "aria-label": t("Add track to playlist"),
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "queue-picker-card",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "queue-picker-head",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                    children: t("Add to playlist")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3333,
                                    columnNumber: 46
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "icon-btn",
                                    type: "button",
                                    title: t("Close"),
                                    onClick: ()=>setPlaylistPicker(null),
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                        name: "close"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3333,
                                        columnNumber: 179
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3333,
                                    columnNumber: 77
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3333,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "queue-picker-list",
                            children: playlists.length ? playlists.map((playlist)=>{
                                const trackId = playlistPicker;
                                const inPlaylist = trackId ? playlist.trackIds.includes(trackId) : false;
                                return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: `qp-row${inPlaylist ? " in-playlist" : ""}`,
                                    type: "button",
                                    disabled: inPlaylist,
                                    onClick: ()=>{
                                        if (trackId) addTrackToPlaylist(playlist.id, trackId);
                                        setPlaylistPicker(null);
                                        notify(`Added to “${playlist.name}”.`);
                                    },
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            className: "qp-meta",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "qp-title",
                                                    children: playlist.name
                                                }, void 0, false, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 3341,
                                                    columnNumber: 42
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "qp-artist",
                                                    children: [
                                                        playlist.trackIds.length,
                                                        " ",
                                                        t("tracks")
                                                    ]
                                                }, void 0, true, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 3341,
                                                    columnNumber: 91
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3341,
                                            columnNumber: 16
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            className: "qp-add",
                                            children: inPlaylist ? "✓" : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                name: "plus"
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 3341,
                                                columnNumber: 218
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3341,
                                            columnNumber: 173
                                        }, this)
                                    ]
                                }, playlist.id, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3337,
                                    columnNumber: 20
                                }, this);
                            }) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "queue-picker-empty",
                                children: t("Create a playlist first.")
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3342,
                                columnNumber: 16
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3334,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "playlist-name-actions",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "btn btn-primary",
                                type: "button",
                                onClick: ()=>{
                                    setPlaylistPicker(null);
                                    setPlaylistName("");
                                    setPlaylistModal({
                                        trackId: playlistPicker ?? undefined
                                    });
                                },
                                children: t("New playlist")
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3343,
                                columnNumber: 50
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3343,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 3332,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3331,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: `queue-picker-overlay${playlistAddTarget ? " open" : ""}`,
                role: "dialog",
                "aria-modal": "true",
                "aria-label": t("Add tracks to playlist"),
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "queue-picker-card",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "queue-picker-head",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                    children: t("Add from library")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3349,
                                    columnNumber: 46
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "icon-btn",
                                    type: "button",
                                    title: t("Close"),
                                    onClick: ()=>setPlaylistAddTarget(null),
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                        name: "close"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3349,
                                        columnNumber: 183
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3349,
                                    columnNumber: 78
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3349,
                            columnNumber: 11
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "queue-picker-list",
                            children: tracksAvailableToAdd.length ? tracksAvailableToAdd.map((track)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "qp-row",
                                    type: "button",
                                    onClick: ()=>{
                                        if (playlistAddTarget) addTrackToPlaylist(playlistAddTarget, track.id);
                                        notify(`Added “${track.title}” to the playlist.`);
                                    },
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(TrackImage, {
                                            track: track
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3354,
                                            columnNumber: 16
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            className: "qp-meta",
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "qp-title",
                                                    children: track.title
                                                }, void 0, false, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 3354,
                                                    columnNumber: 70
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "qp-artist",
                                                    children: track.artist
                                                }, void 0, false, {
                                                    fileName: "[project]/src/components/library-app.tsx",
                                                    lineNumber: 3354,
                                                    columnNumber: 117
                                                }, this)
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3354,
                                            columnNumber: 44
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                            className: "qp-add",
                                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                                name: "plus"
                                            }, void 0, false, {
                                                fileName: "[project]/src/components/library-app.tsx",
                                                lineNumber: 3354,
                                                columnNumber: 198
                                            }, this)
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/library-app.tsx",
                                            lineNumber: 3354,
                                            columnNumber: 173
                                        }, this)
                                    ]
                                }, track.id, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3351,
                                    columnNumber: 80
                                }, this)) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "queue-picker-empty",
                                children: tracks.length ? t("Every song in your library is already in this playlist.") : t("Your library is empty.")
                            }, void 0, false, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3354,
                                columnNumber: 238
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3350,
                            columnNumber: 11
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 3348,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3347,
                columnNumber: 7
            }, this),
            coverEditorTrack ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "queue-picker-overlay open",
                role: "dialog",
                "aria-modal": "true",
                "aria-labelledby": "coverEditorTitle",
                onClick: (event)=>{
                    if (event.target === event.currentTarget && !coverPending) closeCoverEditor();
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("section", {
                    className: "queue-picker-card track-editor-card",
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "queue-picker-head",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                    id: "coverEditorTitle",
                                    children: [
                                        t("Cover for"),
                                        " ",
                                        coverEditorTrack.title
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3371,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "icon-btn",
                                    type: "button",
                                    "aria-label": t("Close"),
                                    onClick: closeCoverEditor,
                                    disabled: coverPending,
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                        name: "close"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3373,
                                        columnNumber: 17
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3372,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3370,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                            className: "track-cover-preview",
                            src: coverPreview ?? coverEditorTrack.coverUrl,
                            alt: `${t("Current cover for")} ${coverEditorTrack.title}`
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3376,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                            className: "track-editor-help",
                            children: t("JPEG, PNG, or WebP; up to 5 MB.")
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3381,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                            className: "track-editor-check",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                    type: "checkbox",
                                    checked: applyCoverToAlbum,
                                    disabled: !coverEditorTrack.album.trim() || /^unknown album$/i.test(coverEditorTrack.album.trim()) || coverPending,
                                    onChange: (event)=>{
                                        setApplyCoverToAlbum(event.currentTarget.checked);
                                        if (!event.currentTarget.checked) setReplaceAlbumUserCovers(false);
                                    }
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3383,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                    children: t("Apply to all tracks of this album")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3392,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3382,
                            columnNumber: 13
                        }, this),
                        !coverEditorTrack.album.trim() || /^unknown album$/i.test(coverEditorTrack.album.trim()) ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                            className: "track-editor-help",
                            children: t("An album name is required to apply a cover to the album.")
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3395,
                            columnNumber: 15
                        }, this) : null,
                        applyCoverToAlbum ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                            className: "track-editor-check track-editor-check-warning",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                    type: "checkbox",
                                    checked: replaceAlbumUserCovers,
                                    disabled: coverPending,
                                    onChange: (event)=>setReplaceAlbumUserCovers(event.currentTarget.checked)
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3399,
                                    columnNumber: 17
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                    children: t("Also replace covers you uploaded on this album")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3405,
                                    columnNumber: 17
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3398,
                            columnNumber: 15
                        }, this) : null,
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                            ref: coverFileInputRef,
                            className: "hidden-input",
                            type: "file",
                            accept: "image/jpeg,image/png,image/webp",
                            onChange: (event)=>{
                                const selected = event.currentTarget.files?.[0] ?? null;
                                event.currentTarget.value = "";
                                if (!selected) return;
                                if (selected.size > 5 * 1024 * 1024) {
                                    setCoverError(t("Cover image must be 5 MB or smaller."));
                                    return;
                                }
                                if (![
                                    "image/jpeg",
                                    "image/png",
                                    "image/webp"
                                ].includes(selected.type)) {
                                    setCoverError(t("Choose a JPEG, PNG, or WebP image."));
                                    return;
                                }
                                if (coverPreviewUrlRef.current) URL.revokeObjectURL(coverPreviewUrlRef.current);
                                const previewUrl = URL.createObjectURL(selected);
                                coverPreviewUrlRef.current = previewUrl;
                                setCoverFile(selected);
                                setCoverPreview(previewUrl);
                                setCoverError("");
                            }
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3408,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "track-editor-error",
                            role: "alert",
                            children: coverError
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3433,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "playlist-name-actions",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn",
                                    type: "button",
                                    onClick: ()=>coverFileInputRef.current?.click(),
                                    disabled: coverPending,
                                    children: t("Choose cover image")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3435,
                                    columnNumber: 15
                                }, this),
                                coverEditorTrack.coverSource === "user" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn btn-danger",
                                    type: "button",
                                    onClick: ()=>void removeCover(),
                                    disabled: coverPending,
                                    children: coverPending ? t("Removing cover…") : t("Remove cover")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3439,
                                    columnNumber: 17
                                }, this) : null,
                                coverEditorTrack.coverSource !== "upload" && coverEditorTrack.coverSource !== "user" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn",
                                    type: "button",
                                    onClick: ()=>void retryCoverLookup(coverEditorTrack),
                                    disabled: coverPending,
                                    children: t("Retry cover")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3444,
                                    columnNumber: 17
                                }, this) : null,
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn btn-primary",
                                    type: "button",
                                    onClick: ()=>void saveCover(),
                                    disabled: coverPending || !coverFile,
                                    children: coverPending ? t("Saving cover…") : t("Save cover")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3453,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3434,
                            columnNumber: 13
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 3369,
                    columnNumber: 11
                }, this)
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3360,
                columnNumber: 9
            }, this) : null,
            metadataEditorTrack ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "queue-picker-overlay open",
                role: "dialog",
                "aria-modal": "true",
                "aria-labelledby": "trackDetailsTitle",
                onClick: (event)=>{
                    if (event.target === event.currentTarget && !metadataPending) setMetadataEditorTrack(null);
                },
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("form", {
                    className: "queue-picker-card track-editor-card",
                    onSubmit: saveTrackDetails,
                    children: [
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "queue-picker-head",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                    id: "trackDetailsTitle",
                                    children: t("Track details")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3473,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "icon-btn",
                                    type: "button",
                                    "aria-label": t("Close"),
                                    onClick: ()=>setMetadataEditorTrack(null),
                                    disabled: metadataPending,
                                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(Icon, {
                                        name: "close"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3475,
                                        columnNumber: 17
                                    }, this)
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3474,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3472,
                            columnNumber: 13
                        }, this),
                        [
                            "title",
                            "artist",
                            "album"
                        ].map((field)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("label", {
                                className: "track-editor-field",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                        children: t(field === "title" ? "Title" : field === "artist" ? "Artist" : "Album")
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3480,
                                        columnNumber: 17
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                                        maxLength: 200,
                                        required: true,
                                        value: metadataDraft[field],
                                        onChange: (event)=>setMetadataDraft((current)=>({
                                                    ...current,
                                                    [field]: event.target.value
                                                }))
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/library-app.tsx",
                                        lineNumber: 3481,
                                        columnNumber: 17
                                    }, this)
                                ]
                            }, field, true, {
                                fileName: "[project]/src/components/library-app.tsx",
                                lineNumber: 3479,
                                columnNumber: 15
                            }, this)),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "track-editor-error",
                            role: "alert",
                            children: metadataError
                        }, void 0, false, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3489,
                            columnNumber: 13
                        }, this),
                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "playlist-name-actions",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn",
                                    type: "button",
                                    onClick: ()=>setMetadataEditorTrack(null),
                                    disabled: metadataPending,
                                    children: t("Cancel")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3491,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn btn-primary",
                                    type: "submit",
                                    disabled: metadataPending,
                                    children: metadataPending ? t("Saving…") : t("Save changes")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/library-app.tsx",
                                    lineNumber: 3492,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/library-app.tsx",
                            lineNumber: 3490,
                            columnNumber: 13
                        }, this)
                    ]
                }, void 0, true, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 3471,
                    columnNumber: 11
                }, this)
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3462,
                columnNumber: 9
            }, this) : null,
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                ref: fileInputRef,
                className: "hidden-input",
                type: "file",
                accept: "audio/*,.mp3,.m4a,.mp4,.wav,.flac,.ogg,.oga,.aac,.opus,.weba",
                multiple: true,
                onChange: (event)=>{
                    if (event.currentTarget.files) void uploadFiles(event.currentTarget.files);
                    event.currentTarget.value = "";
                }
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3500,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("input", {
                ref: folderInputRef,
                className: "hidden-input",
                type: "file",
                accept: "audio/*,.mp3,.m4a,.mp4,.wav,.flac,.ogg,.oga,.aac,.opus,.weba",
                multiple: true,
                ...{
                    webkitdirectory: "",
                    directory: ""
                },
                onChange: (event)=>{
                    if (event.currentTarget.files) void uploadFiles(event.currentTarget.files);
                    event.currentTarget.value = "";
                }
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3511,
                columnNumber: 7
            }, this),
            isDraggingFiles ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "drop-overlay show",
                role: "status",
                "aria-live": "polite",
                onDragLeave: ()=>setIsDraggingFiles(false),
                onDrop: (event)=>{
                    event.preventDefault();
                    setIsDraggingFiles(false);
                    void uploadFiles(event.dataTransfer.files);
                },
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                        children: t("Drop to add music")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 3527,
                        columnNumber: 10
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                        children: t("Your files are uploaded to your account.")
                    }, void 0, false, {
                        fileName: "[project]/src/components/library-app.tsx",
                        lineNumber: 3527,
                        columnNumber: 43
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3523,
                columnNumber: 26
            }, this) : null,
            uploadStatus && typeof document !== "undefined" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createPortal"])(/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "toasts",
                role: "status",
                "aria-live": "polite",
                "aria-atomic": "true",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "toast",
                    children: uploadStatus
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 3529,
                    columnNumber: 100
                }, this)
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3529,
                columnNumber: 24
            }, this), document.body) : null,
            toast && typeof document !== "undefined" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2d$dom$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["createPortal"])(/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "toasts",
                role: "status",
                "aria-live": "polite",
                "aria-atomic": "true",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "toast",
                    children: toast
                }, void 0, false, {
                    fileName: "[project]/src/components/library-app.tsx",
                    lineNumber: 3532,
                    columnNumber: 100
                }, this)
            }, void 0, false, {
                fileName: "[project]/src/components/library-app.tsx",
                lineNumber: 3532,
                columnNumber: 24
            }, this), document.body) : null
        ]
    }, void 0, true, {
        fileName: "[project]/src/components/library-app.tsx",
        lineNumber: 2834,
        columnNumber: 5
    }, this);
}
_s4(LibraryApp, "5IcwwKIT//myjI46O98Z4ndl+kg=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"]
    ];
});
_c6 = LibraryApp;
var _c, _c1, _c2, _c3, _c4, _c5, _c6;
__turbopack_context__.k.register(_c, "GeneratedAura");
__turbopack_context__.k.register(_c1, "LoadedTrackImage");
__turbopack_context__.k.register(_c2, "TrackImage");
__turbopack_context__.k.register(_c3, "PlaybackSeek");
__turbopack_context__.k.register(_c4, "Icon");
__turbopack_context__.k.register(_c5, "TrackMenuPortal");
__turbopack_context__.k.register(_c6, "LibraryApp");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/src/components/lyrics-overlay.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>LyricsOverlay,
    "lookupLyrics",
    ()=>lookupLyrics,
    "parseLyricsText",
    ()=>parseLyricsText
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/api/client.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$artist$2d$explorer$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/components/artist-explorer.tsx [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/store/player-store.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/i18n.tsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
"use client";
;
;
;
;
;
;
function syncSafeInteger(bytes, offset) {
    return (bytes[offset] & 0x7f) << 21 | (bytes[offset + 1] & 0x7f) << 14 | (bytes[offset + 2] & 0x7f) << 7 | bytes[offset + 3] & 0x7f;
}
function bigEndianInteger(bytes, offset, length) {
    let value = 0;
    for(let index = 0; index < length; index += 1){
        value = value * 256 + bytes[offset + index];
    }
    return value;
}
function decodeId3Text(bytes, encoding) {
    try {
        const decoderName = encoding === 0 ? "latin1" : encoding === 1 ? "utf-16" : encoding === 2 ? "utf-16be" : "utf-8";
        return new TextDecoder(decoderName).decode(bytes).replace(/\0+$/g, "");
    } catch  {
        return "";
    }
}
function findId3Terminator(bytes, start, wide) {
    const step = wide ? 2 : 1;
    for(let index = start; index < bytes.length - (wide ? 1 : 0); index += step){
        if (bytes[index] === 0 && (!wide || bytes[index + 1] === 0)) return index;
    }
    return bytes.length;
}
function removeUnsynchronization(bytes) {
    const output = [];
    for(let index = 0; index < bytes.length; index += 1){
        output.push(bytes[index]);
        if (bytes[index] === 0xff && bytes[index + 1] === 0) index += 1;
    }
    return Uint8Array.from(output);
}
function parseSynchronizedId3Frame(frame) {
    try {
        const encoding = frame[0];
        const wide = encoding === 1 || encoding === 2;
        let index = 6;
        const descriptionEnd = findId3Terminator(frame, index, wide);
        index = descriptionEnd + (wide ? 2 : 1);
        const lines = [];
        while(index < frame.length){
            const textEnd = findId3Terminator(frame, index, wide);
            if (textEnd >= frame.length) break;
            const text = decodeId3Text(frame.subarray(index, textEnd), encoding);
            index = textEnd + (wide ? 2 : 1);
            if (index + 4 > frame.length) break;
            const timestamp = bigEndianInteger(frame, index, 4);
            index += 4;
            if (Number.isFinite(timestamp)) {
                lines.push({
                    time: timestamp * (frame[4] === 1 ? 26.122 : 1),
                    text
                });
            }
        }
        return lines.length ? lines.sort((left, right)=>left.time - right.time) : null;
    } catch  {
        return null;
    }
}
function parseUnsynchronizedId3Frame(frame) {
    try {
        const encoding = frame[0];
        const wide = encoding === 1 || encoding === 2;
        const descriptionEnd = findId3Terminator(frame, 4, wide);
        const text = decodeId3Text(frame.subarray(descriptionEnd + (wide ? 2 : 1)), encoding).trim();
        return text || null;
    } catch  {
        return null;
    }
}
async function readEmbeddedLyrics(trackId, signal) {
    const readRange = async (start, end)=>{
        const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])(`/api/tracks/${encodeURIComponent(trackId)}/stream`, {
            cache: "no-store",
            headers: {
                Range: `bytes=${start}-${end}`
            },
            signal
        });
        if (response.status !== 206) return null;
        return new Uint8Array(await response.arrayBuffer());
    };
    let bytes = await readRange(0, 256 * 1024 - 1);
    if (!bytes) return null;
    if (bytes.length < 10 || bytes[0] !== 0x49 || bytes[1] !== 0x44 || bytes[2] !== 0x33) {
        return null;
    }
    const tagLength = 10 + syncSafeInteger(bytes, 6);
    if (tagLength > 32 * 1024 * 1024) return null;
    if (tagLength > bytes.length) {
        const remainder = await readRange(bytes.length, tagLength - 1);
        if (!remainder) return null;
        const completeTag = new Uint8Array(bytes.length + remainder.length);
        completeTag.set(bytes);
        completeTag.set(remainder, bytes.length);
        bytes = completeTag;
    }
    const version = bytes[3];
    const tagEnd = Math.min(bytes.length, 10 + syncSafeInteger(bytes, 6));
    let offset = 10;
    if (version === 2 && (bytes[5] & 0x40) !== 0) return null;
    if (version >= 3 && (bytes[5] & 0x40) !== 0) {
        const extendedSize = version === 3 ? bigEndianInteger(bytes, offset, 4) + 4 : syncSafeInteger(bytes, offset);
        offset += extendedSize;
    }
    const body = (bytes[5] & 0x80) !== 0 ? removeUnsynchronization(bytes.subarray(offset, tagEnd)) : bytes.subarray(offset, tagEnd);
    offset = 0;
    while(offset + (version === 2 ? 6 : 10) <= body.length){
        const headerSize = version === 2 ? 6 : 10;
        const idLength = version === 2 ? 3 : 4;
        const frameId = String.fromCharCode(...body.subarray(offset, offset + idLength));
        if (!frameId.trim() || /^\0+$/.test(frameId)) break;
        const frameSize = version === 2 ? bigEndianInteger(body, offset + 3, 3) : version === 4 ? syncSafeInteger(body, offset + 4) : bigEndianInteger(body, offset + 4, 4);
        const frameFlags = version === 2 ? 0 : bigEndianInteger(body, offset + 8, 2);
        const start = offset + headerSize;
        const end = start + frameSize;
        if (!frameSize || end > body.length) break;
        offset = end;
        if (version !== 2 && (version === 4 ? (frameFlags & 0x000c) !== 0 : (frameFlags & 0x00c0) !== 0)) continue;
        let frame = body.subarray(start, end);
        if (version === 4 && (frameFlags & 0x0002) !== 0) frame = removeUnsynchronization(frame);
        if ([
            "SYLT",
            "SLT"
        ].includes(frameId)) {
            const lines = parseSynchronizedId3Frame(frame);
            if (lines) return {
                source: "sylt",
                lines
            };
        }
        if ([
            "USLT",
            "ULT"
        ].includes(frameId)) {
            const text = parseUnsynchronizedId3Frame(frame);
            if (text) return {
                source: "uslt",
                text
            };
        }
    }
    return null;
}
const LYRICS_CACHE_TTL_MS = 3 * 24 * 60 * 60 * 1000;
const LYRICS_CACHE_PREFIX = "vervfy:lrclib:v1:";
let lyricsProviderEnabledPromise = null;
async function isLrclibEnabled() {
    if (!lyricsProviderEnabledPromise) {
        lyricsProviderEnabledPromise = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])("/api/config", {
            cache: "no-store"
        }).then(async (response)=>{
            if (!response.ok) throw new Error(`Feature configuration returned HTTP ${response.status}`);
            const config = await response.json();
            return config.lyrics_provider_lrclib !== false;
        }).catch((error)=>{
            console.warn("Could not load lyrics provider configuration; using the default enabled state.", error);
            return true;
        });
    }
    return lyricsProviderEnabledPromise;
}
function readBrowserLyricsCache(trackId) {
    try {
        const raw = window.localStorage.getItem(`${LYRICS_CACHE_PREFIX}${trackId}`);
        if (!raw) return null;
        const cached = JSON.parse(raw);
        if (typeof cached.savedAt !== "number" || Date.now() - cached.savedAt > LYRICS_CACHE_TTL_MS || typeof cached.lyrics !== "object" || cached.lyrics === null) {
            window.localStorage.removeItem(`${LYRICS_CACHE_PREFIX}${trackId}`);
            return null;
        }
        const lyrics = cached.lyrics;
        if (![
            "online-synced",
            "online-plain"
        ].includes(lyrics.source)) return null;
        if (lyrics.text !== undefined && typeof lyrics.text !== "string" || lyrics.lines !== undefined && (!Array.isArray(lyrics.lines) || !lyrics.lines.every((line)=>typeof line?.time === "number" && typeof line?.text === "string"))) {
            window.localStorage.removeItem(`${LYRICS_CACHE_PREFIX}${trackId}`);
            return null;
        }
        return lyrics;
    } catch (error) {
        console.warn("Could not read the browser lyrics cache.", error);
        return null;
    }
}
function writeBrowserLyricsCache(trackId, lyrics) {
    if (![
        "online-synced",
        "online-plain"
    ].includes(lyrics.source)) return;
    try {
        window.localStorage.setItem(`${LYRICS_CACHE_PREFIX}${trackId}`, JSON.stringify({
            savedAt: Date.now(),
            lyrics
        }));
    } catch (error) {
        console.warn("Could not cache fetched lyrics in this browser.", error);
    }
}
function parseLrc(value) {
    const lines = [];
    const stamp = /\[(\d{1,2}):(\d{2}(?:[.:]\d{1,3})?)\]/g;
    let offsetMs = 0;
    for (const raw of value.split(/\r?\n/)){
        const offset = raw.match(/^\s*\[offset\s*:\s*([+-]?\d+)\s*\]\s*$/i);
        if (offset) {
            offsetMs = Number(offset[1]) || 0;
            continue;
        }
        const matches = [
            ...raw.matchAll(stamp)
        ];
        if (!matches.length) continue;
        const text = raw.replace(stamp, "").trim();
        for (const match of matches){
            const seconds = Number(match[2].replace(":", "."));
            if (!Number.isFinite(seconds)) continue;
            lines.push({
                time: Math.max(0, (Number(match[1]) * 60 + seconds) * 1000 + offsetMs),
                text
            });
        }
    }
    return lines.sort((left, right)=>left.time - right.time);
}
function cleanTitle(value) {
    return value.replace(/\s*[\[(]\s*(?:feat(?:uring)?\.?|ft\.?|with)\s+[^\])]*[\])]/gi, "").replace(/\s+(?:feat(?:uring)?\.?|ft\.?|with)\s+.+$/gi, "").replace(/\s*[\[(][^\])]*&[^\])]*[\])]/g, "").replace(/\s*[\[(]\s*(?:official\s+)?(?:lyric\s+)?(?:music\s+)?(?:video|audio)\s*[\])]/gi, "").trim();
}
function normalized(value) {
    return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}
function activeLine(lines, timeMs) {
    let low = 0;
    let high = lines.length - 1;
    let active = -1;
    while(low <= high){
        const middle = low + high >> 1;
        if (lines[middle].time <= timeMs) {
            active = middle;
            low = middle + 1;
        } else {
            high = middle - 1;
        }
    }
    return active;
}
function stampToLrc(lines) {
    return lines.map(({ time, text })=>{
        const seconds = Math.max(0, time / 1000);
        const minutes = Math.floor(seconds / 60);
        const remainder = (seconds % 60).toFixed(2).padStart(5, "0");
        return `[${String(minutes).padStart(2, "0")}:${remainder}]${text}`;
    }).join("\n");
}
function parseLyricsText(value, source) {
    const lines = parseLrc(value);
    return lines.length ? {
        source,
        lines
    } : {
        source,
        text: value
    };
}
async function lookupLyrics(track, signal) {
    if (track.customLyrics?.trim()) return parseLyricsText(track.customLyrics, "custom");
    if (!await isLrclibEnabled()) return {
        source: "disabled"
    };
    let embedded = null;
    try {
        embedded = await readEmbeddedLyrics(track.id, signal);
    } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") throw error;
    }
    if (embedded) return embedded;
    const cached = readBrowserLyricsCache(track.id);
    if (cached) return cached;
    const leadArtist = track.artist.split(/[,;/]|\b(?:feat(?:uring)?|ft\.?|with)\b/i)[0]?.trim();
    const title = cleanTitle(track.title);
    if (!title || !leadArtist || /^unknown artist$/i.test(leadArtist)) return {
        source: "none"
    };
    const leadOf = (value)=>value.split(/[,;/]|\b(?:feat(?:uring)?|ft\.?|with)\b/i)[0]?.trim() ?? "";
    const titleKey = normalized(title);
    const artistKey = normalized(leadArtist);
    const durationTolerance = Math.min(15, Math.max(5, track.duration * 0.06));
    const sameSong = (entry)=>normalized(cleanTitle(String(entry.trackName ?? ""))) === titleKey && normalized(leadOf(String(entry.artistName ?? ""))) === artistKey;
    const durationDelta = (entry)=>typeof entry.duration === "number" && entry.duration > 0 ? Math.abs(entry.duration - track.duration) : Number.POSITIVE_INFINITY;
    const within = (entry, tolerance)=>!track.duration || durationDelta(entry) <= tolerance;
    const hasSynced = (entry)=>typeof entry.syncedLyrics === "string" && parseLrc(entry.syncedLyrics).length > 0;
    const hasPlain = (entry)=>typeof entry.plainLyrics === "string" && entry.plainLyrics.trim().length > 0;
    const closest = (entries)=>[
            ...entries
        ].sort((left, right)=>durationDelta(left) - durationDelta(right))[0] ?? null;
    const query = new URLSearchParams({
        track_name: title,
        artist_name: leadArtist,
        ...track.album && !/^unknown album$/i.test(track.album) ? {
            album_name: track.album
        } : {},
        ...track.duration > 0 ? {
            duration: String(Math.round(track.duration))
        } : {}
    });
    const requestOptions = {
        cache: "no-store",
        signal,
        headers: {
            "Lrclib-Client": "Vervfy/1.0 (https://github.com/samvitorsilva/Vervfy)"
        }
    };
    const response = await fetch(`https://lrclib.net/api/get?${query}`, requestOptions);
    let exact = response.ok ? await response.json() : null;
    if (exact && !(sameSong(exact) && within(exact, durationTolerance))) exact = null;
    if (exact?.instrumental === true) return {
        source: "none"
    };
    const pool = exact ? [
        exact
    ] : [];
    // Prefer a timed copy: close in length first, then (only if none) a slightly wider window.
    const pickBest = ()=>{
        const usable = pool.filter((entry)=>entry.instrumental !== true);
        return closest(usable.filter((entry)=>hasSynced(entry) && within(entry, durationTolerance))) ?? closest(usable.filter((entry)=>hasPlain(entry) && within(entry, durationTolerance)));
    };
    const hasTimedChoice = ()=>{
        const best = pickBest();
        return best !== null && hasSynced(best);
    };
    // The exact hit already has timestamps: no extra requests needed.
    if (!hasTimedChoice()) {
        const searches = [
            new URLSearchParams({
                track_name: title,
                artist_name: leadArtist
            }),
            new URLSearchParams({
                q: `${leadArtist} ${title}`
            })
        ];
        const seen = new Set(pool.map((entry)=>entry.id));
        for (const search of searches){
            const searchResponse = await fetch(`https://lrclib.net/api/search?${search}`, {
                ...requestOptions
            });
            if (!searchResponse.ok) continue;
            const results = await searchResponse.json();
            if (!Array.isArray(results)) continue;
            for (const entry of results){
                if (!sameSong(entry) || entry.id !== undefined && seen.has(entry.id)) continue;
                seen.add(entry.id);
                pool.push(entry);
            }
            if (hasTimedChoice()) break;
        }
    }
    const candidate = pickBest();
    if (!candidate) return {
        source: "none"
    };
    const synced = typeof candidate.syncedLyrics === "string" ? candidate.syncedLyrics.trim() : "";
    const plain = typeof candidate.plainLyrics === "string" ? candidate.plainLyrics.trim() : "";
    const result = synced && parseLrc(synced).length ? parseLyricsText(synced, "online-synced") : plain ? {
        source: "online-plain",
        text: plain
    } : {
        source: "none"
    };
    writeBrowserLyricsCache(track.id, result);
    return result;
}
function formatTime(value) {
    const seconds = Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0;
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}
function PlayerIcon({ name }) {
    const paths = {
        previous: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                d: "M6 5v14M18 6 8 12l10 6V6Z"
            }, void 0, false, {
                fileName: "[project]/src/components/lyrics-overlay.tsx",
                lineNumber: 435,
                columnNumber: 17
            }, this)
        }, void 0, false, {
            fileName: "[project]/src/components/lyrics-overlay.tsx",
            lineNumber: 435,
            columnNumber: 15
        }, this),
        next: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                d: "M18 5v14M6 6l10 6-10 6V6Z"
            }, void 0, false, {
                fileName: "[project]/src/components/lyrics-overlay.tsx",
                lineNumber: 436,
                columnNumber: 13
            }, this)
        }, void 0, false, {
            fileName: "[project]/src/components/lyrics-overlay.tsx",
            lineNumber: 436,
            columnNumber: 11
        }, this),
        play: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
            d: "m8 5 11 7-11 7V5Z"
        }, void 0, false, {
            fileName: "[project]/src/components/lyrics-overlay.tsx",
            lineNumber: 437,
            columnNumber: 11
        }, this),
        pause: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                d: "M8 5v14M16 5v14"
            }, void 0, false, {
                fileName: "[project]/src/components/lyrics-overlay.tsx",
                lineNumber: 438,
                columnNumber: 14
            }, this)
        }, void 0, false, {
            fileName: "[project]/src/components/lyrics-overlay.tsx",
            lineNumber: 438,
            columnNumber: 12
        }, this),
        shuffle: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                d: "M3 6h3.2l7.2 11H21M17.5 4.5 21 6.5l-3.5 2M3 17.5h3.2l3.2-4.9M17.5 19.5 21 17.5l-3.5-2"
            }, void 0, false, {
                fileName: "[project]/src/components/lyrics-overlay.tsx",
                lineNumber: 439,
                columnNumber: 16
            }, this)
        }, void 0, false, {
            fileName: "[project]/src/components/lyrics-overlay.tsx",
            lineNumber: 439,
            columnNumber: 14
        }, this),
        repeat: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                d: "m17 3.5 3.5 3.5-3.5 3.5M4 11.5V9.2a3.7 3.7 0 0 1 3.7-3.7h12.8M7 20.5 3.5 17 7 13.5M20 12.5v2.3a3.7 3.7 0 0 1-3.7 3.7H3.5"
            }, void 0, false, {
                fileName: "[project]/src/components/lyrics-overlay.tsx",
                lineNumber: 440,
                columnNumber: 15
            }, this)
        }, void 0, false, {
            fileName: "[project]/src/components/lyrics-overlay.tsx",
            lineNumber: 440,
            columnNumber: 13
        }, this)
    };
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        strokeWidth: "1.8",
        strokeLinecap: "round",
        strokeLinejoin: "round",
        "aria-hidden": "true",
        children: paths[name]
    }, void 0, false, {
        fileName: "[project]/src/components/lyrics-overlay.tsx",
        lineNumber: 443,
        columnNumber: 5
    }, this);
}
_c = PlayerIcon;
function LyricsOverlay({ track, currentTime, onClose, onOpenArtist, onToast, onPrevious, onNext, onTogglePlayback, onToggleShuffle, onToggleRepeat, shuffle, repeat }) {
    _s();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"])();
    const setTrackLyrics = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LyricsOverlay.usePlayerStore[setTrackLyrics]": (state)=>state.setTrackLyrics
    }["LyricsOverlay.usePlayerStore[setTrackLyrics]"]);
    const setCachedLyrics = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LyricsOverlay.usePlayerStore[setCachedLyrics]": (state)=>state.setCachedLyrics
    }["LyricsOverlay.usePlayerStore[setCachedLyrics]"]);
    const isPlaying = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LyricsOverlay.usePlayerStore[isPlaying]": (state)=>state.isPlaying
    }["LyricsOverlay.usePlayerStore[isPlaying]"]);
    const audioElement = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"])({
        "LyricsOverlay.usePlayerStore[audioElement]": (state)=>state.audioElement
    }["LyricsOverlay.usePlayerStore[audioElement]"]);
    const [lyrics, setLyrics] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])({
        "LyricsOverlay.useState": ()=>track.customLyrics ? parseLyricsText(track.customLyrics, "custom") : __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().lyricsByTrack[track.id] ?? null
    }["LyricsOverlay.useState"]);
    const [loading, setLoading] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])({
        "LyricsOverlay.useState": ()=>!track.customLyrics && !__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().lyricsByTrack[track.id]
    }["LyricsOverlay.useState"]);
    const [editorOpen, setEditorOpen] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [draft, setDraft] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])("");
    const [savePending, setSavePending] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const [syncLines, setSyncLines] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const [syncText, setSyncText] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])([]);
    const lyricsViewportRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const lyricsTrackRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const seekingPointerRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const [scrubbingTime, setScrubbingTime] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const smoothTimeRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(currentTime);
    const [smoothCurrentTime, setSmoothCurrentTime] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(currentTime);
    const activeTrack = track;
    // `timeupdate` fires only a few times per second. While this view is open,
    // sample the audio clock on animation frames so timed lyrics switch right on
    // their cue, including after a seek.
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LyricsOverlay.useEffect": ()=>{
            if (!audioElement || !isPlaying) return;
            let frame = 0;
            const update = {
                "LyricsOverlay.useEffect.update": ()=>{
                    const nextTime = audioElement.currentTime;
                    if (Number.isFinite(nextTime) && Math.abs(nextTime - smoothTimeRef.current) >= 0.005) {
                        smoothTimeRef.current = nextTime;
                        setSmoothCurrentTime(nextTime);
                    }
                    frame = requestAnimationFrame(update);
                }
            }["LyricsOverlay.useEffect.update"];
            frame = requestAnimationFrame(update);
            return ({
                "LyricsOverlay.useEffect": ()=>cancelAnimationFrame(frame)
            })["LyricsOverlay.useEffect"];
        }
    }["LyricsOverlay.useEffect"], [
        audioElement,
        isPlaying
    ]);
    const lyricCurrentTime = scrubbingTime ?? (audioElement && isPlaying ? smoothCurrentTime : currentTime);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LyricsOverlay.useEffect": ()=>{
            const currentTrack = track;
            if (currentTrack.customLyrics || __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().lyricsByTrack[currentTrack.id]) return;
            let cancelled = false;
            const controller = new AbortController();
            const timeout = setTimeout({
                "LyricsOverlay.useEffect.timeout": ()=>controller.abort()
            }["LyricsOverlay.useEffect.timeout"], 6000);
            const storeLyrics = {
                "LyricsOverlay.useEffect.storeLyrics": (value)=>{
                    if (cancelled) return;
                    setCachedLyrics(currentTrack.id, value);
                    setLyrics(value);
                }
            }["LyricsOverlay.useEffect.storeLyrics"];
            async function lookup() {
                setLoading(true);
                try {
                    storeLyrics(await lookupLyrics(currentTrack, controller.signal));
                } catch (error) {
                    if (!cancelled && !(error instanceof DOMException && error.name === "AbortError")) {
                        setLyrics({
                            source: "none"
                        });
                    }
                } finally{
                    clearTimeout(timeout);
                    if (!cancelled) setLoading(false);
                }
            }
            void lookup();
            return ({
                "LyricsOverlay.useEffect": ()=>{
                    cancelled = true;
                    controller.abort();
                    clearTimeout(timeout);
                }
            })["LyricsOverlay.useEffect"];
        }
    }["LyricsOverlay.useEffect"], [
        track,
        setCachedLyrics
    ]);
    const lineIndex = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "LyricsOverlay.useMemo[lineIndex]": ()=>lyrics?.lines ? activeLine(lyrics.lines, lyricCurrentTime * 1000) : -1
    }["LyricsOverlay.useMemo[lineIndex]"], [
        lyrics,
        lyricCurrentTime
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "LyricsOverlay.useEffect": ()=>{
            const viewport = lyricsViewportRef.current;
            const lyricTrack = lyricsTrackRef.current;
            if (!viewport || !lyricTrack) return;
            const line = lyricTrack.children[Math.max(0, lineIndex)];
            if (!(line instanceof HTMLElement)) return;
            const offset = viewport.clientHeight / 2 - line.offsetTop - line.offsetHeight / 2;
            lyricTrack.style.transform = `translate3d(0, ${offset}px, 0)`;
        }
    }["LyricsOverlay.useEffect"], [
        lineIndex,
        lyrics
    ]);
    const duration = audioElement && Number.isFinite(audioElement.duration) ? audioElement.duration : 0;
    const progress = duration > 0 ? Math.max(0, Math.min(100, lyricCurrentTime / duration * 100)) : 0;
    function timeAtPosition(clientX, element) {
        const bounds = element.getBoundingClientRect();
        const ratio = bounds.width ? Math.max(0, Math.min(1, (clientX - bounds.left) / bounds.width)) : 0;
        return ratio * duration;
    }
    function beginSeek(event) {
        const audio = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement;
        if (!audio || !duration || !event.isPrimary || event.button !== 0) return;
        event.preventDefault();
        seekingPointerRef.current = {
            pointerId: event.pointerId,
            wasPlaying: !audio.paused
        };
        event.currentTarget.setPointerCapture(event.pointerId);
        setScrubbingTime(timeAtPosition(event.clientX, event.currentTarget));
        if (!audio.paused) audio.pause();
    }
    function continueSeek(event) {
        if (seekingPointerRef.current?.pointerId !== event.pointerId) return;
        setScrubbingTime(timeAtPosition(event.clientX, event.currentTarget));
    }
    function finishSeek(event) {
        const drag = seekingPointerRef.current;
        const audio = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement;
        if (!audio || !drag || drag.pointerId !== event.pointerId) return;
        audio.currentTime = timeAtPosition(event.clientX, event.currentTarget);
        seekingPointerRef.current = null;
        setScrubbingTime(null);
        if (drag.wasPlaying) onTogglePlayback();
    }
    function seekByKeyboard(event) {
        const audio = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement;
        if (!audio || !duration) return;
        const offsets = {
            ArrowLeft: -5,
            ArrowRight: 5,
            Home: -duration,
            End: duration
        };
        const offset = offsets[event.key];
        if (offset === undefined) return;
        event.preventDefault();
        audio.currentTime = Math.max(0, Math.min(duration, audio.currentTime + offset));
    }
    async function saveLyrics(event) {
        event.preventDefault();
        const value = draft.trim();
        if (!value) {
            onToast(t("Paste some lyrics first."));
            return;
        }
        setSavePending(true);
        try {
            const savedResponse = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])(`/api/tracks/${encodeURIComponent(activeTrack.id)}/lyrics`, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    lyrics: value
                })
            }, {
                csrf: true,
                retryCsrfOnForbidden: true
            });
            await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(savedResponse);
            const result = await savedResponse.json();
            setTrackLyrics(activeTrack.id, result.custom_lyrics);
            setLyrics(parseLyricsText(result.custom_lyrics, "custom"));
            setDraft(result.custom_lyrics);
            setEditorOpen(false);
            setSyncLines(null);
            onToast(t("Lyrics saved."));
        } catch (error) {
            onToast(error instanceof Error ? error.message : "Could not save lyrics.");
        } finally{
            setSavePending(false);
        }
    }
    function beginSync() {
        const lines = lyrics?.lines?.length ? lyrics.lines : null;
        const text = lines ? lines.filter((line)=>line.text.trim()).map((line)=>line.text.trim()) : (lyrics?.text ?? activeTrack.customLyrics ?? "").split(/\r?\n/).map((line)=>line.trim()).filter(Boolean);
        if (!text.length) {
            onToast(t("Add lyrics before syncing them."));
            return;
        }
        setSyncText(text);
        setSyncLines(lines ? lines.filter((line)=>line.text.trim()).map((line)=>({
                ...line
            })) : text.map((line)=>({
                time: -1,
                text: line
            })));
    }
    function stampLine(index) {
        const audio = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement;
        if (!audio || !syncLines) return;
        const next = syncLines.map((line, lineIndex)=>lineIndex === index ? {
                ...line,
                time: Math.round(audio.currentTime * 1000)
            } : line);
        setSyncLines(next);
    }
    async function saveSyncedLyrics() {
        if (!syncLines || syncLines.some((line)=>line.time < 0)) return;
        if (syncLines.some((line, index)=>index > 0 && line.time < syncLines[index - 1].time)) {
            onToast(t("Lyrics must be tapped in song order. Correct the out-of-order line."));
            return;
        }
        const value = stampToLrc(syncLines.map((line, index)=>({
                ...line,
                text: syncText[index]
            })));
        setDraft(value);
        setSavePending(true);
        try {
            const response = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["apiFetch"])(`/api/tracks/${encodeURIComponent(activeTrack.id)}/lyrics`, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    lyrics: value
                })
            }, {
                csrf: true,
                retryCsrfOnForbidden: true
            });
            await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$client$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["expectOk"])(response);
            const result = await response.json();
            setTrackLyrics(activeTrack.id, result.custom_lyrics);
            setLyrics(parseLyricsText(result.custom_lyrics, "custom-synced"));
            setDraft(result.custom_lyrics);
            setSyncLines(null);
            onToast(t("Lyrics synced to the track."));
        } catch (error) {
            onToast(error instanceof Error ? error.message : "Could not save synced lyrics.");
        } finally{
            setSavePending(false);
        }
    }
    const sourceName = {
        sylt: "Synced lyrics",
        uslt: "Lyrics",
        custom: "Pasted lyrics",
        "custom-synced": "Synced · adjusted",
        "online-synced": "Synced · LRCLIB",
        "online-plain": "Lyrics · LRCLIB",
        disabled: t("LRCLIB disabled")
    };
    const lrclibDisabled = lyrics?.source === "disabled";
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "lyrics-overlay open",
        role: "dialog",
        "aria-modal": "true",
        "aria-label": t("Lyrics"),
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "lyrics-bg",
                style: {
                    backgroundImage: `url("${activeTrack.coverUrl}")`
                }
            }, void 0, false, {
                fileName: "[project]/src/components/lyrics-overlay.tsx",
                lineNumber: 725,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("header", {
                className: "lyrics-topbar",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "lyrics-close",
                        type: "button",
                        "aria-label": t("Close lyrics"),
                        onClick: onClose,
                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                            viewBox: "0 0 24 24",
                            fill: "none",
                            stroke: "currentColor",
                            strokeWidth: "1.8",
                            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                                d: "m6 9 6 6 6-6"
                            }, void 0, false, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 728,
                                columnNumber: 88
                            }, this)
                        }, void 0, false, {
                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                            lineNumber: 728,
                            columnNumber: 11
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                        lineNumber: 727,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "lyrics-topbar-title",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                children: t("NOW PLAYING")
                            }, void 0, false, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 730,
                                columnNumber: 46
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("strong", {
                                children: activeTrack.title
                            }, void 0, false, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 730,
                                columnNumber: 77
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                        lineNumber: 730,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "lyrics-edit-top",
                        type: "button",
                        onClick: ()=>{
                            setDraft(activeTrack.customLyrics ?? lyrics?.text ?? "");
                            setEditorOpen(true);
                        },
                        children: t("Edit lyrics")
                    }, void 0, false, {
                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                        lineNumber: 731,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/lyrics-overlay.tsx",
                lineNumber: 726,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "lyrics-stage",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "lyrics-side",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "lyrics-art",
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                    src: activeTrack.coverUrl,
                                    alt: ""
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 735,
                                    columnNumber: 39
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 735,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "lyrics-meta",
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "t",
                                        children: activeTrack.title
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                                        lineNumber: 737,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "a",
                                        children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$artist$2d$explorer$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["artistNames"])(activeTrack).map((name, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
                                                children: [
                                                    index > 0 ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                        className: "artist-sep",
                                                        children: ", "
                                                    }, void 0, false, {
                                                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                                                        lineNumber: 741,
                                                        columnNumber: 32
                                                    }, this) : null,
                                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                                        className: "artist-link",
                                                        type: "button",
                                                        onClick: ()=>onOpenArtist(name),
                                                        children: name
                                                    }, void 0, false, {
                                                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                                                        lineNumber: 742,
                                                        columnNumber: 19
                                                    }, this)
                                                ]
                                            }, name, true, {
                                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                                lineNumber: 740,
                                                columnNumber: 17
                                            }, this))
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                                        lineNumber: 738,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "lyrics-album",
                                        children: activeTrack.album
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                                        lineNumber: 748,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 736,
                                columnNumber: 11
                            }, this),
                            lyrics && sourceName[lyrics.source] ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "lyrics-source",
                                children: sourceName[lyrics.source]
                            }, void 0, false, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 750,
                                columnNumber: 50
                            }, this) : null
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                        lineNumber: 734,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: `lyrics-viewport${!syncLines && !editorOpen && (!lyrics || !lyrics.lines?.length && !lyrics.text) ? " lyrics-viewport-empty" : ""}`,
                        ref: lyricsViewportRef,
                        children: syncLines ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "lyrics-sync-editor",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "lyrics-editor-heading",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                            children: t("Sync lyrics to audio")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                                            lineNumber: 759,
                                            columnNumber: 54
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                            children: t("Start playback, then tap each line when it is sung.")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                                            lineNumber: 759,
                                            columnNumber: 90
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 759,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "lyrics-sync-clock",
                                    children: [
                                        t("Playback"),
                                        ": ",
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("strong", {
                                            children: formatTime(lyricCurrentTime)
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                                            lineNumber: 760,
                                            columnNumber: 67
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 760,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "lyrics-sync-lines",
                                    children: syncLines.map((line, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                            type: "button",
                                            className: `lyrics-sync-line${line.time >= 0 ? " stamped" : ""}`,
                                            onClick: ()=>stampLine(index),
                                            children: [
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    className: "lyrics-sync-line-time",
                                                    children: line.time < 0 ? t("Tap at this line") : formatTime(line.time / 1000)
                                                }, void 0, false, {
                                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                                    lineNumber: 762,
                                                    columnNumber: 200
                                                }, this),
                                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                                    children: syncText[index]
                                                }, void 0, false, {
                                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                                    lineNumber: 762,
                                                    columnNumber: 317
                                                }, this)
                                            ]
                                        }, `${index}-${line.text}`, true, {
                                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                                            lineNumber: 762,
                                            columnNumber: 49
                                        }, this))
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 761,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "lyrics-editor-actions",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                            className: "btn",
                                            type: "button",
                                            onClick: ()=>setSyncLines(null),
                                            children: t("Back")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                                            lineNumber: 764,
                                            columnNumber: 54
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                            className: "btn",
                                            type: "button",
                                            onClick: ()=>{
                                                const audio = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement;
                                                if (audio) {
                                                    audio.currentTime = 0;
                                                    void audio.play();
                                                }
                                            },
                                            children: t("Play from start")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                                            lineNumber: 764,
                                            columnNumber: 147
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                            className: "btn btn-primary",
                                            type: "button",
                                            disabled: savePending || syncLines.some((line)=>line.time < 0),
                                            onClick: ()=>void saveSyncedLyrics(),
                                            children: t("Save synced lyrics")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                                            lineNumber: 770,
                                            columnNumber: 49
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 764,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                            lineNumber: 758,
                            columnNumber: 13
                        }, this) : editorOpen ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("form", {
                            className: "lyrics-editor",
                            onSubmit: saveLyrics,
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "lyrics-editor-heading",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                            children: t("Add lyrics")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                                            lineNumber: 774,
                                            columnNumber: 54
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                            children: [
                                                activeTrack.title,
                                                " · ",
                                                activeTrack.artist
                                            ]
                                        }, void 0, true, {
                                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                                            lineNumber: 774,
                                            columnNumber: 80
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 774,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("textarea", {
                                    className: "lyrics-input",
                                    value: draft,
                                    onChange: (event)=>setDraft(event.target.value),
                                    placeholder: t("Paste plain lyrics or timestamped LRC lyrics here…")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 775,
                                    columnNumber: 15
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "lyrics-editor-actions",
                                    children: [
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                            className: "btn",
                                            type: "button",
                                            onClick: ()=>setEditorOpen(false),
                                            children: t("Cancel")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                                            lineNumber: 776,
                                            columnNumber: 54
                                        }, this),
                                        /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                            className: "btn btn-primary",
                                            type: "submit",
                                            disabled: savePending,
                                            children: savePending ? t("Saving…") : t("Save lyrics")
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                                            lineNumber: 776,
                                            columnNumber: 151
                                        }, this)
                                    ]
                                }, void 0, true, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 776,
                                    columnNumber: 15
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                            lineNumber: 773,
                            columnNumber: 13
                        }, this) : loading ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "lyrics-empty",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "empty-orb lyrics-loading-orb"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 779,
                                    columnNumber: 43
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                    children: t("Searching for lyrics…")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 779,
                                    columnNumber: 91
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    children: t("Checking LRCLIB for a match.")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 779,
                                    columnNumber: 128
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                            lineNumber: 779,
                            columnNumber: 13
                        }, this) : lyrics?.lines?.length ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "lyrics-track",
                            ref: lyricsTrackRef,
                            children: lyrics.lines.map((line, index)=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: `lyrics-line${index === lineIndex ? " active" : ""}${index < lineIndex ? " past" : ""}`,
                                    type: "button",
                                    onClick: ()=>{
                                        const audio = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement;
                                        if (audio) audio.currentTime = line.time / 1000;
                                    },
                                    children: line.text || "\u00a0"
                                }, `${line.time}-${index}`, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 782,
                                    columnNumber: 50
                                }, this))
                        }, void 0, false, {
                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                            lineNumber: 781,
                            columnNumber: 13
                        }, this) : lyrics?.text ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "lyrics-plain",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    children: lyrics.text
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 788,
                                    columnNumber: 43
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn btn-primary lyrics-sync-btn",
                                    type: "button",
                                    onClick: beginSync,
                                    children: t("Sync to audio")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 788,
                                    columnNumber: 63
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn lyrics-sync-btn",
                                    type: "button",
                                    onClick: ()=>setEditorOpen(true),
                                    children: t("Edit lyrics")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 788,
                                    columnNumber: 178
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                            lineNumber: 788,
                            columnNumber: 13
                        }, this) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                            className: "lyrics-empty",
                            children: [
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                    className: "empty-orb"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 790,
                                    columnNumber: 43
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("h3", {
                                    children: t(lrclibDisabled ? "Lyrics lookup is disabled." : "No lyrics available")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 790,
                                    columnNumber: 72
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("p", {
                                    children: t(lrclibDisabled ? "Only your own pasted lyrics are shown." : "Vervfy could not find lyrics for this track. Add your own below.")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 790,
                                    columnNumber: 155
                                }, this),
                                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                    className: "btn btn-primary lyrics-paste-btn",
                                    type: "button",
                                    onClick: ()=>{
                                        setDraft(activeTrack.customLyrics ?? "");
                                        setEditorOpen(true);
                                    },
                                    children: t("Paste lyrics")
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 790,
                                    columnNumber: 293
                                }, this)
                            ]
                        }, void 0, true, {
                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                            lineNumber: 790,
                            columnNumber: 13
                        }, this)
                    }, void 0, false, {
                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                        lineNumber: 753,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/lyrics-overlay.tsx",
                lineNumber: 733,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "lyrics-player",
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "lyrics-player-track",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("img", {
                                src: activeTrack.coverUrl,
                                alt: ""
                            }, void 0, false, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 796,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("strong", {
                                        children: activeTrack.title
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                                        lineNumber: 797,
                                        columnNumber: 17
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("small", {
                                        children: activeTrack.artist
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                                        lineNumber: 797,
                                        columnNumber: 53
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 797,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                        lineNumber: 795,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "lyrics-player-seek",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                className: "lyrics-player-time",
                                children: formatTime(lyricCurrentTime)
                            }, void 0, false, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 800,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                className: "seek",
                                role: "slider",
                                tabIndex: duration ? 0 : -1,
                                "aria-label": t("Track progress"),
                                "aria-valuemin": 0,
                                "aria-valuemax": duration,
                                "aria-valuenow": lyricCurrentTime,
                                "aria-valuetext": `${formatTime(lyricCurrentTime)} of ${formatTime(duration)}`,
                                onPointerDown: beginSeek,
                                onPointerMove: continueSeek,
                                onPointerUp: finishSeek,
                                onPointerCancel: finishSeek,
                                onKeyDown: seekByKeyboard,
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "seek-track",
                                        children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                            className: "seek-fill",
                                            style: {
                                                width: `${progress}%`
                                            }
                                        }, void 0, false, {
                                            fileName: "[project]/src/components/lyrics-overlay.tsx",
                                            lineNumber: 816,
                                            columnNumber: 41
                                        }, this)
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                                        lineNumber: 816,
                                        columnNumber: 13
                                    }, this),
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                                        className: "seek-thumb",
                                        style: {
                                            left: `${progress}%`
                                        }
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                                        lineNumber: 817,
                                        columnNumber: 13
                                    }, this)
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 801,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("span", {
                                className: "lyrics-player-time right",
                                children: formatTime(duration)
                            }, void 0, false, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 819,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                        lineNumber: 799,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                        className: "lyrics-player-controls",
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: `tbtn lyrics-mode-button${shuffle ? " on" : ""}`,
                                type: "button",
                                "aria-label": t("Shuffle"),
                                "aria-pressed": shuffle,
                                onClick: onToggleShuffle,
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(PlayerIcon, {
                                    name: "shuffle"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 822,
                                    columnNumber: 169
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 822,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "tbtn",
                                type: "button",
                                "aria-label": t("Previous track"),
                                onClick: onPrevious,
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(PlayerIcon, {
                                    name: "previous"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 823,
                                    columnNumber: 104
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 823,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "tbtn tbtn-play",
                                type: "button",
                                "aria-label": isPlaying ? "Pause" : "Play",
                                onClick: onTogglePlayback,
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(PlayerIcon, {
                                    name: isPlaying ? "pause" : "play"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 824,
                                    columnNumber: 129
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 824,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: "tbtn",
                                type: "button",
                                "aria-label": t("Next track"),
                                onClick: onNext,
                                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(PlayerIcon, {
                                    name: "next"
                                }, void 0, false, {
                                    fileName: "[project]/src/components/lyrics-overlay.tsx",
                                    lineNumber: 825,
                                    columnNumber: 96
                                }, this)
                            }, void 0, false, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 825,
                                columnNumber: 11
                            }, this),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                                className: `tbtn lyrics-mode-button${repeat !== "off" ? " on" : ""}`,
                                type: "button",
                                "aria-label": t(`Repeat: ${repeat}`),
                                "aria-pressed": repeat !== "off",
                                onClick: onToggleRepeat,
                                children: [
                                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])(PlayerIcon, {
                                        name: "repeat"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                                        lineNumber: 826,
                                        columnNumber: 196
                                    }, this),
                                    repeat === "one" ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("small", {
                                        children: "1"
                                    }, void 0, false, {
                                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                                        lineNumber: 826,
                                        columnNumber: 244
                                    }, this) : null
                                ]
                            }, void 0, true, {
                                fileName: "[project]/src/components/lyrics-overlay.tsx",
                                lineNumber: 826,
                                columnNumber: 11
                            }, this)
                        ]
                    }, void 0, true, {
                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                        lineNumber: 821,
                        columnNumber: 9
                    }, this),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                        className: "lyrics-edit-control",
                        type: "button",
                        onClick: ()=>{
                            setDraft(activeTrack.customLyrics ?? lyrics?.text ?? "");
                            setEditorOpen(true);
                        },
                        children: t("Edit lyrics")
                    }, void 0, false, {
                        fileName: "[project]/src/components/lyrics-overlay.tsx",
                        lineNumber: 828,
                        columnNumber: 9
                    }, this)
                ]
            }, void 0, true, {
                fileName: "[project]/src/components/lyrics-overlay.tsx",
                lineNumber: 794,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/src/components/lyrics-overlay.tsx",
        lineNumber: 724,
        columnNumber: 5
    }, this);
}
_s(LyricsOverlay, "wZbK4Pz24t55c84iISjDV1gdeNY=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"],
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"]
    ];
});
_c1 = LyricsOverlay;
var _c, _c1;
__turbopack_context__.k.register(_c, "PlayerIcon");
__turbopack_context__.k.register(_c1, "LyricsOverlay");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/src/components/visualizer-overlay.tsx [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>VisualizerOverlay
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/jsx-dev-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/store/player-store.ts [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/i18n.tsx [app-client] (ecmascript)");
;
var _s = __turbopack_context__.k.signature();
"use client";
;
;
;
const audioGraphs = new WeakMap();
function VisualizerOverlay({ onClose }) {
    _s();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"])();
    const canvasRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const frameRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const frequenciesRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const phasesRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])([]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "VisualizerOverlay.useEffect": ()=>{
            const canvas = canvasRef.current;
            const audio = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$store$2f$player$2d$store$2e$ts__$5b$app$2d$client$5d$__$28$ecmascript$29$__["usePlayerStore"].getState().audioElement;
            if (!canvas || !audio) return;
            let graph = audioGraphs.get(audio);
            if (!graph) {
                const AudioContextConstructor = window.AudioContext ?? window.webkitAudioContext;
                if (!AudioContextConstructor) return;
                try {
                    const context = new AudioContextConstructor();
                    const analyser = context.createAnalyser();
                    analyser.fftSize = 256;
                    const source = context.createMediaElementSource(audio);
                    source.connect(analyser);
                    analyser.connect(context.destination);
                    graph = {
                        context,
                        analyser
                    };
                    audioGraphs.set(audio, graph);
                } catch (error) {
                    console.warn("Visualizer audio analysis unavailable", error);
                    return;
                }
            }
            frequenciesRef.current = new Uint8Array(graph.analyser.frequencyBinCount);
            phasesRef.current = new Array(graph.analyser.frequencyBinCount).fill(0);
            if (graph.context.state === "suspended") void graph.context.resume();
            const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
            const draw = {
                "VisualizerOverlay.useEffect.draw": ()=>{
                    const ctx = canvas.getContext("2d");
                    const data = frequenciesRef.current;
                    if (!ctx || !data) return;
                    const rect = canvas.getBoundingClientRect();
                    const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
                    const width = Math.max(1, Math.round(rect.width * ratio));
                    const height = Math.max(1, Math.round(rect.height * ratio));
                    if (canvas.width !== width || canvas.height !== height) {
                        canvas.width = width;
                        canvas.height = height;
                    }
                    ctx.clearRect(0, 0, width, height);
                    graph.analyser.getByteFrequencyData(data);
                    const centerX = width / 2;
                    const centerY = height / 2;
                    const baseRadius = Math.min(width, height) * 0.2;
                    ctx.save();
                    ctx.translate(centerX, centerY);
                    const glow = ctx.createRadialGradient(0, 0, baseRadius * 0.3, 0, 0, baseRadius * 2.2);
                    glow.addColorStop(0, "rgba(139,127,255,.18)");
                    glow.addColorStop(0.6, "rgba(84,232,212,.06)");
                    glow.addColorStop(1, "rgba(8,10,16,0)");
                    ctx.fillStyle = glow;
                    ctx.beginPath();
                    ctx.arc(0, 0, baseRadius * 2.2, 0, Math.PI * 2);
                    ctx.fill();
                    const bars = 64;
                    const phases = phasesRef.current;
                    for(let index = 0; index < bars; index += 1){
                        const value = data[index] / 255;
                        phases[index] += (value - phases[index]) * 0.16;
                        const angle = index / bars * Math.PI * 2 - Math.PI / 2;
                        const startRadius = baseRadius + 10;
                        const endRadius = startRadius + phases[index] * baseRadius * 0.95;
                        const x1 = Math.cos(angle) * startRadius;
                        const y1 = Math.sin(angle) * startRadius;
                        const x2 = Math.cos(angle) * endRadius;
                        const y2 = Math.sin(angle) * endRadius;
                        const gradient = ctx.createLinearGradient(x1, y1, x2, y2);
                        gradient.addColorStop(0, "rgba(84,232,212,.9)");
                        gradient.addColorStop(1, "rgba(139,127,255,.75)");
                        ctx.strokeStyle = gradient;
                        ctx.lineWidth = Math.max(2, width * 0.004);
                        ctx.lineCap = "round";
                        ctx.beginPath();
                        ctx.moveTo(x1, y1);
                        ctx.lineTo(x2, y2);
                        ctx.stroke();
                    }
                    ctx.beginPath();
                    ctx.arc(0, 0, baseRadius, 0, Math.PI * 2);
                    ctx.fillStyle = "rgba(242,243,247,.06)";
                    ctx.fill();
                    ctx.strokeStyle = "rgba(212,208,255,.36)";
                    ctx.lineWidth = Math.max(1, width * 0.002);
                    ctx.stroke();
                    ctx.restore();
                    frameRef.current = reducedMotion.matches ? null : requestAnimationFrame(draw);
                }
            }["VisualizerOverlay.useEffect.draw"];
            const handleMotionPreferenceChange = {
                "VisualizerOverlay.useEffect.handleMotionPreferenceChange": ()=>{
                    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
                    frameRef.current = requestAnimationFrame(draw);
                }
            }["VisualizerOverlay.useEffect.handleMotionPreferenceChange"];
            reducedMotion.addEventListener("change", handleMotionPreferenceChange);
            frameRef.current = requestAnimationFrame(draw);
            return ({
                "VisualizerOverlay.useEffect": ()=>{
                    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
                    frameRef.current = null;
                    reducedMotion.removeEventListener("change", handleMotionPreferenceChange);
                }
            })["VisualizerOverlay.useEffect"];
        }
    }["VisualizerOverlay.useEffect"], []);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
        className: "viz-overlay open",
        role: "dialog",
        "aria-modal": "true",
        "aria-label": t("Audio visualizer"),
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                className: "viz-layout",
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("div", {
                    className: "viz-stage",
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("canvas", {
                        ref: canvasRef,
                        "aria-label": t("Audio frequency visualizer")
                    }, void 0, false, {
                        fileName: "[project]/src/components/visualizer-overlay.tsx",
                        lineNumber: 130,
                        columnNumber: 36
                    }, this)
                }, void 0, false, {
                    fileName: "[project]/src/components/visualizer-overlay.tsx",
                    lineNumber: 130,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/src/components/visualizer-overlay.tsx",
                lineNumber: 129,
                columnNumber: 7
            }, this),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("button", {
                className: "viz-close",
                type: "button",
                "aria-label": t("Close visualizer"),
                onClick: onClose,
                children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("svg", {
                    viewBox: "0 0 24 24",
                    fill: "none",
                    stroke: "currentColor",
                    strokeWidth: "1.8",
                    children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxDEV"])("path", {
                        d: "m7 7 10 10M17 7 7 17"
                    }, void 0, false, {
                        fileName: "[project]/src/components/visualizer-overlay.tsx",
                        lineNumber: 133,
                        columnNumber: 86
                    }, this)
                }, void 0, false, {
                    fileName: "[project]/src/components/visualizer-overlay.tsx",
                    lineNumber: 133,
                    columnNumber: 9
                }, this)
            }, void 0, false, {
                fileName: "[project]/src/components/visualizer-overlay.tsx",
                lineNumber: 132,
                columnNumber: 7
            }, this)
        ]
    }, void 0, true, {
        fileName: "[project]/src/components/visualizer-overlay.tsx",
        lineNumber: 128,
        columnNumber: 5
    }, this);
}
_s(VisualizerOverlay, "OWUZsNtz1M5s+spPhbfdSCqHPe8=", false, function() {
    return [
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$i18n$2e$tsx__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useLanguage"]
    ];
});
_c = VisualizerOverlay;
var _c;
__turbopack_context__.k.register(_c, "VisualizerOverlay");
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
"[project]/src/lib/api/client.ts [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ApiError",
    ()=>ApiError,
    "apiFetch",
    ()=>apiFetch,
    "expectOk",
    ()=>expectOk,
    "fetchWithRetry",
    ()=>fetchWithRetry,
    "getCsrfToken",
    ()=>getCsrfToken,
    "uploadWithRetry",
    ()=>uploadWithRetry
]);
const CSRF_PATH = "/api/csrf";
class ApiError extends Error {
    status;
    retryAfter;
    constructor(message, status, retryAfter = null){
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.retryAfter = retryAfter;
    }
}
let csrfToken = null;
let csrfRequest = null;
function isRecord(value) {
    return typeof value === "object" && value !== null;
}
function redirectToLoginOnUnauthorized(input, response) {
    if (("TURBOPACK compile-time value", "object") !== "undefined" && input.startsWith("/api/") && response.status === 401) {
        window.location.assign("/login");
    }
}
async function responseError(response) {
    let message = `Request failed (${response.status})`;
    const body = await response.text().catch(()=>"");
    if (body) {
        try {
            const parsed = JSON.parse(body);
            if (isRecord(parsed) && typeof parsed.detail === "string") {
                message = parsed.detail;
            }
        } catch  {
            const text = body.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
            if (text) message = text.slice(0, 500);
        }
    }
    const retryAfterHeader = response.headers.get("Retry-After");
    const parsedRetryAfter = retryAfterHeader === null ? NaN : Number(retryAfterHeader);
    return new ApiError(message, response.status, Number.isFinite(parsedRetryAfter) ? parsedRetryAfter : null);
}
async function getCsrfToken(forceRefresh = false) {
    if (csrfToken && !forceRefresh) return csrfToken;
    if (csrfRequest && !forceRefresh) return csrfRequest;
    csrfRequest = (async ()=>{
        const response = await fetch(CSRF_PATH, {
            credentials: "same-origin",
            cache: "no-store"
        });
        if (!response.ok) throw await responseError(response);
        const payload = await response.json();
        if (!isRecord(payload) || typeof payload.csrf_token !== "string") {
            throw new Error("The backend returned an invalid CSRF token response.");
        }
        csrfToken = payload.csrf_token;
        return csrfToken;
    })().finally(()=>{
        csrfRequest = null;
    });
    return csrfRequest;
}
async function apiFetch(input, init = {}, options = {}) {
    const send = async (refreshCsrf)=>{
        const headers = new Headers(init.headers);
        if (options.csrf) {
            headers.set("X-CSRF-Token", await getCsrfToken(refreshCsrf));
        }
        return fetch(input, {
            ...init,
            headers,
            credentials: init.credentials ?? "same-origin"
        });
    };
    let response = await send(false);
    if (options.csrf && options.retryCsrfOnForbidden && response.status === 403) {
        response = await send(true);
    }
    redirectToLoginOnUnauthorized(input, response);
    return response;
}
async function expectOk(response) {
    if (!response.ok) throw await responseError(response);
    return response;
}
const wait = (milliseconds)=>new Promise((resolve)=>setTimeout(resolve, milliseconds));
async function fetchWithRetry(input, init = {}, attempts = 5) {
    let lastError = new Error("The backend is unavailable.");
    for(let attempt = 0; attempt < attempts; attempt += 1){
        const controller = new AbortController();
        const timeout = setTimeout(()=>controller.abort(), 30_000);
        try {
            const response = await fetch(input, {
                ...init,
                credentials: init.credentials ?? "same-origin",
                signal: controller.signal
            });
            redirectToLoginOnUnauthorized(input, response);
            if (response.ok || response.status === 401 || response.status === 403 || response.status === 404) {
                return response;
            }
            lastError = await responseError(response);
        } catch (error) {
            lastError = error instanceof Error ? error : new Error("The backend is unavailable.");
        } finally{
            clearTimeout(timeout);
        }
        if (attempt < attempts - 1) {
            await wait(Math.min(2_000 * 2 ** attempt, 10_000));
        }
    }
    throw lastError;
}
async function uploadWithRetry(path, file) {
    const body = new FormData();
    body.append("file", file, file.name);
    let rateLimitRetries = 0;
    while(true){
        const response = await apiFetch(path, {
            method: "POST",
            body
        }, {
            csrf: true,
            retryCsrfOnForbidden: true
        });
        if (response.status !== 429) {
            return expectOk(response);
        }
        const retryAfterHeader = response.headers.get("Retry-After");
        const retryAfter = retryAfterHeader === null ? NaN : Number(retryAfterHeader);
        if (Number.isFinite(retryAfter) && retryAfter > 60) {
            throw new ApiError(`Upload rate limited. Try again in ${Math.ceil(retryAfter / 60)} min.`, 429, retryAfter);
        }
        if (rateLimitRetries >= 3) {
            throw new ApiError("Upload is still rate limited. Wait a few minutes and try again.", 429, Number.isFinite(retryAfter) ? retryAfter : null);
        }
        await wait(Math.min(30_000, Math.max(1_000, Number.isFinite(retryAfter) ? retryAfter * 1_000 : 1_000)));
        rateLimitRetries += 1;
    }
}
if (typeof globalThis.$RefreshHelpers$ === 'object' && globalThis.$RefreshHelpers !== null) {
    __turbopack_context__.k.registerExports(__turbopack_context__.m, globalThis.$RefreshHelpers$);
}
}),
]);

//# sourceMappingURL=src_1imgebt._.js.map