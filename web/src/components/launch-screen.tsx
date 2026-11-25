"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import "./launch-screen.css";

/** Shown once per standalone app launch, never during ordinary page navigation. */
export default function LaunchScreen() {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const standalone = window.matchMedia("(display-mode: standalone)").matches ||
      (navigator as Navigator & { standalone?: boolean }).standalone === true;
    const compact = window.matchMedia("(max-width: 1024px)").matches;
    if (!standalone || !compact) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const start = window.setTimeout(() => setVisible(true), 0);
    const end = window.setTimeout(() => setVisible(false), 1050);
    return () => { window.clearTimeout(start); window.clearTimeout(end); };
  }, []);
  if (!visible) return null;
  return (
    <div className="vervfy-launch" aria-hidden="true">
      <div className="vervfy-launch-brand">
        <Image src="/gemini-svg.svg" alt="" width={84} height={84} priority />
        <span>Vervfy</span>
      </div>
      <svg className="vervfy-launch-waves" viewBox="0 0 1000 340" preserveAspectRatio="none" aria-hidden="true">
        <defs><linearGradient id="launchWave" x1="0" y1="0" x2="1" y2="1"><stop stopColor="var(--accent)" stopOpacity=".02"/><stop offset=".7" stopColor="var(--accent)" stopOpacity=".27"/><stop offset="1" stopColor="var(--accent)" stopOpacity=".06"/></linearGradient></defs>
        <path d="M0 120 C210 125 265 260 465 178 S800 0 1000 25 L1000 340 L0 340Z" fill="url(#launchWave)"/>
        <path d="M0 120 C210 125 265 260 465 178 S800 0 1000 25" fill="none" stroke="var(--accent)" strokeOpacity=".65" strokeWidth="1.5"/>
        <path d="M0 230 C280 315 360 340 580 260 S850 180 1000 200" fill="none" stroke="var(--accent)" strokeOpacity=".32" strokeWidth="1.5"/>
      </svg>
    </div>
  );
}
