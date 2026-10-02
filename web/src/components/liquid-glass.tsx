"use client";

import { useEffect } from "react";

export default function LiquidGlass() {
  useEffect(() => {
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
