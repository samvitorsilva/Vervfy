(() => {
  "use strict";

  const BEZEL_WIDTH = 24;
  const REFRACTIVE_INDEX = 1.5;
  const MAX_DISPLACEMENT = 12;
  const CHROMATIC_SPREAD = 0.06;
  const BLUR = 3;
  const SATURATION = 1.65;
  const TINT_ALPHA = 0.06;
  const SPECULAR_POWER = 3.2;

  document.documentElement.style.setProperty("--glass-blur", `${BLUR}px`);
  document.documentElement.style.setProperty("--glass-saturation", SATURATION);
  document.documentElement.style.setProperty("--glass-tint-alpha", TINT_ALPHA);

  const backdrop = document.getElementById("artworkBackdrop");
  const backdropImage = document.getElementById("artworkBackdropImage");
  const nowArt = document.getElementById("nowArt");
  const defs = document.querySelector(".glass-filters defs");
  const glassSurfaces = [...document.querySelectorAll("[data-glass-priority]")];
  const filterStates = new WeakMap();
  const reducedTransparency = matchMedia("(prefers-reduced-transparency: reduce)");
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const supportsSvgBackdropFilter =
    CSS.supports("backdrop-filter", "blur(2px) url(#liquid-glass-test) saturate(1.5)");
  let nextFilterId = 0;
  let lastPointerSurface = null;

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

  function svgElement(name, attributes = {}) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    return element;
  }

  function append(parent, name, attributes = {}) {
    const element = svgElement(name, attributes);
    parent.appendChild(element);
    return element;
  }

  function createFilter(element) {
    if (!defs || filterStates.has(element)) return filterStates.get(element);
    const id = `liquid-glass-${++nextFilterId}`;
    const filter = append(defs, "filter", {
      id,
      x: "-10%",
      y: "-10%",
      width: "120%",
      height: "120%",
      "color-interpolation-filters": "sRGB",
    });
    const maps = [];
    const channelResults = [];
    const channels = [
      { matrix: "1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0" },
      { matrix: "0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 1 0" },
      { matrix: "0 0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 0 0 1 0" },
    ];

    channels.forEach((channel, index) => {
      const map = append(filter, "feImage", {
        x: "0%",
        y: "0%",
        width: "100%",
        height: "100%",
        preserveAspectRatio: "none",
        result: `map${index}`,
      });
      maps.push(map);
      const displaced = append(filter, "feDisplacementMap", {
        in: "SourceGraphic",
        in2: `map${index}`,
        scale: String(2 * MAX_DISPLACEMENT * (1 + CHROMATIC_SPREAD * index)),
        xChannelSelector: "R",
        yChannelSelector: "G",
        result: `displaced${index}`,
      });
      const isolated = append(filter, "feColorMatrix", {
        in: displaced.getAttribute("result"),
        type: "matrix",
        values: channel.matrix,
        result: `channel${index}`,
      });
      channelResults.push(isolated.getAttribute("result"));
    });

    const redGreen = append(filter, "feBlend", {
      in: channelResults[0],
      in2: channelResults[1],
      mode: "screen",
      result: "redGreen",
    });
    append(filter, "feBlend", {
      in: redGreen.getAttribute("result"),
      in2: channelResults[2],
      mode: "screen",
    });

    const state = {
      filter,
      maps,
      mapWidth: 0,
      mapHeight: 0,
      highlightFrame: 0,
      lightX: -Math.SQRT1_2,
      lightY: -Math.SQRT1_2,
      highlightCanvas: document.createElement("canvas"),
      highlightContext: null,
      renderedLightX: -Math.SQRT1_2,
      renderedLightY: -Math.SQRT1_2,
      renderedPressed: false,
      observer: null,
      observing: false,
    };
    state.highlightContext = state.highlightCanvas.getContext("2d", { willReadFrequently: true });
    filterStates.set(element, state);
    return state;
  }

  function signedRoundedRectDistance(x, y, width, height, radius) {
    const halfWidth = width / 2;
    const halfHeight = height / 2;
    const qx = Math.abs(x) - (halfWidth - radius);
    const qy = Math.abs(y) - (halfHeight - radius);
    return Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) +
      Math.min(Math.max(qx, qy), 0) - radius;
  }

  function getRadius(element, width, height) {
    const style = getComputedStyle(element);
    const radius = Math.max(
      parseFloat(style.borderTopLeftRadius) || 0,
      parseFloat(style.borderTopRightRadius) || 0,
      parseFloat(style.borderBottomRightRadius) || 0,
      parseFloat(style.borderBottomLeftRadius) || 0,
    );
    return Math.min(radius, width / 2, height / 2);
  }

  function surfaceNormal(x, y, width, height, radius) {
    const step = 0.5;
    const dx = signedRoundedRectDistance(x + step, y, width, height, radius) -
      signedRoundedRectDistance(x - step, y, width, height, radius);
    const dy = signedRoundedRectDistance(x, y + step, width, height, radius) -
      signedRoundedRectDistance(x, y - step, width, height, radius);
    const length = Math.hypot(dx, dy) || 1;
    return { x: dx / length, y: dy / length };
  }

  function lightDirection(state) {
    const length = Math.hypot(state.lightX, state.lightY);
    if (length < 1) return { x: -Math.SQRT1_2, y: -Math.SQRT1_2 };
    return { x: state.lightX / length, y: state.lightY / length };
  }

  function getRefractionOffset(distance) {
    const t = Math.max(0, Math.min(0.999, distance / BEZEL_WIDTH));
    const remaining = 1 - t;
    const profileBase = Math.max(0, 1 - remaining ** 4);
    const profileHeight = profileBase ** 0.25;
    const slope = Math.min(8, remaining ** 3 / Math.max(1e-6, profileBase) ** 0.75);
    const incidentAngle = Math.atan(slope);
    const refractedSine = Math.sin(incidentAngle) / REFRACTIVE_INDEX;
    const refractedTangent = refractedSine / Math.sqrt(Math.max(1e-6, 1 - refractedSine ** 2));
    return Math.min(MAX_DISPLACEMENT, BEZEL_WIDTH * profileHeight * (slope - refractedTangent));
  }

  function makeDisplacementMap(width, height, radius) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) return null;
    const image = context.createImageData(width, height);
    const data = image.data;

    for (let py = 0; py < height; py += 1) {
      const y = py + 0.5;
      const centeredY = y - height / 2;
      for (let px = 0; px < width; px += 1) {
        const x = px + 0.5;
        const centeredX = x - width / 2;
        const distance = -signedRoundedRectDistance(centeredX, centeredY, width, height, radius);
        const offset = (py * width + px) * 4;
        let dx = 0;
        let dy = 0;

        if (distance >= 0 && distance < BEZEL_WIDTH) {
          const normal = surfaceNormal(centeredX, centeredY, width, height, radius);
          const lateralOffset = getRefractionOffset(distance);
          dx = -normal.x * lateralOffset;
          dy = -normal.y * lateralOffset;
        }

        data[offset] = Math.max(0, Math.min(255, Math.round(128 + dx / MAX_DISPLACEMENT * 127)));
        data[offset + 1] = Math.max(0, Math.min(255, Math.round(128 + dy / MAX_DISPLACEMENT * 127)));
        data[offset + 2] = 128;
        data[offset + 3] = 255;
      }
    }

    context.putImageData(image, 0, 0);
    return canvas.toDataURL("image/png");
  }

  function makeSpecularImage(element, state, width, height, radius) {
    const context = state.highlightContext;
    if (!context) return;
    const renderWidth = Math.max(1, Math.min(256, Math.ceil(width)));
    const renderHeight = Math.max(1, Math.min(256, Math.ceil(height * renderWidth / width)));
    const canvas = state.highlightCanvas;
    canvas.width = renderWidth;
    canvas.height = renderHeight;
    const image = context.createImageData(renderWidth, renderHeight);
    const data = image.data;
    const { x: lightX, y: lightY } = lightDirection(state);
    const pressedBoost = element.classList.contains("glass-pressed") ? 1.35 : 1;

    for (let py = 0; py < renderHeight; py += 1) {
      const centeredY = (py + 0.5) * height / renderHeight - height / 2;
      for (let px = 0; px < renderWidth; px += 1) {
        const centeredX = (px + 0.5) * width / renderWidth - width / 2;
        const distance = -signedRoundedRectDistance(centeredX, centeredY, width, height, radius);
        const offset = (py * renderWidth + px) * 4;
        let alpha = 0;

        if (distance >= 0 && distance < BEZEL_WIDTH) {
          const normal = surfaceNormal(centeredX, centeredY, width, height, radius);
          const rimX = -normal.x;
          const rimY = -normal.y;
          const front = Math.max(0, rimX * lightX + rimY * lightY);
          const back = Math.max(0, -(rimX * lightX + rimY * lightY));
          alpha = Math.min(0.7, (front ** SPECULAR_POWER + back ** SPECULAR_POWER * 0.2) * 0.48 * pressedBoost);
        }

        data[offset] = 255;
        data[offset + 1] = 255;
        data[offset + 2] = 255;
        data[offset + 3] = Math.round(alpha * 255);
      }
    }

    context.putImageData(image, 0, 0);
    element.style.setProperty("--glass-specular-image", `url("${canvas.toDataURL("image/png")}")`);
    element.style.setProperty("--glass-light-x", lightX.toFixed(3));
    element.style.setProperty("--glass-light-y", lightY.toFixed(3));
    state.renderedLightX = lightX;
    state.renderedLightY = lightY;
    state.renderedPressed = element.classList.contains("glass-pressed");
  }

  function updateGlassSurface(element) {
    const state = createFilter(element);
    if (!state) return;
    const rect = element.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return;
    const width = Math.ceil(rect.width);
    const height = Math.ceil(rect.height);
    const radius = getRadius(element, rect.width, rect.height);

    if (
      supportsSvgBackdropFilter &&
      !reducedTransparency.matches &&
      (state.mapWidth !== width || state.mapHeight !== height || !state.maps[0].hasAttribute("href"))
    ) {
      const source = makeDisplacementMap(width, height, radius);
      if (!source) return;
      for (const image of state.maps) image.setAttribute("href", source);
      state.mapWidth = width;
      state.mapHeight = height;
    }

    makeSpecularImage(element, state, rect.width, rect.height, radius);
    if (supportsSvgBackdropFilter && !reducedTransparency.matches) {
      element.style.setProperty("--glass-filter-url", `url(#${state.filter.id})`);
      element.classList.add("refract");
    } else {
      element.style.removeProperty("--glass-filter-url");
      element.classList.remove("refract");
    }
  }

  function scheduleHighlight(element) {
    const state = filterStates.get(element);
    if (!state || state.highlightFrame) return;
    const { x: lightX, y: lightY } = lightDirection(state);
    const movedEnough = Math.hypot(lightX - state.renderedLightX, lightY - state.renderedLightY) > 0.035;
    const pressedChanged = state.renderedPressed !== element.classList.contains("glass-pressed");
    if (!movedEnough && !pressedChanged) return;
    state.highlightFrame = requestAnimationFrame(() => {
      state.highlightFrame = 0;
      const rect = element.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      makeSpecularImage(element, state, rect.width, rect.height, getRadius(element, rect.width, rect.height));
    });
  }

  function isVisible(element) {
    if (element.classList.contains("hidden") || !element.getClientRects().length) return false;
    for (let node = element; node && node !== document.body; node = node.parentElement) {
      if (getComputedStyle(node).display === "none" || getComputedStyle(node).visibility === "hidden") return false;
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
        element.classList.remove("glass", "refract", "glass-pressed");
        element.style.removeProperty("--glass-filter-url");
        element.style.removeProperty("--glass-specular-image");
        element.style.removeProperty("--glass-light-x");
        element.style.removeProperty("--glass-light-y");
        const state = filterStates.get(element);
        if (state?.observing) {
          state.observer.unobserve(element);
          state.observing = false;
        }
        continue;
      }

      element.classList.add("glass");
      if (reducedTransparency.matches) {
        element.classList.remove("refract");
        element.style.removeProperty("--glass-filter-url");
        const state = filterStates.get(element);
        if (state?.observing) {
          state.observer.unobserve(element);
          state.observing = false;
        }
        continue;
      }
      const state = createFilter(element);
      if (!state) continue;
      if (!state.observer) {
        state.observer = new ResizeObserver(() => updateGlassSurface(element));
      }
      if (!state.observing) {
        state.observer.observe(element);
        state.observing = true;
      }
      updateGlassSurface(element);
    }
  }

  function findGlassSurface(target) {
    const surface = target instanceof Element ? target.closest("[data-glass-priority].glass") : null;
    return surface && glassSurfaces.includes(surface) ? surface : null;
  }

  document.addEventListener("pointermove", (event) => {
    const surface = findGlassSurface(event.target);
    if (surface !== lastPointerSurface) {
      if (lastPointerSurface) {
        const oldState = filterStates.get(lastPointerSurface);
        if (oldState) {
          oldState.lightX = -Math.SQRT1_2;
          oldState.lightY = -Math.SQRT1_2;
          scheduleHighlight(lastPointerSurface);
        }
      }
      lastPointerSurface = surface;
    }
    if (!surface) return;
    const state = filterStates.get(surface);
    if (!state) return;
    const rect = surface.getBoundingClientRect();
    state.lightX = event.clientX - (rect.left + rect.width / 2);
    state.lightY = event.clientY - (rect.top + rect.height / 2);
    scheduleHighlight(surface);
  }, { passive: true });

  document.addEventListener("pointerdown", (event) => {
    const surface = findGlassSurface(event.target);
    if (!surface) return;
    surface.classList.add("glass-pressed");
    scheduleHighlight(surface);
  }, { passive: true });

  const releasePressed = () => {
    document.querySelectorAll(".glass-pressed").forEach((element) => {
      element.classList.remove("glass-pressed");
      scheduleHighlight(element);
    });
  };
  document.addEventListener("pointerup", releasePressed, { passive: true });
  document.addEventListener("pointercancel", releasePressed, { passive: true });

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
      if (record.target === nowArt && record.attributeName === "src") updateArtworkBackdrop();
      if (
        record.target.matches?.("[data-glass-priority]") &&
        record.attributeName === "class"
      ) {
        const normalize = (value) => (value || "")
          .split(/\s+/)
          .filter((name) => name && name !== "glass" && name !== "refract" && name !== "glass-pressed")
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

  reducedTransparency.addEventListener?.("change", syncGlassSurfaces);
  reducedMotion.addEventListener?.("change", releasePressed);
})();
