(() => {
"use strict";

// Backend-served pages use their own origin; static deployments keep the
// configured production fallback unless they provide an injected API base.
const configuredApiBase = document.querySelector('meta[name="api-base"]')?.content;
const API_BASE = (configuredApiBase && !configuredApiBase.startsWith("__")
  ? configuredApiBase
  : "https://vervfy-app.onrender.com").replace(/\/+$/, "");

function apiUrl(path) {
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path}`;
}

function loginPageUrl() {
  // Always hit the FastAPI login page (not a static-host rewrite).
  return apiUrl("/login");
}

async function logoutAndRedirect() {
  try {
    // Do not follow the 303 — a broken Location must not block navigation.
    await fetch(apiUrl("/logout"), {
      method: "POST",
      headers: { "X-CSRF-Token": await ensureCsrfToken() },
      redirect: "manual",
    });
  } catch (_) {}
  window.location.assign(loginPageUrl());
}

/* If the session cookie expires mid-use, any /api/* call will start
   returning 401 — send the user back to the login page instead of
   leaving them staring at a library that silently stopped loading. */
(() => {
  const _fetch = window.fetch.bind(window);

window.fetch = async (...args) => {
  // Send API requests to the FastAPI backend on Render
  if (typeof args[0] === "string" && args[0].startsWith("/api/")) {
    args[0] = apiUrl(args[0]);
  }

  // Only attach session cookies to our own API. Third-party calls (e.g. LRCLIB)
  // use Access-Control-Allow-Origin: * without Allow-Credentials — forcing
  // credentials: "include" on those requests makes the browser block them.
  const url =
    typeof args[0] === "string"
      ? args[0]
      : (args[0] && args[0].url) || "";
  let isOurApi = false;
  try {
    isOurApi = new URL(url, window.location.href).origin === new URL(API_BASE, window.location.href).origin;
  } catch (_) {}
  if (isOurApi) {
    if (typeof args[1] === "object" && args[1] !== null) {
      args[1] = { ...args[1], credentials: "include" };
    } else {
      args[1] = { credentials: "include" };
    }
  }

  const response = await _fetch(...args);
  if (isOurApi && response.status === 401) {
    window.location.assign(loginPageUrl());
  }
  return response;
};
})();

/* ============================================================
   STATE
   ============================================================ */
const state = {
  tracks: [],            // {id,title,artist,album,year,art,duration,favorite,file,fingerprint}
  playlists: [],         // {id,name,trackIds:[]}
  view: "library",       // library | playlists | artists | favorites | playlist:<id> | artist:<name>
  listMode: "grid",
  search: "",
  queue: [],             // array of track ids, the play order
  queueIndex: -1,
  playingContext: null,  // page/list that started the current queue
  shuffle: false,
  repeat: "off",         // off | all | one
  volume: 0.7,
  muted: false,
  profilePhotoFit: "cover",
};

let audioEl = new Audio();
audioEl.preload = "metadata";
let audioCtx = null, analyser = null, sourceNode = null, freqData = null, waveData = null;
let rafViz = null;
let vizLastFrameAt = 0;
let vizCanvasSize = 0;

/* ============================================================
   SYSTEM MEDIA CONTROLS
   ============================================================
   Android's notification / lock-screen media card is driven by the browser's
   Media Session API.  Keep it tied to the same audio element that powers the
   in-app player so notification actions and UI actions can never get out of
   sync.  Browsers that do not support Media Session simply ignore this.
   ============================================================ */
const mediaSession = navigator.mediaSession || null;

function mediaArtworkFor(track){
  if(!track || !track.art) return [];
  // MediaMetadata resolves relative URLs in most browsers, but an absolute
  // URL is required by a few Android WebView/browser versions.
  let src = track.art;
  try{ src = new URL(track.art, window.location.href).href; }catch(_){}
  return [96, 128, 192, 256, 384, 512].map(size => ({
    src, sizes: `${size}x${size}`, type: "image/jpeg"
  }));
}

function updateMediaSessionMetadata(){
  if(!mediaSession || !window.MediaMetadata) return;
  const track = currentTrack();
  if(!track) return;
  try{
    mediaSession.metadata = new MediaMetadata({
      title: track.title || "Unknown title",
      artist: artistCreditsLabel(track) || "Unknown artist",
      album: track.album || "",
      artwork: mediaArtworkFor(track),
    });
  }catch(err){
    // Metadata is an enhancement; invalid embedded artwork must never stop
    // playback (notably on older Android browsers).
    console.warn("Could not set system media metadata", err);
  }
}

function updateMediaSessionPosition(){
  if(!mediaSession || !mediaSession.setPositionState) return;
  const duration = audioEl.duration;
  const position = audioEl.currentTime;
  if(!Number.isFinite(duration) || duration <= 0 || !Number.isFinite(position)) return;
  try{
    mediaSession.setPositionState({
      duration,
      position: Math.max(0, Math.min(position, duration)),
      playbackRate: audioEl.playbackRate || 1,
    });
  }catch(_){}
}

const AURA_PALETTE = [
  ["#8b7fff","#54e8d4"], ["#ff8fb1","#8b7fff"], ["#54e8d4","#3aa0ff"],
  ["#ffb86b","#ff6b9d"], ["#6bd6ff","#8b7fff"], ["#c084fc","#54e8d4"],
];

/* ============================================================
   UTIL
   ============================================================ */
const $ = sel => document.querySelector(sel);
const $$ = sel => Array.from(document.querySelectorAll(sel));
const uid = () => Math.random().toString(36).slice(2,10) + Date.now().toString(36);

function fmtTime(s){
  if(!isFinite(s) || s < 0) s = 0;
  const m = Math.floor(s/60), sec = Math.floor(s%60);
  return m + ":" + String(sec).padStart(2,"0");
}
function fmtLongDuration(s){
  if(!Number.isFinite(s) || s < 0) return "0 min";
  const totalMinutes = Math.round(s / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if(hours === 0) return `${minutes} min`;
  return minutes ? `${hours} hr ${minutes} min` : `${hours} hr`;
}
function hashStr(str){
  let h = 0;
  for(let i=0;i<str.length;i++){ h = (Math.imul(31,h) + str.charCodeAt(i))|0; }
  return Math.abs(h);
}
function toast(msg){
  const el = document.createElement("div");
  el.className = "toast"; el.textContent = msg;
  $("#toastWrap").appendChild(el);
  setTimeout(()=>{ el.style.transition="opacity .3s"; el.style.opacity="0"; setTimeout(()=>el.remove(),300); }, 2600);
}

/* ---------- procedural aura artwork (signature visual) ---------- */
function generateAura(seed, size=300){
  const canvas = document.createElement("canvas");
  canvas.width = size; canvas.height = size;
  const ctx = canvas.getContext("2d");
  const h = hashStr(seed);
  const palette = AURA_PALETTE[h % AURA_PALETTE.length];
  const angle = (h % 360) * Math.PI/180;
  const cx = size/2 + Math.cos(angle)*size*0.15;
  const cy = size/2 + Math.sin(angle)*size*0.15;

  ctx.fillStyle = "#12151e";
  ctx.fillRect(0,0,size,size);

  const g1 = ctx.createRadialGradient(cx,cy,0,cx,cy,size*0.75);
  g1.addColorStop(0, palette[0]);
  g1.addColorStop(0.5, palette[1]+"55");
  g1.addColorStop(1, "#0c0e1400");
  ctx.globalAlpha = 0.9;
  ctx.fillStyle = g1;
  ctx.fillRect(0,0,size,size);

  const cx2 = size - cx, cy2 = size - cy;
  const g2 = ctx.createRadialGradient(cx2,cy2,0,cx2,cy2,size*0.6);
  g2.addColorStop(0, palette[1]);
  g2.addColorStop(1, "#0c0e1400");
  ctx.globalAlpha = 0.55;
  ctx.fillStyle = g2;
  ctx.fillRect(0,0,size,size);

  // soft concentric rings
  ctx.globalAlpha = 0.16;
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 1;
  for(let r = size*0.12; r < size*0.55; r += size*0.12){
    ctx.beginPath();
    ctx.arc(cx, cy, r, (h%628)/100, (h%628)/100 + Math.PI*1.3);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
  return canvas.toDataURL("image/jpeg", 0.85);
}

/* ============================================================
   TEMPORARY LYRIC-SYNC DEBUG LOGGING
   Traces the pipeline end to end: SYLT/USLT parsing decisions,
   playback time, matched lyric line, and every seek. Flip
   LYRICS_SYNC_DEBUG to false (or run it from devtools) to silence.
   Safe to delete once sync is confirmed solid in the field.
   ============================================================ */
let LYRICS_SYNC_DEBUG = false;
let _lyricsLastLoggedIdx = null;
let _lyricsRenderedIdx = null;
let lyricsHighlightRaf = null;
let lyricsSyncClockRaf = null;
const LyricsDebug = {
  log(...args){ if(LYRICS_SYNC_DEBUG) console.log("%c[lyrics-sync]", "color:#54e8d4;font-weight:600;", ...args); },
  warn(...args){ if(LYRICS_SYNC_DEBUG) console.warn("[lyrics-sync]", ...args); },
};

/* ============================================================
   ID3 METADATA PARSER (v2.2 / v2.3 / v2.4, common frames)
   ============================================================ */
function syncsafe(bytes, offset){
  return ((bytes[offset]&0x7f)<<21) | ((bytes[offset+1]&0x7f)<<14) | ((bytes[offset+2]&0x7f)<<7) | (bytes[offset+3]&0x7f);
}
function beInt(bytes, offset, len){
  let v = 0;
  for(let i=0;i<len;i++) v = (v<<8) | bytes[offset+i];
  return v >>> 0;
}
function decodeText(bytes, encByte){
  try{
    if(encByte === 0) return new TextDecoder("latin1").decode(bytes).replace(/\0+$/,"");
    if(encByte === 1) return new TextDecoder("utf-16").decode(bytes).replace(/\0+$/,"");
    if(encByte === 2) return new TextDecoder("utf-16be").decode(bytes).replace(/\0+$/,"");
    return new TextDecoder("utf-8").decode(bytes).replace(/\0+$/,"");
  }catch(e){ return ""; }
}
function findNullTerm(bytes, start, wide){
  for(let i=start;i<bytes.length-(wide?1:0);i+= (wide?2:1)){
    if(wide){ if(bytes[i]===0 && bytes[i+1]===0) return i; }
    else{ if(bytes[i]===0) return i; }
  }
  return bytes.length;
}

/* ---- lyric frame parsers (SYLT = synchronized, USLT = plain) ---- */
/*
   ROOT CAUSE (fixed here): SYLT timestamps can be stored in one of two units,
   selected by a byte in the frame itself (`time stamp format`):
     1 = MPEG frame count   2 = absolute milliseconds
   The previous parser treated format-1 timestamps as "frame count * 26ms",
   assuming every file is a standard 44.1kHz MPEG1/Layer III stream (where a
   frame really is ~26.1ms). Any file encoded at a different sample rate or
   MPEG version/layer (32kHz, 48kHz, 22.05kHz, MPEG2, ...) has a genuinely
   different frame duration, so that constant silently produced the wrong
   millisecond value for every single line — which is exactly why lyrics
   appeared to "jump ahead" from the very first line rather than drifting in
   gradually. Fixed by computing the real frame duration from the file's own
   first MPEG audio frame header instead of assuming a fixed number.
*/
function decodeMpegFrameHeader(bytes, offset){
  if(bytes[offset] !== 0xFF || (bytes[offset+1] & 0xE0) !== 0xE0) return null;
  const verId = (bytes[offset+1] >> 3) & 0x03;   // 0=MPEG2.5, 1=reserved, 2=MPEG2, 3=MPEG1
  const layerId = (bytes[offset+1] >> 1) & 0x03; // 0=reserved, 1=Layer III, 2=Layer II, 3=Layer I
  const srIndex = (bytes[offset+2] >> 2) & 0x03;
  if(verId === 1 || layerId === 0 || srIndex === 3) return null; // reserved combinations
  const SAMPLE_RATES = { 3:[44100,48000,32000], 2:[22050,24000,16000], 0:[11025,12000,8000] };
  const sampleRate = SAMPLE_RATES[verId][srIndex];
  if(!sampleRate) return null;
  let samplesPerFrame;
  if(layerId === 3) samplesPerFrame = 384;                 // Layer I
  else if(layerId === 2) samplesPerFrame = 1152;            // Layer II
  else samplesPerFrame = (verId === 3) ? 1152 : 576;        // Layer III: MPEG1=1152, MPEG2/2.5=576
  return { sampleRate, samplesPerFrame, msPerFrame: samplesPerFrame / sampleRate * 1000 };
}
// Scans a window of the actual audio stream (right after the ID3v2 tag) for the
// first valid MPEG frame sync, and returns the true ms-per-frame for THIS file.
// Only called for the rare SYLT files that use frame-count timestamps, so it
// has no cost for the common absolute-millisecond case or for playback itself.
async function detectMpegFrameDurationMs(file, streamStartOffset){
  try{
    const windowSize = Math.min(16384, Math.max(0, file.size - streamStartOffset));
    if(windowSize < 4) return null;
    const buf = await file.slice(streamStartOffset, streamStartOffset + windowSize).arrayBuffer();
    const bytes = new Uint8Array(buf);
    for(let i=0; i<bytes.length-4; i++){
      const hdr = decodeMpegFrameHeader(bytes, i);
      if(hdr) return hdr;
    }
  }catch(e){ LyricsDebug.warn("frame-duration detection failed:", e.message); }
  return null;
}

function parseSyltFrame(frame, msPerUnit){
  try{
    const enc = frame[0];
    const wide = enc===1 || enc===2;
    let idx = 6; // encoding(1) + language(3) + timestamp format(1) + content type(1)
    const descEnd = findNullTerm(frame, idx, wide);
    idx = descEnd + (wide?2:1);
    const lines = [];
    let dropped = 0;
    while(idx < frame.length){
      const textEnd = findNullTerm(frame, idx, wide);
      if(textEnd >= frame.length) break;
      const text = decodeText(frame.subarray(idx, textEnd), enc);
      idx = textEnd + (wide?2:1);
      if(idx + 4 > frame.length) break;
      const timestamp = beInt(frame, idx, 4);
      idx += 4;
      const time = timestamp * msPerUnit;
      if(Number.isFinite(time)) lines.push({ time, text });
      else dropped++;
    }
    if(dropped) LyricsDebug.warn(`SYLT: dropped ${dropped} entr${dropped===1?"y":"ies"} with invalid timestamps`);
    return lines.length ? lines : null;
  }catch(e){ LyricsDebug.warn("SYLT parse threw:", e.message); return null; }
}
function parseUsltFrame(frame){
  try{
    const enc = frame[0];
    const wide = enc===1 || enc===2;
    let idx = 4; // encoding byte + 3-byte language code
    const descEnd = findNullTerm(frame, idx, wide);
    idx = descEnd + (wide?2:1);
    const text = decodeText(frame.subarray(idx), enc);
    return text && text.trim() ? text : null;
  }catch(e){ LyricsDebug.warn("USLT parse threw:", e.message); return null; }
}

async function parseID3(file){
  const meta = { title:null, artist:null, album:null, year:null, picture:null, sylt:null, uslt:null };
  try{
    const headBuf = await file.slice(0,10).arrayBuffer();
    const head = new Uint8Array(headBuf);
    if(!(head[0]===0x49 && head[1]===0x44 && head[2]===0x33)) return meta; // "ID3"
    const majorVer = head[3];
    const tagSize = syncsafe(head, 6);
    if(tagSize <= 0) return meta;
    const bodyBuf = await file.slice(10, 10+tagSize).arrayBuffer();
    const body = new Uint8Array(bodyBuf);
    let pos = 0;

    while(pos < body.length - 4){
      let frameId, frameSize, headerLen;
      if(majorVer === 2){
        frameId = String.fromCharCode(body[pos],body[pos+1],body[pos+2]);
        if(frameId === "\0\0\0") break;
        frameSize = beInt(body,pos+3,3);
        headerLen = 6;
      } else {
        frameId = String.fromCharCode(body[pos],body[pos+1],body[pos+2],body[pos+3]);
        if(frameId === "\0\0\0\0") break;
        frameSize = majorVer===4 ? syncsafe(body,pos+4) : beInt(body,pos+4,4);
        headerLen = 10;
      }
      const dataStart = pos + headerLen;
      const dataEnd = dataStart + frameSize;
      if(frameSize <= 0 || dataEnd > body.length) break;
      const frame = body.subarray(dataStart, dataEnd);

      if(["TIT2","TT2"].includes(frameId)) meta.title = decodeText(frame.subarray(1), frame[0]);
      else if(["TPE1","TP1"].includes(frameId)) meta.artist = decodeText(frame.subarray(1), frame[0]);
      else if(["TALB","TAL"].includes(frameId)) meta.album = decodeText(frame.subarray(1), frame[0]);
      else if(["TYER","TDRC","TYE"].includes(frameId)) meta.year = decodeText(frame.subarray(1), frame[0]).slice(0,4);
      else if(["APIC","PIC"].includes(frameId) && !meta.picture){
        try{
          const enc = frame[0];
          let idx = 1, mime = "image/jpeg";
          if(frameId === "APIC"){
            const mimeEnd = findNullTerm(frame, idx, false);
            mime = decodeText(frame.subarray(idx, mimeEnd), 0) || "image/jpeg";
            idx = mimeEnd + 1;
            idx += 1; // picture type byte
            const wide = enc===1 || enc===2;
            const descEnd = findNullTerm(frame, idx, wide);
            idx = descEnd + (wide?2:1);
          } else {
            const fmt = String.fromCharCode(frame[idx],frame[idx+1],frame[idx+2]);
            mime = fmt.toUpperCase()==="PNG" ? "image/png" : "image/jpeg";
            idx += 3 + 1;
            const wide = enc===1 || enc===2;
            const descEnd = findNullTerm(frame, idx, wide);
            idx = descEnd + (wide?2:1);
          }
          const imgBytes = frame.subarray(idx);
          if(imgBytes.length > 100){
            const blob = new Blob([imgBytes], {type:mime});
            meta.picture = URL.createObjectURL(blob);
          }
        }catch(e){ /* ignore malformed picture frame */ }
      }
      else if(["SYLT","SLT"].includes(frameId) && !meta.sylt){
        const tsFormat = frame[4]; // 1 = MPEG frame count, 2 = absolute milliseconds
        let msPerUnit = 1;
        if(tsFormat === 1){
          const hdr = await detectMpegFrameDurationMs(file, 10 + tagSize);
          if(hdr){
            msPerUnit = hdr.msPerFrame;
            LyricsDebug.log(`${file.name}: SYLT uses MPEG-frame timestamps; detected ${hdr.sampleRate}Hz stream → ${hdr.msPerFrame.toFixed(3)}ms/frame`);
          } else {
            msPerUnit = 26.122; // MPEG1/Layer III @ 44.1kHz frame duration — last-resort fallback only
            LyricsDebug.warn(`${file.name}: SYLT uses MPEG-frame timestamps but no valid audio frame header was found; falling back to a 44.1kHz estimate (times may drift)`);
          }
        }
        const lines = parseSyltFrame(frame, msPerUnit);
        if(lines){
          lines.sort((a,b)=>a.time-b.time);
          meta.sylt = lines;
          LyricsDebug.log(`${file.name}: SYLT parsed — ${lines.length} lines, first="${lines[0].text}" @${(lines[0].time/1000).toFixed(2)}s, last @${(lines[lines.length-1].time/1000).toFixed(2)}s`);
        }
      }
      else if(["USLT","ULT"].includes(frameId) && !meta.uslt){
        const text = parseUsltFrame(frame);
        if(text) meta.uslt = text;
      }
      pos = dataEnd;
    }
  }catch(e){ /* not a readable/ID3 file — fall back to filename */ }
  return meta;
}

function titleFromFilename(name){
  return name.replace(/\.[^.]+$/,"").replace(/^\d+[\s._-]*/,"").replace(/[_]+/g," ").trim() || "Untitled";
}

/* ============================================================
   LYRICS ENGINE — modular and source-agnostic.
   Every source normalizes into one of two shapes:
     synced: { source, lines:[{ time (ms), text }] }   — sorted ascending
     plain:  { source, text }
   or null when nothing usable was found. The UI only ever reads
   this normalized shape, so adding a new source never touches
   the rendering code below.
   ============================================================ */
const LyricsEngine = (() => {
  // Embedded ID3 tags, already extracted during import (SYLT preferred over USLT).
  function fromID3(meta){
    if(!meta) return null;
    if(meta.sylt && meta.sylt.length) return { source:"sylt", lines: meta.sylt };
    if(meta.uslt) return { source:"uslt", text: meta.uslt };
    return null;
  }
  // Future: a standalone .lrc file's contents, in the same synced shape.
  // Pure function — ready to wire up to a file picker or drag-and-drop later.
  function fromLRC(lrcText){
    if(!lrcText) return null;
    const stamp = /\[(\d{1,2}):(\d{2}(?:[.:]\d{1,3})?)\]/g;
    const lines = [];
    let offsetMs = 0;
    lrcText.split(/\r?\n/).forEach(raw => {
      const offset = raw.match(/^\s*\[offset\s*:\s*([+-]?\d+)\s*\]\s*$/i);
      if(offset){
        offsetMs = Number(offset[1]) || 0;
        return;
      }
      const matches = [...raw.matchAll(stamp)];
      if(matches.length === 0) return;
      const text = raw.replace(stamp,"").trim();
      matches.forEach(m => {
        const seconds = Number(m[2].replace(":", "."));
        if(!Number.isFinite(seconds)) return;
        const time = Math.max(0, (parseInt(m[1],10)*60 + seconds) * 1000 + offsetMs);
        lines.push({ time, text });
      });
    });
    if(lines.length === 0) return null;
    lines.sort((a,b)=>a.time-b.time);
    return { source:"lrc", lines };
  }
  // Online lookup — LRCLIB (https://lrclib.net), a free, keyless, CORS-enabled
  // public database purpose-built for synced (LRC) lyrics. Called straight from
  // the browser: this app has no server of its own, so a backend that could
  // hold a private API key isn't an option here, and LRCLIB needs none anyway.
  // Strategy: try the exact-match endpoint first (fast, precise when we know
  // the track's duration), then fall back to fuzzy search and pick whichever
  // candidate's duration is closest to ours.
  const LRCLIB_BASE = "https://lrclib.net/api";
  function lrclibResultToLyrics(data){
    if(!data || data.instrumental) return null;
    if(data.syncedLyrics && data.syncedLyrics.trim()){
      const parsed = fromLRC(data.syncedLyrics);
      if(parsed) return { source:"online-synced", lines: parsed.lines };
    }
    if(data.plainLyrics && data.plainLyrics.trim()){
      return { source:"online-plain", text: data.plainLyrics };
    }
    return null;
  }
  async function fromOnline(track){
    if(!track || !track.title){ LyricsDebug.log("online: skipped, no title to search with"); return null; }
    const artist = (track.artist || "").trim();
    if(!artist || /^unknown artist$/i.test(artist)){
      LyricsDebug.log(`online: skipped for "${track.title}" — artist is unknown, a search would be unreliable`);
      return null;
    }
    const durationSec = Math.round(track.duration || 0);
    const baseParams = { track_name: track.title, artist_name: artist };
    const album = (track.album || "").trim();
    if(album && !/^unknown album$/i.test(album)) baseParams.album_name = album;

    // 1) exact match (only meaningful once we know the track's duration)
    if(durationSec > 0){
      try{
        const url = `${LRCLIB_BASE}/get?` + new URLSearchParams({ ...baseParams, duration:durationSec });
        LyricsDebug.log("online: exact-match query →", url);
        const res = await fetch(url);
        LyricsDebug.log("online: exact-match response status", res.status);
        if(res.ok){
          const data = await res.json();
          const parsed = lrclibResultToLyrics(data);
          LyricsDebug.log("online: exact-match parsed result →", parsed ? `${parsed.source}, ${parsed.lines?parsed.lines.length+" lines":parsed.text.length+" chars"}` : "none usable");
          if(parsed) return parsed;
        }
      }catch(e){ LyricsDebug.warn("online: exact-match request failed —", e.message); }
    }

    // 2) fuzzy search fallback
    try{
      const url = `${LRCLIB_BASE}/search?` + new URLSearchParams(baseParams);
      LyricsDebug.log("online: search query →", url);
      const res = await fetch(url);
      LyricsDebug.log("online: search response status", res.status);
      if(!res.ok) return null;
      const results = await res.json();
      LyricsDebug.log(`online: search returned ${Array.isArray(results)?results.length:0} candidate(s)`);
      if(!Array.isArray(results) || results.length === 0) return null;
      const best = durationSec > 0
        ? results.reduce((a,b) => Math.abs((a.duration||0)-durationSec) <= Math.abs((b.duration||0)-durationSec) ? a : b)
        : results[0];
      const parsed = lrclibResultToLyrics(best);
      LyricsDebug.log("online: best candidate", `"${best.trackName}" by ${best.artistName}`, "→", parsed ? parsed.source : "no usable lyrics (instrumental or empty)");
      return parsed;
    }catch(e){ LyricsDebug.warn("online: search request failed —", e.message); return null; }
  }
  // Embedded synced/plain lyrics are checked before the online fallback.
  async function resolve(track, idMeta){
    let result = fromID3(idMeta);
    if(!result) result = await fromOnline(track);
    return normalizeSyncedLyrics(result, track?.duration) || null;
  }
  return { fromID3, fromLRC, fromOnline, resolve };
})();

function normalizeSyncedLyrics(lyrics, duration){
  if(!lyrics?.lines?.length || !Number.isFinite(duration) || duration <= 0) return lyrics;
  const lines = lyrics.lines
    .filter(line => Number.isFinite(line.time) && line.time >= 0)
    .sort((a,b)=>a.time-b.time);
  if(!lines.length) return null;
  const lastTime = lines[lines.length - 1].time;
  const durationMs = duration * 1000;
  // Some lyric providers return a version whose timestamps run past the
  // actual audio. Compress only that clearly invalid tail; normal outro
  // silence and early final lines are left untouched.
  if(lastTime > durationMs + 1500){
    const scale = Math.max(0.85, (durationMs - 500) / lastTime);
    return {
      ...lyrics,
      lines: lines.map(line => ({...line, time: Math.max(0, line.time * scale)})),
    };
  }
  return {...lyrics, lines};
}

/* ============================================================
   ARTIST PHOTOS — resolved on demand, just like online lyrics.
   Album art remains visible immediately; a verified portrait replaces it only
   when the local server finds an exact artist-name match in its public catalog.
   ============================================================ */
const ArtistPhotoEngine = (() => {
  const resolved = new Map(); // artist name -> URL or null (a confirmed miss)
  const pending = new Map();

  function apply(name, url){
    if(!url) return;
    document.querySelectorAll("[data-artist-photo]").forEach(img => {
      if(img.dataset.artistPhoto !== name) return;
      const fallback = img.src;
      img.addEventListener("error", () => { img.src = fallback; }, {once:true});
      img.src = url;
    });
  }

  async function lookup(name){
    try{
      const res = await fetch("/api/artists/photo?" + new URLSearchParams({name}));
      const data = res.ok ? await res.json() : null;
      const url = data && typeof data.url === "string" ? data.url : null;
      resolved.set(name, url);
      apply(name, url);
    }catch(_){
      // Offline or unavailable catalogs leave the existing album art in place.
      resolved.set(name, null);
      return null;
    }finally{
      pending.delete(name);
    }
  }

  function resolve(name){
    if(!name) return Promise.resolve(null);
    if(offlineArtistPhotos.has(name)){
      const url = offlineArtistPhotos.get(name);
      resolved.set(name, url);
      apply(name, url);
      return Promise.resolve(url);
    }
    if(resolved.has(name)){
      apply(name, resolved.get(name));
      return Promise.resolve(resolved.get(name));
    }
    if(pending.has(name)) return pending.get(name);
    const request = lookup(name);
    pending.set(name, request);
    return request;
  }

  function resolveAll(artists){ artists.forEach(artist => resolve(artist.name)); }
  return { resolve, resolveAll };
})();

const ArtistProfileEngine = (() => {
  const resolved = new Map();
  const pending = new Map();

  function formatProfileNumber(value){
    const number = Number(value);
    return Number.isFinite(number) ? new Intl.NumberFormat().format(number) : value;
  }

  function safeExternalUrl(value){
    if(typeof value !== "string") return null;
    try{
      const url = new URL(value);
      return url.protocol === "https:" ? url.href : null;
    }catch(_){
      return null;
    }
  }

  function apply(name, profile){
    document.querySelectorAll("[data-artist-profile]").forEach(section => {
      if(section.dataset.artistProfile !== name) return;
      section.setAttribute("aria-busy", "false");
      const bio = section.querySelector("[data-artist-bio]");
      const tags = section.querySelector("[data-artist-tags]");
      const socials = section.querySelector("[data-artist-socials]");
      const website = section.querySelector("[data-artist-website]");
      const source = section.querySelector("[data-artist-source]");
      bio.textContent = profile?.bio || "No artist biography is available from the public catalog.";

      const facts = [
        ["Genre", profile?.genre],
        ["Style", profile?.style],
        ["Mood", profile?.mood],
        ["Formed", profile?.formed_year],
        ["Label", profile?.label],
        ["Followers", profile?.followers && formatProfileNumber(profile.followers)],
        ["Popularity", profile?.popularity],
        ["Highlight", profile?.highlights],
      ].filter(([, value]) => value);
      tags.replaceChildren(...facts.map(([label, value]) => {
        const tag = document.createElement("span");
        tag.className = "artist-tag";
        tag.textContent = `${label}: ${value}`;
        return tag;
      }));
      tags.hidden = facts.length === 0;

      const socialLinks = [
        ["Instagram", profile?.instagram, '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="3.5" width="17" height="17" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" class="social-icon-fill"/></svg>'],
        ["YouTube", profile?.youtube, '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 7.2a2.8 2.8 0 0 0-2-2C17.2 4.7 12 4.7 12 4.7s-5.2 0-7 .5a2.8 2.8 0 0 0-2 2A29 29 0 0 0 2.5 12 29 29 0 0 0 3 16.8a2.8 2.8 0 0 0 2 2c1.8.5 7 .5 7 .5s5.2 0 7-.5a2.8 2.8 0 0 0 2-2 29 29 0 0 0 .5-4.8 29 29 0 0 0-.5-4.8Z"/><path d="m10 9 5 3-5 3Z" class="social-icon-cut"/></svg>'],
        ["Twitter", profile?.twitter, '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18.9 3.5h3.7l-8.1 9.3 9.5 7.7h-7.4l-5.8-4.7-4.1 4.7H3l7.7-8.8L1.6 3.5h7.6l5.2 4.3 4.5-4.3Zm-1.3 15.2h2L7.8 5.2H5.7l11.9 13.5Z"/></svg>'],
        ["Facebook", profile?.facebook, '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 20v-7h2.5l.5-3H14V8.1c0-.9.3-1.6 1.7-1.6H17V3.8c-.6-.1-1.4-.2-2.3-.2-2.3 0-3.7 1.4-3.7 3.9V10H8.5v3h2.5v7Z" class="social-icon-fill"/></svg>'],
      ].map(([label, value, icon]) => {
        const url = safeExternalUrl(value);
        if(!url) return null;
        const link = document.createElement("a");
        link.className = `artist-social-link artist-social-${label.toLowerCase()}`;
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.setAttribute("aria-label", `${name} on ${label}`);
        link.title = `${name} on ${label}`;
        link.insertAdjacentHTML("beforeend", icon);
        const text = document.createElement("span");
        text.textContent = label;
        link.append(text);
        return link;
      }).filter(Boolean);
      socials.replaceChildren(...socialLinks);
      socials.hidden = socialLinks.length === 0;

      const sourceUrl = safeExternalUrl(profile?.source_url || profile?.website);
      source.replaceChildren();
      if(profile?.source){
        source.append(`Information for ${profile.lookup_name || name} from `);
        if(sourceUrl){
          const sourceLink = document.createElement("a");
          sourceLink.href = sourceUrl;
          sourceLink.target = "_blank";
          sourceLink.rel = "noopener noreferrer";
          sourceLink.textContent = profile.source;
          source.append(sourceLink);
        }else{
          source.append(profile.source);
        }
        source.hidden = false;
      }else{
        source.textContent = "Artist information unavailable";
        source.hidden = true;
      }

      const websiteUrl = safeExternalUrl(profile?.website);
      if(websiteUrl){
        website.href = websiteUrl;
        website.firstChild.textContent = profile.website_label || "Source page";
        website.hidden = false;
      }else{
        website.firstChild.textContent = "Source page";
        website.hidden = true;
      }
    });
  }

  async function resolve(name){
    if(!name) return null;
    if(offlineArtistProfiles.has(name)){
      const profile = offlineArtistProfiles.get(name);
      resolved.set(name, profile);
      apply(name, profile);
      return profile;
    }
    if(resolved.has(name)){ apply(name, resolved.get(name)); return resolved.get(name); }
    if(pending.has(name)) return pending.get(name);
    const request = (async () => {
      try{
      const res = await fetch("/api/artists/profile?" + new URLSearchParams({name}));
      const data = res.ok ? await res.json() : null;
      const profile = data && data.profile && typeof data.profile === "object" ? data.profile : null;
      resolved.set(name, profile);
      apply(name, profile);
      return profile;
    }catch(_){
      resolved.set(name, null);
      apply(name, null);
      return null;
    }finally{
      pending.delete(name);
    }})();
    pending.set(name, request);
    return request;
  }
  return { resolve };
})();

/* ============================================================
   PERSISTENCE — IndexedDB keeps device-only player settings. Favorites,
   playlists, tracks, lyrics, covers, and audio are PostgreSQL-backed.
   ============================================================ */
const AuralisDB = (() => {
  const DB_NAME = "auralis-db", DB_VERSION = 2;
  const STORE_KV = "kv", STORE_HANDLES = "handles";
  let dbPromise = null;
  function open(){
    if(dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      if(!("indexedDB" in window)){ reject(new Error("IndexedDB unsupported")); return; }
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if(!db.objectStoreNames.contains(STORE_KV)) db.createObjectStore(STORE_KV);
        if(!db.objectStoreNames.contains(STORE_HANDLES)) db.createObjectStore(STORE_HANDLES);
        if(!db.objectStoreNames.contains("offlineTracks")) db.createObjectStore("offlineTracks", {keyPath:"id"});
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    return dbPromise;
  }
  async function store(name, mode){ const db = await open(); return db.transaction(name, mode).objectStore(name); }
  async function get(key, storeName = STORE_KV){
    try{
      const s = await store(storeName, "readonly");
      return await new Promise((resolve,reject)=>{
        const r = s.get(key);
        r.onsuccess = () => resolve(r.result === undefined ? null : r.result);
        r.onerror = () => reject(r.error);
      });
    }catch(e){ return null; }
  }
  async function set(key, value, storeName = STORE_KV){
    try{
      const s = await store(storeName, "readwrite");
      await new Promise((resolve,reject)=>{
        const r = s.put(value, key);
        r.onsuccess = () => resolve(); r.onerror = () => reject(r.error);
      });
      return true;
    }catch(e){ return false; }
  }
  async function del(key, storeName = STORE_KV){
    try{
      const s = await store(storeName, "readwrite");
      await new Promise((resolve,reject)=>{
        const r = s.delete(key);
        r.onsuccess = () => resolve(); r.onerror = () => reject(r.error);
      });
    }catch(e){}
  }
  async function getAll(storeName){
    try{
      const s = await store(storeName, "readonly");
      return await new Promise((resolve,reject)=>{
        const r = s.getAll();
        r.onsuccess = () => resolve(r.result || []);
        r.onerror = () => reject(r.error);
      });
    }catch(e){ return []; }
  }
  async function putRecord(record, storeName){
    try{
      const s = await store(storeName, "readwrite");
      await new Promise((resolve,reject)=>{
        const r = s.put(record);
        r.onsuccess = () => resolve(); r.onerror = () => reject(r.error);
      });
      return true;
    }catch(e){ return false; }
  }
  return { get, set, del, getAll, putRecord, STORE_KV, STORE_HANDLES };
})();

const OFFLINE_STORE = "offlineTracks";
const offlineObjectUrls = new Set();
const offlineArtistProfiles = new Map();
const offlineArtistPhotos = new Map();

function releaseOfflineObjectUrls(){
  offlineObjectUrls.forEach(url => URL.revokeObjectURL(url));
  offlineObjectUrls.clear();
  offlineArtistProfiles.clear();
  offlineArtistPhotos.clear();
}

function offlineTrackFromRecord(record){
  const fallbackArt = generateAura(`${record.artist}|${record.album}|${record.title}`);
  const art = record.cover instanceof Blob
    ? URL.createObjectURL(record.cover)
    : fallbackArt;
  if(art !== fallbackArt) offlineObjectUrls.add(art);
  const audio = record.audio instanceof Blob ? URL.createObjectURL(record.audio) : null;
  if(audio) offlineObjectUrls.add(audio);
  const profiles = record.artistProfiles || (record.artistProfile ? {[record.artist]: record.artistProfile} : {});
  Object.entries(profiles).forEach(([name, profile]) => offlineArtistProfiles.set(name, profile));
  const photos = record.artistPhotos || (record.artistPhoto instanceof Blob ? {[record.artist]: record.artistPhoto} : {});
  Object.entries(photos).forEach(([name, blob]) => {
    if(!(blob instanceof Blob)) return;
    const photo = URL.createObjectURL(blob);
    offlineObjectUrls.add(photo);
    offlineArtistPhotos.set(name, photo);
  });
  const lyrics = record.lyrics
    ? (record.lyrics.lines ? record.lyrics : {source:"offline", text:record.lyrics.text || ""})
    : null;
  return {
    id: record.id, title: record.title, artist: record.artist, album: record.album,
    year: "", duration: record.duration || 0, art, fallbackArt,
    streamUrl: null, file: record.audio, offlineUrl: audio, offline: true,
    favorite: false, dateAdded: record.dateAdded || Date.now(),
    lyrics, customLyrics: record.customLyrics || null,
    lyricsResolved: !!record.lyrics, lyricsLoading: false, fingerprint: record.id,
  };
}

async function loadOfflineTracks(){
  releaseOfflineObjectUrls();
  const records = await AuralisDB.getAll(OFFLINE_STORE);
  return records.map(offlineTrackFromRecord);
}

async function fetchBlob(url){
  const response = await fetch(url, {cache:"no-store"});
  if(!response.ok) throw new Error(`Download failed (${response.status})`);
  return response.blob();
}

async function downloadTrackOffline(track){
  if(!track || track.offline) return;
  try{
    if(!track.lyricsResolved) await ensureTrackLyrics(track);
    const artistNames = artistsOf(track);
    const [audio, cover, profiles] = await Promise.all([
      fetchBlob(track.streamUrl),
      track.has_cover === false || !track.art.includes("/cover") ? Promise.resolve(null) : fetchBlob(trackArtUrl(track, 512)),
      Promise.all(artistNames.map(async name => [name, await ArtistProfileEngine.resolve(name)])),
    ]);
    const artistProfiles = Object.fromEntries(profiles.filter(([, profile]) => profile));
    const artistPhotos = {};
    await Promise.all(artistNames.map(async name => {
      const photoUrl = await ArtistPhotoEngine.resolve(name);
      if(photoUrl) artistPhotos[name] = await fetchBlob(photoUrl);
    }));
    const record = {
      id: track.id, title: track.title, artist: track.artist, album: track.album,
      duration: track.duration, customLyrics: track.customLyrics || null,
      lyrics: track.lyrics || null, audio, cover, artistProfiles, artistPhotos,
      dateAdded: Date.now(),
    };
    if(!await AuralisDB.putRecord(record, OFFLINE_STORE)) throw new Error("This browser could not save the offline track.");
    const replacement = offlineTrackFromRecord(record);
    Object.assign(track, replacement);
    toast(`Downloaded “${track.title}” for offline listening.`);
    render();
  }catch(error){
    console.warn("Offline download failed", error);
    toast(error.message || "Could not download this track.");
  }
}

async function removeOfflineTrack(track){
  if(!track?.offline) return;
  await AuralisDB.del(track.id, OFFLINE_STORE);
  track.offline = false;
  track.offlineUrl = null;
  track.streamUrl = apiUrl(`/api/tracks/${encodeURIComponent(track.id)}/stream`);
  toast(`Removed “${track.title}” from offline storage.`);
  render();
}

//where section is saved
async function saveSettings(){
  await AuralisDB.set("auralis:settings", JSON.stringify({
    volume: state.volume, muted: state.muted, shuffle: state.shuffle,
    repeat: state.repeat, listMode: state.listMode,
    profilePhotoFit: state.profilePhotoFit
  }));
}
let libraryMetaSaveQueue = Promise.resolve();

async function persistLibraryMeta(snapshot){
  let lastError;
  for(let attempt = 0; attempt < 3; attempt++){
    try{
      const token = await ensureCsrfToken(attempt > 0);
      const res = await fetch("/api/library/state", {
        method:"PUT", credentials:"same-origin",
        headers:{"Content-Type":"application/json", "X-CSRF-Token":token || ""},
        body:JSON.stringify(snapshot)
      });
      if(res.status === 403 && attempt < 2) continue;
      if(res.ok) return;
      const error = new Error(`Could not save library state (${res.status})`);
      error.status = res.status;
      if(res.status < 500 && res.status !== 429) throw error;
      lastError = error;
    }catch(error){
      lastError = error;
      if(error?.status && error.status < 500 && error.status !== 429) throw error;
    }
    if(attempt < 2) await wait(250 * (2 ** attempt));
  }
  throw lastError || new Error("Could not save library state");
}

function saveLibraryMeta(){
  const snapshot = {
    favorites: state.tracks.filter(t=>t.favorite).map(t=>t.id),
    playlists: state.playlists.map(p => ({
      id:p.id, name:p.name,
      trackIds: [...p.trackIds]
    }))
  };
  const save = () => persistLibraryMeta(snapshot);
  libraryMetaSaveQueue = libraryMetaSaveQueue.then(save, save);
  return libraryMetaSaveQueue.catch(error => {
    console.warn("Could not sync library state", error);
    toast("Library changes could not be synced. Please try again.");
  });
}
async function loadPersisted(){
  const [settings, library] = await Promise.all([
    AuralisDB.get("auralis:settings"),
    AuralisDB.get("auralis:library"),
  ]);
  try{
    if(settings){
      const v = JSON.parse(settings);
      state.volume = v.volume ?? 0.7; state.muted = !!v.muted;
      state.shuffle = !!v.shuffle; state.repeat = v.repeat || "off";
      state.listMode = v.listMode || "grid";
      state.profilePhotoFit = ["cover","contain","fill","none"].includes(v.profilePhotoFit)
        ? v.profilePhotoFit
        : "cover";
    }
  }catch(e){}
  window._persistedLibrary = null;
  try{
    if(library) window._persistedLibrary = JSON.parse(library);
  }catch(e){}
}

function relinkPersistedLibrary(){
  const persisted = window._persistedLibrary;
  if(!persisted) return;
  const byId = new Map(state.tracks.map(t=>[t.id,t]));
  (persisted.favorites||[]).forEach(key => {
    const t = byId.get(key);
    if(t) t.favorite = true;
  });
  (persisted.playlists||[]).forEach(p => {
    let existing = state.playlists.find(pl=>pl.id===p.id);
    if(!existing){ existing = {id:p.id, name:p.name, trackIds:[]}; state.playlists.push(existing); }
    const keys = p.trackIds || p.fingerprints || [];
    keys.forEach(key => {
      const t = byId.get(key);
      if(t && !existing.trackIds.includes(t.id)) existing.trackIds.push(t.id);
    });
  });
}

/* ============================================================
   SERVER LIBRARY — songs are saved under data/uploads on disk
   ============================================================ */
function trackFromServer(payload){
  const customLyrics = payload.custom_lyrics || null;
  const fallbackArt = generateAura((payload.artist||"")+"|"+(payload.album||"")+"|"+(payload.title||""));
  return {
    id: payload.id,
    title: payload.title || "Unknown title",
    artist: payload.artist || "Unknown artist",
    album: payload.album || "Unknown album",
    year: "",
    duration: payload.duration || 0,
    art: payload.has_cover ? apiUrl(payload.cover_url) : fallbackArt,
    fallbackArt,
    streamUrl: apiUrl(payload.stream_url),
    favorite: false,
    dateAdded: Date.now(),
    lyrics: customLyrics ? (LyricsEngine.fromLRC(customLyrics) || { source:"custom", text:customLyrics }) : null,
    customLyrics,
    lyricsResolved: !!customLyrics,
    lyricsLoading: false,
    fingerprint: payload.id,
  };
}

let serverLibraryRequest = null;
let serverLibraryLoading = true;
let serverLibraryLoaded = false;
let serverLibraryLoadFailed = false;

const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

async function fetchWithRetry(url, options = {}, attempts = 5) {
  let lastError;

  for (let attempt = 0; attempt < attempts; attempt++) {
    let controller = null;
    let timeout = null;

    try {
      if (typeof AbortController !== "undefined") {
        controller = new AbortController();
        timeout = setTimeout(() => controller.abort(), 30000);
      }

      const fetchOptions = { ...options };

      // Only use signal when AbortController exists.
      if (controller) {
        fetchOptions.signal = controller.signal;
      }

      const response = await fetch(url, fetchOptions);

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
      await wait(Math.min(2000 * 2 ** attempt, 10000));
    }
  }

  throw lastError || new Error("Server unavailable");
}

async function loadServerLibrary(force = false){
  if(!force && serverLibraryLoaded){ return state.tracks.length; }
  if(!force && serverLibraryRequest){ return serverLibraryRequest; }

  serverLibraryRequest = (async () => {
    try{
      const [tracksRes, stateRes] = await Promise.all([
        fetchWithRetry("/api/tracks", {}, 3),
        fetch("/api/library/state"),
      ]);
      if(!tracksRes.ok) throw new Error("bad status "+tracksRes.status);
      const data = await tracksRes.json();
      state.tracks = (data.tracks || []).map(trackFromServer);
      const offlineTracks = await loadOfflineTracks();
      const offlineById = new Map(offlineTracks.map(track => [track.id, track]));
      state.tracks = state.tracks.map(track => offlineById.get(track.id) || track);
      offlineTracks.forEach(track => {
        if(!state.tracks.some(existing => existing.id === track.id)) state.tracks.push(track);
      });
      const legacy = window._persistedLibrary;
      if(stateRes.ok){
        const remote = await stateRes.json();
        if(!(remote.favorites||[]).length && !(remote.playlists||[]).length && legacy &&
           ((legacy.favorites||[]).length || (legacy.playlists||[]).length)){
          relinkPersistedLibrary();
          await saveLibraryMeta();
        } else {
          window._persistedLibrary = remote;
          relinkPersistedLibrary();
        }
      } else relinkPersistedLibrary();
      serverLibraryLoaded = true;
      serverLibraryLoading = false;
      serverLibraryLoadFailed = false;
      return state.tracks.length;
    }catch(e){
      console.warn("Could not load server library", e);
      state.tracks = await loadOfflineTracks();
      serverLibraryLoading = false;
      serverLibraryLoadFailed = state.tracks.length === 0;
      return 0;
    } finally {
      serverLibraryRequest = null;
    }
  })();

  return serverLibraryRequest;
}

let librarySyncInFlight = false;
async function syncServerLibrary(){
  if(librarySyncInFlight || document.hidden || !serverLibraryLoaded) return;
  librarySyncInFlight = true;
  try{
    const response = await fetch("/api/tracks", {cache:"no-store"});
    if(!response.ok) return;
    const remoteTracks = (await response.json()).tracks || [];
    const previousIds = new Set(state.tracks.map(track => track.id));
    const previousById = new Map(state.tracks.map(track => [track.id, track]));
    const offlineTracks = await loadOfflineTracks();
    const offlineById = new Map(offlineTracks.map(track => [track.id, track]));
    const remoteById = new Map(remoteTracks.map(payload => {
      const track = trackFromServer(payload);
      const syncedTrack = offlineById.get(track.id) || track;
      syncedTrack.favorite = previousById.get(track.id)?.favorite || false;
      return [track.id, syncedTrack];
    }));
    const localOnly = state.tracks.filter(track => track.offline && !remoteById.has(track.id));
    state.tracks = [...remoteById.values(), ...localOnly];
    const added = state.tracks.filter(track => !previousIds.has(track.id));
    if(added.length){
      render();
      toast(`${added.length} new song${added.length === 1 ? "" : "s"} synced.`);
    }
  }catch(error){
    console.warn("Background library sync failed", error);
  }finally{
    librarySyncInFlight = false;
  }
}

/* ============================================================
   CSRF — fetched once per page load, sent on any state-changing
   /api/* call (upload, delete, password change).
   ============================================================ */
let csrfToken = $("meta[name='csrf-token']")?.content || null;
async function ensureCsrfToken(forceRefresh=false){
  if(csrfToken && !forceRefresh) return csrfToken;
  try{
    const res = await fetch("/api/csrf");
    if(res.ok){
      csrfToken = (await res.json()).csrf_token;
      return csrfToken;
    }
  }catch(_){}
  return null;
}

async function uploadFileToServer(file){
  const body = new FormData();
  body.append("file", file, file.name);
  const upload = async (refreshCsrf=false) => fetch("/api/library/upload", {
    method: "POST",
    headers: { "X-CSRF-Token": await ensureCsrfToken(refreshCsrf) },
    body,
  });
  let res = await upload();
  // A page can keep an old token after the session changes in another tab.
  // Refresh it once before reporting the upload as failed.
  if(res.status === 403) res = await upload(true);
  if(!res.ok){
    let detail = "Upload failed";
    try{ const err = await res.json(); detail = err.detail || detail; }catch(_){}
    const error = new Error(detail);
    error.status = res.status;
    throw error;
  }
  const payload = await res.json();
  if(res.status === 202 || payload.status === "processing"){
    for(let attempt = 0; attempt < 60; attempt++){
      await wait(1000);
      const statusRes = await fetch(`/api/library/upload/${encodeURIComponent(payload.id)}`);
      if(!statusRes.ok) throw new Error("Could not check upload status");
      const status = await statusRes.json();
      if(status.status === "completed"){
        if(status.track) return trackFromServer(status.track);
        await loadServerLibrary(true);
        const refreshed = state.tracks.find(t => t.id === status.track?.id);
        if(refreshed) return refreshed;
        throw new Error("Upload completed but the track is not available yet");
      }
      if(status.status === "failed") throw new Error(status.error || "Upload processing failed");
    }
    throw new Error("Upload is still processing; refresh the library shortly");
  }
  return trackFromServer(payload);
}

async function deleteTrackOnServer(trackId){
  try{
    const res = await fetch(`/api/tracks/${encodeURIComponent(trackId)}`, {
      method: "DELETE",
      headers: { "X-CSRF-Token": await ensureCsrfToken() },
    });
    return res.ok;
  }catch(e){
    return false;
  }
}

async function saveTrackLyrics(track, lyrics){
  const save = async (refreshCsrf=false) => {
    const token = await ensureCsrfToken(refreshCsrf);
    return fetch(`/api/tracks/${encodeURIComponent(track.id)}/lyrics`, {
      method: "PUT",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": token || "" },
      body: JSON.stringify({ lyrics }),
    });
  };
  let res = await save();
  // A tab can retain a token after the server-side session has rotated. Retry
  // once with a new token; do not turn a genuine authorization failure into a
  // lyric lookup miss.
  if(res.status === 403){
    res = await save(true);
  }
  if(res.status === 404){
    // A library migration can change the browser's cached fingerprint while
    // the title, artist, and audio remain the same. Rebind once, then retry.
    const libraryRes = await fetch("/api/tracks");
    if(libraryRes.ok){
      const data = await libraryRes.json();
      const match = (data.tracks || []).find(candidate =>
        candidate.title === track.title &&
        candidate.artist === track.artist &&
        Math.abs((candidate.duration || 0) - (track.duration || 0)) < 1
      );
      if(match){
        const oldId = track.id;
        Object.assign(track, trackFromServer(match));
        state.queue = state.queue.map(id => id === oldId ? track.id : id);
        res = await save();
      }
    }
  }
  if(!res.ok){
    let detail = res.status === 401 ? "Your session expired. Please sign in again." : "Could not save lyrics";
    try{ detail = (await res.json()).detail || detail; }catch(_){ }
    throw new Error(detail);
  }
  return await res.json();
}

const FS_SUPPORTED = "showDirectoryPicker" in window;
const AUDIO_EXT_RE = /\.(mp3|m4a|mp4|wav|flac|ogg|oga|aac|opus|weba)$/i;

async function collectAudioFiles(dirHandle, out = []){
  for await (const [name, handle] of dirHandle.entries()){
    if(handle.kind === "file"){
      if(AUDIO_EXT_RE.test(name)){
        try{ out.push(await handle.getFile()); }catch(e){}
      }
    } else if(handle.kind === "directory"){
      await collectAudioFiles(handle, out);
    }
  }
  return out;
}

async function connectMusicFolder(){
  if(FS_SUPPORTED){
    let dirHandle;
    try{
      dirHandle = await window.showDirectoryPicker({ id: "auralis-music", mode: "read" });
    }catch(e){ return; }
    toast(`Scanning “${dirHandle.name}”…`);
    const files = await collectAudioFiles(dirHandle);
    await importFiles(files);
    return;
  }
  $("#folderInput").click();
}

async function importFiles(fileList){
  const files = Array.from(fileList).filter(f => /audio\//.test(f.type) || AUDIO_EXT_RE.test(f.name));
  if(files.length === 0){ toast("No audio files found in that selection."); return; }
  toast(`Saving ${files.length} track${files.length>1?"s":""}…`);

  let added = 0, failed = 0;
  const failures = [];
  for(const file of files){
    try{
      const track = await uploadFileToServer(file);
      if(state.tracks.some(t=>t.id === track.id)) continue;
      state.tracks.push(track);
      added++;
    }catch(e){
      failed++;
      failures.push(e?.message || "Upload failed");
      console.warn("Upload failed for", file.name, e);
    }
  }
  relinkPersistedLibrary();
  saveLibraryMeta();
  if(added && failed){
    const reason = failures[0] || "Upload failed";
    toast(`Saved ${added} track${added!==1?"s":""}; ${failed} couldn't be saved: ${reason}`);
  } else if(added) toast(`Saved ${added} track${added!==1?"s":""} to your library.`);
  else if(failed){
    const reason = failures[0] || "Upload failed";
    toast(files.length === 1 ? `Couldn't save the file: ${reason}` :
      `Couldn't save those files: ${reason}${failed > 1 ? ` (+${failed - 1} more)` : ""}`);
  }
  else toast("Those tracks were already in your library.");
  render();
}

