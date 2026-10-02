"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { usePlayerStore } from "@/store/player-store";
import LiquidGlass from "@/components/liquid-glass";
import ServiceWorkerRegistration from "@/components/service-worker-registration";

export default function RootProviders({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const setAudioElement = usePlayerStore((store) => store.setAudioElement);

  useEffect(() => {
    const audioElement = audioRef.current;
    if (!audioElement) return;
    setAudioElement(audioElement);
    return () => setAudioElement(null);
  }, [setAudioElement]);

  return (
    <>
      <ServiceWorkerRegistration />
      <LiquidGlass />
      {children}
      <audio ref={audioRef} preload="metadata" hidden />
    </>
  );
}
