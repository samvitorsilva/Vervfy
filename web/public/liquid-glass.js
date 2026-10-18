(() => {
  "use strict";

  // ── Tuning (matches liquid-glass-player.html reference) ─────────────────
  const BEZEL_WIDTH = 22;       // rim thickness in the displacement map
  const CORNER_RADIUS = 32;     // fallback when element radius can't be read
  const DISPLACEMENT_SCALE = 70;
  const BLUR = 3;               // Chromium refraction blur
  const FROST_BLUR = 18;        // Safari / Firefox frost
  const SATURATION_FROST = 1.8;
  const SATURATION_REFRACT = 1.7;
  const TINT_ALPHA = 0.1;       // frost fill
  const TINT_ALPHA_REFRACT = 0.04;
  const MAX_ACTIVE_SURFACES = 4;

  document.documentElement.style.setProperty("--glass-blur", `${BLUR}px`);
  document.documentElement.style.setProperty("--glass-frost-blur", `${FROST_BLUR}px`);
  document.documentElement.style.setProperty("--glass-saturation", String(SATURATION_FROST));
  document.documentElement.style.setProperty("--glass-saturation-refract", String(SATURATION_REFRACT));
  document.documentElement.style.setProperty("--glass-tint-alpha", String(TINT_ALPHA));
  document.documentElement.style.setProperty("--glass-tint-alpha-refract", String(TINT_ALPHA_REFRACT));

  const backdrop = document.getElementById("artworkBackdrop");
  const backdropImage = document.getElementById("artworkBackdropImage");
  const artwork = document.getElementById("nowArt");
  const defs = document.querySelector(".glass-filters defs");
  const reducedTransparency = matchMedia("(prefers-reduced-transparency: reduce)");
  // SVG filters inside backdrop-filter only work in Chromium.
  const canRefract = Boolean(window.chrome);

  const filterStates = new WeakMap();
  const trackedSurfaces = new Set();
  let nextFilterId = 0;
  let syncFrame = 0;
  const surfacePriorities = [
    [".queue-picker-card, .photo-editor-card, .shortcuts-card, .sleep-timer-card, .lyrics-player, .lyrics-side", 0],
    [".mobile-player-info", 1],
    [".nowbar", 2],
    [".rail", 3],
    [".side-panel", 4],
  ];

  function updateArtwork() {
    if (!backdrop || !backdropImage || !artwork) return;
    const source = artwork.dataset.artwork || "";
    if (!source) {
      backdrop.classList.remove("has-art");
      backdropImage.removeAttribute("src");
      return;
    }
    if (backdropImage.src === new URL(source, document.baseURI).href) return;
    backdrop.classList.remove("has-art");
    backdropImage.src = source;
  }

  backdropImage?.addEventListener("load", () => {
    backdrop?.classList.toggle("has-art", backdropImage.naturalWidth > 0);
  });
  backdropImage?.addEventListener("error", () => backdrop?.classList.remove("has-art"));

  function svgElement(name, attributes = {}) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    return element;
  }

  function createFilter(element) {
    if (!defs) return null;
    const existing = filterStates.get(element);
    if (existing) return existing;

    const id = nextFilterId === 0 ? "lg" : `lg-${nextFilterId}`;
    nextFilterId += 1;
    const filter = svgElement("filter", {
      id,
      x: "0",
      y: "0",
      width: "100%",
      height: "100%",
      filterUnits: "objectBoundingBox",
      "color-interpolation-filters": "sRGB",
    });
    const map = svgElement("feImage", {
      x: "0",
      y: "0",
      width: "100%",
      height: "100%",
      result: "map",
      preserveAspectRatio: "none",
    });
    // Red = x shift, Blue = y shift (same as the reference demo).
    const displace = svgElement("feDisplacementMap", {
      in: "SourceGraphic",
      in2: "map",
      scale: String(DISPLACEMENT_SCALE),
      xChannelSelector: "R",
      yChannelSelector: "B",
    });
    filter.append(map, displace);
    defs.append(filter);

    const state = {
      filter,
      map,
      width: 0,
      height: 0,
      radius: 0,
      observer: null,
      observing: false,
    };
    filterStates.set(element, state);
    return state;
  }

  function getRadius(element, width, height) {
    const style = getComputedStyle(element);
    const parsed = Math.max(
      parseFloat(style.borderTopLeftRadius) || 0,
      parseFloat(style.borderTopRightRadius) || 0,
      parseFloat(style.borderBottomRightRadius) || 0,
      parseFloat(style.borderBottomLeftRadius) || 0,
    );
    const radius = parsed || CORNER_RADIUS;
    return Math.min(radius, width / 2, height / 2);
  }

  // Build a rounded lens map: red and blue encode signed x/y offsets around
  // neutral grey, with a smooth edge falloff and an undistorted centre.
  function mapSVG(w, h, radius, rim) {
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) return "";

    const image = context.createImageData(w, h);
    const pixels = image.data;
    const r = Math.min(radius, w / 2, h / 2);
    const cx = w / 2;
    const cy = h / 2;
    const halfW = w / 2;
    const halfH = h / 2;
    const edgeWidth = Math.max(1, Math.min(rim, halfW, halfH));
    const strength = 112;

    for (let y = 0; y < h; y += 1) {
      for (let x = 0; x < w; x += 1) {
        const qx = Math.abs(x + 0.5 - cx) - (halfW - r);
        const qy = Math.abs(y + 0.5 - cy) - (halfH - r);
        const outsideX = Math.max(qx, 0);
        const outsideY = Math.max(qy, 0);
        const signedDistance =
          Math.hypot(outsideX, outsideY) + Math.min(Math.max(qx, qy), 0) - r;
        const edgeDistance = Math.max(0, -signedDistance);
        const t = Math.max(0, Math.min(1, 1 - edgeDistance / edgeWidth));
        const falloff = t * t * (3 - 2 * t);

        let normalX = 0;
        let normalY = 0;
        if (outsideX > 0 || outsideY > 0) {
          const length = Math.hypot(outsideX, outsideY) || 1;
          normalX = Math.sign(x + 0.5 - cx) * outsideX / length;
          normalY = Math.sign(y + 0.5 - cy) * outsideY / length;
        } else if (qx > qy) {
          normalX = Math.sign(x + 0.5 - cx);
        } else {
          normalY = Math.sign(y + 0.5 - cy);
        }

        const offset = (y * w + x) * 4;
        pixels[offset] = Math.round(128 + normalX * strength * falloff);
        pixels[offset + 1] = 128;
        pixels[offset + 2] = Math.round(128 + normalY * strength * falloff);
        pixels[offset + 3] = 255;
      }
    }

    context.putImageData(image, 0, 0);
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><image width="${w}" height="${h}" href="${canvas.toDataURL("image/png")}" preserveAspectRatio="none"/></svg>`;
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  }

  function updateSurface(element) {
    if (!canRefract || reducedTransparency.matches) {
      element.classList.remove("refract");
      element.style.removeProperty("--glass-filter-url");
      return;
    }

    const state = createFilter(element);
    if (!state) return;

    const rect = element.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return;

    const width = Math.round(rect.width);
    const height = Math.round(rect.height);
    const radius = getRadius(element, width, height);

    if (
      state.width !== width ||
      state.height !== height ||
      state.radius !== radius ||
      !state.map.hasAttribute("href")
    ) {
      const href = mapSVG(width, height, radius, BEZEL_WIDTH);
      if (!href) return;
      state.map.setAttribute("width", String(width));
      state.map.setAttribute("height", String(height));
      state.map.setAttribute("href", href);
      state.width = width;
      state.height = height;
      state.radius = radius;
    }

    element.style.setProperty("--glass-filter-url", `url(#${state.filter.id})`);
    element.classList.add("refract");
  }

  function isVisible(element) {
    if (element.classList.contains("hidden") || !element.getClientRects().length) {
      return false;
    }
    for (let node = element; node && node !== document.body; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.display === "none" || style.visibility === "hidden") return false;
    }
    const rect = element.getBoundingClientRect();
    return (
      rect.bottom > 0 &&
      rect.right > 0 &&
      rect.top < innerHeight &&
      rect.left < innerWidth
    );
  }

  function deactivateSurface(element) {
    element.classList.remove("glass", "refract", "glass-pressed");
    element.style.removeProperty("--glass-filter-url");
    const state = filterStates.get(element);
    if (state?.observing) {
      state.observer.disconnect();
      state.observing = false;
    }
  }

  function queueSync() {
    if (syncFrame) return;
    syncFrame = requestAnimationFrame(() => {
      syncFrame = 0;
      syncSurfaces();
    });
  }

  function syncSurfaces() {
    for (const [selector, priority] of surfacePriorities) {
      for (const element of document.querySelectorAll(selector)) {
        if (!element.hasAttribute("data-glass-priority")) {
          element.setAttribute("data-glass-priority", String(priority));
        }
      }
    }

    const surfaces = [...document.querySelectorAll("[data-glass-priority]")];
    const surfaceSet = new Set(surfaces);

    for (const element of trackedSurfaces) {
      if (surfaceSet.has(element)) continue;
      deactivateSurface(element);
      const state = filterStates.get(element);
      state?.filter.remove();
      filterStates.delete(element);
      trackedSurfaces.delete(element);
    }

    const active = surfaces
      .filter(isVisible)
      .sort(
        (a, b) => Number(a.dataset.glassPriority) - Number(b.dataset.glassPriority),
      )
      .slice(0, MAX_ACTIVE_SURFACES);
    const activeSet = new Set(active);

    for (const element of surfaces) {
      trackedSurfaces.add(element);
      if (!activeSet.has(element)) {
        deactivateSurface(element);
        continue;
      }

      element.classList.add("glass");

      if (reducedTransparency.matches || !canRefract) {
        element.classList.remove("refract");
        element.style.removeProperty("--glass-filter-url");
        const state = filterStates.get(element);
        if (state?.observing) {
          state.observer.disconnect();
          state.observing = false;
        }
        continue;
      }

      const state = createFilter(element);
      if (!state) continue;
      if (!state.observer) {
        state.observer = new ResizeObserver(() => updateSurface(element));
      }
      if (!state.observing) {
        state.observer.observe(element);
        state.observing = true;
      }
      updateSurface(element);
    }
  }

  const observer = new MutationObserver((records) => {
    let needsSync = false;
    for (const record of records) {
      if (
        record.target === artwork &&
        (record.attributeName === "data-artwork" || record.attributeName === "src")
      ) {
        updateArtwork();
        continue;
      }
      if (record.attributeName === "src") continue;
      if (record.type === "childList") {
        needsSync = true;
        continue;
      }
      if (
        record.attributeName === "class" &&
        record.target.matches?.("[data-glass-priority]")
      ) {
        const normalize = (value) =>
          (value || "")
            .split(/\s+/)
            .filter(
              (name) =>
                name && !["glass", "refract"].includes(name),
            )
            .sort()
            .join(" ");
        if (normalize(record.oldValue) === normalize(record.target.className)) {
          continue;
        }
      }
      if (record.type === "attributes") needsSync = true;
    }
    if (needsSync) queueSync();
  });

  observer.observe(document.body, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["class", "hidden", "data-artwork", "src"],
    attributeOldValue: true,
  });

  reducedTransparency.addEventListener?.("change", syncSurfaces);
  window.addEventListener("resize", queueSync, { passive: true });

  updateArtwork();
  syncSurfaces();
})();