/* ============================================================
   PLAYBACK ENGINE
   ============================================================ */
function ensureAudioGraph(){
  if(audioCtx) return true;
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if(!AudioContextClass) return false;
  try{
    audioCtx = new AudioContextClass();
    sourceNode = audioCtx.createMediaElementSource(audioEl);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    freqData = new Uint8Array(analyser.frequencyBinCount);
    waveData = new Uint8Array(analyser.fftSize);
    sourceNode.connect(analyser);
    analyser.connect(audioCtx.destination);
    return true;
  }catch(error){
    console.warn("Visualizer audio analysis unavailable", error);
    try{ audioCtx?.close(); }catch(_){}
    audioCtx = null;
    sourceNode = null;
    analyser = null;
    freqData = null;
    waveData = null;
    return false;
  }
}

function currentTrack(){
  if(state.queueIndex < 0 || state.queueIndex >= state.queue.length) return null;
  const id = state.queue[state.queueIndex];
  return state.tracks.find(t => t.id === id) || null;
}

function buildQueueFrom(list, startId){
  state.queue = list.map(t=>t.id);
  state.queueIndex = Math.max(0, state.queue.indexOf(startId));
}

// Moves the track at fromIndex to sit at toIndex, keeping queueIndex pointed
// at whichever track it was pointed at before the move (not just the same
// numeric slot) so a reorder never silently changes what's "now playing".
function reorderQueue(fromIndex, toIndex){
  if(fromIndex === toIndex) return;
  const [moved] = state.queue.splice(fromIndex, 1);
  let insertAt = toIndex;
  if(fromIndex < toIndex) insertAt--;
  state.queue.splice(insertAt, 0, moved);
  if(state.queueIndex === fromIndex) state.queueIndex = insertAt;
  else if(fromIndex < state.queueIndex && insertAt >= state.queueIndex) state.queueIndex--;
  else if(fromIndex > state.queueIndex && insertAt <= state.queueIndex) state.queueIndex++;
}

