var __defProp = Object.defineProperty;
var __defProps = Object.defineProperties;
var __getOwnPropDescs = Object.getOwnPropertyDescriptors;
var __getOwnPropSymbols = Object.getOwnPropertySymbols;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __propIsEnum = Object.prototype.propertyIsEnumerable;
var __knownSymbol = (name, symbol) => (symbol = Symbol[name]) ? symbol : /* @__PURE__ */ Symbol.for("Symbol." + name);
var __pow = Math.pow;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __spreadValues = (a, b) => {
  for (var prop in b || (b = {}))
    if (__hasOwnProp.call(b, prop))
      __defNormalProp(a, prop, b[prop]);
  if (__getOwnPropSymbols)
    for (var prop of __getOwnPropSymbols(b)) {
      if (__propIsEnum.call(b, prop))
        __defNormalProp(a, prop, b[prop]);
    }
  return a;
};
var __spreadProps = (a, b) => __defProps(a, __getOwnPropDescs(b));
var __async = (__this, __arguments, generator) => {
  return new Promise((resolve, reject) => {
    var fulfilled = (value) => {
      try {
        step(generator.next(value));
      } catch (e) {
        reject(e);
      }
    };
    var rejected = (value) => {
      try {
        step(generator.throw(value));
      } catch (e) {
        reject(e);
      }
    };
    var step = (x) => x.done ? resolve(x.value) : Promise.resolve(x.value).then(fulfilled, rejected);
    step((generator = generator.apply(__this, __arguments)).next());
  });
};
var __forAwait = (obj, it, method) => (it = obj[__knownSymbol("asyncIterator")]) ? it.call(obj) : (obj = obj[__knownSymbol("iterator")](), it = {}, method = (key, fn) => (fn = obj[key]) && (it[key] = (arg) => new Promise((yes, no, done) => (arg = fn.call(obj, arg), done = arg.done, Promise.resolve(arg.value).then((value) => yes({ value, done }), no)))), method("next"), method("return"), it);
(() => {
  "use strict";
  var _a, _b;
  const configuredApiBase = (_a = document.querySelector('meta[name="api-base"]')) == null ? void 0 : _a.content;
  const API_BASE = (configuredApiBase && !configuredApiBase.startsWith("__") ? configuredApiBase : "https://verfy-5znt.onrender.com").replace(/\/+$/, "");
  function apiUrl(path) {
    return `${API_BASE}${path}`;
  }
  function loginPageUrl() {
    return apiUrl("/login");
  }
  // Older smart-TV browsers often have XMLHttpRequest but no fetch API.
  if (!window.fetch && window.XMLHttpRequest && window.Promise) {
    window.fetch = function (input, options) {
      if (options === void 0) options = {};
      return new Promise(function (resolve, reject) {
        var request = new XMLHttpRequest();
        var method = options.method || "GET";
        request.open(method, input, true);
        request.withCredentials = options.credentials === "include";
        if (options.headers) {
          Object.keys(options.headers).forEach(function (name) {
            request.setRequestHeader(name, options.headers[name]);
          });
        }
        request.onload = function () {
          var body = request.responseText || "";
          resolve({
            status: request.status,
            ok: request.status >= 200 && request.status < 300,
            text: function () { return Promise.resolve(body); },
            json: function () { return Promise.resolve(JSON.parse(body)); }
          });
        };
        request.onerror = function () { reject(new Error("Network request failed")); };
        request.ontimeout = function () { reject(new Error("Network request timed out")); };
        request.timeout = 3e4;
        request.send(options.body || null);
      });
    };
  }
  function logoutAndRedirect() {
    return __async(this, null, function* () {
      try {
        yield fetch(apiUrl("/logout"), {
          method: "POST",
          headers: { "X-CSRF-Token": yield ensureCsrfToken() },
          redirect: "manual"
        });
      } catch (_) {
      }
      window.location.assign(loginPageUrl());
    });
  }
  (() => {
    const _fetch = window.fetch.bind(window);
    window.fetch = (...args) => __async(null, null, function* () {
      if (typeof args[0] === "string" && args[0].startsWith("/api/")) {
        args[0] = apiUrl(args[0]);
      }
      const url = typeof args[0] === "string" ? args[0] : args[0] && args[0].url || "";
      const isOurApi = typeof url === "string" && url.startsWith(API_BASE);
      if (isOurApi) {
        if (typeof args[1] === "object" && args[1] !== null) {
          args[1] = __spreadProps(__spreadValues({}, args[1]), { credentials: "include" });
        } else {
          args[1] = { credentials: "include" };
        }
      }
      const response = yield _fetch(...args);
      if (isOurApi && response.status === 401) {
        window.location.assign(loginPageUrl());
      }
      return response;
    });
  })();
  const state = {
    tracks: [],
    // {id,title,artist,album,year,art,duration,favorite,file,fingerprint}
    playlists: [],
    // {id,name,trackIds:[]}
    view: "library",
    // library | playlists | artists | favorites | queue | playlist:<id> | artist:<name>
    listMode: "grid",
    search: "",
    queue: [],
    // array of track ids, the play order
    queueIndex: -1,
    shuffle: false,
    repeat: "off",
    // off | all | one
    volume: 0.7,
    muted: false
  };
  let audioEl = new Audio();
  audioEl.preload = "metadata";
  let audioCtx = null, analyser = null, sourceNode = null, freqData = null;
  let rafViz = null;
  const mediaSession = navigator.mediaSession || null;
  function mediaArtworkFor(track) {
    if (!track || !track.art) return [];
    let src = track.art;
    try {
      src = new URL(track.art, window.location.href).href;
    } catch (_) {
    }
    return [96, 128, 192, 256, 384, 512].map((size) => ({
      src,
      sizes: `${size}x${size}`,
      type: "image/jpeg"
    }));
  }
  function updateMediaSessionMetadata() {
    if (!mediaSession || !window.MediaMetadata) return;
    const track = currentTrack();
    if (!track) return;
    try {
      mediaSession.metadata = new MediaMetadata({
        title: track.title || "Unknown title",
        artist: artistCreditsLabel(track) || "Unknown artist",
        album: track.album || "",
        artwork: mediaArtworkFor(track)
      });
    } catch (err) {
      console.warn("Could not set system media metadata", err);
    }
  }
  function updateMediaSessionPosition() {
    if (!mediaSession || !mediaSession.setPositionState) return;
    const duration = audioEl.duration;
    const position = audioEl.currentTime;
    if (!Number.isFinite(duration) || duration <= 0 || !Number.isFinite(position)) return;
    try {
      mediaSession.setPositionState({
        duration,
        position: Math.max(0, Math.min(position, duration)),
        playbackRate: audioEl.playbackRate || 1
      });
    } catch (_) {
    }
  }
  const AURA_PALETTE = [
    ["#8b7fff", "#54e8d4"],
    ["#ff8fb1", "#8b7fff"],
    ["#54e8d4", "#3aa0ff"],
    ["#ffb86b", "#ff6b9d"],
    ["#6bd6ff", "#8b7fff"],
    ["#c084fc", "#54e8d4"]
  ];
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));
  const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  function fmtTime(s) {
    if (!isFinite(s) || s < 0) s = 0;
    const m = Math.floor(s / 60), sec = Math.floor(s % 60);
    return m + ":" + String(sec).padStart(2, "0");
  }
  function fmtLongDuration(s) {
    if (!Number.isFinite(s) || s < 0) return "0 min";
    const totalMinutes = Math.round(s / 60);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    if (hours === 0) return `${minutes} min`;
    return minutes ? `${hours} hr ${minutes} min` : `${hours} hr`;
  }
  function hashStr(str) {
    let h = 0;
    for (let i = 0; i < str.length; i++) {
      h = Math.imul(31, h) + str.charCodeAt(i) | 0;
    }
    return Math.abs(h);
  }
  function toast(msg) {
    const el = document.createElement("div");
    el.className = "toast";
    el.textContent = msg;
    $("#toastWrap").appendChild(el);
    setTimeout(() => {
      el.style.transition = "opacity .3s";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 300);
    }, 2600);
  }
  function generateAura(seed, size = 300) {
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    const h = hashStr(seed);
    const palette = AURA_PALETTE[h % AURA_PALETTE.length];
    const angle = h % 360 * Math.PI / 180;
    const cx = size / 2 + Math.cos(angle) * size * 0.15;
    const cy = size / 2 + Math.sin(angle) * size * 0.15;
    ctx.fillStyle = "#12151e";
    ctx.fillRect(0, 0, size, size);
    const g1 = ctx.createRadialGradient(cx, cy, 0, cx, cy, size * 0.75);
    g1.addColorStop(0, palette[0]);
    g1.addColorStop(0.5, palette[1] + "55");
    g1.addColorStop(1, "#0c0e1400");
    ctx.globalAlpha = 0.9;
    ctx.fillStyle = g1;
    ctx.fillRect(0, 0, size, size);
    const cx2 = size - cx, cy2 = size - cy;
    const g2 = ctx.createRadialGradient(cx2, cy2, 0, cx2, cy2, size * 0.6);
    g2.addColorStop(0, palette[1]);
    g2.addColorStop(1, "#0c0e1400");
    ctx.globalAlpha = 0.55;
    ctx.fillStyle = g2;
    ctx.fillRect(0, 0, size, size);
    ctx.globalAlpha = 0.16;
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1;
    for (let r = size * 0.12; r < size * 0.55; r += size * 0.12) {
      ctx.beginPath();
      ctx.arc(cx, cy, r, h % 628 / 100, h % 628 / 100 + Math.PI * 1.3);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    return canvas.toDataURL("image/jpeg", 0.85);
  }
  let LYRICS_SYNC_DEBUG = false;
  let _lyricsLastLoggedIdx = null;
  let lyricsSyncClockRaf = null;
  const LyricsDebug = {
    log(...args) {
      if (LYRICS_SYNC_DEBUG) console.log("%c[lyrics-sync]", "color:#54e8d4;font-weight:600;", ...args);
    },
    warn(...args) {
      if (LYRICS_SYNC_DEBUG) console.warn("[lyrics-sync]", ...args);
    }
  };
  function syncsafe(bytes, offset) {
    return (bytes[offset] & 127) << 21 | (bytes[offset + 1] & 127) << 14 | (bytes[offset + 2] & 127) << 7 | bytes[offset + 3] & 127;
  }
  function beInt(bytes, offset, len) {
    let v = 0;
    for (let i = 0; i < len; i++) v = v << 8 | bytes[offset + i];
    return v >>> 0;
  }
  function decodeText(bytes, encByte) {
    try {
      if (encByte === 0) return new TextDecoder("latin1").decode(bytes).replace(/\0+$/, "");
      if (encByte === 1) return new TextDecoder("utf-16").decode(bytes).replace(/\0+$/, "");
      if (encByte === 2) return new TextDecoder("utf-16be").decode(bytes).replace(/\0+$/, "");
      return new TextDecoder("utf-8").decode(bytes).replace(/\0+$/, "");
    } catch (e) {
      return "";
    }
  }
  function findNullTerm(bytes, start, wide) {
    for (let i = start; i < bytes.length - (wide ? 1 : 0); i += wide ? 2 : 1) {
      if (wide) {
        if (bytes[i] === 0 && bytes[i + 1] === 0) return i;
      } else {
        if (bytes[i] === 0) return i;
      }
    }
    return bytes.length;
  }
  function decodeMpegFrameHeader(bytes, offset) {
    if (bytes[offset] !== 255 || (bytes[offset + 1] & 224) !== 224) return null;
    const verId = bytes[offset + 1] >> 3 & 3;
    const layerId = bytes[offset + 1] >> 1 & 3;
    const srIndex = bytes[offset + 2] >> 2 & 3;
    if (verId === 1 || layerId === 0 || srIndex === 3) return null;
    const SAMPLE_RATES = { 3: [44100, 48e3, 32e3], 2: [22050, 24e3, 16e3], 0: [11025, 12e3, 8e3] };
    const sampleRate = SAMPLE_RATES[verId][srIndex];
    if (!sampleRate) return null;
    let samplesPerFrame;
    if (layerId === 3) samplesPerFrame = 384;
    else if (layerId === 2) samplesPerFrame = 1152;
    else samplesPerFrame = verId === 3 ? 1152 : 576;
    return { sampleRate, samplesPerFrame, msPerFrame: samplesPerFrame / sampleRate * 1e3 };
  }
  function detectMpegFrameDurationMs(file, streamStartOffset) {
    return __async(this, null, function* () {
      try {
        const windowSize = Math.min(16384, Math.max(0, file.size - streamStartOffset));
        if (windowSize < 4) return null;
        const buf = yield file.slice(streamStartOffset, streamStartOffset + windowSize).arrayBuffer();
        const bytes = new Uint8Array(buf);
        for (let i = 0; i < bytes.length - 4; i++) {
          const hdr = decodeMpegFrameHeader(bytes, i);
          if (hdr) return hdr;
        }
      } catch (e) {
        LyricsDebug.warn("frame-duration detection failed:", e.message);
      }
      return null;
    });
  }
  function parseSyltFrame(frame, msPerUnit) {
    try {
      const enc = frame[0];
      const wide = enc === 1 || enc === 2;
      let idx = 6;
      const descEnd = findNullTerm(frame, idx, wide);
      idx = descEnd + (wide ? 2 : 1);
      const lines = [];
      let dropped = 0;
      while (idx < frame.length) {
        const textEnd = findNullTerm(frame, idx, wide);
        if (textEnd >= frame.length) break;
        const text = decodeText(frame.subarray(idx, textEnd), enc);
        idx = textEnd + (wide ? 2 : 1);
        if (idx + 4 > frame.length) break;
        const timestamp = beInt(frame, idx, 4);
        idx += 4;
        const time = timestamp * msPerUnit;
        if (Number.isFinite(time)) lines.push({ time, text });
        else dropped++;
      }
      if (dropped) LyricsDebug.warn(`SYLT: dropped ${dropped} entr${dropped === 1 ? "y" : "ies"} with invalid timestamps`);
      return lines.length ? lines : null;
    } catch (e) {
      LyricsDebug.warn("SYLT parse threw:", e.message);
      return null;
    }
  }
  function parseUsltFrame(frame) {
    try {
      const enc = frame[0];
      const wide = enc === 1 || enc === 2;
      let idx = 4;
      const descEnd = findNullTerm(frame, idx, wide);
      idx = descEnd + (wide ? 2 : 1);
      const text = decodeText(frame.subarray(idx), enc);
      return text && text.trim() ? text : null;
    } catch (e) {
      LyricsDebug.warn("USLT parse threw:", e.message);
      return null;
    }
  }
  function parseID3(file) {
    return __async(this, null, function* () {
      const meta = { title: null, artist: null, album: null, year: null, picture: null, sylt: null, uslt: null };
      try {
        const headBuf = yield file.slice(0, 10).arrayBuffer();
        const head = new Uint8Array(headBuf);
        if (!(head[0] === 73 && head[1] === 68 && head[2] === 51)) return meta;
        const majorVer = head[3];
        const tagSize = syncsafe(head, 6);
        if (tagSize <= 0) return meta;
        const bodyBuf = yield file.slice(10, 10 + tagSize).arrayBuffer();
        const body = new Uint8Array(bodyBuf);
        let pos = 0;
        while (pos < body.length - 4) {
          let frameId, frameSize, headerLen;
          if (majorVer === 2) {
            frameId = String.fromCharCode(body[pos], body[pos + 1], body[pos + 2]);
            if (frameId === "\0\0\0") break;
            frameSize = beInt(body, pos + 3, 3);
            headerLen = 6;
          } else {
            frameId = String.fromCharCode(body[pos], body[pos + 1], body[pos + 2], body[pos + 3]);
            if (frameId === "\0\0\0\0") break;
            frameSize = majorVer === 4 ? syncsafe(body, pos + 4) : beInt(body, pos + 4, 4);
            headerLen = 10;
          }
          const dataStart = pos + headerLen;
          const dataEnd = dataStart + frameSize;
          if (frameSize <= 0 || dataEnd > body.length) break;
          const frame = body.subarray(dataStart, dataEnd);
          if (["TIT2", "TT2"].includes(frameId)) meta.title = decodeText(frame.subarray(1), frame[0]);
          else if (["TPE1", "TP1"].includes(frameId)) meta.artist = decodeText(frame.subarray(1), frame[0]);
          else if (["TALB", "TAL"].includes(frameId)) meta.album = decodeText(frame.subarray(1), frame[0]);
          else if (["TYER", "TDRC", "TYE"].includes(frameId)) meta.year = decodeText(frame.subarray(1), frame[0]).slice(0, 4);
          else if (["APIC", "PIC"].includes(frameId) && !meta.picture) {
            try {
              const enc = frame[0];
              let idx = 1, mime = "image/jpeg";
              if (frameId === "APIC") {
                const mimeEnd = findNullTerm(frame, idx, false);
                mime = decodeText(frame.subarray(idx, mimeEnd), 0) || "image/jpeg";
                idx = mimeEnd + 1;
                idx += 1;
                const wide = enc === 1 || enc === 2;
                const descEnd = findNullTerm(frame, idx, wide);
                idx = descEnd + (wide ? 2 : 1);
              } else {
                const fmt = String.fromCharCode(frame[idx], frame[idx + 1], frame[idx + 2]);
                mime = fmt.toUpperCase() === "PNG" ? "image/png" : "image/jpeg";
                idx += 3 + 1;
                const wide = enc === 1 || enc === 2;
                const descEnd = findNullTerm(frame, idx, wide);
                idx = descEnd + (wide ? 2 : 1);
              }
              const imgBytes = frame.subarray(idx);
              if (imgBytes.length > 100) {
                const blob = new Blob([imgBytes], { type: mime });
                meta.picture = URL.createObjectURL(blob);
              }
            } catch (e) {
            }
          } else if (["SYLT", "SLT"].includes(frameId) && !meta.sylt) {
            const tsFormat = frame[4];
            let msPerUnit = 1;
            if (tsFormat === 1) {
              const hdr = yield detectMpegFrameDurationMs(file, 10 + tagSize);
              if (hdr) {
                msPerUnit = hdr.msPerFrame;
                LyricsDebug.log(`${file.name}: SYLT uses MPEG-frame timestamps; detected ${hdr.sampleRate}Hz stream \u2192 ${hdr.msPerFrame.toFixed(3)}ms/frame`);
              } else {
                msPerUnit = 26.122;
                LyricsDebug.warn(`${file.name}: SYLT uses MPEG-frame timestamps but no valid audio frame header was found; falling back to a 44.1kHz estimate (times may drift)`);
              }
            }
            const lines = parseSyltFrame(frame, msPerUnit);
            if (lines) {
              lines.sort((a, b) => a.time - b.time);
              meta.sylt = lines;
              LyricsDebug.log(`${file.name}: SYLT parsed \u2014 ${lines.length} lines, first="${lines[0].text}" @${(lines[0].time / 1e3).toFixed(2)}s, last @${(lines[lines.length - 1].time / 1e3).toFixed(2)}s`);
            }
          } else if (["USLT", "ULT"].includes(frameId) && !meta.uslt) {
            const text = parseUsltFrame(frame);
            if (text) meta.uslt = text;
          }
          pos = dataEnd;
        }
      } catch (e) {
      }
      return meta;
    });
  }
  function titleFromFilename(name) {
    return name.replace(/\.[^.]+$/, "").replace(/^\d+[\s._-]*/, "").replace(/[_]+/g, " ").trim() || "Untitled";
  }
  const LyricsEngine = /* @__PURE__ */ (() => {
    function fromID3(meta) {
      if (!meta) return null;
      if (meta.sylt && meta.sylt.length) return { source: "sylt", lines: meta.sylt };
      if (meta.uslt) return { source: "uslt", text: meta.uslt };
      return null;
    }
    function fromLRC(lrcText) {
      if (!lrcText) return null;
      const stamp = /\[(\d{1,2}):(\d{2}(?:[.:]\d{1,3})?)\]/g;
      const lines = [];
      lrcText.split(/\r?\n/).forEach((raw) => {
        const matches = [...raw.matchAll(stamp)];
        if (matches.length === 0) return;
        const text = raw.replace(stamp, "").trim();
        matches.forEach((m) => {
          const time = (parseInt(m[1], 10) * 60 + parseFloat(m[2].replace(":", "."))) * 1e3;
          lines.push({ time, text });
        });
      });
      if (lines.length === 0) return null;
      lines.sort((a, b) => a.time - b.time);
      return { source: "lrc", lines };
    }
    const LRCLIB_BASE = "https://lrclib.net/api";
    function lrclibResultToLyrics(data) {
      if (!data || data.instrumental) return null;
      if (data.syncedLyrics && data.syncedLyrics.trim()) {
        const parsed = fromLRC(data.syncedLyrics);
        if (parsed) return { source: "online-synced", lines: parsed.lines };
      }
      if (data.plainLyrics && data.plainLyrics.trim()) {
        return { source: "online-plain", text: data.plainLyrics };
      }
      return null;
    }
    function fromOnline(track) {
      return __async(this, null, function* () {
        if (!track || !track.title) {
          LyricsDebug.log("online: skipped, no title to search with");
          return null;
        }
        const artist = (track.artist || "").trim();
        if (!artist || /^unknown artist$/i.test(artist)) {
          LyricsDebug.log(`online: skipped for "${track.title}" \u2014 artist is unknown, a search would be unreliable`);
          return null;
        }
        const durationSec = Math.round(track.duration || 0);
        const baseParams = { track_name: track.title, artist_name: artist };
        const album = (track.album || "").trim();
        if (album && !/^unknown album$/i.test(album)) baseParams.album_name = album;
        if (durationSec > 0) {
          try {
            const url = `${LRCLIB_BASE}/get?` + new URLSearchParams(__spreadProps(__spreadValues({}, baseParams), { duration: durationSec }));
            LyricsDebug.log("online: exact-match query \u2192", url);
            const res = yield fetch(url);
            LyricsDebug.log("online: exact-match response status", res.status);
            if (res.ok) {
              const data = yield res.json();
              const parsed = lrclibResultToLyrics(data);
              LyricsDebug.log("online: exact-match parsed result \u2192", parsed ? `${parsed.source}, ${parsed.lines ? parsed.lines.length + " lines" : parsed.text.length + " chars"}` : "none usable");
              if (parsed) return parsed;
            }
          } catch (e) {
            LyricsDebug.warn("online: exact-match request failed \u2014", e.message);
          }
        }
        try {
          const url = `${LRCLIB_BASE}/search?` + new URLSearchParams(baseParams);
          LyricsDebug.log("online: search query \u2192", url);
          const res = yield fetch(url);
          LyricsDebug.log("online: search response status", res.status);
          if (!res.ok) return null;
          const results = yield res.json();
          LyricsDebug.log(`online: search returned ${Array.isArray(results) ? results.length : 0} candidate(s)`);
          if (!Array.isArray(results) || results.length === 0) return null;
          const best = durationSec > 0 ? results.reduce((a, b) => Math.abs((a.duration || 0) - durationSec) <= Math.abs((b.duration || 0) - durationSec) ? a : b) : results[0];
          const parsed = lrclibResultToLyrics(best);
          LyricsDebug.log("online: best candidate", `"${best.trackName}" by ${best.artistName}`, "\u2192", parsed ? parsed.source : "no usable lyrics (instrumental or empty)");
          return parsed;
        } catch (e) {
          LyricsDebug.warn("online: search request failed \u2014", e.message);
          return null;
        }
      });
    }
    function resolve(track, idMeta) {
      return __async(this, null, function* () {
        let result = fromID3(idMeta);
        if (!result) result = yield fromOnline(track);
        return result || null;
      });
    }
    return { fromID3, fromLRC, fromOnline, resolve };
  })();
  const ArtistPhotoEngine = /* @__PURE__ */ (() => {
    const resolved = /* @__PURE__ */ new Map();
    const pending = /* @__PURE__ */ new Set();
    const queue = [];
    let activeRequests = 0;
    const MAX_CONCURRENT_REQUESTS = 4;
    function apply(name, url) {
      if (!url) return;
      document.querySelectorAll("[data-artist-photo]").forEach((img) => {
        if (img.dataset.artistPhoto !== name) return;
        const fallback = img.src;
        img.addEventListener("error", () => {
          img.src = fallback;
        }, { once: true });
        img.src = url;
      });
    }
    function lookup(name) {
      return __async(this, null, function* () {
        try {
          const res = yield fetch("/api/artists/photo?" + new URLSearchParams({ name }));
          const data = res.ok ? yield res.json() : null;
          const url = data && typeof data.url === "string" ? data.url : null;
          resolved.set(name, url);
          apply(name, url);
        } catch (_) {
          resolved.set(name, null);
        } finally {
          pending.delete(name);
        }
      });
    }
    function pump() {
      while (activeRequests < MAX_CONCURRENT_REQUESTS && queue.length) {
        const name = queue.shift();
        activeRequests++;
        lookup(name).finally(() => {
          activeRequests--;
          pump();
        });
      }
    }
    function resolve(name) {
      if (!name) return;
      if (resolved.has(name)) {
        apply(name, resolved.get(name));
        return;
      }
      if (pending.has(name)) return;
      pending.add(name);
      queue.push(name);
      pump();
    }
    function resolveAll(artists) {
      artists.forEach((artist) => resolve(artist.name));
    }
    return { resolve, resolveAll };
  })();
  const ArtistProfileEngine = /* @__PURE__ */ (() => {
    const resolved = /* @__PURE__ */ new Map();
    const pending = /* @__PURE__ */ new Set();
    function displayCount(value) {
      const number = Number(value);
      return Number.isFinite(number) ? new Intl.NumberFormat().format(number) : value;
    }
    function safeExternalUrl(value) {
      if (typeof value !== "string") return null;
      try {
        const url = new URL(value);
        return url.protocol === "https:" ? url.href : null;
      } catch (_) {
        return null;
      }
    }
    function apply(name, profile) {
      document.querySelectorAll("[data-artist-profile]").forEach((section) => {
        if (section.dataset.artistProfile !== name) return;
        section.setAttribute("aria-busy", "false");
        const bio = section.querySelector("[data-artist-bio]");
        const tags = section.querySelector("[data-artist-tags]");
        const website = section.querySelector("[data-artist-website]");
        const source = section.querySelector("[data-artist-source]");
        bio.textContent = (profile == null ? void 0 : profile.bio) || "No artist biography is available from the public catalog.";
        const facts = [
          ["Genre", profile == null ? void 0 : profile.genre],
          ["Style", profile == null ? void 0 : profile.style],
          ["Mood", profile == null ? void 0 : profile.mood],
          ["Formed", profile == null ? void 0 : profile.formed_year],
          ["Followers", (profile == null ? void 0 : profile.followers) && displayCount(profile.followers)],
          ["Popularity", (profile == null ? void 0 : profile.popularity) && `${profile.popularity}/100`],
          ["Label", profile == null ? void 0 : profile.label]
        ].filter(([, value]) => value);
        tags.replaceChildren(...facts.map(([label, value]) => {
          const tag = document.createElement("span");
          tag.className = "artist-tag";
          tag.textContent = `${label}: ${value}`;
          return tag;
        }));
        tags.hidden = facts.length === 0;
        const sourceUrl = safeExternalUrl((profile == null ? void 0 : profile.source_url) || (profile == null ? void 0 : profile.website));
        source.replaceChildren();
        if (profile == null ? void 0 : profile.source) {
          source.append(`Information for ${profile.lookup_name || name} from `);
          if (sourceUrl) {
            const sourceLink = document.createElement("a");
            sourceLink.href = sourceUrl;
            sourceLink.target = "_blank";
            sourceLink.rel = "noopener noreferrer";
            sourceLink.textContent = profile.source;
            source.append(sourceLink);
          } else {
            source.append(profile.source);
          }
          source.hidden = false;
        } else {
          source.textContent = "Artist information unavailable";
          source.hidden = true;
        }
        const websiteUrl = safeExternalUrl(profile == null ? void 0 : profile.website);
        if (websiteUrl) {
          website.href = websiteUrl;
          website.firstChild.textContent = profile.website_label || "Source page";
          website.hidden = false;
        } else {
          website.firstChild.textContent = "Source page";
          website.hidden = true;
        }
      });
    }
    function resolve(name) {
      return __async(this, null, function* () {
        if (!name) return;
        if (resolved.has(name)) {
          apply(name, resolved.get(name));
          return;
        }
        if (pending.has(name)) return;
        pending.add(name);
        try {
          const res = yield fetch("/api/artists/profile?" + new URLSearchParams({ name }));
          const data = res.ok ? yield res.json() : null;
          const profile = data && data.profile && typeof data.profile === "object" ? data.profile : null;
          resolved.set(name, profile);
          apply(name, profile);
        } catch (_) {
          resolved.set(name, null);
          apply(name, null);
        } finally {
          pending.delete(name);
        }
      });
    }
    return { resolve };
  })();
  const AuralisDB = /* @__PURE__ */ (() => {
    const DB_NAME = "auralis-db", DB_VERSION = 1;
    const STORE_KV = "kv", STORE_HANDLES = "handles";
    let dbPromise = null;
    function open() {
      if (dbPromise) return dbPromise;
      dbPromise = new Promise((resolve, reject) => {
        if (!("indexedDB" in window)) {
          reject(new Error("IndexedDB unsupported"));
          return;
        }
        const req = indexedDB.open(DB_NAME, DB_VERSION);
        req.onupgradeneeded = () => {
          const db = req.result;
          if (!db.objectStoreNames.contains(STORE_KV)) db.createObjectStore(STORE_KV);
          if (!db.objectStoreNames.contains(STORE_HANDLES)) db.createObjectStore(STORE_HANDLES);
        };
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      });
      return dbPromise;
    }
    function store(name, mode) {
      return __async(this, null, function* () {
        const db = yield open();
        return db.transaction(name, mode).objectStore(name);
      });
    }
    function get(_0) {
      return __async(this, arguments, function* (key, storeName = STORE_KV) {
        try {
          const s = yield store(storeName, "readonly");
          return yield new Promise((resolve, reject) => {
            const r = s.get(key);
            r.onsuccess = () => resolve(r.result === void 0 ? null : r.result);
            r.onerror = () => reject(r.error);
          });
        } catch (e) {
          return null;
        }
      });
    }
    function set(_0, _1) {
      return __async(this, arguments, function* (key, value, storeName = STORE_KV) {
        try {
          const s = yield store(storeName, "readwrite");
          yield new Promise((resolve, reject) => {
            const r = s.put(value, key);
            r.onsuccess = () => resolve();
            r.onerror = () => reject(r.error);
          });
          return true;
        } catch (e) {
          return false;
        }
      });
    }
    function del(_0) {
      return __async(this, arguments, function* (key, storeName = STORE_KV) {
        try {
          const s = yield store(storeName, "readwrite");
          yield new Promise((resolve, reject) => {
            const r = s.delete(key);
            r.onsuccess = () => resolve();
            r.onerror = () => reject(r.error);
          });
        } catch (e) {
        }
      });
    }
    return { get, set, del, STORE_KV, STORE_HANDLES };
  })();
  function saveSettings() {
    return __async(this, null, function* () {
      yield AuralisDB.set("auralis:settings", JSON.stringify({
        volume: state.volume,
        muted: state.muted,
        shuffle: state.shuffle,
        repeat: state.repeat,
        listMode: state.listMode
      }));
    });
  }
  function saveLibraryMeta() {
    return __async(this, null, function* () {
      const favorites = state.tracks.filter((t) => t.favorite).map((t) => t.id);
      const playlists = state.playlists.map((p) => ({
        id: p.id,
        name: p.name,
        trackIds: [...p.trackIds]
      }));
      try {
        const res = yield fetch("/api/library/state", {
          method: "PUT",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": yield ensureCsrfToken() },
          body: JSON.stringify({ favorites, playlists })
        });
        if (!res.ok) throw new Error("Could not save library state");
      } catch (error) {
        console.warn("Could not sync library state", error);
      }
    });
  }
  function loadPersisted() {
    return __async(this, null, function* () {
      var _a2;
      const [settings, library] = yield Promise.all([
        AuralisDB.get("auralis:settings"),
        AuralisDB.get("auralis:library")
      ]);
      try {
        if (settings) {
          const v = JSON.parse(settings);
          state.volume = (_a2 = v.volume) != null ? _a2 : 0.7;
          state.muted = !!v.muted;
          state.shuffle = !!v.shuffle;
          state.repeat = v.repeat || "off";
          state.listMode = v.listMode || "grid";
        }
      } catch (e) {
      }
      window._persistedLibrary = null;
      try {
        if (library) window._persistedLibrary = JSON.parse(library);
      } catch (e) {
      }
    });
  }
  function relinkPersistedLibrary() {
    const persisted = window._persistedLibrary;
    if (!persisted) return;
    const byId = new Map(state.tracks.map((t) => [t.id, t]));
    (persisted.favorites || []).forEach((key) => {
      const t = byId.get(key);
      if (t) t.favorite = true;
    });
    (persisted.playlists || []).forEach((p) => {
      let existing = state.playlists.find((pl) => pl.id === p.id);
      if (!existing) {
        existing = { id: p.id, name: p.name, trackIds: [] };
        state.playlists.push(existing);
      }
      const keys = p.trackIds || p.fingerprints || [];
      keys.forEach((key) => {
        const t = byId.get(key);
        if (t && !existing.trackIds.includes(t.id)) existing.trackIds.push(t.id);
      });
    });
  }
  function trackFromServer(payload) {
    const customLyrics = payload.custom_lyrics || null;
    return {
      id: payload.id,
      title: payload.title || "Unknown title",
      artist: payload.artist || "Unknown artist",
      album: payload.album || "Unknown album",
      year: "",
      duration: payload.duration || 0,
      art: payload.cover_url || generateAura((payload.artist || "") + "|" + (payload.album || "") + "|" + (payload.title || "")),
      streamUrl: payload.stream_url,
      favorite: false,
      dateAdded: Date.now(),
      lyrics: customLyrics ? LyricsEngine.fromLRC(customLyrics) || { source: "custom", text: customLyrics } : null,
      customLyrics,
      lyricsResolved: !!customLyrics,
      lyricsLoading: false,
      fingerprint: payload.id
    };
  }
  let serverLibraryRequest = null;
  let serverLibraryLoading = true;
  let serverLibraryLoaded = false;
  let serverLibraryLoadFailed = false;
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  function fetchWithRetry(_0) {
  return __async(this, arguments, function* (url, options = {}, attempts = 5) {
    let lastError;

    for (let attempt = 0; attempt < attempts; attempt++) {
      let controller = null;
      let timeout = null;

      try {
        // Older Samsung TV browsers may not support AbortController.
        if (typeof AbortController !== "undefined") {
          controller = new AbortController();
          timeout = setTimeout(() => controller.abort(), 3e4);
        }

        const fetchOptions = __spreadValues({}, options);

        if (controller) {
          fetchOptions.signal = controller.signal;
        }

        const response = yield fetch(url, fetchOptions);

        if (
          response.ok ||
          response.status === 401 ||
          response.status === 403 ||
          response.status === 404
        ) {
          return response;
        }

        lastError = new Error(`Server returned ${response.status}`);
      } catch (error) {
        lastError = error;
      } finally {
        if (timeout) {
          clearTimeout(timeout);
        }
      }

      if (attempt < attempts - 1) {
        yield wait(Math.min(2e3 * __pow(2, attempt), 1e4));
      }
    }

    throw lastError || new Error("Server unavailable");
  });
}
  function loadServerLibrary(force = false) {
    return __async(this, null, function* () {
      if (!force && serverLibraryLoaded) {
        return state.tracks.length;
      }
      if (!force && serverLibraryRequest) {
        return serverLibraryRequest;
      }
      serverLibraryRequest = (() => __async(null, null, function* () {
        try {
          const [tracksRes, stateRes] = yield Promise.all([
            fetchWithRetry("/api/tracks"),
            fetch("/api/library/state")
          ]);
          if (!tracksRes.ok) throw new Error("bad status " + tracksRes.status);
          const data = yield tracksRes.json();
          state.tracks = (data.tracks || []).map(trackFromServer);
          const legacy = window._persistedLibrary;
          if (stateRes.ok) {
            const remote = yield stateRes.json();
            if (!(remote.favorites || []).length && !(remote.playlists || []).length && legacy && ((legacy.favorites || []).length || (legacy.playlists || []).length)) {
              relinkPersistedLibrary();
              yield saveLibraryMeta();
            } else {
              window._persistedLibrary = remote;
              relinkPersistedLibrary();
            }
          } else relinkPersistedLibrary();
          serverLibraryLoaded = true;
          serverLibraryLoading = false;
          serverLibraryLoadFailed = false;
          return state.tracks.length;
        } catch (e) {
          console.warn("Could not load server library", e);
          serverLibraryLoading = false;
          serverLibraryLoadFailed = true;
          return 0;
        } finally {
          serverLibraryRequest = null;
        }
      }))();
      return serverLibraryRequest;
    });
  }
  let csrfToken = ((_b = $("meta[name='csrf-token']")) == null ? void 0 : _b.content) || null;
  function ensureCsrfToken(forceRefresh = false) {
    return __async(this, null, function* () {
      if (csrfToken && !forceRefresh) return csrfToken;
      try {
        const res = yield fetch("/api/csrf");
        if (res.ok) {
          csrfToken = (yield res.json()).csrf_token;
          return csrfToken;
        }
      } catch (_) {
      }
      return null;
    });
  }
  function uploadFileToServer(file) {
    return __async(this, null, function* () {
      const body = new FormData();
      body.append("file", file, file.name);
      const res = yield fetch("/api/library/upload", {
        method: "POST",
        headers: { "X-CSRF-Token": yield ensureCsrfToken() },
        body
      });
      if (!res.ok) {
        let detail = "Upload failed";
        try {
          const err = yield res.json();
          detail = err.detail || detail;
        } catch (_) {
        }
        throw new Error(detail);
      }
      return trackFromServer(yield res.json());
    });
  }
  function deleteTrackOnServer(trackId) {
    return __async(this, null, function* () {
      try {
        const res = yield fetch(`/api/tracks/${encodeURIComponent(trackId)}`, {
          method: "DELETE",
          headers: { "X-CSRF-Token": yield ensureCsrfToken() }
        });
        return res.ok;
      } catch (e) {
        return false;
      }
    });
  }
  function saveTrackLyrics(track, lyrics) {
    return __async(this, null, function* () {
      const save = (refreshCsrf = false) => __async(null, null, function* () {
        const token = yield ensureCsrfToken(refreshCsrf);
        return fetch(`/api/tracks/${encodeURIComponent(track.id)}/lyrics`, {
          method: "PUT",
          credentials: "same-origin",
          cache: "no-store",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": token || "" },
          body: JSON.stringify({ lyrics })
        });
      });
      let res = yield save();
      if (res.status === 403) {
        res = yield save(true);
      }
      if (res.status === 404) {
        const libraryRes = yield fetch("/api/tracks");
        if (libraryRes.ok) {
          const data = yield libraryRes.json();
          const match = (data.tracks || []).find(
            (candidate) => candidate.title === track.title && candidate.artist === track.artist && Math.abs((candidate.duration || 0) - (track.duration || 0)) < 1
          );
          if (match) {
            const oldId = track.id;
            Object.assign(track, trackFromServer(match));
            state.queue = state.queue.map((id) => id === oldId ? track.id : id);
            res = yield save();
          }
        }
      }
      if (!res.ok) {
        let detail = res.status === 401 ? "Your session expired. Please sign in again." : "Could not save lyrics";
        try {
          detail = (yield res.json()).detail || detail;
        } catch (_) {
        }
        throw new Error(detail);
      }
      return yield res.json();
    });
  }
  const FS_SUPPORTED = "showDirectoryPicker" in window;
  const AUDIO_EXT_RE = /\.(mp3|m4a|mp4|wav|flac|ogg|oga|aac|opus|weba)$/i;
  function collectAudioFiles(_0) {
    return __async(this, arguments, function* (dirHandle, out = []) {
      try {
        for (var iter = __forAwait(dirHandle.entries()), more, temp, error; more = !(temp = yield iter.next()).done; more = false) {
          const [name, handle] = temp.value;
          if (handle.kind === "file") {
            if (AUDIO_EXT_RE.test(name)) {
              try {
                out.push(yield handle.getFile());
              } catch (e) {
              }
            }
          } else if (handle.kind === "directory") {
            yield collectAudioFiles(handle, out);
          }
        }
      } catch (temp) {
        error = [temp];
      } finally {
        try {
          more && (temp = iter.return) && (yield temp.call(iter));
        } finally {
          if (error)
            throw error[0];
        }
      }
      return out;
    });
  }
  function connectMusicFolder() {
    return __async(this, null, function* () {
      if (FS_SUPPORTED) {
        let dirHandle;
        try {
          dirHandle = yield window.showDirectoryPicker({ id: "auralis-music", mode: "read" });
        } catch (e) {
          return;
        }
        toast(`Scanning \u201C${dirHandle.name}\u201D\u2026`);
        const files = yield collectAudioFiles(dirHandle);
        yield importFiles(files);
        return;
      }
      $("#folderInput").click();
    });
  }
  function importFiles(fileList) {
    return __async(this, null, function* () {
      const files = Array.from(fileList).filter((f) => /audio\//.test(f.type) || AUDIO_EXT_RE.test(f.name));
      if (files.length === 0) {
        toast("No audio files found in that selection.");
        return;
      }
      toast(`Saving ${files.length} track${files.length > 1 ? "s" : ""}\u2026`);
      let added = 0, failed = 0;
      for (const file of files) {
        try {
          const track = yield uploadFileToServer(file);
          if (state.tracks.some((t) => t.id === track.id)) continue;
          state.tracks.push(track);
          added++;
        } catch (e) {
          failed++;
          console.warn("Upload failed for", file.name, e);
        }
      }
      relinkPersistedLibrary();
      saveLibraryMeta();
      if (added) toast(`Saved ${added} track${added !== 1 ? "s" : ""} to your library.`);
      else if (failed) toast("Couldn't save those files. Is Auralis running?");
      else toast("Those tracks were already in your library.");
      render();
    });
  }
  function ensureAudioGraph() {
    if (audioCtx) return;
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    sourceNode = audioCtx.createMediaElementSource(audioEl);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 128;
    freqData = new Uint8Array(analyser.frequencyBinCount);
    sourceNode.connect(analyser);
    analyser.connect(audioCtx.destination);
  }
  function currentTrack() {
    if (state.queueIndex < 0 || state.queueIndex >= state.queue.length) return null;
    const id = state.queue[state.queueIndex];
    return state.tracks.find((t) => t.id === id) || null;
  }
  function buildQueueFrom(list, startId) {
    state.queue = list.map((t) => t.id);
    state.queueIndex = Math.max(0, state.queue.indexOf(startId));
  }
  function reorderQueue(fromIndex, toIndex) {
    if (fromIndex === toIndex) return;
    const [moved] = state.queue.splice(fromIndex, 1);
    let insertAt = toIndex;
    if (fromIndex < toIndex) insertAt--;
    state.queue.splice(insertAt, 0, moved);
    if (state.queueIndex === fromIndex) state.queueIndex = insertAt;
    else if (fromIndex < state.queueIndex && insertAt >= state.queueIndex) state.queueIndex--;
    else if (fromIndex > state.queueIndex && insertAt <= state.queueIndex) state.queueIndex++;
  }
  function playTrackFromList(list, trackId) {
    buildQueueFrom(list, trackId);
    playCurrent();
  }
  let currentBlobUrl = null;
  let audioRetryPending = false;
  function playCurrent() {
    const t = currentTrack();
    if (!t) return;
    ensureAudioGraph();
    if (audioCtx.state === "suspended") audioCtx.resume();
    if (currentBlobUrl) {
      URL.revokeObjectURL(currentBlobUrl);
      currentBlobUrl = null;
    }
    if (t.streamUrl) {
      audioEl.src = t.streamUrl;
    } else if (t.file) {
      currentBlobUrl = URL.createObjectURL(t.file);
      audioEl.src = currentBlobUrl;
    } else {
      toast("This track has no playable source.");
      return;
    }
    audioEl.volume = state.muted ? 0 : state.volume;
    updateMediaSessionMetadata();
    audioRetryPending = false;
    audioEl.play().catch(() => {
      if (audioRetryPending) return;
      audioRetryPending = true;
      toast("Waking the music server\u2026");
      wait(2e3).then(() => {
        var _a2;
        if (((_a2 = currentTrack()) == null ? void 0 : _a2.id) !== t.id || !audioEl.paused) return;
        audioRetryPending = false;
        audioEl.load();
        audioEl.play().catch(() => {
          audioRetryPending = false;
          toast("The track could not start. Please try again.");
        });
      });
    });
    updateNowPlayingUI();
    renderQueuePanel();
    renderLibraryHighlight();
  }
  function togglePlay() {
    if (!currentTrack()) {
      const list = getVisibleTracks();
      if (list.length) {
        playTrackFromList(list, list[0].id);
      }
      return;
    }
    if (audioEl.paused) {
      ensureAudioGraph();
      if (audioCtx.state === "suspended") audioCtx.resume();
      if (!audioEl.getAttribute("src")) {
        playCurrent();
        return;
      }
      audioEl.play().catch(() => {
        playCurrent();
      });
    } else audioEl.pause();
  }
  function playNext(auto = false) {
    if (state.queue.length === 0) return;
    if (state.repeat === "one" && auto) {
      audioEl.currentTime = 0;
      audioEl.play();
      return;
    }
    if (state.shuffle) {
      let next;
      if (state.queue.length === 1) next = 0;
      else {
        do {
          next = Math.floor(Math.random() * state.queue.length);
        } while (next === state.queueIndex);
      }
      state.queueIndex = next;
    } else {
      state.queueIndex++;
      if (state.queueIndex >= state.queue.length) {
        state.queueIndex = 0;
      }
    }
    playCurrent();
  }
  function playPrev() {
    if (state.queue.length === 0) return;
    if (audioEl.currentTime > 3) {
      audioEl.currentTime = 0;
      return;
    }
    state.queueIndex = Math.max(0, state.queueIndex - 1);
    playCurrent();
  }
  function installMediaSessionHandlers() {
    if (!mediaSession) return;
    const handlers = {
      play: () => togglePlay(),
      pause: () => audioEl.pause(),
      previoustrack: () => playPrev(),
      nexttrack: () => playNext(false),
      seekbackward: (details) => {
        const offset = Number(details.seekOffset) || 10;
        audioEl.currentTime = Math.max(0, (audioEl.currentTime || 0) - offset);
      },
      seekforward: (details) => {
        const offset = Number(details.seekOffset) || 10;
        if (Number.isFinite(audioEl.duration)) {
          audioEl.currentTime = Math.min(audioEl.duration, (audioEl.currentTime || 0) + offset);
        }
      },
      seekto: (details) => {
        if (Number.isFinite(details.seekTime)) {
          const duration = audioEl.duration;
          audioEl.currentTime = Number.isFinite(duration) ? Math.max(0, Math.min(duration, details.seekTime)) : Math.max(0, details.seekTime);
        }
      }
    };
    Object.entries(handlers).forEach(([action, handler]) => {
      try {
        mediaSession.setActionHandler(action, handler);
      } catch (_) {
      }
    });
  }
  installMediaSessionHandlers();
  audioEl.addEventListener("ended", () => playNext(true));
  audioEl.addEventListener("play", () => {
    syncPlayIcons(true);
    try {
      if (mediaSession) mediaSession.playbackState = "playing";
    } catch (_) {
    }
    updateMediaSessionPosition();
  });
  audioEl.addEventListener("pause", () => {
    syncPlayIcons(false);
    try {
      if (mediaSession) mediaSession.playbackState = "paused";
    } catch (_) {
    }
    updateMediaSessionPosition();
  });
  audioEl.addEventListener("timeupdate", () => {
    updateSeekUI();
    updateMobileLyricsPreview(currentTrack());
    updateMediaSessionPosition();
    if ($("#lyricsOverlay").classList.contains("open")) updateLyricsHighlight();
  });
  audioEl.addEventListener("seeked", () => {
    LyricsDebug.log(`seeked \u2192 t=${audioEl.currentTime.toFixed(2)}s, recalculating active line`);
    updateMediaSessionPosition();
    if ($("#lyricsOverlay").classList.contains("open")) updateLyricsHighlight(true);
  });
  audioEl.addEventListener("loadedmetadata", () => {
    updateSeekUI();
    updateMediaSessionPosition();
  });
  function syncPlayIcons(playing) {
    const pathPlay = "M9 6.8v10.4L18.2 12z";
    const pathPause = "M8 6.5h3.2v11H8zM12.8 6.5H16v11h-3.2z";
    $("#iconPlay").innerHTML = `<path d="${playing ? pathPause : pathPlay}"/>`;
    $("#miniIconPlay").innerHTML = `<path d="${playing ? pathPause : pathPlay}"/>`;
    $("#mobileIconPlay").innerHTML = `<path d="${playing ? pathPause : pathPlay}"/>`;
  }
  function updateSeekUI() {
    const dur = audioEl.duration || 0;
    const cur = audioEl.currentTime || 0;
    const pct = dur ? cur / dur * 100 : 0;
    $("#timeCur").textContent = fmtTime(cur);
    $("#timeDur").textContent = fmtTime(dur);
    $("#seekFill").style.width = pct + "%";
    $("#seekThumb").style.left = pct + "%";
    $("#miniCur").textContent = fmtTime(cur);
    $("#miniDur").textContent = fmtTime(dur);
    $("#miniSeekFill").style.width = pct + "%";
    $("#miniSeekThumb").style.left = pct + "%";
    $("#mobileTimeCur").textContent = fmtTime(cur);
    $("#mobileTimeDur").textContent = fmtTime(dur);
    $("#mobileSeekFill").style.width = pct + "%";
    $("#mobileSeekThumb").style.left = pct + "%";
  }
  function mobilePlayerContext() {
    if (state.view === "favorites") return "Liked Songs";
    if (state.view.startsWith("playlist:")) {
      const playlist = state.playlists.find((p) => p.id === state.view.slice(9));
      return playlist ? playlist.name : "Playlist";
    }
    if (state.view === "queue") return "Queue";
    if (state.view === "artists" || state.view.startsWith("artist:")) return "Artist radio";
    return "Library";
  }
  function updateMobileLyricsPreview(track) {
    var _a2, _b2, _c, _d, _e;
    const el = $("#mobileLyricsText");
    if (!el) return;
    if (track && !track.lyricsResolved && !track.lyricsLoading) {
      ensureTrackLyrics(track);
    }
    if ((_b2 = (_a2 = track == null ? void 0 : track.lyrics) == null ? void 0 : _a2.lines) == null ? void 0 : _b2.length) {
      const time = (audioEl.currentTime || 0) * 1e3;
      let index = 0;
      track.lyrics.lines.forEach((line, i) => {
        if (line.time <= time) index = i;
      });
      const active = ((_c = track.lyrics.lines[index]) == null ? void 0 : _c.text) || "";
      const next = ((_d = track.lyrics.lines[index + 1]) == null ? void 0 : _d.text) || "";
      el.innerHTML = [
        active ? `<span class="lyric-active">${escapeHtml(active)}</span>` : "",
        next ? `<span class="lyric-next">${escapeHtml(next)}</span>` : ""
      ].filter(Boolean).join("\n") || "Lyrics are ready.";
    } else if ((_e = track == null ? void 0 : track.lyrics) == null ? void 0 : _e.text) {
      const lines = track.lyrics.text.split(/\n+/).filter(Boolean).slice(0, 2);
      el.innerHTML = lines.map(
        (line, i) => `<span class="${i === 0 ? "lyric-active" : "lyric-next"}">${escapeHtml(line)}</span>`
      ).join("\n");
    } else if (track && !track.lyricsResolved) {
      el.textContent = "Finding lyrics for this song\u2026";
    } else {
      el.textContent = track ? "No lyrics available for this song." : "Play a song to see its lyrics here.";
    }
  }
  function ensureTrackLyrics(track) {
    if (!track || track.lyricsResolved || track.lyricsLoading) return;
    track.lyricsLoading = true;
    const requestedTrackId = track.id;
    LyricsDebug.log(`state: lyrics lookup started for "${track.title}" by ${track.artist}`);
    (() => __async(null, null, function* () {
      let result = track.customLyrics ? LyricsEngine.fromLRC(track.customLyrics) || { source: "custom", text: track.customLyrics } : null;
      try {
        const headRes = result ? null : yield fetch(`/api/tracks/${encodeURIComponent(track.id)}/tag-head`);
        if (headRes == null ? void 0 : headRes.ok) {
          const blob = yield headRes.blob();
          const file = new File([blob], `${track.title || "track"}.mp3`, { type: "audio/mpeg" });
          const meta = yield parseID3(file);
          result = LyricsEngine.fromID3(meta);
          if (result) LyricsDebug.log(`state: embedded ID3 lyrics found \u2192 ${result.source}`);
        }
      } catch (e) {
        LyricsDebug.warn("state: embedded ID3 lyrics read failed \u2014", e.message);
      }
      if (!result) {
        result = yield LyricsEngine.fromOnline(track);
      }
      return result;
    }))().then((result) => {
      var _a2;
      if (track.customLyrics) {
        track.lyricsLoading = false;
        return;
      }
      track.lyrics = result;
      track.lyricsResolved = true;
      track.lyricsLoading = false;
      LyricsDebug.log(`state: lyrics lookup finished for "${track.title}" \u2192`, result ? result.source : "nothing found");
      if (((_a2 = currentTrack()) == null ? void 0 : _a2.id) !== requestedTrackId) return;
      updateMobileLyricsPreview(track);
      if ($("#lyricsOverlay").classList.contains("open")) renderLyricsStage();
    }).catch((e) => {
      var _a2;
      track.lyricsResolved = true;
      track.lyricsLoading = false;
      LyricsDebug.warn("state: lyrics lookup threw \u2014", e.message);
      if (((_a2 = currentTrack()) == null ? void 0 : _a2.id) === requestedTrackId) {
        updateMobileLyricsPreview(track);
        if ($("#lyricsOverlay").classList.contains("open")) renderLyricsStage();
      }
    });
  }
  function updateNowPlayingUI() {
    var _a2;
    const t = currentTrack();
    const bar = $("#nowbar");
    if (!t) {
      bar.classList.add("hidden");
      document.body.classList.remove("now-playing");
      (_a2 = $("#mobilePlayer")) == null ? void 0 : _a2.classList.remove("open");
      return;
    }
    bar.classList.remove("hidden");
    document.body.classList.add("now-playing");
    $("#nowArt").src = t.art;
    $("#miniArt").src = t.art;
    $("#nowTitle").textContent = t.title;
    $("#miniTitle").textContent = t.title;
    const credits = artistCreditsLabel(t);
    $("#nowArtist").innerHTML = artistLinksMarkup(t);
    $("#nowArtist").classList.remove("artist-link");
    $("#nowArtist").title = credits;
    $("#miniArtist").textContent = credits;
    document.title = `${t.title} \u2014 ${credits} \xB7 Vervfy`;
    $("#nowFav").classList.toggle("on", !!t.favorite);
    $("#mobilePlayerBg").style.backgroundImage = `url("${t.art}")`;
    $("#mobilePlayerArt").src = t.art;
    $("#mobilePlayerTitle").textContent = t.title;
    $("#mobilePlayerArtist").textContent = credits;
    $("#mobilePlayerContext").textContent = mobilePlayerContext();
    $("#mobilePlayerFav").classList.toggle("on", !!t.favorite);
    updateMobileLyricsPreview(t);
    updateVolUI();
    if ($("#lyricsOverlay").classList.contains("open")) renderLyricsStage();
  }
  function renderLibraryHighlight() {
    const t = currentTrack();
    $$(".card").forEach((c) => c.classList.toggle("playing", t && c.dataset.id === t.id));
    $$(".row").forEach((r) => r.classList.toggle("playing", t && r.dataset.id === t.id));
  }
  function lyricsEmptyMarkup(title, sub) {
    return `<div class="lyrics-empty">
    <div class="empty-orb"></div>
    <h3>${escapeHtml(title)}</h3>
    <p>${escapeHtml(sub)}</p>
  </div>`;
  }
  function renderLyricsStage() {
    var _a2, _b2;
    if (lyricsSyncClockRaf) {
      cancelAnimationFrame(lyricsSyncClockRaf);
      lyricsSyncClockRaf = null;
    }
    const stage = $("#lyricsStage");
    const bg = $("#lyricsBg");
    const t = currentTrack();
    if (!t) {
      bg.style.backgroundImage = "";
      stage.innerHTML = lyricsEmptyMarkup("Nothing playing", "Play a track to see its lyrics here.");
      return;
    }
    bg.style.backgroundImage = `url("${t.art}")`;
    const sourceLabel = { sylt: "Synced lyrics", lrc: "Synced \xB7 LRC", uslt: "Lyrics", custom: "Pasted lyrics", "custom-synced": "Synced \xB7 pasted", "online-synced": "Synced \xB7 LRCLIB", "online-plain": "Lyrics \xB7 LRCLIB" };
    const sideMarkup = `
    <div class="lyrics-side">
      <div class="lyrics-art"><img src="${t.art}" alt=""></div>
      <div class="lyrics-meta"><div class="t">${escapeHtml(t.title)}</div><div class="a">${escapeHtml(t.artist)}</div></div>
      ${t.lyrics ? `<div class="lyrics-source">${sourceLabel[t.lyrics.source] || "Lyrics"}</div>` : ""}
    </div>`;
    if (t.lyrics && t.lyrics.lines && t.lyrics.lines.length) {
      const linesHtml = t.lyrics.lines.map(
        (ln, i) => `<div class="lyrics-line" data-time="${ln.time}" data-i="${i}">${escapeHtml(ln.text) || "&nbsp;"}</div>`
      ).join("");
      const resyncButton = t.customLyrics ? `<button class="btn lyrics-resync-btn" id="btnResyncLyrics">Re-sync to audio</button>` : "";
      stage.innerHTML = sideMarkup + `<div class="lyrics-viewport"><div class="lyrics-track" id="lyricsTrack">${linesHtml}</div></div>${resyncButton}`;
      const linesRef = t.lyrics.lines;
      for (let i = 1; i < linesRef.length; i++) {
        if (linesRef[i].time < linesRef[i - 1].time) {
          LyricsDebug.warn(`${t.title}: lyric lines were not ascending (index ${i - 1}=${linesRef[i - 1].time}ms > index ${i}=${linesRef[i].time}ms) \u2014 re-sorting`);
          linesRef.sort((a, b) => a.time - b.time);
          break;
        }
      }
      _lyricsLastLoggedIdx = null;
      $$(".lyrics-line").forEach((el) => {
        el.addEventListener("click", () => {
          const time = parseFloat(el.dataset.time) / 1e3;
          LyricsDebug.log(`click-to-seek \u2192 line "${el.textContent}" @ ${time.toFixed(2)}s`);
          if (isFinite(time)) audioEl.currentTime = time;
        });
      });
      (_a2 = $("#btnResyncLyrics")) == null ? void 0 : _a2.addEventListener("click", () => openLyricsSyncEditor(t));
      updateLyricsHighlight(true);
    } else if (t.lyrics && t.lyrics.text) {
      const paragraphs = t.lyrics.text.split(/\n{2,}/).map((p) => `<p>${escapeHtml(p)}</p>`).join("");
      stage.innerHTML = sideMarkup + `<div class="lyrics-plain">${paragraphs}<button class="btn btn-primary lyrics-sync-btn" id="btnSyncLyrics">Sync to audio</button></div>`;
      $("#btnSyncLyrics").addEventListener("click", () => openLyricsSyncEditor(t));
    } else if (!t.lyricsResolved) {
      stage.innerHTML = sideMarkup + lyricsEmptyMarkup("Searching for lyrics\u2026", "Checking this file and LRCLIB for a match.");
      (_b2 = stage.querySelector(".empty-orb")) == null ? void 0 : _b2.classList.add("lyrics-loading-orb");
      ensureTrackLyrics(t);
    } else {
      stage.innerHTML = sideMarkup + lyricsEmptyMarkup(
        "No lyrics available",
        "Vervfy checked this file's tags and LRCLIB's database, but couldn't find any lyrics for this track."
      ) + `<button class="btn btn-primary lyrics-paste-btn" id="btnPasteLyrics">Paste lyrics</button>`;
      $("#btnPasteLyrics").addEventListener("click", () => openLyricsEditor(t));
    }
  }
  function timedLyricsToLrc(lines) {
    return lines.map((line) => {
      const totalSeconds = Math.max(0, line.time) / 1e3;
      const minutes = Math.floor(totalSeconds / 60);
      const seconds = (totalSeconds % 60).toFixed(2).padStart(5, "0");
      return `[${String(minutes).padStart(2, "0")}:${seconds}]${line.text}`;
    }).join("\n");
  }
  function openLyricsSyncEditor(track) {
    var _a2, _b2;
    const timedLines = (_a2 = track.lyrics) == null ? void 0 : _a2.lines;
    const text = ((_b2 = track.lyrics) == null ? void 0 : _b2.text) || track.customLyrics || "";
    const lines = (timedLines == null ? void 0 : timedLines.length) ? timedLines.map((line) => line.text.trim()).filter(Boolean) : text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    if (!lines.length) {
      toast("Paste lyrics before syncing them.");
      return;
    }
    const stamps = new Array(lines.length).fill(null);
    const stage = $("#lyricsStage");
    const renderRows = () => lines.map((line, index) => {
      const stamp = stamps[index];
      return `<button type="button" class="lyrics-sync-line${stamp !== null ? " stamped" : ""}" data-line-index="${index}">
      <span class="lyrics-sync-line-time">${stamp === null ? "Tap at this line" : fmtTime(stamp / 1e3)}</span>
      <span>${escapeHtml(line)}</span>
    </button>`;
    }).join("");
    stage.innerHTML = `
    <div class="lyrics-sync-editor">
      <div class="lyrics-editor-heading">
        <h3>Sync lyrics to audio</h3>
        <p>Start the song, then tap each line when it is sung. You can tap a line again to correct it.</p>
      </div>
      <div class="lyrics-sync-clock">Playback: <strong id="lyricsSyncTime">${fmtTime(audioEl.currentTime || 0)}</strong></div>
      <div class="lyrics-sync-lines" id="lyricsSyncLines">${renderRows()}</div>
      <div class="lyrics-editor-actions">
        <button class="btn" id="btnCancelLyricsSync">Back</button>
        <button class="btn" id="btnSyncFromStart">Play from start</button>
        <button class="btn btn-primary" id="btnSaveSyncedLyrics" disabled>Save synced lyrics</button>
      </div>
    </div>`;
    const saveButton = $("#btnSaveSyncedLyrics");
    const refresh = () => {
      const list = $("#lyricsSyncLines");
      if (!list) return;
      list.innerHTML = renderRows();
      list.querySelectorAll("[data-line-index]").forEach((button) => {
        button.addEventListener("click", () => {
          const index = Number(button.dataset.lineIndex);
          stamps[index] = Math.max(0, Math.round((audioEl.currentTime || 0) * 1e3));
          refresh();
        });
      });
      saveButton.disabled = stamps.some((stamp) => stamp === null);
    };
    refresh();
    $("#btnCancelLyricsSync").addEventListener("click", renderLyricsStage);
    $("#btnSyncFromStart").addEventListener("click", () => {
      audioEl.currentTime = 0;
      audioEl.play().catch(() => toast("Press play, then tap each lyric line."));
    });
    saveButton.addEventListener("click", () => __async(null, null, function* () {
      for (let index = 1; index < stamps.length; index++) {
        if (stamps[index] < stamps[index - 1]) {
          toast("Lyrics must be tapped in song order. Correct the out-of-order line.");
          return;
        }
      }
      saveButton.disabled = true;
      try {
        const synced = { source: "custom-synced", lines: lines.map((line, index) => ({ time: stamps[index], text: line })) };
        const saved = yield saveTrackLyrics(track, timedLyricsToLrc(synced.lines));
        track.customLyrics = saved.custom_lyrics;
        track.lyrics = synced;
        track.lyricsResolved = true;
        toast("Lyrics synced to the track");
        renderLyricsStage();
      } catch (e) {
        saveButton.disabled = false;
        toast(e.message || "Could not save synced lyrics");
      }
    }));
    const updateClock = () => {
      const clock = $("#lyricsSyncTime");
      if (!clock) {
        lyricsSyncClockRaf = null;
        return;
      }
      clock.textContent = fmtTime(audioEl.currentTime || 0);
      lyricsSyncClockRaf = requestAnimationFrame(updateClock);
    };
    updateClock();
  }
  function openLyricsEditor(track) {
    var _a2;
    const stage = $("#lyricsStage");
    stage.innerHTML = `
    <div class="lyrics-editor">
      <div class="lyrics-editor-heading">
        <h3>Add lyrics</h3>
        <p>${escapeHtml(track.title)} \xB7 ${escapeHtml(track.artist)}</p>
      </div>
      <textarea id="lyricsInput" class="lyrics-input" placeholder="Paste plain lyrics or timestamped LRC lyrics here\u2026">${escapeHtml(track.customLyrics || ((_a2 = track.lyrics) == null ? void 0 : _a2.text) || "")}</textarea>
      <div class="lyrics-editor-actions">
        <button class="btn" id="btnCancelLyrics">Cancel</button>
        <button class="btn btn-primary" id="btnSaveLyrics">Save lyrics</button>
      </div>
    </div>`;
    $("#btnCancelLyrics").addEventListener("click", renderLyricsStage);
    $("#btnSaveLyrics").addEventListener("click", () => __async(null, null, function* () {
      const input = $("#lyricsInput");
      const lyrics = input.value.trim();
      if (!lyrics) {
        input.focus();
        toast("Paste some lyrics first.");
        return;
      }
      const button = $("#btnSaveLyrics");
      button.disabled = true;
      try {
        const parsed = LyricsEngine.fromLRC(lyrics);
        const synced = parsed;
        const lyricsToSave = (synced == null ? void 0 : synced.lines) ? timedLyricsToLrc(synced.lines) : lyrics;
        const saved = yield saveTrackLyrics(track, lyricsToSave);
        track.customLyrics = saved.custom_lyrics;
        track.lyrics = LyricsEngine.fromLRC(track.customLyrics) || synced || { source: "custom", text: track.customLyrics };
        track.lyricsResolved = true;
        toast((synced == null ? void 0 : synced.lines) ? "Timestamped lyrics saved" : "Lyrics saved \u2014 use Sync to audio to add timing");
        renderLyricsStage();
      } catch (e) {
        button.disabled = false;
        toast(e.message || "Could not save lyrics");
      }
    }));
    $("#lyricsInput").focus();
  }
  function updateLyricsHighlight(instant) {
    const t = currentTrack();
    if (!t || !t.lyrics || !t.lyrics.lines) return;
    const track = $("#lyricsTrack");
    if (!track) return;
    const curSec = audioEl.currentTime || 0;
    const curMs = curSec * 1e3;
    const lines = t.lyrics.lines;
    let activeIdx = -1;
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].time <= curMs) activeIdx = i;
      else break;
    }
    if (LYRICS_SYNC_DEBUG && activeIdx !== _lyricsLastLoggedIdx) {
      const matched = activeIdx >= 0 ? lines[activeIdx] : null;
      LyricsDebug.log(
        `t=${curSec.toFixed(2)}s`,
        "\u2192 activeIdx=",
        activeIdx,
        matched ? `lineTime=${(matched.time / 1e3).toFixed(2)}s text="${matched.text}"` : "(before first line)"
      );
      _lyricsLastLoggedIdx = activeIdx;
    }
    const els = track.children;
    for (let i = 0; i < els.length; i++) {
      els[i].classList.toggle("active", i === activeIdx);
      els[i].classList.toggle("past", i < activeIdx);
    }
    const anchorIdx = activeIdx >= 0 ? activeIdx : 0;
    const anchorEl = els[anchorIdx];
    if (anchorEl) {
      const targetY = -(anchorEl.offsetTop + anchorEl.clientHeight / 2);
      if (instant) {
        track.style.transition = "none";
        track.style.transform = `translateY(${targetY}px)`;
        requestAnimationFrame(() => {
          track.style.transition = "";
        });
      } else {
        track.style.transform = `translateY(${targetY}px)`;
      }
    }
  }
  function openLyrics() {
    var _a2;
    (_a2 = $("#mobilePlayer")) == null ? void 0 : _a2.classList.remove("open");
    closeViz();
    renderLyricsStage();
    $("#lyricsOverlay").classList.add("open");
  }
  function closeLyrics() {
    $("#lyricsOverlay").classList.remove("open");
    if (lyricsSyncClockRaf) {
      cancelAnimationFrame(lyricsSyncClockRaf);
      lyricsSyncClockRaf = null;
    }
  }
  function drawViz() {
    const canvas = $("#vizCanvas");
    const ctx = canvas.getContext("2d");
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    const cx = w / 2, cy = h / 2, baseR = w * 0.22;
    ctx.beginPath();
    ctx.arc(cx, cy, baseR, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(255,255,255,0.02)";
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.lineWidth = 1;
    ctx.stroke();
    if (analyser && !audioEl.paused) {
      analyser.getByteFrequencyData(freqData);
      const bands = 64;
      const step = Math.floor(freqData.length / bands);
      ctx.save();
      ctx.translate(cx, cy);
      for (let i = 0; i < bands; i++) {
        let sum = 0;
        for (let j = 0; j < step; j++) sum += freqData[i * step + j];
        const amp = sum / step / 255;
        const angle = i / bands * Math.PI * 2 - Math.PI / 2;
        const r1 = baseR + 4, r2 = baseR + 4 + amp * (w * 0.24);
        const x1 = Math.cos(angle) * r1, y1 = Math.sin(angle) * r1;
        const x2 = Math.cos(angle) * r2, y2 = Math.sin(angle) * r2;
        const grad = ctx.createLinearGradient(x1, y1, x2, y2);
        grad.addColorStop(0, "#8b7fff");
        grad.addColorStop(1, "#54e8d455");
        ctx.strokeStyle = grad;
        ctx.lineWidth = w * 6e-3;
        ctx.lineCap = "round";
        ctx.shadowBlur = 14;
        ctx.shadowColor = "#8b7fff88";
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
      ctx.restore();
    }
    rafViz = requestAnimationFrame(drawViz);
  }
  function openViz() {
    closeLyrics();
    const t = currentTrack();
    $("#vizTitle").textContent = t ? t.title : "Nothing playing";
    $("#vizArtist").textContent = t ? t.artist : "Import and play a track";
    $("#vizOverlay").classList.add("open");
    ensureAudioGraph();
    drawViz();
  }
  function closeViz() {
    $("#vizOverlay").classList.remove("open");
    if (rafViz) cancelAnimationFrame(rafViz);
  }
  function updateVolUI() {
    const pct = state.muted ? 0 : state.volume * 100;
    $("#volFill").style.width = pct + "%";
    const svg = $("#iconVol");
    svg.style.opacity = state.muted ? 0.4 : 1;
  }
  function setVolume(v) {
    state.volume = Math.min(1, Math.max(0, v));
    state.muted = false;
    audioEl.volume = state.volume;
    updateVolUI();
    saveSettings();
  }
  function artistNameOf(t) {
    return t && t.artist ? t.artist : "Unknown artist";
  }
  const ARTIST_LIST_SEP_RE = /\s*(?:,|;|\/|\bfeat(?:uring)?\.?\b|\bft\.?\b|\bwith\b)\s*/i;
  const ARTIST_LIST_SEP_TEST_RE = /[,;/]|\bfeat(?:uring)?\.?\b|\bft\.?\b|\bwith\b/i;
  const TITLE_FEATURED_RE = /\((?:feat(?:uring)?|ft|with)\.?\s+([^)]+)\)/ig;
  const ARTIST_AND_SPLIT_RE = /\s+(?:&|and)\s+/i;
  function cleanArtistCredit(part) {
    return String(part || "").replace(/^[\s\-–—·•]+|[\s\-–—·•]+$/g, "").replace(/\s+/g, " ").trim();
  }
  function splitArtistCreditList(raw) {
    const text = cleanArtistCredit(raw);
    if (!text) return [];
    if (text.toLocaleLowerCase() === "unknown artist") return [text];
    const hasListSep = ARTIST_LIST_SEP_TEST_RE.test(text);
    let parts = hasListSep ? text.split(ARTIST_LIST_SEP_RE) : [text];
    if (hasListSep) {
      parts = parts.flatMap((part) => part.split(ARTIST_AND_SPLIT_RE));
    }
    return parts.map(cleanArtistCredit).filter(Boolean);
  }
  function featuredArtistsFromTitle(title) {
    const text = String(title || "");
    const found = [];
    let match;
    TITLE_FEATURED_RE.lastIndex = 0;
    while ((match = TITLE_FEATURED_RE.exec(text)) !== null) {
      found.push(...splitArtistCreditList(match[1]));
    }
    return found;
  }
  function artistsOf(t) {
    const names = [
      ...splitArtistCreditList(artistNameOf(t)),
      ...featuredArtistsFromTitle(t && t.title)
    ];
    const seen = /* @__PURE__ */ new Map();
    for (const name of names) {
      const key = name.toLocaleLowerCase();
      if (!seen.has(key)) seen.set(key, name);
    }
    return Array.from(seen.values());
  }
  function artistKey(name) {
    return String(name || "").toLocaleLowerCase();
  }
  function trackHasArtist(t, name) {
    const key = artistKey(name);
    return artistsOf(t).some((n) => artistKey(n) === key);
  }
  function getArtists() {
    const map = /* @__PURE__ */ new Map();
    for (const t of state.tracks) {
      const names = artistsOf(t);
      if (!names.length) continue;
      const album = typeof t.album === "string" ? t.album.trim() : "";
      const duration = Number(t.duration);
      for (const name of names) {
        const key = artistKey(name);
        let entry = map.get(key);
        if (!entry) {
          entry = { name, art: t.art, tracks: [], albums: /* @__PURE__ */ new Set(), duration: 0 };
          map.set(key, entry);
        } else if (name.length > entry.name.length) {
          entry.name = name;
        }
        if (entry.tracks.some((existing) => existing.id === t.id)) continue;
        entry.tracks.push(t);
        if (album && album.toLocaleLowerCase() !== "unknown album") {
          entry.albums.add(album.toLocaleLowerCase());
        }
        if (Number.isFinite(duration) && duration > 0) {
          entry.duration += duration;
        }
      }
    }
    return Array.from(map.values()).map((artist) => __spreadProps(__spreadValues({}, artist), {
      albumCount: artist.albums.size
    })).sort((a, b) => a.name.localeCompare(b.name, void 0, { sensitivity: "base" }));
  }
  function artistViewKey(name) {
    return "artist:" + encodeURIComponent(name);
  }
  function artistNameFromView(view) {
    return decodeURIComponent(view.slice(7));
  }
  function openArtist(name) {
    if (!name) return;
    state.view = artistViewKey(name);
    state.search = "";
    const input = $("#searchInput");
    if (input) input.value = "";
    render();
  }
  function getVisibleTracks() {
    let list;
    if (state.view === "library") list = state.tracks;
    else if (state.view === "favorites") list = state.tracks.filter((t) => t.favorite);
    else if (state.view.startsWith("playlist:")) {
      const pl = state.playlists.find((p) => p.id === state.view.slice(9));
      list = pl ? pl.trackIds.map((id) => state.tracks.find((t) => t.id === id)).filter(Boolean) : [];
    } else if (state.view.startsWith("artist:")) {
      const name = artistNameFromView(state.view);
      list = state.tracks.filter((t) => trackHasArtist(t, name));
    } else list = state.tracks;
    if (state.search.trim()) {
      const q = state.search.toLowerCase();
      list = list.filter((t) => (t.title + " " + t.artist + " " + t.album).toLowerCase().includes(q));
    }
    return list;
  }
  function render() {
    renderTopbar();
    if (state.view === "account") renderAccountView();
    else if (state.view === "playlists") renderPlaylistsView();
    else if (state.view === "artists") renderArtistsView();
    else if (state.view.startsWith("artist:")) renderArtistDetailView();
    else if (state.view === "queue") renderQueueView();
    else renderTrackListView();
    renderQueuePanel();
    renderLibraryHighlight();
  }
  function renderTopbar() {
    const titles = { library: "Library", favorites: "Favorites", playlists: "Playlists", artists: "Artists", queue: "Queue", account: "Account" };
    let title = titles[state.view];
    if (!title && state.view.startsWith("playlist:")) {
      const pl = state.playlists.find((p) => p.id === state.view.slice(9));
      title = pl ? pl.name : "Playlist";
    } else if (!title && state.view.startsWith("artist:")) {
      title = artistNameFromView(state.view);
    }
    $("#viewTitle").textContent = title || "Library";
    let count;
    if (state.view === "playlists") count = state.playlists.length;
    else if (state.view === "artists") {
      let artists = getArtists();
      if (state.search.trim()) {
        const q = state.search.toLowerCase();
        artists = artists.filter((a) => a.name.toLowerCase().includes(q));
      }
      count = artists.length;
    } else count = getVisibleTracks().length;
    $("#viewCount").textContent = state.view !== "account" && state.tracks.length ? `\xB7 ${count}` : "";
    $("#viewToggle").style.display = state.view === "playlists" || state.view === "artists" || state.view === "queue" || state.view === "account" ? "none" : "flex";
    $(".search-wrap").style.display = state.view === "account" ? "none" : "flex";
    $("#btnImportTop").style.display = state.view === "account" ? "none" : "flex";
    $$(".rail-btn[data-view]").forEach((b) => {
      const active = b.dataset.view === state.view || state.view.startsWith("playlist") && b.dataset.view === "playlists" || state.view.startsWith("artist") && b.dataset.view === "artists";
      b.classList.toggle("active", active);
    });
  }
  function artistLinkMarkup(name) {
    const label = escapeHtml(name);
    return `<button type="button" class="artist-link" data-action="artist" data-artist="${encodeURIComponent(name)}" title="View ${label}">${label}</button>`;
  }
  function artistLinksMarkup(t) {
    const names = artistsOf(t);
    if (!names.length) return artistLinkMarkup("Unknown artist");
    return names.map(artistLinkMarkup).join('<span class="artist-sep">, </span>');
  }
  function artistCreditsLabel(t) {
    const names = artistsOf(t);
    return names.length ? names.join(", ") : artistNameOf(t);
  }
  function trackRowMarkup(t, idx, showAlbum = true) {
    var _a2;
    const playing = ((_a2 = currentTrack()) == null ? void 0 : _a2.id) === t.id;
    const artistText = escapeHtml(artistCreditsLabel(t));
    const title = escapeHtml(t.title);
    const albumText = showAlbum ? escapeHtml(t.album) : "";
    const metaTitle = showAlbum && albumText ? `${artistText} \u2014 ${albumText}` : artistText;
    return `
  <div class="row" data-id="${t.id}" draggable="true">
    <div class="row-idx">
      <span class="num">${idx + 1}</span>
      <span class="play-mini" data-action="play"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></span>
      <span class="bars"><span></span><span></span><span></span></span>
    </div>
    <div class="row-title-wrap">
      <img class="row-art" src="${t.art}" alt="">
      <div class="row-title-stack">
        <div class="row-title" title="${title}">${title}</div>
        <div class="row-meta" title="${metaTitle}">
          <div class="row-artist">${artistLinksMarkup(t)}</div>
          ${showAlbum ? `<span class="row-meta-sep" aria-hidden="true">\xB7</span><div class="row-album" title="${albumText}">${albumText}</div>` : ""}
        </div>
      </div>
    </div>
    <div class="row-album-cell" title="${albumText}">${showAlbum ? albumText : ""}</div>
    <div class="row-time" data-track-time="${t.id}">${t.duration ? fmtTime(t.duration) : "--:--"}</div>
    <div class="row-actions">
      <button data-action="queue" title="Add to queue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6.5h16M4 12h10M4 17.5h10"/><path d="M16.5 14.2l4 2.3-4 2.3z" fill="currentColor" stroke="none"/></svg></button>
      <button data-action="fav" class="${t.favorite ? "fav-on" : ""}" title="Favorite"><svg viewBox="0 0 24 24" fill="${t.favorite ? "currentColor" : "none"}" stroke="currentColor" stroke-width="1.8"><path d="M12 20s-7-4.3-9.5-9C0.8 7.4 3 4 6.5 4c2 0 3.4 1.1 4.5 2.6C12.1 5.1 13.5 4 15.5 4 19 4 21.2 7.4 19.5 11 17 15.7 12 20 12 20Z"/></svg></button>
      <button data-action="menu" title="More"><svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/></svg></button>
    </div>
  </div>`;
  }
  function cardMarkup(t) {
    var _a2;
    const playing = ((_a2 = currentTrack()) == null ? void 0 : _a2.id) === t.id;
    return `
  <div class="card ${playing ? "playing" : ""}" data-id="${t.id}">
    <div class="card-art">
      <img src="${t.art}" alt="">
      <div class="card-play"><button data-action="play"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></button></div>
    </div>
    <button class="card-queue" data-action="queue" title="Add to queue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6.5h16M4 12h10M4 17.5h10"/><path d="M16.5 14.2l4 2.3-4 2.3z" fill="currentColor" stroke="none"/></svg></button>
    <button class="card-fav ${t.favorite ? "on" : ""}" data-action="fav" title="Favorite"><svg viewBox="0 0 24 24" fill="${t.favorite ? "currentColor" : "none"}" stroke="currentColor" stroke-width="1.8"><path d="M12 20s-7-4.3-9.5-9C0.8 7.4 3 4 6.5 4c2 0 3.4 1.1 4.5 2.6C12.1 5.1 13.5 4 15.5 4 19 4 21.2 7.4 19.5 11 17 15.7 12 20 12 20Z"/></svg></button>
    <div class="card-title">${escapeHtml(t.title)}</div>
    <div class="card-sub">${artistLinksMarkup(t)}</div>
  </div>`;
  }
  function escapeHtml(s) {
    return (s || "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[m]);
  }
  function renderTrackListView() {
    var _a2, _b2, _c, _d, _e;
    const content = $("#content");
    if (serverLibraryLoading) {
      content.innerHTML = `<div class="library-skeleton" aria-label="Loading library" aria-busy="true">
      <div class="skeleton-row"><span class="skeleton-art"></span><span class="skeleton-copy"><i></i><i></i></span><span class="skeleton-time"></span></div>
      <div class="skeleton-row"><span class="skeleton-art"></span><span class="skeleton-copy"><i></i><i></i></span><span class="skeleton-time"></span></div>
      <div class="skeleton-row"><span class="skeleton-art"></span><span class="skeleton-copy"><i></i><i></i></span><span class="skeleton-time"></span></div>
    </div>`;
      return;
    }
    const list = getVisibleTracks();
    const playlistId = state.view.startsWith("playlist:") ? state.view.slice(9) : null;
    const playlist = playlistId ? state.playlists.find((p) => p.id === playlistId) : null;
    const addPlaylistBtn = playlist ? `<button class="btn" id="btnAddPlaylistTracks" type="button">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
      Add from library
    </button>` : "";
    if (serverLibraryLoadFailed) {
      content.innerHTML = '<div class="empty"><div class="empty-orb"></div><h3>Music server unavailable</h3><p>The server may still be waking up. Try connecting again.</p><button class="btn btn-primary" id="retryLibrary">Retry connection</button></div>';
      (_a2 = $("#retryLibrary")) == null ? void 0 : _a2.addEventListener("click", () => __async(null, null, function* () {
        const button = $("#retryLibrary");
        button.disabled = true;
        button.textContent = "Connecting\u2026";
        yield loadServerLibrary(true);
        render();
      }));
      return;
    }
    if (state.tracks.length === 0) {
      content.innerHTML = emptyStateMarkup();
      (_b2 = $("#emptyAddFiles")) == null ? void 0 : _b2.addEventListener("click", () => $("#fileInput").click());
      (_c = $("#emptyAddFolder")) == null ? void 0 : _c.addEventListener("click", connectMusicFolder);
      return;
    }
    if (list.length === 0) {
      if (playlist && !state.search.trim()) {
        content.innerHTML = `<div class="empty"><div class="empty-orb"></div><h3>This playlist is empty</h3><p>Add songs from your library to start building it.</p><div style="margin-top:6px;">${addPlaylistBtn}</div></div>`;
        (_d = $("#btnAddPlaylistTracks")) == null ? void 0 : _d.addEventListener("click", () => openPlaylistLibraryPicker(playlist.id));
        return;
      }
      content.innerHTML = `<div class="empty"><div class="empty-orb"></div><h3>No matches</h3><p>Try a different search term, or browse your full library.</p></div>`;
      return;
    }
    const toolbar = addPlaylistBtn ? `<div class="queue-toolbar">${addPlaylistBtn}</div>` : "";
    if (state.listMode === "grid") {
      content.innerHTML = `${toolbar}<div class="grid">${list.map((t) => cardMarkup(t)).join("")}</div>`;
    } else {
      content.innerHTML = `
      ${toolbar}
      <div class="list">
        <div class="list-head"><div></div><div>Title</div><div>Album</div><div>Time</div><div></div></div>
        ${list.map((t, i) => trackRowMarkup(t, i)).join("")}
      </div>`;
    }
    (_e = $("#btnAddPlaylistTracks")) == null ? void 0 : _e.addEventListener("click", () => openPlaylistLibraryPicker(playlist.id));
    wireTrackInteractions(list);
  }
  function emptyStateMarkup() {
    return `
  <div class="empty">
    <div class="empty-orb"></div>
    <h3>Your library is empty</h3>
    <p>Add songs or a folder. Auralis saves them on this computer so they come back next time.</p>
    <div style="display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin-top:6px;">
      <button class="btn btn-primary" id="emptyAddFiles">Add music</button>
      <button class="btn" id="emptyAddFolder">Add folder</button>
    </div>
  </div>`;
  }
  function wireArtistLinks(root = document) {
    root.querySelectorAll('[data-action="artist"]').forEach((el) => {
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        openArtist(decodeURIComponent(el.dataset.artist || ""));
      });
    });
  }
  function wireTrackInteractions(list) {
    $$(".card").forEach((card) => {
      var _a2;
      const t = state.tracks.find((x) => x.id === card.dataset.id);
      card.addEventListener("click", (e) => {
        if (e.target.closest('[data-action="fav"],[data-action="queue"],[data-action="artist"]')) return;
        playTrackFromList(list, t.id);
      });
      card.querySelector('[data-action="fav"]').addEventListener("click", (e) => {
        e.stopPropagation();
        toggleFavorite(t);
      });
      (_a2 = card.querySelector('[data-action="queue"]')) == null ? void 0 : _a2.addEventListener("click", (e) => {
        e.stopPropagation();
        addToQueue(t);
      });
      card.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        openTrackMenu(e, t);
      });
    });
    $$(".row").forEach((row) => {
      var _a2;
      const t = state.tracks.find((x) => x.id === row.dataset.id);
      row.addEventListener("click", (e) => {
        if (e.target.closest('[data-action="fav"],[data-action="queue"],[data-action="menu"],[data-action="artist"]')) return;
        playTrackFromList(list, t.id);
      });
      row.querySelector('[data-action="fav"]').addEventListener("click", (e) => {
        e.stopPropagation();
        toggleFavorite(t);
      });
      (_a2 = row.querySelector('[data-action="queue"]')) == null ? void 0 : _a2.addEventListener("click", (e) => {
        e.stopPropagation();
        addToQueue(t);
      });
      const menuBtn = row.querySelector('[data-action="menu"]');
      if (menuBtn) menuBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        openTrackMenu(e, t);
      });
      row.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        openTrackMenu(e, t);
      });
      row.addEventListener("dragstart", (e) => {
        e.dataTransfer.setData("text/plain", t.id);
      });
    });
    wireArtistLinks($("#content"));
  }
  function toggleFavorite(t) {
    var _a2;
    t.favorite = !t.favorite;
    saveLibraryMeta();
    render();
    if (((_a2 = currentTrack()) == null ? void 0 : _a2.id) === t.id) $("#nowFav").classList.toggle("on", t.favorite);
  }
  function openTrackMenu(e, t) {
    var _a2, _b2;
    closeMenus();
    const menu = document.createElement("div");
    menu.className = "menu";
    const anchor = (_b2 = (_a2 = e.target).closest) == null ? void 0 : _b2.call(_a2, "button");
    if (anchor) {
      const rect = anchor.getBoundingClientRect();
      menu.style.top = rect.bottom + 6 + "px";
      menu.style.left = Math.min(window.innerWidth - 210, rect.left - 150) + "px";
    } else {
      menu.style.top = Math.min(window.innerHeight - 160, e.clientY + 4) + "px";
      menu.style.left = Math.min(window.innerWidth - 210, e.clientX) + "px";
    }
    const inPlaylist = state.view.startsWith("playlist:") ? state.view.slice(9) : null;
    menu.innerHTML = `
    <div class="menu-item" data-act="queue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 6h16M4 12h10M4 18h10"/></svg>Add to queue</div>
    <div class="menu-item" data-act="playlist"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 5v14M5 12h14"/></svg>Add to playlist</div>
    <div class="menu-sep"></div>
    ${inPlaylist ? `<div class="menu-item" data-act="remove-from-playlist"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 6l12 12M18 6 6 18"/></svg>Remove from this playlist</div>` : ""}
    <div class="menu-item" data-act="remove"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/></svg>Remove from library</div>
  `;
    document.body.appendChild(menu);
    menu.querySelector('[data-act="queue"]').addEventListener("click", () => {
      addToQueue(t);
      closeMenus();
    });
    menu.querySelector('[data-act="playlist"]').addEventListener("click", (ev) => {
      openPlaylistSubmenu(ev, t, menu);
    });
    if (inPlaylist) menu.querySelector('[data-act="remove-from-playlist"]').addEventListener("click", () => {
      removeFromPlaylist(inPlaylist, t);
      closeMenus();
    });
    menu.querySelector('[data-act="remove"]').addEventListener("click", () => {
      removeTrack(t);
      closeMenus();
    });
    setTimeout(() => document.addEventListener("click", closeMenus, { once: true }), 0);
  }
  function openPlaylistSubmenu(e, t, parentMenu) {
    e.stopPropagation();
    const old = parentMenu.querySelector(".menu-sub");
    if (old) old.remove();
    const sub = document.createElement("div");
    sub.className = "menu menu-sub";
    const items = state.playlists.map((p) => `<div class="menu-item" data-pl="${p.id}">${escapeHtml(p.name)}</div>`).join("");
    sub.innerHTML = items + `<div class="menu-sep"></div><div class="menu-item" data-pl="new"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 5v14M5 12h14"/></svg>New playlist\u2026</div>`;
    parentMenu.appendChild(sub);
    sub.querySelectorAll("[data-pl]").forEach((item) => {
      item.addEventListener("click", () => {
        if (item.dataset.pl === "new") {
          const name = prompt("Name your playlist");
          if (name && name.trim()) {
            const pl = { id: uid(), name: name.trim(), trackIds: [t.id] };
            state.playlists.push(pl);
            saveLibraryMeta();
            toast(`Created \u201C${pl.name}\u201D and added the track.`);
          }
        } else {
          addTrackToPlaylist(item.dataset.pl, t);
        }
        closeMenus();
        render();
      });
    });
  }
  function closeMenus() {
    $$(".menu").forEach((m) => m.remove());
  }
  function stopPlayback() {
    audioEl.pause();
    audioEl.removeAttribute("src");
    audioEl.load();
    if (currentBlobUrl) {
      URL.revokeObjectURL(currentBlobUrl);
      currentBlobUrl = null;
    }
    updateNowPlayingUI();
    syncPlayIcons(false);
  }
  function removeQueueSlot(i) {
    if (i < 0 || i >= state.queue.length) return;
    const removingCurrent = i === state.queueIndex;
    state.queue.splice(i, 1);
    if (state.queue.length === 0) {
      state.queueIndex = -1;
      stopPlayback();
      return;
    }
    if (i < state.queueIndex) state.queueIndex--;
    else if (removingCurrent) {
      if (state.queueIndex >= state.queue.length) state.queueIndex = state.queue.length - 1;
      playCurrent();
    }
  }
  function removeTrack(t) {
    return __async(this, null, function* () {
      var _a2;
      const playingId = ((_a2 = currentTrack()) == null ? void 0 : _a2.id) || null;
      const wasPlaying = playingId === t.id;
      if (!(yield deleteTrackOnServer(t.id))) {
        toast("Could not remove the track. Please try again.");
        return;
      }
      state.tracks = state.tracks.filter((x) => x.id !== t.id);
      state.playlists.forEach((p) => p.trackIds = p.trackIds.filter((id) => id !== t.id));
      state.queue = state.queue.filter((id) => id !== t.id);
      if (wasPlaying) {
        if (state.queue.length === 0) {
          state.queueIndex = -1;
          stopPlayback();
        } else {
          if (state.queueIndex >= state.queue.length) state.queueIndex = state.queue.length - 1;
          if (state.queueIndex < 0) state.queueIndex = 0;
          playCurrent();
        }
      } else if (playingId) {
        state.queueIndex = state.queue.indexOf(playingId);
      } else if (state.queueIndex >= state.queue.length) {
        state.queueIndex = state.queue.length ? state.queue.length - 1 : -1;
      }
      if (t.art && t.art.startsWith("blob:")) URL.revokeObjectURL(t.art);
      saveLibraryMeta();
      toast(`Removed \u201C${t.title}\u201D.`);
      render();
    });
  }
  function removeFromPlaylist(playlistId, t) {
    const pl = state.playlists.find((p) => p.id === playlistId);
    if (!pl) return;
    pl.trackIds = pl.trackIds.filter((id) => id !== t.id);
    saveLibraryMeta();
    toast(`Removed \u201C${t.title}\u201D from \u201C${pl.name}\u201D.`);
    render();
  }
  function addToQueue(t) {
    state.queue.push(t.id);
    if (state.queueIndex < 0) state.queueIndex = 0;
    toast(`Added \u201C${t.title}\u201D to the queue.`);
    renderQueuePanel();
    if (state.view === "queue") renderQueueView();
  }
  function addTrackToPlaylist(playlistId, t, { quiet = false } = {}) {
    const pl = state.playlists.find((p) => p.id === playlistId);
    if (!pl) return false;
    if (pl.trackIds.includes(t.id)) {
      if (!quiet) toast(`Already in \u201C${pl.name}\u201D.`);
      return false;
    }
    pl.trackIds.push(t.id);
    saveLibraryMeta();
    if (!quiet) toast(`Added to \u201C${pl.name}\u201D.`);
    if (state.view === "playlist:" + playlistId) renderTrackListView();
    renderTopbar();
    return true;
  }
  let accountInfo = null;
  function fetchAccountInfo() {
    return __async(this, null, function* () {
      try {
        const res = yield fetch("/api/me");
        if (res.ok) accountInfo = yield res.json();
      } catch (_) {
      }
      return accountInfo;
    });
  }
  function fmtDate(unixSeconds) {
    if (!unixSeconds) return "\u2014";
    try {
      return new Date(unixSeconds * 1e3).toLocaleDateString(void 0, { year: "numeric", month: "long", day: "numeric" });
    } catch (_) {
      return "\u2014";
    }
  }
  function renderAccountView() {
    return __async(this, null, function* () {
      const content = $("#content");
      if (!accountInfo) {
        content.innerHTML = `<div class="account-view acct-loading">Loading account\u2026</div>`;
        yield fetchAccountInfo();
        if (state.view !== "account") return;
      }
      const info = accountInfo;
      const liked = state.tracks.filter((t) => t.favorite);
      const playlists = state.playlists;
      const artists = getArtists();
      content.innerHTML = `
    <div class="account-view">
      <section class="acct-card">
        <div class="acct-avatar">${escapeHtml(((info == null ? void 0 : info.username) || "?").slice(0, 1).toUpperCase())}</div>
        <div>
          <div class="acct-name">${escapeHtml((info == null ? void 0 : info.username) || "Unknown")}</div>
          <div class="acct-sub">${escapeHtml((info == null ? void 0 : info.email) || "No email on file")} \xB7 Member since ${fmtDate(info == null ? void 0 : info.created_at)}</div>
        </div>
      </section>

      <div class="acct-grid">
        <section class="acct-panel" data-nav="library">
          <div class="acct-panel-head">
            <span>Music files</span><span class="acct-count">${state.tracks.length}</span>
          </div>
          <div class="acct-panel-sub">tracks in your library</div>
        </section>
        <section class="acct-panel" data-nav="favorites">
          <div class="acct-panel-head">
            <span>Liked songs</span><span class="acct-count">${liked.length}</span>
          </div>
          <div class="acct-panel-sub">${liked.slice(0, 3).map((t) => escapeHtml(t.title)).join(", ") || "None yet"}</div>
        </section>
        <section class="acct-panel" data-nav="artists">
          <div class="acct-panel-head">
            <span>Artists</span><span class="acct-count">${artists.length}</span>
          </div>
          <div class="acct-panel-sub">${artists.slice(0, 3).map((a) => escapeHtml(a.name)).join(", ") || "None yet"}</div>
        </section>
        <section class="acct-panel" data-nav="playlists">
          <div class="acct-panel-head">
            <span>Playlists</span><span class="acct-count">${playlists.length}</span>
          </div>
          <div class="acct-panel-sub">${playlists.slice(0, 3).map((p) => escapeHtml(p.name)).join(", ") || "None yet"}</div>
        </section>
      </div>

      <section class="acct-settings">
        <div class="acct-settings-title">Change password</div>
        <form id="pwForm" class="acct-form">
          <input type="password" id="pwCurrent" placeholder="Current password" autocomplete="current-password" required>
          <input type="password" id="pwNew" placeholder="New password (min 8 characters)" autocomplete="new-password" required minlength="8">
          <button type="submit" class="btn btn-primary">Update password</button>
          <div class="acct-form-msg" id="pwMsg"></div>
        </form>
      </section>

      <section class="acct-settings">
        <div class="acct-settings-title">Session</div>
        <button type="button" class="btn" id="btnAcctLogout">Log out</button>
      </section>
    </div>`;
      $$(".acct-panel[data-nav]").forEach((panel) => {
        panel.addEventListener("click", () => {
          state.view = panel.dataset.nav;
          render();
        });
      });
      const acctLogout = $("#btnAcctLogout");
      if (acctLogout) acctLogout.addEventListener("click", () => logoutAndRedirect());
      const pwForm = $("#pwForm");
      pwForm.addEventListener("submit", (e) => __async(null, null, function* () {
        e.preventDefault();
        const msg = $("#pwMsg");
        const current_password = $("#pwCurrent").value;
        const new_password = $("#pwNew").value;
        msg.textContent = "Updating\u2026";
        msg.className = "acct-form-msg";
        try {
          const res = yield fetch("/api/account/password", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRF-Token": yield ensureCsrfToken() },
            body: JSON.stringify({ current_password, new_password })
          });
          const data = yield res.json().catch(() => ({}));
          if (!res.ok) throw new Error(data.detail || "Could not update password");
          msg.textContent = "Password updated.";
          msg.className = "acct-form-msg ok";
          pwForm.reset();
        } catch (err) {
          msg.textContent = err.message;
          msg.className = "acct-form-msg error";
        }
      }));
    });
  }
  function renderPlaylistsView() {
    const content = $("#content");
    const cards = state.playlists.map((p) => `
    <div class="pl-card" data-id="${p.id}">
      <div class="pl-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 6h13M4 12h13M4 18h9"/><circle cx="20" cy="16" r="2.4"/><path d="M20 6v10"/></svg></div>
      <div class="pl-name">${escapeHtml(p.name)}</div>
      <div class="pl-count">${p.trackIds.length} track${p.trackIds.length !== 1 ? "s" : ""}</div>
    </div>`).join("");
    content.innerHTML = `
    <div class="pl-grid">
      ${cards}
      <div class="pl-card pl-new" id="plNewCard">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="22" height="22"><path d="M12 5v14M5 12h14"/></svg>
        New playlist
      </div>
    </div>`;
    $$(".pl-card[data-id]").forEach((card) => {
      card.addEventListener("click", () => {
        state.view = "playlist:" + card.dataset.id;
        render();
      });
    });
    $("#plNewCard").addEventListener("click", () => {
      const name = prompt("Name your playlist");
      if (name && name.trim()) {
        const pl = { id: uid(), name: name.trim(), trackIds: [] };
        state.playlists.push(pl);
        saveLibraryMeta();
        state.view = "playlist:" + pl.id;
        render();
      }
    });
  }
  function renderArtistsView() {
    var _a2, _b2;
    const content = $("#content");
    if (state.tracks.length === 0) {
      content.innerHTML = emptyStateMarkup();
      (_a2 = $("#emptyAddFiles")) == null ? void 0 : _a2.addEventListener("click", () => $("#fileInput").click());
      (_b2 = $("#emptyAddFolder")) == null ? void 0 : _b2.addEventListener("click", connectMusicFolder);
      return;
    }
    let artists = getArtists();
    if (state.search.trim()) {
      const q = state.search.toLowerCase();
      artists = artists.filter((a) => a.name.toLowerCase().includes(q));
    }
    if (artists.length === 0) {
      content.innerHTML = `<div class="empty"><div class="empty-orb"></div><h3>No matches</h3><p>Try a different search term, or browse your full library.</p></div>`;
      return;
    }
    content.innerHTML = `
    <div class="artist-grid">
      ${artists.map((a) => `
        <button type="button" class="artist-card" data-artist="${encodeURIComponent(a.name)}">
          <img class="artist-card-photo" data-artist-photo="${escapeHtml(a.name)}" src="${a.art}" alt="${escapeHtml(a.name)}">
          <div class="artist-card-name">${escapeHtml(a.name)}</div>
          <div class="artist-card-count">${a.tracks.length} song${a.tracks.length !== 1 ? "s" : ""}</div>
        </button>`).join("")}
    </div>`;
    ArtistPhotoEngine.resolveAll(artists);
    $$(".artist-card").forEach((card) => {
      card.addEventListener("click", () => openArtist(decodeURIComponent(card.dataset.artist)));
    });
  }
  function renderArtistDetailView() {
    const content = $("#content");
    const name = artistNameFromView(state.view);
    const artist = getArtists().find((a) => artistKey(a.name) === artistKey(name));
    if (!artist) {
      content.innerHTML = `<div class="empty"><div class="empty-orb"></div><h3>Artist not found</h3><p>This artist no longer has songs in your library.</p></div>`;
      return;
    }
    const list = getVisibleTracks();
    const libraryFacts = [
      ["Songs", artist.tracks.length],
      ["Albums", artist.albumCount],
      ["Play time", artist.duration > 0 ? fmtLongDuration(artist.duration) : null]
    ].filter(([, value]) => value !== null && value !== void 0);
    const tracksHtml = list.length === 0 ? `<div class="empty"><div class="empty-orb"></div><h3>No matches</h3><p>Try a different search term.</p></div>` : state.listMode === "grid" ? `<div class="grid">${list.map((t) => cardMarkup(t)).join("")}</div>` : `<div class="list">
          <div class="list-head"><div></div><div>Title</div><div>Album</div><div>Time</div><div></div></div>
          ${list.map((t, i) => trackRowMarkup(t, i)).join("")}
        </div>`;
    content.innerHTML = `
    <div class="artist-page">
      <header class="artist-hero">
        <img class="artist-photo" data-artist-photo="${escapeHtml(artist.name)}" src="${artist.art}" alt="${escapeHtml(artist.name)}">
        <div class="artist-hero-meta">
          <div class="artist-kicker">Artist</div>
          <h1 class="artist-name">${escapeHtml(artist.name)}</h1>
          <div class="artist-sub">${artist.tracks.length} song${artist.tracks.length !== 1 ? "s" : ""} in your library${artist.albumCount ? ` \xB7 ${artist.albumCount} album${artist.albumCount !== 1 ? "s" : ""}` : ""}</div>
        </div>
      </header>
      <section class="artist-library-info" aria-label="Library information">
        ${libraryFacts.map(([label, value]) => `<div class="artist-library-stat"><span>${label}</span><strong>${escapeHtml(String(value))}</strong></div>`).join("")}
      </section>
      <section class="artist-info" data-artist-profile="${escapeHtml(artist.name)}" aria-busy="true">
        <h2>About</h2>
        <p class="artist-bio" data-artist-bio>Looking up artist details\u2026</p>
        <div class="artist-tags" data-artist-tags hidden></div>
        <p class="artist-source" data-artist-source hidden></p>
        <a class="artist-website" data-artist-website hidden target="_blank" rel="noopener noreferrer">Source page <span aria-hidden="true">\u2197</span></a>
      </section>
      ${tracksHtml}
    </div>`;
    ArtistPhotoEngine.resolve(artist.name);
    ArtistProfileEngine.resolve(artist.name);
    if (list.length) wireTrackInteractions(list);
  }
  function renderQueueView() {
    var _a2, _b2;
    const content = $("#content");
    const addBtn = `<button class="btn" id="btnAddQueueView" type="button">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
      Add from library
    </button>`;
    if (state.queue.length === 0) {
      content.innerHTML = `<div class="empty"><div class="empty-orb"></div><h3>Queue is empty</h3><p>Add songs from your library to build an up-next list.</p><div style="margin-top:6px;">${addBtn}</div></div>`;
      (_a2 = $("#btnAddQueueView")) == null ? void 0 : _a2.addEventListener("click", openQueueLibraryPicker);
      return;
    }
    const rows = state.queue.map((id, i) => {
      const t = state.tracks.find((x) => x.id === id);
      if (!t) return "";
      const playing = i === state.queueIndex;
      const title = escapeHtml(t.title);
      return `
    <div class="row" data-id="${t.id}" data-qi="${i}" draggable="true">
      <div class="row-idx"><span class="num">${i + 1}</span></div>
      <div class="row-title-wrap">
        <img class="row-art" src="${t.art}" alt="">
        <div class="row-title-stack">
          <div class="row-title" title="${title}">${title}</div>
          <div class="row-meta"><div class="row-artist">${artistLinksMarkup(t)}</div></div>
        </div>
      </div>
      <div class="row-time">${t.duration ? fmtTime(t.duration) : "--:--"}</div>
      <div class="row-actions"><button data-act="remove"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6 6 18"/></svg></button></div>
    </div>`;
    }).join("");
    content.innerHTML = `<div class="queue-toolbar">${addBtn}</div><div class="list">${rows}</div>`;
    (_b2 = $("#btnAddQueueView")) == null ? void 0 : _b2.addEventListener("click", openQueueLibraryPicker);
    let dragSrcIndex = null;
    $$(".row[data-qi]").forEach((row) => {
      row.addEventListener("click", (e) => {
        if (e.target.closest("button")) return;
        state.queueIndex = +row.dataset.qi;
        playCurrent();
      });
      row.querySelector('[data-act="remove"]').addEventListener("click", (e) => {
        e.stopPropagation();
        removeQueueSlot(+row.dataset.qi);
        render();
      });
      row.addEventListener("dragstart", (e) => {
        dragSrcIndex = +row.dataset.qi;
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(dragSrcIndex));
        row.classList.add("dragging");
      });
      row.addEventListener("dragend", () => row.classList.remove("dragging"));
      row.addEventListener("dragover", (e) => {
        if (dragSrcIndex === null) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        row.classList.add("drag-over");
      });
      row.addEventListener("dragleave", () => row.classList.remove("drag-over"));
      row.addEventListener("drop", (e) => {
        if (dragSrcIndex === null) return;
        e.preventDefault();
        row.classList.remove("drag-over");
        const toIndex = +row.dataset.qi;
        if (dragSrcIndex !== toIndex) reorderQueue(dragSrcIndex, toIndex);
        dragSrcIndex = null;
        renderQueueView();
        renderQueuePanel();
      });
    });
    wireArtistLinks(content);
  }
  function renderQueuePanel() {
    var _a2;
    const el = $("#queueList");
    if (state.queue.length === 0) {
      el.innerHTML = `<div class="side-empty"><p>Nothing queued yet.</p><button class="btn" id="btnAddQueueEmpty" type="button"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>Add from library</button></div>`;
      (_a2 = $("#btnAddQueueEmpty")) == null ? void 0 : _a2.addEventListener("click", openQueueLibraryPicker);
      return;
    }
    el.innerHTML = state.queue.map((id, i) => {
      const t = state.tracks.find((x) => x.id === id);
      if (!t) return "";
      return `
    <div class="q-row ${i === state.queueIndex ? "playing" : ""}" data-i="${i}" draggable="true">
      <span class="q-drag"><svg viewBox="0 0 24 24" fill="currentColor"><circle cx="8" cy="6" r="1.4"/><circle cx="8" cy="12" r="1.4"/><circle cx="8" cy="18" r="1.4"/><circle cx="16" cy="6" r="1.4"/><circle cx="16" cy="12" r="1.4"/><circle cx="16" cy="18" r="1.4"/></svg></span>
      <img src="${t.art}">
      <div class="q-meta"><div class="q-title">${escapeHtml(t.title)}</div><div class="q-artist">${escapeHtml(t.artist)}</div></div>
      <button class="q-remove" data-act="rm"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
    </div>`;
    }).join("");
    let dragSrcIndex = null;
    el.querySelectorAll(".q-row").forEach((row) => {
      row.addEventListener("click", (e) => {
        if (e.target.closest("button")) return;
        state.queueIndex = +row.dataset.i;
        playCurrent();
      });
      row.querySelector('[data-act="rm"]').addEventListener("click", (e) => {
        e.stopPropagation();
        removeQueueSlot(+row.dataset.i);
        renderQueuePanel();
        if (state.view === "queue") renderQueueView();
      });
      row.addEventListener("dragstart", (e) => {
        dragSrcIndex = +row.dataset.i;
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(dragSrcIndex));
        row.classList.add("dragging");
      });
      row.addEventListener("dragend", () => row.classList.remove("dragging"));
      row.addEventListener("dragover", (e) => {
        if (dragSrcIndex === null) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        row.classList.add("drag-over");
      });
      row.addEventListener("dragleave", () => row.classList.remove("drag-over"));
      row.addEventListener("drop", (e) => {
        if (dragSrcIndex === null) return;
        e.preventDefault();
        row.classList.remove("drag-over");
        const toIndex = +row.dataset.i;
        if (dragSrcIndex !== toIndex) reorderQueue(dragSrcIndex, toIndex);
        dragSrcIndex = null;
        renderQueuePanel();
        if (state.view === "queue") renderQueueView();
      });
    });
  }
  let libraryPickerTarget = { mode: "queue" };
  function openQueueLibraryPicker() {
    openLibraryPicker({ mode: "queue" });
  }
  function openPlaylistLibraryPicker(playlistId) {
    openLibraryPicker({ mode: "playlist", playlistId });
  }
  function openLibraryPicker(target) {
    const overlay = $("#queuePicker");
    if (!overlay) return;
    libraryPickerTarget = target || { mode: "queue" };
    const search = $("#queuePickerSearch");
    if (search) search.value = "";
    const title = overlay.querySelector(".queue-picker-head h3");
    if (title) {
      if (libraryPickerTarget.mode === "playlist") {
        const pl = state.playlists.find((p) => p.id === libraryPickerTarget.playlistId);
        title.textContent = pl ? `Add to \u201C${pl.name}\u201D` : "Add to playlist";
      } else {
        title.textContent = "Add from library";
      }
    }
    overlay.setAttribute("aria-label", (title == null ? void 0 : title.textContent) || "Add from library");
    renderLibraryPicker();
    overlay.classList.add("open");
    setTimeout(() => search == null ? void 0 : search.focus(), 30);
  }
  function closeQueueLibraryPicker() {
    var _a2;
    (_a2 = $("#queuePicker")) == null ? void 0 : _a2.classList.remove("open");
  }
  function renderQueueLibraryPicker() {
    renderLibraryPicker();
  }
  function renderLibraryPicker() {
    var _a2;
    const listEl = $("#queuePickerList");
    if (!listEl) return;
    const forPlaylist = libraryPickerTarget.mode === "playlist";
    const pl = forPlaylist ? state.playlists.find((p) => p.id === libraryPickerTarget.playlistId) : null;
    if (state.tracks.length === 0) {
      listEl.innerHTML = `<div class="queue-picker-empty">Your library is empty. Add music first, then come back to build a ${forPlaylist ? "playlist" : "queue"}.</div>`;
      return;
    }
    const q = (((_a2 = $("#queuePickerSearch")) == null ? void 0 : _a2.value) || "").trim().toLowerCase();
    const tracks = q ? state.tracks.filter((t) => (t.title + " " + t.artist + " " + t.album).toLowerCase().includes(q)) : state.tracks;
    if (!tracks.length) {
      listEl.innerHTML = `<div class="queue-picker-empty">No matches for that search.</div>`;
      return;
    }
    listEl.innerHTML = tracks.map((t) => {
      const inPlaylist = !!(pl && pl.trackIds.includes(t.id));
      return `
    <button type="button" class="qp-row${inPlaylist ? " in-playlist" : ""}" data-id="${t.id}" ${inPlaylist ? 'aria-disabled="true"' : ""}>
      <img src="${t.art}" alt="">
      <div class="qp-meta">
        <div class="qp-title">${escapeHtml(t.title)}</div>
        <div class="qp-artist">${escapeHtml(t.artist)}</div>
      </div>
      <span class="qp-add" aria-hidden="true">${inPlaylist ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 12l5 5L20 7"/></svg>` : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>`}</span>
    </button>`;
    }).join("");
    listEl.querySelectorAll(".qp-row").forEach((row) => {
      row.addEventListener("click", () => {
        const t = state.tracks.find((x) => x.id === row.dataset.id);
        if (!t) return;
        if (libraryPickerTarget.mode === "playlist") {
          if (row.classList.contains("in-playlist")) {
            toast(`Already in this playlist.`);
            return;
          }
          if (addTrackToPlaylist(libraryPickerTarget.playlistId, t)) {
            renderLibraryPicker();
          }
        } else {
          addToQueue(t);
        }
      });
    });
  }
  function on(sel, event, handler) {
    const el = typeof sel === "string" ? $(sel) : sel;
    if (!el) {
      console.warn("Auralis: missing element", sel);
      return;
    }
    el.addEventListener(event, handler);
  }
  on("#btnImportTop", "click", () => {
    var _a2;
    return (_a2 = $("#fileInput")) == null ? void 0 : _a2.click();
  });
  on("#btnImportRail", "click", () => {
    var _a2;
    return (_a2 = $("#fileInput")) == null ? void 0 : _a2.click();
  });
  on("#fileInput", "change", (e) => {
    importFiles(e.target.files);
    e.target.value = "";
  });
  on("#folderInput", "change", (e) => {
    importFiles(e.target.files);
    e.target.value = "";
  });
  $$(".rail-btn[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.view = btn.dataset.view;
      state.search = "";
      $("#searchInput").value = "";
      render();
    });
  });
  $$("#viewToggle button").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.listMode = btn.dataset.mode;
      $$("#viewToggle button").forEach((b) => b.classList.toggle("active", b === btn));
      saveSettings();
      render();
    });
  });
  on("#searchInput", "input", (e) => {
    state.search = e.target.value;
    if (state.view === "artists") renderArtistsView();
    else if (state.view.startsWith("artist:")) renderArtistDetailView();
    else renderTrackListView();
    renderTopbar();
  });
  on("#nowArtist", "click", (e) => {
    const btn = e.target.closest('[data-action="artist"]');
    if (btn) {
      openArtist(decodeURIComponent(btn.dataset.artist || ""));
      return;
    }
    const t = currentTrack();
    if (!t) return;
    const names = artistsOf(t);
    if (names[0]) openArtist(names[0]);
  });
  on("#btnPlay", "click", togglePlay);
  on("#miniPlay", "click", togglePlay);
  on("#btnNext", "click", () => playNext(false));
  on("#miniNext", "click", () => playNext(false));
  on("#btnPrev", "click", playPrev);
  on("#miniPrev", "click", playPrev);
  on("#btnShuffle", "click", () => {
    state.shuffle = !state.shuffle;
    $("#btnShuffle").classList.toggle("on", state.shuffle);
    saveSettings();
    toast(state.shuffle ? "Shuffle on" : "Shuffle off");
  });
  on("#btnRepeat", "click", () => {
    state.repeat = state.repeat === "off" ? "all" : state.repeat === "all" ? "one" : "off";
    $("#btnRepeat").classList.toggle("on", state.repeat !== "off");
    $("#btnRepeat").title = "Repeat: " + state.repeat;
    saveSettings();
    toast("Repeat: " + state.repeat);
  });
  on("#nowFav", "click", () => {
    const t = currentTrack();
    if (t) toggleFavorite(t);
  });
  on("#mobilePlayerFav", "click", () => {
    const t = currentTrack();
    if (t) toggleFavorite(t);
  });
  on("#nowbar", "click", (e) => {
    if (window.matchMedia("(max-width: 900px)").matches && !e.target.closest("button,.seek")) {
      $("#mobilePlayer").classList.add("open");
      updateNowPlayingUI();
    }
  });
  on("#btnMobilePlayerClose", "click", () => $("#mobilePlayer").classList.remove("open"));
  on("#mobilePlay", "click", togglePlay);
  on("#mobileNext", "click", () => playNext(false));
  on("#mobilePrev", "click", playPrev);
  on("#mobileShuffle", "click", () => $("#btnShuffle").click());
  on("#mobileRepeat", "click", () => $("#btnRepeat").click());
  on("#mobileLyrics", "click", () => {
    $("#mobilePlayer").classList.remove("open");
    openLyrics();
  });
  on("#mobileLyricsOpen", "click", (e) => {
    e.stopPropagation();
    $("#mobilePlayer").classList.remove("open");
    openLyrics();
  });
  on("#mobileLyricsCard", "click", () => {
    $("#mobilePlayer").classList.remove("open");
    openLyrics();
  });
  on("#mobileLyricsCard", "keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      $("#mobilePlayer").classList.remove("open");
      openLyrics();
    }
  });
  on("#mobileQueue", "click", () => {
    $("#mobilePlayer").classList.remove("open");
    $("#sidePanel").classList.add("open");
  });
  function seekTo(clientX, seekEl) {
    const rect = seekEl.getBoundingClientRect();
    const pct = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    if (audioEl.duration) audioEl.currentTime = pct * audioEl.duration;
  }
  [$("#seek"), $("#miniSeek"), $("#mobileSeek")].forEach((el) => {
    if (el) el.addEventListener("click", (e) => seekTo(e.clientX, el));
  });
  on("#volTrack", "click", (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setVolume((e.clientX - rect.left) / rect.width);
  });
  on("#btnMute", "click", () => {
    state.muted = !state.muted;
    audioEl.volume = state.muted ? 0 : state.volume;
    updateVolUI();
    saveSettings();
  });
  on("#btnLyrics", "click", () => $("#lyricsOverlay").classList.contains("open") ? closeLyrics() : openLyrics());
  on("#lyricsClose", "click", closeLyrics);
  on("#lyricsOverlay", "click", (e) => {
    if (e.target.id === "lyricsOverlay") closeLyrics();
  });
  on("#btnViz", "click", openViz);
  on("#vizClose", "click", closeViz);
  on("#vizOverlay", "click", (e) => {
    if (e.target.id === "vizOverlay") closeViz();
  });
  on("#btnQueueToggle", "click", () => $("#sidePanel").classList.toggle("open"));
  on("#btnCloseQueue", "click", () => $("#sidePanel").classList.remove("open"));
  on("#btnAddQueueSide", "click", openQueueLibraryPicker);
  on("#btnCloseQueuePicker", "click", closeQueueLibraryPicker);
  on("#queuePicker", "click", (e) => {
    if (e.target.id === "queuePicker") closeQueueLibraryPicker();
  });
  on("#queuePickerSearch", "input", () => renderQueueLibraryPicker());
  on("#btnLogout", "click", () => logoutAndRedirect());
  on("#btnMini", "click", () => enterMiniMode());
  on("#btnMiniExit", "click", () => exitMiniMode());
  function enterMiniMode() {
    document.body.classList.add("mini-mode");
    const mp = $("#miniPlayer");
    mp.style.right = "24px";
    mp.style.bottom = "24px";
    mp.style.left = "auto";
    mp.style.top = "auto";
  }
  function exitMiniMode() {
    document.body.classList.remove("mini-mode");
  }
  (function() {
    const mp = $("#miniPlayer"), handle = $("#miniDrag");
    if (!mp || !handle) return;
    let dragging = false, offX = 0, offY = 0;
    handle.addEventListener("pointerdown", (e) => {
      dragging = true;
      const r = mp.getBoundingClientRect();
      offX = e.clientX - r.left;
      offY = e.clientY - r.top;
      handle.setPointerCapture(e.pointerId);
    });
    handle.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      mp.style.left = Math.max(4, Math.min(window.innerWidth - 304, e.clientX - offX)) + "px";
      mp.style.top = Math.max(4, Math.min(window.innerHeight - 320, e.clientY - offY)) + "px";
      mp.style.right = "auto";
      mp.style.bottom = "auto";
    });
    handle.addEventListener("pointerup", () => dragging = false);
  })();
  on("#btnShortcuts", "click", () => $("#shortcutsOverlay").classList.add("open"));
  on("#shortcutsOverlay", "click", (e) => {
    if (e.target.id === "shortcutsOverlay") $("#shortcutsOverlay").classList.remove("open");
  });
  document.addEventListener("keydown", (e) => {
    var _a2, _b2, _c, _d, _e, _f, _g, _h, _i, _j, _k;
    const tag = (e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea") {
      if (e.key === "Escape") {
        if ((_a2 = $("#queuePicker")) == null ? void 0 : _a2.classList.contains("open")) closeQueueLibraryPicker();
        else e.target.blur();
      }
      return;
    }
    if (e.key === "/") {
      e.preventDefault();
      (_b2 = $("#searchInput")) == null ? void 0 : _b2.focus();
      return;
    }
    if (e.key === "?") {
      (_c = $("#shortcutsOverlay")) == null ? void 0 : _c.classList.toggle("open");
      return;
    }
    if (e.key === "Escape") {
      if ((_d = $("#queuePicker")) == null ? void 0 : _d.classList.contains("open")) {
        closeQueueLibraryPicker();
        return;
      }
      (_e = $("#mobilePlayer")) == null ? void 0 : _e.classList.remove("open");
      (_f = $("#shortcutsOverlay")) == null ? void 0 : _f.classList.remove("open");
      (_g = $("#sidePanel")) == null ? void 0 : _g.classList.remove("open");
      (_h = $("#dropOverlay")) == null ? void 0 : _h.classList.remove("show");
      dragCounter = 0;
      closeViz();
      closeLyrics();
      closeMenus();
      return;
    }
    switch (e.key) {
      case " ":
        e.preventDefault();
        togglePlay();
        break;
      case "ArrowRight":
        if (e.shiftKey) playNext(false);
        else if (audioEl.duration) audioEl.currentTime = Math.min(audioEl.duration, audioEl.currentTime + 5);
        break;
      case "ArrowLeft":
        if (e.shiftKey) playPrev();
        else audioEl.currentTime = Math.max(0, audioEl.currentTime - 5);
        break;
      case "ArrowUp":
        e.preventDefault();
        setVolume(state.volume + 0.05);
        break;
      case "ArrowDown":
        e.preventDefault();
        setVolume(state.volume - 0.05);
        break;
      case "m":
      case "M":
        (_i = $("#btnMute")) == null ? void 0 : _i.click();
        break;
      case "f":
      case "F": {
        const t = currentTrack();
        if (t) toggleFavorite(t);
        break;
      }
      case "n":
      case "N":
        document.body.classList.contains("mini-mode") ? exitMiniMode() : enterMiniMode();
        break;
      case "l":
      case "L":
        ((_j = $("#lyricsOverlay")) == null ? void 0 : _j.classList.contains("open")) ? closeLyrics() : openLyrics();
        break;
      case "v":
      case "V":
        ((_k = $("#vizOverlay")) == null ? void 0 : _k.classList.contains("open")) ? closeViz() : openViz();
        break;
    }
  });
  let dragCounter = 0;
  function isFileDrag(e) {
    return e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).includes("Files");
  }
  function hideDropOverlay() {
    var _a2;
    dragCounter = 0;
    (_a2 = $("#dropOverlay")) == null ? void 0 : _a2.classList.remove("show");
  }
  window.addEventListener("dragenter", (e) => {
    var _a2;
    if (!isFileDrag(e)) return;
    e.preventDefault();
    dragCounter++;
    (_a2 = $("#dropOverlay")) == null ? void 0 : _a2.classList.add("show");
  });
  window.addEventListener("dragover", (e) => {
    if (isFileDrag(e)) e.preventDefault();
  });
  window.addEventListener("dragleave", (e) => {
    if (!isFileDrag(e)) return;
    dragCounter--;
    if (dragCounter <= 0) hideDropOverlay();
  });
  window.addEventListener("drop", (e) => {
    if (!isFileDrag(e)) return;
    e.preventDefault();
    hideDropOverlay();
    const files = [];
    if (e.dataTransfer.items) {
      for (const item of e.dataTransfer.items) if (item.kind === "file") files.push(item.getAsFile());
    } else Array.from(e.dataTransfer.files).forEach((f) => files.push(f));
    importFiles(files);
  });
  on("#dropOverlay", "click", hideDropOverlay);
  document.addEventListener("visibilitychange", () => {
    var _a2;
    if (document.hidden) {
      if (rafViz) {
        cancelAnimationFrame(rafViz);
        rafViz = null;
      }
    } else {
      if (((_a2 = $("#vizOverlay")) == null ? void 0 : _a2.classList.contains("open")) && !rafViz) drawViz();
    }
  });
  let initializationStarted = false;
  function init() {
    return __async(this, null, function* () {
      var _a2, _b2, _c;
      if (initializationStarted) return;
      initializationStarted = true;
      try {
        const label = $("#btnImportTopLabel");
        if (label) label.textContent = "Add music";
        (_a2 = $("#btnImportRail")) == null ? void 0 : _a2.setAttribute("data-tip", "Add music");
        yield loadPersisted();
        audioEl.volume = state.muted ? 0 : state.volume;
        $$("#viewToggle button").forEach((b) => b.classList.toggle("active", b.dataset.mode === state.listMode));
        state.shuffle && ((_b2 = $("#btnShuffle")) == null ? void 0 : _b2.classList.add("on"));
        if (state.repeat !== "off") (_c = $("#btnRepeat")) == null ? void 0 : _c.classList.add("on");
        updateVolUI();
        ensureCsrfToken();
        render();
        loadServerLibrary().then((count) => {
          render();
          if (count) toast(`Loaded ${count} saved track${count !== 1 ? "s" : ""}.`);
        });
      } catch (e) {
        console.error("Auralis init failed", e);
        toast("Something went wrong loading the library.");
        try {
          render();
        } catch (_) {
        }
      }
    });
  }
  init();
})();
