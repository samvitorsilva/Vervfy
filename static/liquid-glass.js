(() => {
  "use strict";

  const backdrop = document.getElementById("artworkBackdrop");
  const backdropImage = document.getElementById("artworkBackdropImage");
  const nowArt = document.getElementById("nowArt");
  const defs = document.querySelector(".glass-filters defs");
  const baseFilter = document.getElementById("lg");
  const glassSurfaces = [...document.querySelectorAll("[data-glass-priority]")];
  const filterStates = new WeakMap();
  let nextFilterId = 0;

  function updateArtworkBackdrop() {
    if (!backdrop || !backdropImage || !nowArt) return;
    const source = nowArt.getAttribute("src") || "";
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
  updateArtworkBackdrop();

  function createFilterState(element) {
    if (!defs || !baseFilter || filterStates.has(element)) return filterStates.get(element);
    const filter = baseFilter.cloneNode(true);
    const id = `lg-${++nextFilterId}`;
    filter.id = id;
    const image = filter.querySelector("feImage");
    if (!image) return null;
    image.id = `${id}-map`;
    defs.appendChild(filter);
    const state = { filter, image, observer: null, width: 0, height: 0 };
    filterStates.set(element, state);
    return state;
  }

  function createDisplacementMap(width, height) {
    const size = 128;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) return null;

    const image = context.createImageData(size, size);
    const smoothstep = (start, end, value) => {
      const t = Math.max(0, Math.min(1, (value - start) / (end - start)));
      return t * t * (3 - 2 * t);
    };
    for (let y = 0; y < size; y += 1) {
      const ny = (y / (size - 1)) * 2 - 1;
      for (let x = 0; x < size; x += 1) {
        const nx = (x / (size - 1)) * 2 - 1;
        const edge = smoothstep(0.58, 0.98, Math.max(Math.abs(nx), Math.abs(ny)));
        const offset = (y * size + x) * 4;
        image.data[offset] = Math.round(128 + nx * edge * 76);
        image.data[offset + 1] = 128;
        image.data[offset + 2] = Math.round(128 + ny * edge * 76);
        image.data[offset + 3] = 255;
      }
    }
    context.putImageData(image, 0, 0);

    const png = canvas.toDataURL("image/png");
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><image width="${width}" height="${height}" preserveAspectRatio="none" href="${png}"/></svg>`;
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  }

  function updateDisplacementMap(element) {
    const state = createFilterState(element);
    if (!state) return;
    const { width, height } = element.getBoundingClientRect();
    if (width < 1 || height < 1) return;
    const mapWidth = Math.ceil(width);
    const mapHeight = Math.ceil(height);
    if (state.width !== mapWidth || state.height !== mapHeight || !state.image.hasAttribute("href")) {
      const source = createDisplacementMap(mapWidth, mapHeight);
      if (!source) return;
      state.image.setAttribute("href", source);
      state.width = mapWidth;
      state.height = mapHeight;
    }
    element.style.setProperty("--glass-filter-url", `url(#${state.filter.id})`);
    element.classList.add("refract");
  }

  function isVisible(element) {
    if (element.classList.contains("hidden")) return false;
    if (!element.getClientRects().length) return false;
    for (let node = element; node && node !== document.body; node = node.parentElement) {
      if (getComputedStyle(node).display === "none") return false;
    }
    return true;
  }

  function syncGlassSurfaces() {
    const active = glassSurfaces
      .filter(isVisible)
      .sort((a, b) => Number(a.dataset.glassPriority) - Number(b.dataset.glassPriority))
      .slice(0, 4);
    const activeSet = new Set(active);

    for (const element of glassSurfaces) {
      if (!activeSet.has(element)) {
        element.classList.remove("glass", "refract");
        element.style.removeProperty("--glass-filter-url");
        const state = filterStates.get(element);
        state?.observer?.unobserve(element);
        continue;
      }
      element.classList.add("glass");
      if (!window.chrome) continue;
      const state = createFilterState(element);
      if (!state) continue;
      if (!state.observer) {
        state.observer = new ResizeObserver(() => updateDisplacementMap(element));
        state.observer.observe(element);
      }
      updateDisplacementMap(element);
    }
  }

  syncGlassSurfaces();
  const visibilityTargets = new Set([document.body, nowArt].filter(Boolean));
  for (const element of glassSurfaces) {
    for (let node = element; node && node !== document.body; node = node.parentElement) {
      visibilityTargets.add(node);
    }
  }
  const observer = new MutationObserver((records) => {
    let shouldSync = false;
    for (const record of records) {
      if (record.target === nowArt && record.attributeName === "src") {
        updateArtworkBackdrop();
      }
      if (
        record.target.matches?.("[data-glass-priority]") &&
        record.attributeName === "class"
      ) {
        const normalize = (value) => (value || "")
          .split(/\s+/)
          .filter((name) => name && name !== "glass" && name !== "refract")
          .sort()
          .join(" ");
        if (normalize(record.oldValue) === normalize(record.target.className)) continue;
      }
      shouldSync = true;
    }
    if (shouldSync) syncGlassSurfaces();
  });
  for (const target of visibilityTargets) {
    if (target === nowArt) {
      observer.observe(target, { attributes: true, attributeFilter: ["src"] });
    } else {
      observer.observe(target, {
        attributes: true,
        attributeFilter: ["class", "hidden"],
        attributeOldValue: true,
      });
    }
  }
})();