function playTrackFromList(list, trackId){
  capturePlaybackContext();
  buildQueueFrom(list, trackId);
  playCurrent();
}

let currentBlobUrl = null;
let audioRetryPending = false;
function playCurrent(){
  const t = currentTrack();
  if(!t) return;
  if(ensureAudioGraph() && audioCtx.state === "suspended") audioCtx.resume();
  if(currentBlobUrl){ URL.revokeObjectURL(currentBlobUrl); currentBlobUrl = null; }
  if(t.offlineUrl){
    audioEl.src = t.offlineUrl;
  } else if(t.streamUrl){
    audioEl.src = t.streamUrl;
  } else if(t.file){
    currentBlobUrl = URL.createObjectURL(t.file);
    audioEl.src = currentBlobUrl;
  } else {
    toast("This track has no playable source.");
    return;
  }
  audioEl.volume = state.muted ? 0 : state.volume;
  updateMediaSessionMetadata();
  audioRetryPending = false;
  audioEl.play().catch(()=>{
    if(audioRetryPending) return;
    audioRetryPending = true;
    toast("Waking the music server…");
    wait(2000).then(() => {
      if(currentTrack()?.id !== t.id || !audioEl.paused) return;
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

function togglePlay(){
  if(!currentTrack()){
    // nothing loaded yet: play first track of current view
    const list = getVisibleTracks();
    if(list.length){ playTrackFromList(list, list[0].id); }
    return;
  }
  if(audioEl.paused){
    if(ensureAudioGraph() && audioCtx.state==="suspended") audioCtx.resume();
    if(csrfToken?.startsWith("__")) csrfToken = null;
    // "Add to queue" on an empty queue sets queueIndex without ever assigning
    // audioEl.src — resume would call play() on an empty element and fail.
    if(!audioEl.getAttribute("src")){ playCurrent(); return; }
    audioEl.play().catch(()=>{
      playCurrent();
    });
  }
  else audioEl.pause();
}

function playNext(auto=false){
  if(state.queue.length === 0) return;
  if(state.repeat === "one" && auto){ audioEl.currentTime = 0; audioEl.play(); return; }
  if(state.shuffle){
    let next;
    if(state.queue.length === 1) next = 0;
    else { do { next = Math.floor(Math.random()*state.queue.length); } while(next === state.queueIndex); }
    state.queueIndex = next;
  } else {
    state.queueIndex++;
    if(state.queueIndex >= state.queue.length){
      state.queueIndex = 0; // wrap to first track when the list ends
    }
  }
  playCurrent();
}
function playPrev(){
  if(state.queue.length === 0) return;
  if(audioEl.currentTime > 3){ audioEl.currentTime = 0; return; }
  state.queueIndex = Math.max(0, state.queueIndex - 1);
  playCurrent();
}

function installMediaSessionHandlers(){
  if(!mediaSession) return;
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
      if(Number.isFinite(audioEl.duration)){
        audioEl.currentTime = Math.min(audioEl.duration, (audioEl.currentTime || 0) + offset);
      }
    },
    seekto: (details) => {
      if(Number.isFinite(details.seekTime)){
        const duration = audioEl.duration;
        audioEl.currentTime = Number.isFinite(duration)
          ? Math.max(0, Math.min(duration, details.seekTime))
          : Math.max(0, details.seekTime);
      }
    },
  };
  Object.entries(handlers).forEach(([action, handler]) => {
    try{ mediaSession.setActionHandler(action, handler); }catch(_){}
  });
}

installMediaSessionHandlers();

audioEl.addEventListener("ended", () => playNext(true));
audioEl.addEventListener("play", () => {
  syncPlayIcons(true);
  try{ if(mediaSession) mediaSession.playbackState = "playing"; }catch(_){}
  updateMediaSessionPosition();
});
audioEl.addEventListener("pause", () => {
  syncPlayIcons(false);
  try{ if(mediaSession) mediaSession.playbackState = "paused"; }catch(_){}
  updateMediaSessionPosition();
});
audioEl.addEventListener("timeupdate", () => {
  updateSeekUI();
  updateMobileLyricsPreview(currentTrack());
  updateMediaSessionPosition();
});
audioEl.addEventListener("seeked", () => {
  LyricsDebug.log(`seeked → t=${audioEl.currentTime.toFixed(2)}s, recalculating active line`);
  updateMediaSessionPosition();
  if($("#lyricsOverlay").classList.contains("open")) updateLyricsHighlight(true);
});
audioEl.addEventListener("loadedmetadata", () => {
  updateSeekUI();
  updateMediaSessionPosition();
});

function syncPlayIcons(playing){
  const pathPlay = 'M9 6.8v10.4L18.2 12z';
  const pathPause = 'M8 6.5h3.2v11H8zM12.8 6.5H16v11h-3.2z';
  $("#iconPlay").innerHTML = `<path d="${playing?pathPause:pathPlay}"/>`;
  $("#miniIconPlay").innerHTML = `<path d="${playing?pathPause:pathPlay}"/>`;
  $("#mobileIconPlay").innerHTML = `<path d="${playing?pathPause:pathPlay}"/>`;
}

function updateSeekUI(){
  const dur = audioEl.duration || 0;
  const cur = audioEl.currentTime || 0;
  const pct = dur ? (cur/dur*100) : 0;
  $("#timeCur").textContent = fmtTime(cur);
  $("#timeDur").textContent = fmtTime(dur);
  $("#seekFill").style.width = pct+"%";
  $("#seekThumb").style.left = pct+"%";
  $("#miniCur").textContent = fmtTime(cur);
  $("#miniDur").textContent = fmtTime(dur);
  $("#miniSeekFill").style.width = pct+"%";
  $("#miniSeekThumb").style.left = pct+"%";
  $("#mobileTimeCur").textContent = fmtTime(cur);
  $("#mobileTimeDur").textContent = fmtTime(dur);
  $("#mobileSeekFill").style.width = pct+"%";
  $("#mobileSeekThumb").style.left = pct+"%";
  [$("#seek"), $("#miniSeek"), $("#mobileSeek")].forEach(el=>{
    if(!el) return;
    el.setAttribute("aria-valuemax", String(Math.round(dur)));
    el.setAttribute("aria-valuenow", String(Math.round(cur)));
    el.setAttribute("aria-valuetext", `${fmtTime(cur)} of ${fmtTime(dur)}`);
  });
}

function viewPlaybackContext(){
  if(state.view === "favorites") return "Liked Songs";
  if(state.view.startsWith("playlist:")){
    const playlist = state.playlists.find(p => p.id === state.view.slice(9));
    return playlist ? playlist.name : "Playlist";
  }
  if(state.view === "artists" || state.view.startsWith("artist:")) return "Artist radio";
  return "Library";
}

function capturePlaybackContext(){
  state.playingContext = viewPlaybackContext();
}

function updateMobileLyricsPreview(track){
  const el = $("#mobileLyricsText");
  if(!el) return;
  if(track && !track.lyricsResolved && !track.lyricsLoading){
    ensureTrackLyrics(track);
  }
  if(track?.lyrics?.lines?.length){
    const time = (audioEl.currentTime || 0) * 1000;
    let index = 0;
    track.lyrics.lines.forEach((line, i)=>{ if(line.time <= time) index = i; });
    const active = track.lyrics.lines[index]?.text || "";
    const next = track.lyrics.lines[index + 1]?.text || "";
    el.innerHTML = [
      active ? `<span class="lyric-active">${escapeHtml(active)}</span>` : "",
      next ? `<span class="lyric-next">${escapeHtml(next)}</span>` : "",
    ].filter(Boolean).join("\n") || "Lyrics are ready.";
  } else if(track?.lyrics?.text){
    const lines = track.lyrics.text.split(/\n+/).filter(Boolean).slice(0, 2);
    el.innerHTML = lines.map((line, i) =>
      `<span class="${i === 0 ? "lyric-active" : "lyric-next"}">${escapeHtml(line)}</span>`
    ).join("\n");
  } else if(track && !track.lyricsResolved){
    el.textContent = "Finding lyrics for this song…";
  } else {
    el.textContent = track ? "No lyrics available for this song." : "Play a song to see its lyrics here.";
  }
}

/** Resolve lyrics for a track once (ID3 → LRCLIB). Safe to call from preview or overlay. */
function ensureTrackLyrics(track){
  if(!track || track.lyricsResolved) return Promise.resolve(track?.lyrics || null);
  if(track.lyricsPromise) return track.lyricsPromise;
  track.lyricsLoading = true;
  const requestedTrackId = track.id;
  LyricsDebug.log(`state: lyrics lookup started for "${track.title}" by ${track.artist}`);
  track.lyricsPromise = (async () => {
    let result = track.customLyrics
      ? (LyricsEngine.fromLRC(track.customLyrics) || { source:"custom", text:track.customLyrics })
      : null;
    try{
      const headRes = result || track.offline
        ? null
        : await fetch(`/api/tracks/${encodeURIComponent(track.id)}/tag-head`);
      const blob = track.offline && track.file ? track.file : (headRes?.ok ? await headRes.blob() : null);
      if(blob){
        const file = track.offline && track.file ? track.file : new File([blob], `${track.title || "track"}.mp3`, { type: "audio/mpeg" });
        const meta = await parseID3(file);
        result = LyricsEngine.fromID3(meta);
        if(result) LyricsDebug.log(`state: embedded ID3 lyrics found → ${result.source}`);
      }
    }catch(e){
      LyricsDebug.warn("state: embedded ID3 lyrics read failed —", e.message);
    }
    if(!result){
      result = await LyricsEngine.fromOnline(track);
    }
    return result;
  })().then(result => {
    if(track.customLyrics){
      track.lyricsLoading = false;
      return;
    }
    track.lyrics = result;
    track.lyricsResolved = true;
    track.lyricsLoading = false;
    LyricsDebug.log(`state: lyrics lookup finished for "${track.title}" →`, result ? result.source : "nothing found");
    if(currentTrack()?.id !== requestedTrackId) return;
    updateMobileLyricsPreview(track);
    if($("#lyricsOverlay").classList.contains("open")) renderLyricsStage();
    return result;
  }).catch(e => {
    track.lyricsResolved = true;
    track.lyricsLoading = false;
    LyricsDebug.warn("state: lyrics lookup threw —", e.message);
    if(currentTrack()?.id === requestedTrackId){
      updateMobileLyricsPreview(track);
      if($("#lyricsOverlay").classList.contains("open")) renderLyricsStage();
    }
    return null;
  });
  return track.lyricsPromise;
}

function updateNowPlayingUI(){
  const t = currentTrack();
  const bar = $("#nowbar");
  if(!t){
    bar.classList.add("hidden");
    document.body.classList.remove("now-playing");
    $("#mobilePlayer")?.classList.remove("open");
    return;
  }
  bar.classList.remove("hidden");
  document.body.classList.add("now-playing");
  $("#nowArt").src = t.art; $("#miniArt").src = t.art;
  $("#nowTitle").textContent = t.title; $("#miniTitle").textContent = t.title;
  const credits = artistCreditsLabel(t);
  $("#nowArtist").innerHTML = artistLinksMarkup(t);
  $("#nowArtist").classList.remove("artist-link");
  $("#nowArtist").title = credits;
  $("#miniArtist").textContent = credits;
  document.title = `${t.title} — ${credits} · Vervfy`;
  $("#nowFav").classList.toggle("on", !!t.favorite);
  const offlineButton = $("#btnOffline");
  if(offlineButton){
    offlineButton.classList.toggle("on", !!t.offline);
    offlineButton.title = t.offline ? "Remove offline download" : "Download for offline";
    offlineButton.setAttribute("aria-label", offlineButton.title);
  }
  $("#mobilePlayerBg").style.backgroundImage = `url("${t.art}")`;
  $("#mobilePlayerArt").src = t.art;
  $("#mobilePlayerTitle").textContent = t.title;
  $("#mobilePlayerArtist").innerHTML = artistLinksMarkup(t);
  wireArtistLinks($("#mobilePlayerArtist"));
  $("#mobilePlayerContext").textContent = state.playingContext || viewPlaybackContext();
  $("#mobilePlayerFav").classList.toggle("on", !!t.favorite);
  updateMobileLyricsPreview(t);
  updateVolUI();
  resetVizTrack(t);
  if($("#lyricsOverlay").classList.contains("open")) renderLyricsStage();
}

function renderLibraryHighlight(){
  const t = currentTrack();
  $$(".card").forEach(c => c.classList.toggle("playing", t && c.dataset.id===t.id));
  $$(".row").forEach(r => r.classList.toggle("playing", t && r.dataset.id===t.id));
}

/* ---------- lyrics view ---------- */
function lyricsEmptyMarkup(title, sub){
  return `<div class="lyrics-empty">
    <div class="empty-orb"></div>
    <h3>${escapeHtml(title)}</h3>
    <p>${escapeHtml(sub)}</p>
  </div>`;
}
function renderLyricsStage(){
  if(lyricsSyncClockRaf){
    cancelAnimationFrame(lyricsSyncClockRaf);
    lyricsSyncClockRaf = null;
  }
  const stage = $("#lyricsStage");
  const bg = $("#lyricsBg");
  const t = currentTrack();
  if(!t){
    bg.style.backgroundImage = "";
    stage.innerHTML = lyricsEmptyMarkup("Nothing playing", "Play a track to see its lyrics here.");
    return;
  }
  bg.style.backgroundImage = `url("${t.art}")`;
  const sourceLabel = { sylt:"Synced lyrics", lrc:"Synced · LRC", uslt:"Lyrics", custom:"Pasted lyrics", "custom-synced":"Synced · pasted", "online-synced":"Synced · LRCLIB", "online-plain":"Lyrics · LRCLIB" };
  const sideMarkup = `
    <div class="lyrics-side">
      <div class="lyrics-art"><img src="${escapeHtml(t.art)}" alt=""></div>
      <div class="lyrics-meta"><div class="t">${escapeHtml(t.title)}</div><div class="a">${artistLinksMarkup(t)}</div></div>
      ${t.lyrics ? `<div class="lyrics-source">${sourceLabel[t.lyrics.source] || "Lyrics"}</div>` : ""}
    </div>`;

  if(t.lyrics && t.lyrics.lines && t.lyrics.lines.length){
    const linesHtml = t.lyrics.lines.map((ln,i) =>
      `<div class="lyrics-line" data-time="${ln.time}" data-i="${i}">${escapeHtml(ln.text) || "&nbsp;"}</div>`
    ).join("");
    const resyncButton = t.customLyrics
      ? `<button class="btn lyrics-resync-btn" id="btnResyncLyrics">Re-sync to audio</button>`
      : "";
    stage.innerHTML = sideMarkup + `<div class="lyrics-viewport"><div class="lyrics-track" id="lyricsTrack">${linesHtml}</div></div>${resyncButton}`;
    // defensive: confirm lines are truly ascending — the highlight scan below
    // assumes this and only re-sorts here if something upstream ever regresses.
    const linesRef = t.lyrics.lines;
    for(let i=1;i<linesRef.length;i++){
      if(linesRef[i].time < linesRef[i-1].time){
        LyricsDebug.warn(`${t.title}: lyric lines were not ascending (index ${i-1}=${linesRef[i-1].time}ms > index ${i}=${linesRef[i].time}ms) — re-sorting`);
        linesRef.sort((a,b)=>a.time-b.time);
        break;
      }
    }
    _lyricsLastLoggedIdx = null; // new track/lines: force the next highlight update to log
    _lyricsRenderedIdx = null;
    $$(".lyrics-line").forEach(el => {
      el.addEventListener("click", () => {
        const time = parseFloat(el.dataset.time)/1000;
        LyricsDebug.log(`click-to-seek → line "${el.textContent}" @ ${time.toFixed(2)}s`);
        if(isFinite(time)) audioEl.currentTime = time;
      });
    });
    $("#btnResyncLyrics")?.addEventListener("click", () => openLyricsSyncEditor(t));
    updateLyricsHighlight(true);
  } else if(t.lyrics && t.lyrics.text){
    const paragraphs = t.lyrics.text.split(/\n{2,}/).map(p => `<p>${escapeHtml(p)}</p>`).join("");
    stage.innerHTML = sideMarkup + `<div class="lyrics-plain">${paragraphs}<button class="btn btn-primary lyrics-sync-btn" id="btnSyncLyrics">Sync to audio</button></div>`;
    $("#btnSyncLyrics").addEventListener("click", () => openLyricsSyncEditor(t));
  } else if(!t.lyricsResolved){
    // Nothing cached yet — kick off shared lookup (ID3 → LRCLIB).
    stage.innerHTML = sideMarkup + lyricsEmptyMarkup("Searching for lyrics…", "Checking this file and LRCLIB for a match.");
    stage.querySelector(".empty-orb")?.classList.add("lyrics-loading-orb");
    ensureTrackLyrics(t);
  } else {
    stage.innerHTML = sideMarkup + lyricsEmptyMarkup(
      "No lyrics available",
      "Vervfy checked this file's tags and LRCLIB's database, but couldn't find any lyrics for this track."
    ) + `<button class="btn btn-primary lyrics-paste-btn" id="btnPasteLyrics">Paste lyrics</button>`;
    $("#btnPasteLyrics").addEventListener("click", () => openLyricsEditor(t));
  }
  wireArtistLinks(stage);
}
function timedLyricsToLrc(lines){
  return lines.map(line => {
    const totalSeconds = Math.max(0, line.time) / 1000;
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = (totalSeconds % 60).toFixed(2).padStart(5, "0");
    return `[${String(minutes).padStart(2, "0")}:${seconds}]${line.text}`;
  }).join("\n");
}
function openLyricsSyncEditor(track){
  const timedLines = track.lyrics?.lines;
  const text = track.lyrics?.text || track.customLyrics || "";
  const lines = timedLines?.length
    ? timedLines.map(line => line.text.trim()).filter(Boolean)
    : text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  if(!lines.length){ toast("Paste lyrics before syncing them."); return; }

  // Plain lyric text contains no timing information.  Do not invent evenly
  // spaced timestamps: it looks synced, but every verse is wrong.  Instead,
  // record the audio clock when the listener taps each line.
  const stamps = new Array(lines.length).fill(null);
  const stage = $("#lyricsStage");
  const renderRows = () => lines.map((line, index) => {
    const stamp = stamps[index];
    return `<button type="button" class="lyrics-sync-line${stamp !== null ? " stamped" : ""}" data-line-index="${index}">
      <span class="lyrics-sync-line-time">${stamp === null ? "Tap at this line" : fmtTime(stamp / 1000)}</span>
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
    if(!list) return;
    list.innerHTML = renderRows();
    list.querySelectorAll("[data-line-index]").forEach(button => {
      button.addEventListener("click", () => {
        const index = Number(button.dataset.lineIndex);
        stamps[index] = Math.max(0, Math.round((audioEl.currentTime || 0) * 1000));
        refresh();
      });
    });
    saveButton.disabled = stamps.some(stamp => stamp === null);
  };
  refresh();

  $("#btnCancelLyricsSync").addEventListener("click", renderLyricsStage);
  $("#btnSyncFromStart").addEventListener("click", () => {
    audioEl.currentTime = 0;
    audioEl.play().catch(() => toast("Press play, then tap each lyric line."));
  });
  saveButton.addEventListener("click", async () => {
    for(let index=1; index<stamps.length; index++){
      if(stamps[index] < stamps[index - 1]){
        toast("Lyrics must be tapped in song order. Correct the out-of-order line.");
        return;
      }
    }
    saveButton.disabled = true;
    try{
      const synced = { source:"custom-synced", lines: lines.map((line, index) => ({ time:stamps[index], text:line })) };
      const saved = await saveTrackLyrics(track, timedLyricsToLrc(synced.lines));
      track.customLyrics = saved.custom_lyrics;
      track.lyrics = synced;
      track.lyricsResolved = true;
      toast("Lyrics synced to the track");
      renderLyricsStage();
    }catch(e){
      saveButton.disabled = false;
      toast(e.message || "Could not save synced lyrics");
    }
  });

  const updateClock = () => {
    const clock = $("#lyricsSyncTime");
    if(!clock){ lyricsSyncClockRaf = null; return; }
    clock.textContent = fmtTime(audioEl.currentTime || 0);
    lyricsSyncClockRaf = requestAnimationFrame(updateClock);
  };
  updateClock();
}
function openLyricsEditor(track){
  const stage = $("#lyricsStage");
  stage.innerHTML = `
    <div class="lyrics-editor">
      <div class="lyrics-editor-heading">
        <h3>Add lyrics</h3>
        <p>${escapeHtml(track.title)} · ${escapeHtml(track.artist)}</p>
      </div>
      <textarea id="lyricsInput" class="lyrics-input" placeholder="Paste plain lyrics or timestamped LRC lyrics here…">${escapeHtml(track.customLyrics || track.lyrics?.text || "")}</textarea>
      <div class="lyrics-editor-actions">
        <button class="btn" id="btnCancelLyrics">Cancel</button>
        <button class="btn btn-primary" id="btnSaveLyrics">Save lyrics</button>
      </div>
    </div>`;
  $("#btnCancelLyrics").addEventListener("click", renderLyricsStage);
  $("#btnSaveLyrics").addEventListener("click", async () => {
    const input = $("#lyricsInput");
    const lyrics = input.value.trim();
    if(!lyrics){ input.focus(); toast("Paste some lyrics first."); return; }
    const button = $("#btnSaveLyrics");
    button.disabled = true;
    try{
      const parsed = LyricsEngine.fromLRC(lyrics);
      const synced = parsed;
      const lyricsToSave = synced?.lines ? timedLyricsToLrc(synced.lines) : lyrics;
      const saved = await saveTrackLyrics(track, lyricsToSave);
      // Use the value accepted by the account-scoped API, rather than merely
      // assuming the browser's request succeeded.
      track.customLyrics = saved.custom_lyrics;
      track.lyrics = normalizeSyncedLyrics(
        LyricsEngine.fromLRC(track.customLyrics) || synced,
        track.duration
      ) || { source:"custom", text:track.customLyrics };
      track.lyricsResolved = true;
      toast(synced?.lines ? "Timestamped lyrics saved" : "Lyrics saved — use Sync to audio to add timing");
      renderLyricsStage();
    }catch(e){
      button.disabled = false;
      toast(e.message || "Could not save lyrics");
    }
  });
  $("#lyricsInput").focus();
}
function updateLyricsHighlight(instant){
  const t = currentTrack();
  if(!t || !t.lyrics || !t.lyrics.lines) return;
  const track = $("#lyricsTrack");
  if(!track) return;
  const curSec = audioEl.currentTime || 0;
  const curMs = curSec * 1000;
  const lines = t.lyrics.lines;
  // "Active" is defined as the LAST line whose timestamp is <= current playback
  // time. Use a binary search so the animation-clock update stays cheap for
  // long transcripts and always chooses the correct line after seeking.
  let low = 0, high = lines.length - 1, activeIdx = -1;
  while(low <= high){
    const middle = (low + high) >> 1;
    if(lines[middle].time <= curMs){
      activeIdx = middle;
      low = middle + 1;
    }else{
      high = middle - 1;
    }
  }

  if(LYRICS_SYNC_DEBUG && activeIdx !== _lyricsLastLoggedIdx){
    const matched = activeIdx >= 0 ? lines[activeIdx] : null;
    LyricsDebug.log(
      `t=${curSec.toFixed(2)}s`,
      "→ activeIdx=", activeIdx,
      matched ? `lineTime=${(matched.time/1000).toFixed(2)}s text="${matched.text}"` : "(before first line)"
    );
    _lyricsLastLoggedIdx = activeIdx;
  }

  if(!instant && activeIdx === _lyricsRenderedIdx) return;
  _lyricsRenderedIdx = activeIdx;

  const els = track.children;
  for(let i=0;i<els.length;i++){
    els[i].classList.toggle("active", i === activeIdx);
    els[i].classList.toggle("past", i < activeIdx);
  }
  // Always keep some line vertically centered in the viewport. Before playback
  // reaches the first timestamp (or when nothing is playing yet), activeIdx is
  // -1 and this used to skip centering entirely — leaving the whole lyrics
  // block pinned at the container's top edge with every line trailing
  // downward off-center instead of lining up with the album art beside it.
  // Anchor on the first line in that case so the block is centered even
  // before anything is "active".
  const anchorIdx = activeIdx >= 0 ? activeIdx : 0;
  const anchorEl = els[anchorIdx];
  if(anchorEl){
    // .lyrics-track already sits with its own top edge at the viewport's
    // vertical middle via `top:50%` in CSS. The translateY only needs to
    // pull the anchor line's own center up to that point — it must NOT also
    // add viewport.clientHeight/2, or the line ends up offset an extra half
    // a viewport-height too low (which is why lines were landing near the
    // bottom of the screen instead of centered next to the album art).
    const targetY = -(anchorEl.offsetTop + anchorEl.clientHeight/2);
    if(instant){
      track.style.transition = "none";
      track.style.transform = `translateY(${targetY}px)`;
      requestAnimationFrame(() => { track.style.transition = ""; });
    } else {
      track.style.transform = `translateY(${targetY}px)`;
    }
  }
}
function startLyricsHighlightLoop(){
  if(lyricsHighlightRaf) return;
  const tick = () => {
    lyricsHighlightRaf = null;
    if(!$("#lyricsOverlay").classList.contains("open")) return;
    updateLyricsHighlight();
    lyricsHighlightRaf = requestAnimationFrame(tick);
  };
  lyricsHighlightRaf = requestAnimationFrame(tick);
}
function stopLyricsHighlightLoop(){
  if(lyricsHighlightRaf){
    cancelAnimationFrame(lyricsHighlightRaf);
    lyricsHighlightRaf = null;
  }
}
function openLyrics(){
  $("#mobilePlayer")?.classList.remove("open");
  closeViz();
  // Render only after the overlay is visible so the lyric viewport has real
  // dimensions when the active line is positioned.
  $("#lyricsOverlay").classList.add("open");
  renderLyricsStage();
  requestAnimationFrame(() => {
    if($("#lyricsOverlay").classList.contains("open")) updateLyricsHighlight(true);
  });
  startLyricsHighlightLoop();
}
function closeLyrics(){
  $("#lyricsOverlay").classList.remove("open");
  stopLyricsHighlightLoop();
  if(lyricsSyncClockRaf){
    cancelAnimationFrame(lyricsSyncClockRaf);
    lyricsSyncClockRaf = null;
  }
}

/* ---------- full visualizer overlay (radial spectrum) ---------- */
let vizAmplitudes = [];
let vizPhase = 0;
let vizEnergy = 0;
let vizBeatTimes = [];
let vizLastBeat = 0;
let vizBeatKick = 0;      // spikes to 1 on each detected beat, decays every frame
let vizBpm = 0;            // last known bpm, drives rotation speed
let vizHue = 255;          // smoothed color hue, shifts with the bass/treble balance
let vizParticles = [];     // beat-triggered sparks
let vizTrackId = null;

function spawnVizParticles(intensity){
  const count = 5 + Math.round(intensity * 6);
  for(let i=0;i<count;i++){
    vizParticles.push({
      angle: Math.random() * Math.PI * 2,
      r: 0,
      speed: 2.2 + Math.random() * 2.4,
      life: 1,
      decay: 0.018 + Math.random() * 0.012,
    });
  }
  if(vizParticles.length > 160) vizParticles = vizParticles.slice(-160);
}

function resetVizTrack(track = currentTrack()){
  if(!$("#vizOverlay")?.classList.contains("open")) return;
  const trackId = track?.id || null;
  if(trackId !== vizTrackId){
    vizTrackId = trackId;
    vizBeatTimes = [];
    vizLastBeat = 0;
    vizEnergy = 0;
    vizBeatKick = 0;
    vizBpm = 0;
    vizParticles = [];
  }
}

function updateVizMotion(low, mid, high, energy){
  const now = performance.now();
  const threshold = Math.max(.22, vizEnergy * 1.18);
  const beatHit = low > threshold && low > mid * .72 && now - vizLastBeat > 260;
  if(beatHit){
    if(vizLastBeat) vizBeatTimes.push(now - vizLastBeat);
    vizLastBeat = now;
    vizBeatTimes = vizBeatTimes.slice(-8);
    vizBeatKick = 1;
    spawnVizParticles(low);
  }
  vizEnergy += (energy - vizEnergy) * .1;
  const average = vizBeatTimes.length ? vizBeatTimes.reduce((a,b)=>a+b,0) / vizBeatTimes.length : 0;
  const bpm = average ? Math.max(60, Math.min(180, Math.round(60000 / average))) : null;
  vizBpm = bpm || vizBpm;

  const targetHue = 255 - Math.min(1, Math.max(0, high - low + .5)) * 90;
  vizHue += (targetHue - vizHue) * .04;
}

function isCompactViz(){
  return window.matchMedia("(max-width: 900px)").matches ||
    window.matchMedia("(pointer: coarse)").matches;
}

function resizeVizCanvas(){
  const canvas = $("#vizCanvas");
  if(!canvas) return;
  const cssSize = Math.min(
    window.innerWidth <= 780 ? window.innerWidth * .84 : window.innerHeight * .76,
    window.innerWidth <= 780 ? 520 : 760
  );
  const pixelRatio = Math.min(window.devicePixelRatio || 1, isCompactViz() ? 1.25 : 1.5);
  const maxPixels = isCompactViz() ? 640 : 900;
  const size = Math.max(320, Math.min(maxPixels, Math.round(cssSize * pixelRatio)));
  if(size === vizCanvasSize) return;
  vizCanvasSize = size;
  canvas.width = size;
  canvas.height = size;
  canvas.getContext("2d")?.clearRect(0, 0, size, size);
}

function drawViz(timestamp = performance.now()){
  const canvas = $("#vizCanvas");
  if(!canvas) return;
  const compact = isCompactViz();
  if(compact && timestamp - vizLastFrameAt < 32){
    rafViz = requestAnimationFrame(drawViz);
    return;
  }
  vizLastFrameAt = timestamp;
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;

  ctx.fillStyle = "rgba(8,10,16,.16)";     // trail instead of a hard clear
  ctx.fillRect(0,0,w,h);

  const cx=w/2, cy=h/2, baseR = w*0.21;
  const rotSpeed = 0.003 + (vizBpm ? (vizBpm/120) * 0.006 : 0.003);
  vizPhase += rotSpeed;
  vizBeatKick *= 0.90;

  const calmPulse = Math.sin(vizPhase) * 0.5 + 0.5;
  const kick = vizBeatKick;

  ctx.save();
  ctx.translate(cx, cy);

  const haloR = baseR*2.2 * (1 + kick*0.12);
  const halo = ctx.createRadialGradient(0,0,baseR*.35,0,0,haloR);
  halo.addColorStop(0, `hsla(${vizHue},85%,72%,${0.13 + calmPulse*.03 + kick*.12})`);
  halo.addColorStop(.55, `hsla(${vizHue+40},85%,60%,${0.035 + kick*.05})`);
  halo.addColorStop(1, "rgba(8,10,16,0)");
  ctx.fillStyle = halo;
  ctx.beginPath(); ctx.arc(0,0,haloR,0,Math.PI*2); ctx.fill();

  const coreR = baseR + calmPulse*3 + kick*10;
  ctx.beginPath(); ctx.arc(0,0,coreR,0,Math.PI*2);
  ctx.fillStyle = `hsla(${vizHue},60%,90%,${.035 + kick*.05})`; ctx.fill();
  ctx.strokeStyle = `hsla(${vizHue},70%,80%,${.14 + kick*.25})`; ctx.lineWidth=1 + kick*1.5; ctx.stroke();

  ctx.beginPath(); ctx.arc(0,0,baseR + 14 + calmPulse*2 + kick*6,0,Math.PI*2);
  ctx.strokeStyle = `hsla(${vizHue+60},80%,65%,${.13 + kick*.2})`; ctx.lineWidth=1; ctx.stroke();
  ctx.restore();

  if(analyser && !audioEl.paused){
    analyser.getByteFrequencyData(freqData);
    analyser.getByteTimeDomainData(waveData);

    const bands = compact ? 32 : 48;
    const step = Math.max(1, Math.floor(freqData.length/bands));
    let low = 0, mid = 0, high = 0;
    ctx.save(); ctx.translate(cx,cy);
    for(let i=0;i<bands;i++){
      let sum=0; for(let j=0;j<step;j++) sum += freqData[i*step+j];
      const amp = (sum/step)/255;
      if(i < bands * .24) low += amp;
      else if(i < bands * .65) mid += amp;
      else high += amp;
      const previous = vizAmplitudes[i] || 0;
      vizAmplitudes[i] = previous + (amp - previous) * 0.12;
      const angle = (i/bands)*Math.PI*2 - Math.PI/2 + vizPhase;
      const r1 = baseR+8, r2 = baseR+8+vizAmplitudes[i]*(w*0.2)*(1+kick*.25);
      const x1=Math.cos(angle)*r1, y1=Math.sin(angle)*r1;
      const x2=Math.cos(angle)*r2, y2=Math.sin(angle)*r2;
      const grad = ctx.createLinearGradient(x1,y1,x2,y2);
      grad.addColorStop(0,`hsla(${vizHue},80%,72%,.78)`); grad.addColorStop(1,`hsla(${vizHue+50},80%,60%,.3)`);
      ctx.strokeStyle=grad; ctx.lineWidth=Math.max(2, w*0.004); ctx.lineCap="round";
      ctx.shadowBlur = compact ? 0 : 8 + kick*10;
      ctx.shadowColor=`hsla(${vizHue},80%,70%,.4)`;
      ctx.beginPath(); ctx.moveTo(x1,y1); ctx.lineTo(x2,y2); ctx.stroke();
    }

    ctx.beginPath();
    const waveR = baseR - 30;
    for(let i=0;i<waveData.length;i++){
      const v = (waveData[i]-128)/128;
      const angle = (i/waveData.length)*Math.PI*2 - Math.PI/2 - vizPhase*1.4;
      const r = waveR + v * 16 * (1+kick*.4);
      const x = Math.cos(angle)*r, y = Math.sin(angle)*r;
      if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
    }
    ctx.closePath();
    ctx.strokeStyle = `hsla(${vizHue+20},85%,75%,${.4 + kick*.3})`;
    ctx.lineWidth = 1.5;
    ctx.shadowBlur = compact ? 0 : 6;
    ctx.shadowColor = `hsla(${vizHue+20},85%,70%,.5)`;
    ctx.stroke();

    ctx.restore();
    updateVizMotion(low/(bands*.24), mid/(bands*.41), high/(bands*.35), Math.min(1, low/(bands*.24)*.45 + mid/(bands*.41)*.4 + high/(bands*.35)*.15));
  } else {
    vizAmplitudes = vizAmplitudes.map(value => value * 0.92);
    vizEnergy *= .98;
    updateVizMotion(0, 0, 0, vizEnergy);
  }

  ctx.save(); ctx.translate(cx,cy);
  vizParticles.forEach(p=>{
    p.r += p.speed;
    p.life -= p.decay;
    if(p.life <= 0) return;
    const x = Math.cos(p.angle)*(baseR+8+p.r), y = Math.sin(p.angle)*(baseR+8+p.r);
    ctx.beginPath();
    ctx.arc(x,y, 2 + p.life*2, 0, Math.PI*2);
    ctx.fillStyle = `hsla(${vizHue},90%,80%,${p.life*.8})`;
    ctx.fill();
  });
  vizParticles = vizParticles.filter(p=>p.life > 0);
  ctx.restore();

  rafViz = requestAnimationFrame(drawViz);
}
function openViz(){
  closeLyrics();
  vizBeatTimes = [];
  vizLastBeat = 0;
  vizEnergy = 0;
  vizBeatKick = 0;
  vizBpm = 0;
  vizParticles = [];
  vizTrackId = null;
  $("#vizOverlay").classList.add("open");
  resizeVizCanvas();
  resetVizTrack();
  ensureAudioGraph();
  if(!rafViz) drawViz();
}
function closeViz(){
  $("#vizOverlay").classList.remove("open");
  if(rafViz){ cancelAnimationFrame(rafViz); rafViz = null; }
}

function updateVolUI(){
  const pct = state.muted ? 0 : state.volume*100;
  $("#volFill").style.width = pct+"%";
  const svg = $("#iconVol");
  svg.style.opacity = state.muted ? 0.4 : 1;
}
function setVolume(v){
  state.volume = Math.min(1, Math.max(0, v));
  state.muted = false;
  audioEl.volume = state.volume;
  updateVolUI(); saveSettings();
}

/* ============================================================
   VIEW / FILTER HELPERS
   ============================================================ */
function artistNameOf(t){
  return (t && t.artist) ? t.artist : "Unknown artist";
}

/* Split collaboration credits into individual performers.
   Keep duo/band names that only use "&" / "and" (e.g. "Strings & Heart").
   Also pull featured names out of titles like "(feat. A, B & C)" / "(with SZA)". */
const ARTIST_LIST_SEP_RE = /\s*(?:,|;|\/|\bfeat(?:uring)?\.?\b|\bft\.?\b|\bwith\b)\s*/i;
const ARTIST_LIST_SEP_TEST_RE = /[,;/]|\bfeat(?:uring)?\.?\b|\bft\.?\b|\bwith\b/i;
const TITLE_FEATURED_RE = /\((?:feat(?:uring)?|ft|with)\.?\s+([^)]+)\)/ig;
const ARTIST_AND_SPLIT_RE = /\s+(?:&|and)\s+/i;

function cleanArtistCredit(part){
  return String(part || "")
    .replace(/^[\s\-–—·•]+|[\s\-–—·•]+$/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function splitArtistCreditList(raw){
  const text = cleanArtistCredit(raw);
  if(!text) return [];
  if(text.toLocaleLowerCase() === "unknown artist") return [text];

  const hasListSep = ARTIST_LIST_SEP_TEST_RE.test(text);
  let parts = hasListSep ? text.split(ARTIST_LIST_SEP_RE) : [text];
  if(hasListSep){
    // Inside an already-listed credit, "&" / "and" separate people
    // ("Lalo Brito & José…"). Leave sole credits like "Strings & Heart" intact.
    parts = parts.flatMap(part => part.split(ARTIST_AND_SPLIT_RE));
  }
  return parts.map(cleanArtistCredit).filter(Boolean);
}

function featuredArtistsFromTitle(title){
  const text = String(title || "");
  const found = [];
  let match;
  TITLE_FEATURED_RE.lastIndex = 0;
  while((match = TITLE_FEATURED_RE.exec(text)) !== null){
    found.push(...splitArtistCreditList(match[1]));
  }
  return found;
}

function artistsOf(t){
  const names = [
    ...splitArtistCreditList(artistNameOf(t)),
    ...featuredArtistsFromTitle(t && t.title),
  ];
  const seen = new Map();
  for(const name of names){
    const key = name.toLocaleLowerCase();
    if(!seen.has(key)) seen.set(key, name);
  }
  return Array.from(seen.values());
}

function artistKey(name){
  return String(name || "").toLocaleLowerCase();
}

function trackHasArtist(t, name){
  const key = artistKey(name);
  return artistsOf(t).some(n => artistKey(n) === key);
}

function getArtists(){
  const map = new Map();
  for(const t of state.tracks){
    const names = artistsOf(t);
    if(!names.length) continue;
    const album = typeof t.album === "string" ? t.album.trim() : "";
    const duration = Number(t.duration);
    for(const name of names){
      const key = artistKey(name);
      let entry = map.get(key);
      if(!entry){
        entry = { name, art: t.art, fallbackArt: t.fallbackArt, tracks: [], albums: new Set(), duration: 0 };
        map.set(key, entry);
      } else if(name.length > entry.name.length){
        // Prefer the fuller casing/spelling when the same person appears twice.
        entry.name = name;
      }
      // A collab track belongs on each performer's profile once.
      if(entry.tracks.some(existing => existing.id === t.id)) continue;
      entry.tracks.push(t);
      if(album && album.toLocaleLowerCase() !== "unknown album"){
        entry.albums.add(album.toLocaleLowerCase());
      }
      if(Number.isFinite(duration) && duration > 0){
        entry.duration += duration;
      }
    }
  }
  return Array.from(map.values()).map(artist => ({
    ...artist,
    albumCount: artist.albums.size,
  })).sort((a,b)=> a.name.localeCompare(b.name, undefined, {sensitivity:"base"}));
}
function artistViewKey(name){
  return "artist:" + encodeURIComponent(name);
}
function artistNameFromView(view){
  return decodeURIComponent(view.slice(7));
}
function openArtist(name){
  if(!name) return;
  state.view = artistViewKey(name);
  state.search = "";
  const input = $("#searchInput");
  if(input) input.value = "";
  render();
  const content = $("#content");
  if(content) content.scrollTop = 0;
}

function getVisibleTracks(){
  let list;
  if(state.view === "library") list = state.tracks;
  else if(state.view === "favorites") list = state.tracks.filter(t=>t.favorite);
  else if(state.view === "offline") list = state.tracks.filter(t=>t.offline);
  else if(state.view.startsWith("playlist:")){
    const pl = state.playlists.find(p=>p.id===state.view.slice(9));
    list = pl ? pl.trackIds.map(id=>state.tracks.find(t=>t.id===id)).filter(Boolean) : [];
  } else if(state.view.startsWith("artist:")){
    const name = artistNameFromView(state.view);
    list = state.tracks.filter(t => trackHasArtist(t, name));
  } else if(state.view.startsWith("album:")){
    const info = albumInfoFromView(state.view);
    list = info ? state.tracks.filter(t =>
      (t.album || "Unknown album") === info.album && artistNameOf(t) === info.artist
    ) : [];
  } else list = state.tracks;

  if(state.search.trim()){
    const q = state.search.toLowerCase();
    list = list.filter(t => (t.title+" "+t.artist+" "+t.album).toLowerCase().includes(q));
  }
  return list;
}

/* ============================================================
   RENDERING
   ============================================================ */
function render(){
  renderTopbar();
  if(state.view === "account") renderAccountView();
  else if(state.view === "playlists") renderPlaylistsView();
  else if(state.view === "artists") renderArtistsView();
  else if(state.view.startsWith("artist:")) renderArtistDetailView();
  else renderTrackListView();
  renderQueuePanel();
  renderLibraryHighlight();
  wireMediaImages($("#content"));
}

function renderTopbar(){
  const titles = { library:"Library", favorites:"Favorites", offline:"Offline", playlists:"Playlists", artists:"Artists", account:"Account" };
  let title = titles[state.view];
  if(!title && state.view.startsWith("playlist:")){
    const pl = state.playlists.find(p=>p.id===state.view.slice(9));
    title = pl ? pl.name : "Playlist";
  } else if(!title && state.view.startsWith("artist:")){
    title = artistNameFromView(state.view);
  } else if(!title && state.view.startsWith("album:")){
    title = albumInfoFromView(state.view)?.album || "Album";
  }
  $("#viewTitle").textContent = title || "Library";
  let count;
  if(state.view === "playlists") count = state.playlists.length;
  else if(state.view === "artists"){
    let artists = getArtists();
    if(state.search.trim()){
      const q = state.search.toLowerCase();
      artists = artists.filter(a => a.name.toLowerCase().includes(q));
    }
    count = artists.length;
  }
  else count = getVisibleTracks().length;
  $("#viewCount").textContent = (state.view!=="account" && state.tracks.length) ? `· ${count}` : "";
  $("#viewToggle").style.display = (state.view==="playlists"||state.view==="artists"||state.view==="account") ? "none" : "flex";
  $(".search-wrap").style.display = state.view==="account" ? "none" : "flex";
  $("#btnImportTop").style.display = state.view==="account" ? "none" : "flex";
  $$(".rail-btn[data-view]").forEach(b=>{
    const active = b.dataset.view === state.view
      || (state.view.startsWith("playlist") && b.dataset.view==="playlists")
      || (state.view.startsWith("artist") && b.dataset.view==="artists");
    b.classList.toggle("active", active);
  });
}

function artistLinkMarkup(name){
  const label = escapeHtml(name);
  return `<button type="button" class="artist-link" data-action="artist" data-artist="${escapeHtml(encodeURIComponent(name))}" title="View ${label}">${label}</button>`;
}
function artistLinksMarkup(t){
  const names = artistsOf(t);
  if(!names.length) return artistLinkMarkup("Unknown artist");
  return names.map(artistLinkMarkup).join('<span class="artist-sep">, </span>');
}
function artistCreditsLabel(t){
  const names = artistsOf(t);
  return names.length ? names.join(", ") : artistNameOf(t);
}
function trackRowMarkup(t, idx, showAlbum=true){
  const playing = currentTrack()?.id === t.id;
  const artistText = escapeHtml(artistCreditsLabel(t));
  const title = escapeHtml(t.title);
  const albumText = showAlbum ? escapeHtml(t.album) : "";
  const metaTitle = showAlbum && albumText ? `${artistText} — ${albumText}` : artistText;
  return `
  <div class="row" data-id="${escapeHtml(t.id)}" draggable="true">
    <div class="row-idx">
      <span class="num">${idx+1}</span>
      <span class="play-mini" data-action="play"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></span>
      <span class="bars"><span></span><span></span><span></span></span>
    </div>
    <div class="row-title-wrap">
      <img class="row-art media-image" ${artAttrs(t, 160)} alt="">
      <div class="row-title-stack">
        <div class="row-title" title="${escapeHtml(title)}">${title}</div>
        <div class="row-meta" title="${escapeHtml(metaTitle)}">
          <div class="row-artist">${artistLinksMarkup(t)}</div>
          ${showAlbum ? `<span class="row-meta-sep" aria-hidden="true">·</span><div class="row-album" title="${escapeHtml(albumText)}">${albumText}</div>` : ""}
        </div>
      </div>
    </div>
    <div class="row-album-cell" title="${escapeHtml(albumText)}">${showAlbum ? albumText : ""}</div>
    <div class="row-time" data-track-time="${escapeHtml(t.id)}">${t.duration?fmtTime(t.duration):"--:--"}</div>
    <div class="row-actions">
      <button data-action="queue" title="Add to queue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6.5h16M4 12h10M4 17.5h10"/><path d="M16.5 14.2l4 2.3-4 2.3z" fill="currentColor" stroke="none"/></svg></button>
      <button data-action="fav" class="${t.favorite?'fav-on':''}" title="Favorite"><svg viewBox="0 0 24 24" fill="${t.favorite?'currentColor':'none'}" stroke="currentColor" stroke-width="1.8"><path d="M12 20s-7-4.3-9.5-9C0.8 7.4 3 4 6.5 4c2 0 3.4 1.1 4.5 2.6C12.1 5.1 13.5 4 15.5 4 19 4 21.2 7.4 19.5 11 17 15.7 12 20 12 20Z"/></svg></button>
      <button data-action="menu" title="More"><svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/></svg></button>
    </div>
  </div>`;
}
function cardMarkup(t){
  const playing = currentTrack()?.id === t.id;
  return `
  <div class="card ${playing?'playing':''}" data-id="${escapeHtml(t.id)}">
    <div class="card-art">
      <img class="media-image" ${artAttrs(t, 320)} alt="">
      <div class="card-play"><button data-action="play"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></button></div>
    </div>
    <button class="card-queue" data-action="queue" title="Add to queue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6.5h16M4 12h10M4 17.5h10"/><path d="M16.5 14.2l4 2.3-4 2.3z" fill="currentColor" stroke="none"/></svg></button>
    <button class="card-menu" data-action="menu" title="More options" aria-label="More options"><svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/></svg></button>
    <button class="card-fav ${t.favorite?'on':''}" data-action="fav" title="Favorite"><svg viewBox="0 0 24 24" fill="${t.favorite?'currentColor':'none'}" stroke="currentColor" stroke-width="1.8"><path d="M12 20s-7-4.3-9.5-9C0.8 7.4 3 4 6.5 4c2 0 3.4 1.1 4.5 2.6C12.1 5.1 13.5 4 15.5 4 19 4 21.2 7.4 19.5 11 17 15.7 12 20 12 20Z"/></svg></button>
    <div class="card-title">${escapeHtml(t.title)}</div>
    <div class="card-sub">${artistLinksMarkup(t)}</div>
  </div>`;
}
function escapeHtml(s){ return (s||"").replace(/[&<>"']/g, m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m])); }

function trackArtUrl(track, size=512){
  if(!track?.art) return track?.fallbackArt || "";
  if(!track.art.includes("/cover")) return track.art;
  try{
    const url = new URL(track.art, window.location.href);
    url.searchParams.set("size", String(size));
    return url.href;
  }catch(_){ return track.art; }
}

function artAttrs(track, size=512, priority="low"){
  const src = escapeHtml(trackArtUrl(track, size));
  const fallback = escapeHtml(track.fallbackArt || "");
  const loading = priority === "high" ? "eager" : "lazy";
  return `src="${src}" data-fallback="${fallback}" loading="${loading}" decoding="async" fetchpriority="${priority}"`;
}

function wireMediaImages(root=document){
  root.querySelectorAll("img[data-fallback]").forEach(img => {
    if(img.complete && img.naturalWidth) img.classList.add("media-image-ready");
    img.addEventListener("load", () => img.classList.add("media-image-ready"), {once:true});
    img.addEventListener("error", () => {
      const fallback = img.dataset.fallback;
      if(fallback && img.src !== fallback){ img.src = fallback; return; }
      img.classList.add("media-image-broken");
    }, {once:false});
  });
}

function renderTrackListView(){
  const content = $("#content");
  if(serverLibraryLoading){
    content.innerHTML = `<div class="library-skeleton" aria-label="Loading library" aria-busy="true">
      <div class="skeleton-row"><span class="skeleton-art"></span><span class="skeleton-copy"><i></i><i></i></span><span class="skeleton-time"></span></div>
      <div class="skeleton-row"><span class="skeleton-art"></span><span class="skeleton-copy"><i></i><i></i></span><span class="skeleton-time"></span></div>
      <div class="skeleton-row"><span class="skeleton-art"></span><span class="skeleton-copy"><i></i><i></i></span><span class="skeleton-time"></span></div>
    </div>`;
    return;
  }
  const list = getVisibleTracks();
  const playlistId = state.view.startsWith("playlist:") ? state.view.slice(9) : null;
  const playlist = playlistId ? state.playlists.find(p=>p.id===playlistId) : null;
  const addPlaylistBtn = playlist ? `<button class="btn" id="btnAddPlaylistTracks" type="button">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
      Add from library
    </button>` : "";
  if(serverLibraryLoadFailed){
    content.innerHTML = '<div class="empty"><div class="empty-orb"></div><h3>Music server unavailable</h3><p>The server may still be waking up. Try connecting again.</p><button class="btn btn-primary" id="retryLibrary">Retry connection</button></div>';
    $("#retryLibrary")?.addEventListener("click", async () => {
      const button = $("#retryLibrary");
      button.disabled = true;
      button.textContent = "Connecting…";
      await loadServerLibrary(true);
      render();
    });
    return;
  }
  if(state.tracks.length === 0){
    content.innerHTML = emptyStateMarkup();
    $("#emptyAddFiles")?.addEventListener("click", ()=> $("#fileInput").click());
    $("#emptyAddFolder")?.addEventListener("click", connectMusicFolder);
    return;
  }
  if(list.length === 0){
    if(state.view === "offline"){
      content.innerHTML = `<div class="empty"><div class="empty-orb"></div><h3>No downloaded songs</h3><p>Download a song from the player or its menu to listen without an internet connection.</p></div>`;
      return;
    }
    if(playlist && !state.search.trim()){
      content.innerHTML = `<div class="empty"><div class="empty-orb"></div><h3>This playlist is empty</h3><p>Add songs from your library to start building it.</p><div style="margin-top:6px;">${addPlaylistBtn}</div></div>`;
      $("#btnAddPlaylistTracks")?.addEventListener("click", ()=> openPlaylistLibraryPicker(playlist.id));
      return;
    }
    content.innerHTML = `<div class="empty"><div class="empty-orb"></div><h3>No matches</h3><p>Try a different search term, or browse your full library.</p></div>`;
    return;
  }
  const toolbar = addPlaylistBtn ? `<div class="queue-toolbar">${addPlaylistBtn}</div>` : "";
  if(state.listMode === "grid"){
    content.innerHTML = `${toolbar}<div class="grid">${list.map(t=>cardMarkup(t)).join("")}</div>`;
  } else {
    content.innerHTML = `
      ${toolbar}
      <div class="list">
        <div class="list-head"><div></div><div>Title</div><div>Album</div><div>Time</div><div></div></div>
        ${list.map((t,i)=>trackRowMarkup(t,i)).join("")}
      </div>`;
  }
  $("#btnAddPlaylistTracks")?.addEventListener("click", ()=> openPlaylistLibraryPicker(playlist.id));
  wireTrackInteractions(list);
}

function emptyStateMarkup(){
  return `
  <div class="empty">
    <div class="empty-orb"></div>
    <h3>Your library is empty</h3>
    <p>Add songs or a folder. Vervfy saves them to your account so they are available on your other devices.</p>
    <div style="display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin-top:6px;">
      <button class="btn btn-primary" id="emptyAddFiles">Add music</button>
      <button class="btn" id="emptyAddFolder">Add folder</button>
    </div>
  </div>`;
}

function wireArtistLinks(root=document){
  root.querySelectorAll('[data-action="artist"]').forEach(el=>{
    el.addEventListener("click",(e)=>{
      e.stopPropagation();
      $("#lyricsOverlay")?.classList.remove("open");
      closeViz();
      $("#mobilePlayer")?.classList.remove("open");
      openArtist(decodeURIComponent(el.dataset.artist || ""));
    });
  });
}
function wireTrackInteractions(list){
  $$(".card").forEach(card => {
    const t = state.tracks.find(x=>x.id===card.dataset.id);
    card.addEventListener("click",(e)=>{
      if(e.target.closest('[data-action="fav"],[data-action="queue"],[data-action="menu"],[data-action="artist"]')) return;
      playTrackFromList(list, t.id);
    });
    card.querySelector('[data-action="fav"]').addEventListener("click",(e)=>{ e.stopPropagation(); toggleFavorite(t); });
    card.querySelector('[data-action="queue"]')?.addEventListener("click",(e)=>{ e.stopPropagation(); addToQueue(t); });
    card.querySelector('[data-action="menu"]')?.addEventListener("click",(e)=>{ e.stopPropagation(); openTrackMenu(e, t); });
    card.addEventListener("contextmenu",(e)=>{ e.preventDefault(); openTrackMenu(e, t); });
  });
  $$(".row").forEach(row => {
    const t = state.tracks.find(x=>x.id===row.dataset.id);
    row.addEventListener("click",(e)=>{
      if(e.target.closest('[data-action="fav"],[data-action="queue"],[data-action="menu"],[data-action="artist"]')) return;
      playTrackFromList(list, t.id);
    });
    row.querySelector('[data-action="fav"]').addEventListener("click",(e)=>{ e.stopPropagation(); toggleFavorite(t); });
    row.querySelector('[data-action="queue"]')?.addEventListener("click",(e)=>{ e.stopPropagation(); addToQueue(t); });
    const menuBtn = row.querySelector('[data-action="menu"]');
    if(menuBtn) menuBtn.addEventListener("click",(e)=>{ e.stopPropagation(); openTrackMenu(e, t); });
    row.addEventListener("contextmenu",(e)=>{ e.preventDefault(); openTrackMenu(e, t); });
    row.addEventListener("dragstart", e=>{ e.dataTransfer.setData("text/plain", t.id); });
  });
  wireArtistLinks($("#content"));
  wireMediaImages($("#content"));
}

function toggleFavorite(t){
  t.favorite = !t.favorite;
  saveLibraryMeta();
  render();
  if(currentTrack()?.id === t.id){
    $("#nowFav")?.classList.toggle("on", t.favorite);
    $("#mobilePlayerFav")?.classList.toggle("on", t.favorite);
  }
}

let menuOutsideHandler = null;
function armMenuOutsideClick(){
  if(menuOutsideHandler) document.removeEventListener("click", menuOutsideHandler);
  menuOutsideHandler = (e)=>{
    if(e.target.closest(".menu,[data-action='menu'],#btnMobilePlayerMenu")) return;
    closeMenus();
  };
  document.addEventListener("click", menuOutsideHandler);
}
function openTrackMenu(e, t){
  closeMenus();
  const menu = document.createElement("div");
  menu.className = "menu";
  const anchor = e.target.closest?.("button");
  if(anchor){
    const rect = anchor.getBoundingClientRect();
    menu.style.top = rect.bottom+6+"px";
    menu.style.left = Math.max(8, Math.min(window.innerWidth-204, rect.left-150))+"px";
  } else {
    menu.style.top = Math.min(window.innerHeight-160, e.clientY+4)+"px";
    menu.style.left = Math.max(8, Math.min(window.innerWidth-204, e.clientX))+"px";
  }
  const inPlaylist = state.view.startsWith("playlist:") ? state.view.slice(9) : null;
  menu.innerHTML = `
    <div class="menu-item" data-act="play-next"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 12h10M4 18h10"/><path d="m16 15 4 3-4 3"/></svg>Play next</div>
    <div class="menu-item" data-act="queue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 6h16M4 12h10M4 18h10"/></svg>Add to queue</div>
    <div class="menu-item" data-act="playlist"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 5v14M5 12h14"/></svg>Add to playlist</div>
    <div class="menu-item" data-act="offline"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M12 4v11"/><path d="m8 11 4 4 4-4"/><path d="M5 20h14"/></svg>${t.offline ? "Remove offline download" : "Download for offline"}</div>
    <div class="menu-sep"></div>
    ${inPlaylist ? `<div class="menu-item" data-act="remove-from-playlist"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 6l12 12M18 6 6 18"/></svg>Remove from this playlist</div>` : ""}
    <div class="menu-item" data-act="remove"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/></svg>Remove from library</div>
  `;
  document.body.appendChild(menu);
  menu.querySelector('[data-act="play-next"]').addEventListener("click", ()=>{ playNextTrack(t); closeMenus(); });
  menu.querySelector('[data-act="queue"]').addEventListener("click", ()=>{ addToQueue(t); closeMenus(); });
  menu.querySelector('[data-act="playlist"]').addEventListener("click", (ev)=>{ openPlaylistSubmenu(ev, t, menu); });
  menu.querySelector('[data-act="offline"]').addEventListener("click", ()=>{ closeMenus(); t.offline ? removeOfflineTrack(t) : downloadTrackOffline(t); });
  if(inPlaylist) menu.querySelector('[data-act="remove-from-playlist"]').addEventListener("click", ()=>{ removeFromPlaylist(inPlaylist, t); closeMenus(); });
  menu.querySelector('[data-act="remove"]').addEventListener("click", ()=>{ removeTrack(t); closeMenus(); });
  setTimeout(armMenuOutsideClick, 0);
}
function openNowPlayingMenu(anchor, t){
  closeMenus();
  const menu = document.createElement("div");
  menu.className = "menu";
  const rect = anchor.getBoundingClientRect();
  menu.style.top = Math.min(window.innerHeight - 260, rect.bottom + 6) + "px";
  menu.style.left = Math.max(8, Math.min(window.innerWidth - 212, rect.right - 196)) + "px";
  const artist = artistsOf(t)[0] || artistNameOf(t);
  menu.innerHTML = `
    <div class="menu-item" data-act="play-next"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 12h10M4 18h10"/><path d="m16 15 4 3-4 3"/></svg>Play next</div>
    <div class="menu-item" data-act="queue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 6h16M4 12h10M4 18h10"/></svg>Add to queue</div>
    <div class="menu-item" data-act="favorite"><svg viewBox="0 0 24 24" fill="${t.favorite ? "currentColor" : "none"}" stroke="currentColor" stroke-width="1.8"><path d="M12 20s-7-4.3-9.5-9C0.8 7.4 3 4 6.5 4c2 0 3.4 1.1 4.5 2.6C12.1 5.1 13.5 4 15.5 4 19 4 21.2 7.4 19.5 11 17 15.7 12 20 12 20Z"/></svg>${t.favorite ? "Remove from liked songs" : "Save to liked songs"}</div>
    <div class="menu-item" data-act="playlist"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 5v14M5 12h14"/></svg>Add to playlist</div>
    <div class="menu-item" data-act="offline"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M12 4v11"/><path d="m8 11 4 4 4-4"/><path d="M5 20h14"/></svg>${t.offline ? "Remove offline download" : "Download for offline"}</div>
    <div class="menu-sep"></div>
    <div class="menu-item" data-act="artist"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="8" r="3.5"/><path d="M5 20c.8-3.7 3.1-5.5 7-5.5s6.2 1.8 7 5.5"/></svg>About ${escapeHtml(artist)}</div>
    <div class="menu-item" data-act="album"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="4" y="4" width="16" height="16" rx="2"/><circle cx="12" cy="12" r="3.5"/><path d="M7.5 7.5h.01M16.5 16.5h.01"/></svg>Go to album</div>
    <div class="menu-item" data-act="share"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="m8.2 10.8 7.6-4.4M8.2 13.2l7.6 4.4"/></svg>Share</div>
  `;
  document.body.appendChild(menu);
  menu.querySelector('[data-act="play-next"]').addEventListener("click", ()=>{ playNextTrack(t); closeMenus(); });
  menu.querySelector('[data-act="queue"]').addEventListener("click", ()=>{ addToQueue(t); closeMenus(); });
  menu.querySelector('[data-act="favorite"]').addEventListener("click", ()=>{ toggleFavorite(t); closeMenus(); });
  menu.querySelector('[data-act="playlist"]').addEventListener("click", ev=> openPlaylistSubmenu(ev, t, menu));
  menu.querySelector('[data-act="offline"]').addEventListener("click", ()=>{ closeMenus(); t.offline ? removeOfflineTrack(t) : downloadTrackOffline(t); });
  menu.querySelector('[data-act="artist"]').addEventListener("click", ()=>{
    closeMenus();
    $("#mobilePlayer")?.classList.remove("open");
    openArtist(artist);
  });
  menu.querySelector('[data-act="album"]').addEventListener("click", ()=>{
    closeMenus();
    $("#mobilePlayer")?.classList.remove("open");
    openAlbum(t);
  });
  menu.querySelector('[data-act="share"]').addEventListener("click", ()=>{ closeMenus(); shareTrack(t); });
  setTimeout(armMenuOutsideClick, 0);
}
function albumViewKey(t){
  return "album:" + encodeURIComponent(JSON.stringify([t.album || "Unknown album", artistNameOf(t)]));
}
function albumInfoFromView(view){
  try{
    const [album, artist] = JSON.parse(decodeURIComponent(view.slice(6)));
    return { album, artist };
  }catch(_){ return null; }
}
function openAlbum(t){
  if(!t) return;
  state.view = albumViewKey(t);
  state.search = "";
  const input = $("#searchInput");
  if(input) input.value = "";
  render();
}
async function shareTrack(t){
  const shareData = { title: t.title, text: `${t.title} — ${artistCreditsLabel(t)}` };
  if(navigator.share){
    try{ await navigator.share(shareData); }catch(error){
      if(error?.name !== "AbortError") toast("Could not share this song.");
    }
    return;
  }
  try{
    await navigator.clipboard.writeText(`${shareData.text}\n${window.location.href}`);
    toast("Song details copied to clipboard.");
  }catch(_){ toast("Sharing is not available in this browser."); }
}
function openPlaylistSubmenu(e, t, parentMenu){
  e.stopPropagation();
  const old = document.querySelector(".menu-sub"); if(old) old.remove();
  const anchor = e.currentTarget?.closest?.('[data-act="playlist"]') || e.target.closest?.('[data-act="playlist"]');
  if(!anchor) return;
  const sub = document.createElement("div");
  sub.className = "menu menu-sub";
  const items = state.playlists.map(p=>`<div class="menu-item" data-pl="${escapeHtml(p.id)}">${escapeHtml(p.name)}</div>`).join("");
  sub.innerHTML = items + `<div class="menu-sep"></div><div class="menu-item" data-pl="new"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 5v14M5 12h14"/></svg>New playlist…</div>`;
  document.body.appendChild(sub);
  requestAnimationFrame(()=>{
    const anchorRect = anchor.getBoundingClientRect();
    const subRect = sub.getBoundingClientRect();
    const viewportPadding = 8;
    const bottomReserved = (() => {
      const nowbar = $("#nowbar");
      if(!nowbar || nowbar.classList.contains("hidden")) return 0;
      const rect = nowbar.getBoundingClientRect();
      return rect.top > 0 && rect.top < window.innerHeight ? window.innerHeight - rect.top : 0;
    })();
    const minTop = viewportPadding;
    const maxBottom = Math.max(minTop, window.innerHeight - Math.max(viewportPadding, bottomReserved + viewportPadding));
    const rightLeft = anchorRect.right + 6;
    const leftLeft = anchorRect.left - subRect.width - 6;
    const left = rightLeft + subRect.width <= window.innerWidth - viewportPadding
      ? rightLeft
      : Math.max(viewportPadding, leftLeft);
    const top = Math.max(minTop, Math.min(anchorRect.top, maxBottom - subRect.height));
    sub.style.left = `${Math.max(viewportPadding, Math.min(left, window.innerWidth - subRect.width - viewportPadding))}px`;
    sub.style.top = `${top}px`;
  });
  sub.querySelectorAll("[data-pl]").forEach(item=>{
    item.addEventListener("click", ()=>{
      if(item.dataset.pl === "new"){
        const name = prompt("Name your playlist");
        if(name && name.trim()){
          const pl = {id:uid(), name:name.trim(), trackIds:[t.id]};
          state.playlists.push(pl); saveLibraryMeta(); toast(`Created “${pl.name}” and added the track.`);
        }
      } else {
        addTrackToPlaylist(item.dataset.pl, t);
      }
      closeMenus(); render();
    });
  });
}
function closeMenus(){
  $$(".menu").forEach(m=>m.remove());
  if(menuOutsideHandler){
    document.removeEventListener("click", menuOutsideHandler);
    menuOutsideHandler = null;
  }
}

function stopPlayback(){
  audioEl.pause();
  audioEl.removeAttribute("src");
  audioEl.load();
  if(currentBlobUrl){ URL.revokeObjectURL(currentBlobUrl); currentBlobUrl = null; }
  updateNowPlayingUI();
  syncPlayIcons(false);
}

// Drop one queue slot at `i`. If that slot was currently playing, advance
// playback to whatever lands in its place (or stop when the queue empties).
function removeQueueSlot(i){
  if(i < 0 || i >= state.queue.length) return;
  const removingCurrent = i === state.queueIndex;
  state.queue.splice(i, 1);
  if(state.queue.length === 0){
    state.queueIndex = -1;
    stopPlayback();
    return;
  }

  if(i < state.queueIndex) state.queueIndex--;
  else if(removingCurrent){
    if(state.queueIndex >= state.queue.length) state.queueIndex = state.queue.length - 1;
    playCurrent();
  }
}

function wireTouchQueueDrag(row, getIndex, refresh, {longPress = false} = {}){
  let startX = 0, startY = 0, dragging = false, moved = false, startIndex = -1, longPressTimer = null;
  const targetRowAt = clientY=>{
    const rows = [...row.parentElement.querySelectorAll(".q-row")];
    if(!rows.length) return null;
    return rows.reduce((closest, candidate)=>{
      const distance = Math.abs(clientY - (candidate.getBoundingClientRect().top + candidate.offsetHeight / 2));
      if(!closest || distance < closest.distance) return {row:candidate, distance};
      return closest;
    }, null)?.row || null;
  };
  const clearLongPress = ()=>{
    if(longPressTimer){
      clearTimeout(longPressTimer);
      longPressTimer = null;
    }
  };
  row.addEventListener("pointerdown", e=>{
    if(e.pointerType === "mouse") return;
    if(longPress && !e.target.closest(".q-drag")) return;
    if(longPress) row.draggable = false;
    startX = e.clientX;
    startY = e.clientY;
    startIndex = getIndex();
    dragging = false;
    moved = false;
    e.stopPropagation();
    row.setPointerCapture?.(e.pointerId);
    if(longPress){
      longPressTimer = setTimeout(()=>{
        dragging = true;
        row.classList.add("dragging");
      }, 300);
    }
  });
  row.addEventListener("pointermove", e=>{
    if(startIndex < 0) return;
    const distance = Math.hypot(e.clientX-startX, e.clientY-startY);
    if(longPress && !dragging){
      if(distance > 24) clearLongPress();
      return;
    }
    if(!dragging && distance < 8) return;
    clearLongPress();
    dragging = true;
    e.preventDefault();
    row.classList.add("dragging");
    const target = targetRowAt(e.clientY);
    document.querySelectorAll(".drag-over").forEach(el=>el.classList.remove("drag-over"));
    if(target && target !== row){
      target.classList.add("drag-over");
      moved = true;
    }
  });
  const finish = e=>{
    if(startIndex < 0) return;
    clearLongPress();
    const target = targetRowAt(e.clientY);
    if(row.hasPointerCapture?.(e.pointerId)) row.releasePointerCapture(e.pointerId);
    row.classList.remove("dragging");
    document.querySelectorAll(".drag-over").forEach(el=>el.classList.remove("drag-over"));
    if(dragging && moved && target){
      const targetIndex = Number(target.dataset.qi ?? target.dataset.i);
      if(startIndex !== targetIndex) reorderQueue(startIndex, targetIndex);
      row.dataset.dragged = "true";
      refresh();
    }
    startIndex = -1;
    dragging = false;
    if(longPress) row.draggable = true;
  };
  row.addEventListener("pointerup", finish);
  row.addEventListener("pointercancel", finish);
  row.addEventListener("lostpointercapture", clearLongPress);
}

async function removeTrack(t){
  const playingId = currentTrack()?.id || null;
  const wasPlaying = playingId === t.id;
  if(!await deleteTrackOnServer(t.id)){
    toast("Could not remove the track. Please try again.");
    return;
  }
  state.tracks = state.tracks.filter(x=>x.id!==t.id);
  state.playlists.forEach(p=> p.trackIds = p.trackIds.filter(id=>id!==t.id));
  // Strip every occurrence; keep queueIndex pointed at the same playing
  // track when it survived, otherwise advance / stop.
  state.queue = state.queue.filter(id=>id!==t.id);
  if(wasPlaying){
    if(state.queue.length === 0){
      state.queueIndex = -1;
      stopPlayback();
    } else {
      if(state.queueIndex >= state.queue.length) state.queueIndex = state.queue.length - 1;
      if(state.queueIndex < 0) state.queueIndex = 0;
      playCurrent();
    }
  } else if(playingId){
    state.queueIndex = state.queue.indexOf(playingId);
  } else if(state.queueIndex >= state.queue.length){
    state.queueIndex = state.queue.length ? state.queue.length - 1 : -1;
  }
  if(t.art && t.art.startsWith("blob:")) URL.revokeObjectURL(t.art);
  saveLibraryMeta();
  toast(`Removed “${t.title}”.`);
  render();
}

function removeFromPlaylist(playlistId, t){
  const pl = state.playlists.find(p=>p.id===playlistId);
  if(!pl) return;
  pl.trackIds = pl.trackIds.filter(id=>id!==t.id);
  saveLibraryMeta();
  toast(`Removed “${t.title}” from “${pl.name}”.`);
  render();
}

function addToQueue(t){
  state.queue.push(t.id);
  if(state.queueIndex < 0) state.queueIndex = 0;
  toast(`Added “${t.title}” to the queue.`);
  renderQueuePanel();
}

// Insert directly after the current song, without disturbing the active slot.
// If nothing is playing yet, this is equivalent to adding the first queue item.
function playNextTrack(t){
  const insertAt = state.queueIndex < 0 ? state.queue.length : state.queueIndex + 1;
  state.queue.splice(insertAt, 0, t.id);
  if(state.queueIndex < 0) state.queueIndex = 0;
  toast(`“${t.title}” will play next.`);
  renderQueuePanel();
}

function addTrackToPlaylist(playlistId, t, {quiet=false}={}){
  const pl = state.playlists.find(p=>p.id===playlistId);
  if(!pl) return false;
  if(pl.trackIds.includes(t.id)){
    if(!quiet) toast(`Already in “${pl.name}”.`);
    return false;
  }
  pl.trackIds.push(t.id);
  saveLibraryMeta();
  if(!quiet) toast(`Added to “${pl.name}”.`);
  if(state.view === "playlist:"+playlistId) renderTrackListView();
  renderTopbar();
  return true;
}

/* ---------- playlists view ---------- */
/* ---------- account view ---------- */
const ProfilePhotoEditor = (() => {
  const OUTPUT_SIZE = 512;
  let image = null;
  let objectUrl = null;
  let scale = 1;
  let offsetX = 0;
  let offsetY = 0;
  let drag = null;

  const overlay = () => $("#photoEditorOverlay");
  const stage = () => $("#photoEditorStage");
  const preview = () => $("#photoEditorImage");
  const zoom = () => $("#photoEditorZoom");
  const message = () => $("#photoEditorMsg");

  function baseScale(){
    const rect = stage().getBoundingClientRect();
    return Math.max(rect.width / image.naturalWidth, rect.height / image.naturalHeight);
  }

  function clampOffset(){
    const rect = stage().getBoundingClientRect();
    const width = image.naturalWidth * baseScale() * scale;
    const height = image.naturalHeight * baseScale() * scale;
    offsetX = Math.max(-(width - rect.width) / 2, Math.min((width - rect.width) / 2, offsetX));
    offsetY = Math.max(-(height - rect.height) / 2, Math.min((height - rect.height) / 2, offsetY));
  }

  function draw(){
    if(!image) return;
    clampOffset();
    const rect = stage().getBoundingClientRect();
    const width = image.naturalWidth * baseScale() * scale;
    const height = image.naturalHeight * baseScale() * scale;
    const img = preview();
    img.style.width = `${width}px`;
    img.style.height = `${height}px`;
    img.style.left = `${(rect.width - width) / 2 + offsetX}px`;
    img.style.top = `${(rect.height - height) / 2 + offsetY}px`;
  }

  function reset(){
    scale = 1;
    offsetX = 0;
    offsetY = 0;
    zoom().value = String(scale);
    draw();
  }

  function close(){
    overlay()?.classList.remove("open");
    drag = null;
    if(objectUrl){ URL.revokeObjectURL(objectUrl); objectUrl = null; }
  }

  function openSource(src, revokeOnClose=false){
    const img = preview();
    message().textContent = "";
    image = null;
    if(objectUrl){ URL.revokeObjectURL(objectUrl); objectUrl = null; }
    if(revokeOnClose) objectUrl = src;
    img.onload = () => { image = img; reset(); };
    img.onerror = () => { message().textContent = "This image could not be opened."; };
    overlay().classList.add("open");
    img.src = src;
  }

  function openFile(file){
    if(!file) return;
    if(!file.type.startsWith("image/")){
      message().textContent = "Choose a JPEG, PNG, WebP, or GIF image.";
      return;
    }
    if(file.size > 5 * 1024 * 1024){
      message().textContent = "Profile photo must be 5 MB or smaller.";
      return;
    }
    openSource(URL.createObjectURL(file), true);
  }

  async function save(){
    if(!image) return;
    const saveButton = $("#btnSavePhotoEditor");
    saveButton.disabled = true;
    message().textContent = "Saving…";
    try{
      const rect = stage().getBoundingClientRect();
      const displayScale = baseScale() * scale;
      const width = image.naturalWidth * displayScale;
      const height = image.naturalHeight * displayScale;
      const left = (rect.width - width) / 2 + offsetX;
      const top = (rect.height - height) / 2 + offsetY;
      const canvas = document.createElement("canvas");
      canvas.width = OUTPUT_SIZE;
      canvas.height = OUTPUT_SIZE;
      const context = canvas.getContext("2d");
      context.drawImage(image, left * OUTPUT_SIZE / rect.width, top * OUTPUT_SIZE / rect.height,
        width * OUTPUT_SIZE / rect.width, height * OUTPUT_SIZE / rect.height);
      const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.92));
      if(!blob) throw new Error("Could not create the cropped photo");
      await uploadProfilePhoto(blob, "profile-photo.jpg");
      close();
      renderAccountView();
    }catch(err){
      message().textContent = err.message || "Could not save photo";
    }finally{
      saveButton.disabled = false;
    }
  }

  function bind(){
    stage()?.addEventListener("pointerdown", e => {
      if(!image) return;
      drag = { x:e.clientX, y:e.clientY, offsetX, offsetY };
      stage().setPointerCapture?.(e.pointerId);
    });
    stage()?.addEventListener("pointermove", e => {
      if(!drag) return;
      offsetX = drag.offsetX + e.clientX - drag.x;
      offsetY = drag.offsetY + e.clientY - drag.y;
      draw();
    });
    const endDrag = () => { drag = null; };
    stage()?.addEventListener("pointerup", endDrag);
    stage()?.addEventListener("pointercancel", endDrag);
    zoom()?.addEventListener("input", () => { scale = Number(zoom().value); draw(); });
    $("#btnResetPhotoEditor")?.addEventListener("click", reset);
    $("#btnClosePhotoEditor")?.addEventListener("click", close);
    $("#btnSavePhotoEditor")?.addEventListener("click", save);
    overlay()?.addEventListener("click", e => { if(e.target === overlay()) close(); });
    $("#photoEditorInput")?.addEventListener("change", e => {
      openFile(e.target.files?.[0]);
      e.target.value = "";
    });
  }
  bind();
  return { openFile, openSource, close };
})();

async function uploadProfilePhoto(file, filename){
  const body = new FormData();
  body.append("file", file, filename || "profile-photo.jpg");
  const res = await fetch("/api/account/photo", {
    method: "POST",
    headers: { "X-CSRF-Token": await ensureCsrfToken() },
    body,
  });
  const data = await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(data.detail || "Could not upload photo");
  accountInfo = {...accountInfo, photo_url: `${data.photo_url}?v=${Date.now()}`};
  renderHomeProfileAvatar();
}

let accountInfo = null;
function renderHomeProfileAvatar(){
  const avatar = $("#homeProfileAvatar");
  if(!avatar) return;
  const info = accountInfo;
  const username = info?.username || "?";
  avatar.title = info?.username ? `Account: ${info.username}` : "Account";
  avatar.setAttribute("aria-label", `Open account${info?.username ? ` for ${info.username}` : ""}`);
  avatar.innerHTML = info?.photo_url
    ? `<img src="${escapeHtml(info.photo_url)}" alt="Profile photo" style="object-fit:${state.profilePhotoFit || "cover"};">`
    : escapeHtml(username.slice(0, 1).toUpperCase());
}
async function fetchAccountInfo(){
  try{
    const res = await fetch("/api/me");
    if(res.ok) accountInfo = await res.json();
  }catch(_){}
  renderHomeProfileAvatar();
  return accountInfo;
}

function fmtDate(unixSeconds){
  if(!unixSeconds) return "—";
  try{ return new Date(unixSeconds*1000).toLocaleDateString(undefined,{year:"numeric",month:"long",day:"numeric"}); }
  catch(_){ return "—"; }
}

async function renderAccountView(){
  const content = $("#content");
  if(!accountInfo){
    content.innerHTML = `<div class="account-view acct-loading">Loading account…</div>`;
    await fetchAccountInfo();
    if(state.view !== "account") return; // user navigated away while this was in flight
  }
  const info = accountInfo;
  const liked = state.tracks.filter(t=>t.favorite);
  const playlists = state.playlists;
  const artists = getArtists();

  const avatarFit = state.profilePhotoFit || "cover";
  content.innerHTML = `
    <div class="account-view">
      <section class="acct-card">
        <button type="button" class="acct-avatar" id="acctAvatarButton" title="${info?.photo_url ? "Edit profile photo" : "Choose custom profile photo"}" aria-label="${info?.photo_url ? "Edit profile photo" : "Choose custom profile photo"}">
          ${info?.photo_url
            ? `<img src="${escapeHtml(info.photo_url)}" alt="Profile photo" style="object-fit:${avatarFit};">`
            : escapeHtml((info?.username||"?").slice(0,1).toUpperCase())}
        </button>
        <div>
          <div class="acct-name">${escapeHtml(info?.username || "Unknown")}</div>
          <div class="acct-sub">${escapeHtml(info?.email || "No email on file")} · Member since ${fmtDate(info?.created_at)}</div>
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
          <div class="acct-panel-sub">${liked.slice(0,3).map(t=>escapeHtml(t.title)).join(", ") || "None yet"}</div>
        </section>
        <section class="acct-panel" data-nav="artists">
          <div class="acct-panel-head">
            <span>Artists</span><span class="acct-count">${artists.length}</span>
          </div>
          <div class="acct-panel-sub">${artists.slice(0,3).map(a=>escapeHtml(a.name)).join(", ") || "None yet"}</div>
        </section>
        <section class="acct-panel" data-nav="playlists">
          <div class="acct-panel-head">
            <span>Playlists</span><span class="acct-count">${playlists.length}</span>
          </div>
          <div class="acct-panel-sub">${playlists.slice(0,3).map(p=>escapeHtml(p.name)).join(", ") || "None yet"}</div>
        </section>
      </div>

      <section class="acct-settings">
        <div class="acct-settings-title">Profile photo</div>
        <form id="photoForm" class="acct-form acct-photo-form">
          <input type="file" id="profilePhoto" accept="image/jpeg,image/png,image/webp,image/gif" hidden>
          <label for="profilePhoto" class="btn">Choose photo</label>
          ${info?.photo_url ? '<button type="button" class="btn" id="btnRemovePhoto">Remove photo</button>' : ""}
          <div class="acct-form-msg" id="photoMsg">JPEG, PNG, WebP, or GIF up to 5 MB.</div>
        </form>
      </section>

      <section class="acct-settings">
        <div class="acct-settings-title">Profile photo fit</div>
        <div class="acct-form">
          <select id="profilePhotoFit" class="acct-select" aria-label="Profile photo fit">
            <option value="cover" ${avatarFit === "cover" ? "selected" : ""}>Cover</option>
            <option value="contain" ${avatarFit === "contain" ? "selected" : ""}>Contain</option>
            <option value="fill" ${avatarFit === "fill" ? "selected" : ""}>Fill</option>
            <option value="none" ${avatarFit === "none" ? "selected" : ""}>None</option>
          </select>
        </div>
      </section>

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
        <button type="button" class="btn" id="btnAcctLogoutAll">Sign out of all devices</button>
      </section>

      <section class="acct-settings acct-danger-zone">
        <div class="acct-settings-title">Delete account</div>
        <p class="acct-danger-copy">Permanently removes your profile, music files, playlists, favorites, and saved lyrics. This cannot be undone.</p>
        <form id="deleteAccountForm" class="acct-form">
          <input type="password" id="deleteAccountPassword" placeholder="Current password" autocomplete="current-password" required>
          <input type="text" id="deleteAccountConfirmation" placeholder="Type DELETE to confirm" autocomplete="off" required>
          <button type="submit" class="btn btn-danger">Delete account</button>
          <div class="acct-form-msg" id="deleteAccountMsg"></div>
        </form>
      </section>
    </div>`;

  $$(".acct-panel[data-nav]").forEach(panel=>{
    panel.addEventListener("click", ()=>{ state.view = panel.dataset.nav; render(); });
  });

  const acctLogout = $("#btnAcctLogout");
  if (acctLogout) acctLogout.addEventListener("click", () => logoutAndRedirect());
  const acctLogoutAll = $("#btnAcctLogoutAll");
  if (acctLogoutAll) acctLogoutAll.addEventListener("click", async () => {
    acctLogoutAll.disabled = true;
    try{
      const res = await fetch("/api/account/logout-all", {
        method: "POST",
        headers: { "X-CSRF-Token": await ensureCsrfToken() },
      });
      if(!res.ok) throw new Error("Could not sign out of all devices");
      accountInfo = null;
      csrfToken = null;
      window.location.assign("/login");
    }catch(err){
      acctLogoutAll.disabled = false;
      toast(err.message);
    }
  });

  const avatarButton = $("#acctAvatarButton");
  const photoInput = $("#profilePhoto");
  if (avatarButton && photoInput) {
    avatarButton.addEventListener("click", () => {
      if(accountInfo?.photo_url) ProfilePhotoEditor.openSource(accountInfo.photo_url);
      else photoInput.click();
    });
  }

  const photoFitSelect = $("#profilePhotoFit");
  if (photoFitSelect) {
    photoFitSelect.addEventListener("change", async () => {
      state.profilePhotoFit = ["cover","contain","fill","none"].includes(photoFitSelect.value)
        ? photoFitSelect.value
        : "cover";
      await saveSettings();
      renderHomeProfileAvatar();
      renderAccountView();
    });
  }

  const photoMsg = $("#photoMsg");
  photoInput.addEventListener("change", async ()=>{
    const file = photoInput.files?.[0];
    if(!file) return;
    ProfilePhotoEditor.openFile(file);
    photoInput.value = "";
  });
  const removePhoto = $("#btnRemovePhoto");
  if(removePhoto) removePhoto.addEventListener("click", async ()=>{
    photoMsg.textContent = "Removing…"; photoMsg.className = "acct-form-msg";
    try{
      const res = await fetch("/api/account/photo", {
        method: "DELETE",
        headers: { "X-CSRF-Token": await ensureCsrfToken() },
      });
      if(!res.ok) throw new Error("Could not remove photo");
      accountInfo = {...accountInfo, photo_url: null};
      renderHomeProfileAvatar();
      renderAccountView();
    }catch(err){
      photoMsg.textContent = err.message; photoMsg.className = "acct-form-msg error";
    }
  });

  const pwForm = $("#pwForm");
  pwForm.addEventListener("submit", async (e)=>{
    e.preventDefault();
    const msg = $("#pwMsg");
    const current_password = $("#pwCurrent").value;
    const new_password = $("#pwNew").value;
    msg.textContent = "Updating…"; msg.className = "acct-form-msg";
    try{
      const res = await fetch("/api/account/password", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": await ensureCsrfToken() },
        body: JSON.stringify({ current_password, new_password }),
      });
      const data = await res.json().catch(()=>({}));
      if(!res.ok) throw new Error(data.detail || "Could not update password");
      msg.textContent = "Password updated."; msg.className = "acct-form-msg ok";
      pwForm.reset();
    }catch(err){
      msg.textContent = err.message; msg.className = "acct-form-msg error";
    }
  });

  const deleteForm = $("#deleteAccountForm");
  deleteForm.addEventListener("submit", async (e)=>{
    e.preventDefault();
    const msg = $("#deleteAccountMsg");
    const current_password = $("#deleteAccountPassword").value;
    const confirmation = $("#deleteAccountConfirmation").value;
    if(!window.confirm("Delete your account and all of its music data permanently?")) return;
    const button = deleteForm.querySelector("button[type='submit']");
    button.disabled = true;
    msg.textContent = "Deleting account…"; msg.className = "acct-form-msg";
    try{
      const res = await fetch("/api/account", {
        method: "DELETE",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": await ensureCsrfToken() },
        body: JSON.stringify({ current_password, confirmation }),
      });
      const data = await res.json().catch(()=>({}));
      if(!res.ok) throw new Error(data.detail || "Could not delete account");
      accountInfo = null;
      csrfToken = null;
      window.location.assign("/login?account_deleted=1");
    }catch(err){
      msg.textContent = err.message; msg.className = "acct-form-msg error";
      button.disabled = false;
    }
  });
}

function renderPlaylistsView(){
  const content = $("#content");
  const cards = state.playlists.map(p => `
    <div class="pl-card" data-id="${escapeHtml(p.id)}">
      <div class="pl-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 6h13M4 12h13M4 18h9"/><circle cx="20" cy="16" r="2.4"/><path d="M20 6v10"/></svg></div>
      <div class="pl-name">${escapeHtml(p.name)}</div>
      <div class="pl-count">${p.trackIds.length} track${p.trackIds.length!==1?"s":""}</div>
    </div>`).join("");
  content.innerHTML = `
    <div class="pl-grid">
      ${cards}
      <div class="pl-card pl-new" id="plNewCard">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="22" height="22"><path d="M12 5v14M5 12h14"/></svg>
        New playlist
      </div>
    </div>`;
  $$(".pl-card[data-id]").forEach(card=>{
    card.addEventListener("click", ()=>{ state.view = "playlist:"+card.dataset.id; render(); });
  });
  $("#plNewCard").addEventListener("click", ()=>{
    const name = prompt("Name your playlist");
    if(name && name.trim()){
      const pl = {id:uid(), name:name.trim(), trackIds:[]};
      state.playlists.push(pl);
      saveLibraryMeta();
      state.view = "playlist:"+pl.id;
      render();
    }
  });
}

function renderArtistsView(){
  const content = $("#content");
  if(state.tracks.length === 0){
    content.innerHTML = emptyStateMarkup();
    $("#emptyAddFiles")?.addEventListener("click", ()=> $("#fileInput").click());
    $("#emptyAddFolder")?.addEventListener("click", connectMusicFolder);
    return;
  }
  let artists = getArtists();
  if(state.search.trim()){
    const q = state.search.toLowerCase();
    artists = artists.filter(a => a.name.toLowerCase().includes(q));
  }
  if(artists.length === 0){
    content.innerHTML = `<div class="empty"><div class="empty-orb"></div><h3>No matches</h3><p>Try a different search term, or browse your full library.</p></div>`;
    return;
  }
  content.innerHTML = `
    <div class="artist-grid">
      ${artists.map(a => `
        <div class="artist-card" role="button" tabindex="0" data-artist="${escapeHtml(encodeURIComponent(a.name))}">
          <img class="artist-card-photo media-image" data-artist-photo="${escapeHtml(a.name)}" ${artAttrs(a, 256, "high")} alt="${escapeHtml(a.name)}">
          <div class="artist-card-name">${escapeHtml(a.name)}</div>
          <div class="artist-card-count">${a.tracks.length} song${a.tracks.length!==1?"s":""}</div>
          <button type="button" class="artist-card-play" aria-label="Play ${escapeHtml(a.name)}">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6.8v10.4L18.2 12z"/></svg>
            <span>Play</span>
          </button>
        </div>`).join("")}
    </div>`;
  ArtistPhotoEngine.resolveAll(artists);
  $$(".artist-card").forEach(card=>{
    const artist = artists.find(a => encodeURIComponent(a.name) === card.dataset.artist);
    const open = () => openArtist(decodeURIComponent(card.dataset.artist));
    card.addEventListener("click", event => {
      if(event.target.closest(".artist-card-play")) return;
      open();
    });
    card.addEventListener("keydown", event => {
      if(event.target !== card || !["Enter", " "].includes(event.key)) return;
      event.preventDefault();
      open();
    });
    card.querySelector(".artist-card-play")?.addEventListener("click", event => {
      event.stopPropagation();
      if(!artist?.tracks.length) return;
      playTrackFromList(artist.tracks, artist.tracks[0].id);
    });
  });
}

function renderArtistDetailView(){
  const content = $("#content");
  const name = artistNameFromView(state.view);
  const artist = getArtists().find(a => artistKey(a.name) === artistKey(name));
  if(!artist){
    content.innerHTML = `<div class="empty"><div class="empty-orb"></div><h3>Artist not found</h3><p>This artist no longer has songs in your library.</p></div>`;
    return;
  }
  const list = getVisibleTracks();
  const libraryFacts = [
    ["Songs", artist.tracks.length],
    ["Albums", artist.albumCount],
    ["Play time", artist.duration > 0 ? fmtLongDuration(artist.duration) : null],
  ].filter(([, value]) => value !== null && value !== undefined);
  const tracksHtml = list.length === 0
    ? `<div class="empty"><div class="empty-orb"></div><h3>No matches</h3><p>Try a different search term.</p></div>`
    : (state.listMode === "grid"
      ? `<div class="grid">${list.map(t=>cardMarkup(t)).join("")}</div>`
      : `<div class="list">
          <div class="list-head"><div></div><div>Title</div><div>Album</div><div>Time</div><div></div></div>
          ${list.map((t,i)=>trackRowMarkup(t,i)).join("")}
        </div>`);
  content.innerHTML = `
    <div class="artist-page">
      <header class="artist-hero">
        <img class="artist-photo media-image" data-artist-photo="${escapeHtml(artist.name)}" ${artAttrs(artist, 384, "high")} alt="${escapeHtml(artist.name)}">
        <div class="artist-hero-meta">
          <div class="artist-kicker">Artist</div>
          <h1 class="artist-name">${escapeHtml(artist.name)}</h1>
          <div class="artist-sub">${artist.tracks.length} song${artist.tracks.length!==1?"s":""} in your library${artist.albumCount ? ` · ${artist.albumCount} album${artist.albumCount!==1?"s":""}` : ""}</div>
        </div>
      </header>
      <section class="artist-library-info" aria-label="Library information">
        ${libraryFacts.map(([label, value]) => `<div class="artist-library-stat"><span>${label}</span><strong>${escapeHtml(String(value))}</strong></div>`).join("")}
      </section>
      <section class="artist-info" data-artist-profile="${escapeHtml(artist.name)}" aria-busy="true">
        <h2>About</h2>
        <p class="artist-bio" data-artist-bio>Looking up artist details…</p>
        <div class="artist-tags" data-artist-tags hidden></div>
        <nav class="artist-socials" data-artist-socials aria-label="Social media" hidden></nav>
        <p class="artist-source" data-artist-source hidden></p>
        <a class="artist-website" data-artist-website hidden target="_blank" rel="noopener noreferrer">Source page <span aria-hidden="true">↗</span></a>
      </section>
      ${tracksHtml}
    </div>`;
  ArtistPhotoEngine.resolve(artist.name);
  ArtistProfileEngine.resolve(artist.name);
  if(list.length) wireTrackInteractions(list);
}

/* ---------- queue side panel ---------- */
function renderQueuePanel(){
  const el = $("#queueList");
  if(state.queue.length===0){
    el.innerHTML = `<div class="side-empty"><p>Nothing queued yet.</p><button class="btn" id="btnAddQueueEmpty" type="button"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>Add from library</button></div>`;
    $("#btnAddQueueEmpty")?.addEventListener("click", openQueueLibraryPicker);
    return;
  }
  el.innerHTML = state.queue.map((id,i)=>{
    const t = state.tracks.find(x=>x.id===id); if(!t) return "";
    return `
    <div class="q-row ${i===state.queueIndex?'playing':''}" data-i="${i}" draggable="true">
      <span class="q-drag"><svg viewBox="0 0 24 24" fill="currentColor"><circle cx="8" cy="6" r="1.4"/><circle cx="8" cy="12" r="1.4"/><circle cx="8" cy="18" r="1.4"/><circle cx="16" cy="6" r="1.4"/><circle cx="16" cy="12" r="1.4"/><circle cx="16" cy="18" r="1.4"/></svg></span>
      <img class="media-image" ${artAttrs(t, 96)} alt="">
      <div class="q-meta"><div class="q-title">${escapeHtml(t.title)}</div><div class="q-artist">${escapeHtml(t.artist)}</div></div>
      <button class="q-remove" data-act="rm"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
    </div>`;
  }).join("");
  let dragSrcIndex = null;
  el.querySelectorAll(".q-row").forEach(row=>{
    row.addEventListener("click",(e)=>{
      if(e.target.closest("button")) return;
      if(row.dataset.dragged){
        delete row.dataset.dragged;
        return;
      }
      capturePlaybackContext();
      state.queueIndex = +row.dataset.i; playCurrent();
    });
    row.querySelector('[data-act="rm"]').addEventListener("click",(e)=>{
      e.stopPropagation();
      removeQueueSlot(+row.dataset.i);
      renderQueuePanel();
    });
    row.addEventListener("dragstart", e=>{
      dragSrcIndex = +row.dataset.i;
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", String(dragSrcIndex));
      row.classList.add("dragging");
    });
    row.addEventListener("dragend", ()=> row.classList.remove("dragging"));
    row.addEventListener("dragover", e=>{
      if(dragSrcIndex===null) return;
      e.preventDefault(); e.dataTransfer.dropEffect = "move";
      row.classList.add("drag-over");
    });
    row.addEventListener("dragleave", ()=> row.classList.remove("drag-over"));
    row.addEventListener("drop", e=>{
      if(dragSrcIndex===null) return;
      e.preventDefault(); row.classList.remove("drag-over");
      const toIndex = +row.dataset.i;
      if(dragSrcIndex !== toIndex) reorderQueue(dragSrcIndex, toIndex);
      dragSrcIndex = null;
      renderQueuePanel();
    });
    wireTouchQueueDrag(row, ()=>+row.dataset.i, ()=>{
      renderQueuePanel();
    }, {longPress:true});
  });
}

/* ---------- add-from-library picker ---------- */
// Shared modal for queue and playlist "Add from library".
let libraryPickerTarget = { mode: "queue" };

function openQueueLibraryPicker(){
  openLibraryPicker({ mode: "queue" });
}
function openPlaylistLibraryPicker(playlistId){
  openLibraryPicker({ mode: "playlist", playlistId });
}
function openLibraryPicker(target){
  const overlay = $("#queuePicker");
  if(!overlay) return;
  libraryPickerTarget = target || { mode: "queue" };
  const search = $("#queuePickerSearch");
  if(search) search.value = "";
  const title = overlay.querySelector(".queue-picker-head h3");
  if(title){
    if(libraryPickerTarget.mode === "playlist"){
      const pl = state.playlists.find(p=>p.id===libraryPickerTarget.playlistId);
      title.textContent = pl ? `Add to “${pl.name}”` : "Add to playlist";
    } else {
      title.textContent = "Add from library";
    }
  }
  overlay.setAttribute("aria-label", title?.textContent || "Add from library");
  renderLibraryPicker();
  overlay.classList.add("open");
  setTimeout(()=> search?.focus(), 30);
}
function closeQueueLibraryPicker(){
  $("#queuePicker")?.classList.remove("open");
}
function renderQueueLibraryPicker(){
  renderLibraryPicker();
}
function renderLibraryPicker(){
  const listEl = $("#queuePickerList");
  if(!listEl) return;
  const forPlaylist = libraryPickerTarget.mode === "playlist";
  const pl = forPlaylist
    ? state.playlists.find(p=>p.id===libraryPickerTarget.playlistId)
    : null;
  if(state.tracks.length === 0){
    listEl.innerHTML = `<div class="queue-picker-empty">Your library is empty. Add music first, then come back to build a ${forPlaylist ? "playlist" : "queue"}.</div>`;
    return;
  }
  const q = ($("#queuePickerSearch")?.value || "").trim().toLowerCase();
  const tracks = q
    ? state.tracks.filter(t => (t.title+" "+t.artist+" "+t.album).toLowerCase().includes(q))
    : state.tracks;
  if(!tracks.length){
    listEl.innerHTML = `<div class="queue-picker-empty">No matches for that search.</div>`;
    return;
  }
  listEl.innerHTML = tracks.map(t => {
    const inPlaylist = !!(pl && pl.trackIds.includes(t.id));
    return `
    <button type="button" class="qp-row${inPlaylist ? " in-playlist" : ""}" data-id="${escapeHtml(t.id)}" ${inPlaylist ? "aria-disabled=\"true\"" : ""}>
      <img class="media-image" ${artAttrs(t, 160)} alt="">
      <div class="qp-meta">
        <div class="qp-title">${escapeHtml(t.title)}</div>
        <div class="qp-artist">${escapeHtml(t.artist)}</div>
      </div>
      <span class="qp-add" aria-hidden="true">${inPlaylist
        ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 12l5 5L20 7"/></svg>`
        : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>`}</span>
    </button>`;
  }).join("");
  listEl.querySelectorAll(".qp-row").forEach(row=>{
    row.addEventListener("click", ()=>{
      const t = state.tracks.find(x=>x.id===row.dataset.id);
      if(!t) return;
      if(libraryPickerTarget.mode === "playlist"){
        if(row.classList.contains("in-playlist")){
          toast(`Already in this playlist.`);
          return;
        }
        if(addTrackToPlaylist(libraryPickerTarget.playlistId, t)){
          renderLibraryPicker();
        }
      } else {
        addToQueue(t);
      }
    });
  });
}

/* ============================================================
   EVENT WIRING
   ============================================================ */
function on(sel, event, handler){
  const el = typeof sel === "string" ? $(sel) : sel;
  if(!el){ console.warn("Vervfy: missing element", sel); return; }
  el.addEventListener(event, handler);
}
on("#btnImportTop", "click", ()=> $("#fileInput")?.click());
on("#btnImportRail", "click", ()=> $("#fileInput")?.click());
on("#homeProfileAvatar", "click", ()=>{ state.view = "account"; state.search=""; $("#searchInput").value=""; render(); });
on("#fileInput", "change", (e)=>{ importFiles(e.target.files); e.target.value = ""; });
on("#folderInput", "change", (e)=>{ importFiles(e.target.files); e.target.value = ""; });

$$(".rail-btn[data-view]").forEach(btn=>{
  btn.addEventListener("click", ()=>{ state.view = btn.dataset.view; state.search=""; $("#searchInput").value=""; render(); });
});
$$("#viewToggle button").forEach(btn=>{
  btn.addEventListener("click", ()=>{
    state.listMode = btn.dataset.mode;
    $$("#viewToggle button").forEach(b=>b.classList.toggle("active", b===btn));
    saveSettings(); render();
  });
});
on("#searchInput", "input", (e)=>{
  state.search = e.target.value;
  if(state.view === "artists") renderArtistsView();
  else if(state.view.startsWith("artist:")) renderArtistDetailView();
  else renderTrackListView();
  renderTopbar();
});
on("#nowArtist", "click", (e)=>{
  const btn = e.target.closest('[data-action="artist"]');
  if(btn){
    openArtist(decodeURIComponent(btn.dataset.artist || ""));
    return;
  }
  const t = currentTrack();
  if(!t) return;
  const names = artistsOf(t);
  if(names[0]) openArtist(names[0]);
});

on("#btnPlay", "click", togglePlay);
on("#miniPlay", "click", togglePlay);
on("#btnNext", "click", ()=>playNext(false));
on("#miniNext", "click", ()=>playNext(false));
on("#btnPrev", "click", playPrev);
on("#miniPrev", "click", playPrev);
on("#btnShuffle", "click", ()=>{ state.shuffle=!state.shuffle; $("#btnShuffle").classList.toggle("on",state.shuffle); saveSettings(); toast(state.shuffle?"Shuffle on":"Shuffle off"); });
on("#btnRepeat", "click", ()=>{
  state.repeat = state.repeat==="off" ? "all" : state.repeat==="all" ? "one" : "off";
  $("#btnRepeat").classList.toggle("on", state.repeat!=="off");
  $("#btnRepeat").title = "Repeat: "+state.repeat;
  saveSettings(); toast("Repeat: "+state.repeat);
});
on("#nowFav", "click", ()=>{ const t=currentTrack(); if(t) toggleFavorite(t); });
on("#btnOffline", "click", ()=>{
  const t = currentTrack();
  if(t) t.offline ? removeOfflineTrack(t) : downloadTrackOffline(t);
});
on("#mobilePlayerFav", "click", ()=>{ const t=currentTrack(); if(t) toggleFavorite(t); });
function isCompactTouchLayout(){
  const compact = window.matchMedia("(max-width: 900px)");
  const coarse = window.matchMedia("(pointer: coarse)");
  const noHover = window.matchMedia("(hover: none)");
  return compact.matches && (coarse.matches || noHover.matches || navigator.maxTouchPoints > 0);
}

on("#nowbar", "click", (e)=>{
  if(isCompactTouchLayout() && !e.target.closest("button,.seek")){
    $("#mobilePlayer").classList.add("open");
    updateNowPlayingUI();
  }
});
on("#btnMobilePlayerClose", "click", ()=> $("#mobilePlayer").classList.remove("open"));
on("#btnMobilePlayerMenu", "click", (e)=>{
  const t = currentTrack();
  if(t) openNowPlayingMenu(e.currentTarget, t);
});
on("#mobilePlay", "click", togglePlay);
on("#mobileNext", "click", ()=>playNext(false));
on("#mobilePrev", "click", playPrev);
on("#mobileShuffle", "click", ()=> $("#btnShuffle").click());
on("#mobileRepeat", "click", ()=> $("#btnRepeat").click());
on("#mobileLyrics", "click", ()=>{ $("#mobilePlayer").classList.remove("open"); openLyrics(); });
on("#mobileLyricsOpen", "click", (e)=>{ e.stopPropagation(); $("#mobilePlayer").classList.remove("open"); openLyrics(); });
on("#mobileLyricsCard", "click", ()=>{ $("#mobilePlayer").classList.remove("open"); openLyrics(); });
on("#mobileLyricsCard", "keydown", (e)=>{
  if(e.key === "Enter" || e.key === " "){
    e.preventDefault();
    $("#mobilePlayer").classList.remove("open");
    openLyrics();
  }
});
on("#mobileQueue", "click", ()=>{ $("#mobilePlayer").classList.remove("open"); $("#sidePanel").classList.add("open"); });

function seekPercent(clientX, seekEl){
  const rect = seekEl.getBoundingClientRect();
  if(!rect.width) return 0;
  return Math.min(1, Math.max(0, (clientX-rect.left)/rect.width));
}
function previewSeek(pct){
  if(!audioEl.duration) return;
  const time = pct * audioEl.duration;
  const percent = `${pct * 100}%`;
  $("#seekFill").style.width = percent;
  $("#seekThumb").style.left = percent;
  $("#miniSeekFill").style.width = percent;
  $("#miniSeekThumb").style.left = percent;
  $("#mobileSeekFill").style.width = percent;
  $("#mobileSeekThumb").style.left = percent;
  $("#timeCur").textContent = fmtTime(time);
  $("#miniCur").textContent = fmtTime(time);
  $("#mobileTimeCur").textContent = fmtTime(time);
}
function commitSeek(pct){
  if(!audioEl.duration) return;
  audioEl.currentTime = Math.min(audioEl.duration, Math.max(0, pct * audioEl.duration));
  updateSeekUI();
}
function bindSeek(seekEl){
  if(!seekEl) return;
  let dragging = false;
  let wasPlaying = false;
  let pendingPercent = 0;
  const updateFromPointer = e => {
    pendingPercent = seekPercent(e.clientX, seekEl);
    previewSeek(pendingPercent);
  };
  seekEl.addEventListener("pointerdown", e=>{
    if(e.button !== undefined && e.button !== 0) return;
    dragging = true;
    wasPlaying = !audioEl.paused;
    if(wasPlaying) audioEl.pause();
    seekEl.setPointerCapture?.(e.pointerId);
    updateFromPointer(e);
    e.preventDefault();
  });
  seekEl.addEventListener("pointermove", e=>{
    if(dragging)     updateFromPointer(e);
  });
  const stopDragging = e=>{
    if(!dragging) return;
    updateFromPointer(e);
    commitSeek(pendingPercent);
    dragging = false;
    if(seekEl.hasPointerCapture?.(e.pointerId)) seekEl.releasePointerCapture(e.pointerId);
    if(wasPlaying) audioEl.play().catch(()=>{});
  };
  seekEl.addEventListener("pointerup", stopDragging);
  seekEl.addEventListener("pointercancel", e=>{
    if(!dragging) return;
    dragging = false;
    updateSeekUI();
    if(seekEl.hasPointerCapture?.(e.pointerId)) seekEl.releasePointerCapture(e.pointerId);
    if(wasPlaying) audioEl.play().catch(()=>{});
  });
  seekEl.addEventListener("keydown", e=>{
    if(!audioEl.duration) return;
    const step = e.shiftKey ? 10 : 5;
    if(e.key === "ArrowRight" || e.key === "ArrowUp"){
      audioEl.currentTime = Math.min(audioEl.duration, audioEl.currentTime + step);
      e.preventDefault();
    } else if(e.key === "ArrowLeft" || e.key === "ArrowDown"){
      audioEl.currentTime = Math.max(0, audioEl.currentTime - step);
      e.preventDefault();
    } else if(e.key === "Home"){
      audioEl.currentTime = 0;
      e.preventDefault();
    } else if(e.key === "End"){
      audioEl.currentTime = audioEl.duration;
      e.preventDefault();
    }
  });
}
[$("#seek"), $("#miniSeek"), $("#mobileSeek")].forEach(bindSeek);
on("#volTrack", "click", (e)=>{
  const rect = e.currentTarget.getBoundingClientRect();
  setVolume((e.clientX-rect.left)/rect.width);
});
on("#btnMute", "click", ()=>{ state.muted=!state.muted; audioEl.volume = state.muted?0:state.volume; updateVolUI(); saveSettings(); });

on("#btnLyrics", "click", ()=> $("#lyricsOverlay").classList.contains("open") ? closeLyrics() : openLyrics());
on("#lyricsClose", "click", closeLyrics);
on("#lyricsOverlay", "click", (e)=>{ if(e.target.id==="lyricsOverlay") closeLyrics(); });

on("#btnViz", "click", openViz);
on("#vizClose", "click", closeViz);
on("#vizOverlay", "click",(e)=>{ if(e.target.id==="vizOverlay") closeViz(); });

on("#btnQueueToggle", "click", ()=> $("#sidePanel").classList.toggle("open"));
on("#btnCloseQueue", "click", ()=> $("#sidePanel").classList.remove("open"));
on("#btnAddQueueSide", "click", openQueueLibraryPicker);
on("#btnCloseQueuePicker", "click", closeQueueLibraryPicker);
on("#queuePicker", "click", (e)=>{ if(e.target.id==="queuePicker") closeQueueLibraryPicker(); });
on("#queuePickerSearch", "input", ()=> renderQueueLibraryPicker());

on("#btnLogout", "click", () => logoutAndRedirect());
  
on("#btnMini", "click", ()=> enterMiniMode());
on("#btnMiniExit", "click", ()=> exitMiniMode());
function clampMiniPosition(mp, left, top){
  const margin = 8;
  const rect = mp.getBoundingClientRect();
  return {
    left: Math.max(margin, Math.min(window.innerWidth - rect.width - margin, left)),
    top: Math.max(margin, Math.min(window.innerHeight - rect.height - margin, top)),
  };
}
function enterMiniMode(){
  document.body.classList.add("mini-mode");
  const mp = $("#miniPlayer");
  const saved = (() => {
    try { return JSON.parse(localStorage.getItem("vervfy:mini-position") || "null"); } catch(_) { return null; }
  })();
  mp.style.right = "auto"; mp.style.bottom = "auto";
  const position = saved && Number.isFinite(saved.left) && Number.isFinite(saved.top)
    ? clampMiniPosition(mp, saved.left, saved.top)
    : clampMiniPosition(mp, window.innerWidth - mp.offsetWidth - 24, window.innerHeight - mp.offsetHeight - 24);
  mp.style.left = `${position.left}px`;
  mp.style.top = `${position.top}px`;
}
function exitMiniMode(){ document.body.classList.remove("mini-mode"); }

// mini player drag
(function(){
  const mp = $("#miniPlayer"), handle = $("#miniDrag");
  if(!mp || !handle) return;
  let dragging=false, offX=0, offY=0;
  handle.addEventListener("pointerdown",(e)=>{
    dragging=true; const r=mp.getBoundingClientRect();
    offX = e.clientX-r.left; offY = e.clientY-r.top;
    handle.setPointerCapture(e.pointerId);
  });
  handle.addEventListener("pointermove",(e)=>{
    if(!dragging) return;
    const position = clampMiniPosition(mp, e.clientX-offX, e.clientY-offY);
    mp.style.left = position.left+"px";
    mp.style.top = position.top+"px";
    mp.style.right="auto"; mp.style.bottom="auto";
  });
  const stopDragging = ()=>{
    if(!dragging) return;
    dragging=false;
    try {
      const rect = mp.getBoundingClientRect();
      localStorage.setItem("vervfy:mini-position", JSON.stringify({left:rect.left, top:rect.top}));
    } catch(_) {}
  };
  handle.addEventListener("pointerup", stopDragging);
  handle.addEventListener("pointercancel", stopDragging);
  window.addEventListener("resize", ()=>{
    if(document.body.classList.contains("mini-mode")){
      const rect = mp.getBoundingClientRect();
      const position = clampMiniPosition(mp, rect.left, rect.top);
      mp.style.left = position.left+"px";
      mp.style.top = position.top+"px";
    }
    if($("#vizOverlay")?.classList.contains("open")) resizeVizCanvas();
  });
})();

on("#btnShortcuts", "click", ()=> $("#shortcutsOverlay").classList.add("open"));
on("#shortcutsOverlay", "click",(e)=>{ if(e.target.id==="shortcutsOverlay") $("#shortcutsOverlay").classList.remove("open"); });

/* keyboard shortcuts */
document.addEventListener("keydown",(e)=>{
  if(e.key === "Escape" && $("#photoEditorOverlay")?.classList.contains("open")){
    ProfilePhotoEditor.close();
    return;
  }
  const tag = (e.target.tagName||"").toLowerCase();
  if(tag==="input" || tag==="textarea"){
    if(e.key==="Escape"){
      if($("#queuePicker")?.classList.contains("open")) closeQueueLibraryPicker();
      else e.target.blur();
    }
    return;
  }
  if(e.key==="/"){ e.preventDefault(); $("#searchInput")?.focus(); return; }
  if(e.key==="?"){ $("#shortcutsOverlay")?.classList.toggle("open"); return; }
  if(e.key==="Escape"){
    if($("#queuePicker")?.classList.contains("open")){ closeQueueLibraryPicker(); return; }
    $("#mobilePlayer")?.classList.remove("open");
    $("#shortcutsOverlay")?.classList.remove("open");
    $("#sidePanel")?.classList.remove("open");
    $("#dropOverlay")?.classList.remove("show");
    dragCounter = 0;
    closeViz();
    closeLyrics();
    closeMenus();
    return;
  }
  switch(e.key){
    case " ": e.preventDefault(); togglePlay(); break;
    case "ArrowRight": if(e.shiftKey) playNext(false); else if(audioEl.duration) audioEl.currentTime = Math.min(audioEl.duration, audioEl.currentTime+5); break;
    case "ArrowLeft": if(e.shiftKey) playPrev(); else audioEl.currentTime = Math.max(0, audioEl.currentTime-5); break;
    case "ArrowUp": e.preventDefault(); setVolume(state.volume+0.05); break;
    case "ArrowDown": e.preventDefault(); setVolume(state.volume-0.05); break;
    case "m": case "M": $("#btnMute")?.click(); break;
    case "f": case "F": { const t=currentTrack(); if(t) toggleFavorite(t); break; }
    case "n": case "N": document.body.classList.contains("mini-mode") ? exitMiniMode() : enterMiniMode(); break;
    case "l": case "L": $("#lyricsOverlay")?.classList.contains("open") ? closeLyrics() : openLyrics(); break;
    case "v": case "V": $("#vizOverlay")?.classList.contains("open") ? closeViz() : openViz(); break;
  }
});

/* drag & drop import anywhere on window */
// Only real OS file drags carry a "Files" type; a drag started on a queue
// row (for reordering) carries "text/plain" instead. Without this check the
// import overlay would pop up — and a failed "No audio files found" toast
// would fire — every time someone dragged a track to reorder the queue.
let dragCounter = 0;
function isFileDrag(e){ return e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).includes("Files"); }
function hideDropOverlay(){ dragCounter=0; $("#dropOverlay")?.classList.remove("show"); }
window.addEventListener("dragenter", (e)=>{ if(!isFileDrag(e)) return; e.preventDefault(); dragCounter++; $("#dropOverlay")?.classList.add("show"); });
window.addEventListener("dragover", (e)=>{ if(isFileDrag(e)) e.preventDefault(); });
window.addEventListener("dragleave", (e)=>{ if(!isFileDrag(e)) return; dragCounter--; if(dragCounter<=0) hideDropOverlay(); });
window.addEventListener("drop", (e)=>{
  if(!isFileDrag(e)) return;
  e.preventDefault(); hideDropOverlay();
  const files = [];
  if(e.dataTransfer.items){
    for(const item of e.dataTransfer.items) if(item.kind==="file") files.push(item.getAsFile());
  } else Array.from(e.dataTransfer.files).forEach(f=>files.push(f));
  importFiles(files);
});
// Clicking the overlay dismisses a stuck drag state that would otherwise
// block every button under it.
on("#dropOverlay", "click", hideDropOverlay);

/* pause visualizer rAF when tab hidden to save CPU */
document.addEventListener("visibilitychange", ()=>{
  if(document.hidden){ if(rafViz){ cancelAnimationFrame(rafViz); rafViz=null; } }
  else {
    if($("#vizOverlay")?.classList.contains("open") && !rafViz) drawViz();
    syncServerLibrary();
  }
});

/* ============================================================
   INIT
   ============================================================ */
let initializationStarted = false;

async function init(){
  if(initializationStarted) return;
  initializationStarted = true;
  try{
    render();
    const label = $("#btnImportTopLabel"); if(label) label.textContent = "Add music";
    $("#btnImportRail")?.setAttribute("data-tip", "Add music");
    await loadPersisted();
    audioEl.volume = state.muted ? 0 : state.volume;
    $$("#viewToggle button").forEach(b=>b.classList.toggle("active", b.dataset.mode===state.listMode));
    state.shuffle && $("#btnShuffle")?.classList.add("on");
    if(state.repeat!=="off") $("#btnRepeat")?.classList.add("on");
    updateVolUI();
    ensureCsrfToken();
    render();
    fetchAccountInfo();
    loadServerLibrary().then(count => {
      render();
      if(count) toast(`Loaded ${count} saved track${count!==1?"s":""}.`);
    });
    window.setInterval(syncServerLibrary, 15000);
  }catch(e){
    console.error("Vervfy init failed", e);
    toast("Something went wrong loading the library.");
    try{ render(); }catch(_){}
  }
}
init();

})();