"use client";

import { useEffect } from "react";

export type GlassMaterial = "clear" | "default" | "tinted";

export const GLASS_MATERIAL_KEY = "vervfy.glass-material";
export const ACCENT_COLOR_KEY = "vervfy.accent-color";

export function applyAppearance(
  material: GlassMaterial = "default",
  accentColor?: string,
) {
  const root = document.documentElement;
  root.dataset.glass = material;
  if (accentColor) root.style.setProperty("--accent", accentColor);
  else root.style.removeProperty("--accent");
}

export default function LiquidGlass() {
  useEffect(() => {
    const storedMaterial = localStorage.getItem(GLASS_MATERIAL_KEY);
    const material: GlassMaterial = storedMaterial === "clear" || storedMaterial === "tinted"
      ? storedMaterial
      : "default";
    applyAppearance(material, localStorage.getItem(ACCENT_COLOR_KEY) ?? undefined);

    const existing = document.querySelector<HTMLScriptElement>(
      'script[data-vervfy-liquid-glass="true"]',
    );
    if (existing) return;

    const script = document.createElement("script");
    script.src = "/liquid-glass.js";
    script.async = true;
    script.dataset.vervfyLiquidGlass = "true";
    script.onerror = () => {
      console.error("Could not load the Vervfy liquid-glass effect.");
    };
    document.head.append(script);
  }, []);

  return (
    <>
      {/* Per-surface feImage + feDisplacementMap filters are created by liquid-glass.js */}
      <svg className="glass-filters" width="0" height="0" aria-hidden="true" focusable="false">
        <defs />
      </svg>
      <div className="artwork-backdrop" id="artworkBackdrop" aria-hidden="true">
        <img id="artworkBackdropImage" alt="" />
      </div>
    </>
  );
}
