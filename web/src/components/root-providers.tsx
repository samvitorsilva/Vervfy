"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { usePlayerStore } from "@/store/player-store";
import LiquidGlass from "@/components/liquid-glass";
import ServiceWorkerRegistration from "@/components/service-worker-registration";
import { LanguageProvider, type Language } from "@/lib/i18n";

export default function RootProviders({
  children,
  initialLanguage,
}: {
  children: ReactNode;
  initialLanguage: Language;
}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const setAudioElement = usePlayerStore((store) => store.setAudioElement);

  useEffect(() => {
    const audioElement = audioRef.current;
    if (!audioElement) return;
    setAudioElement(audioElement);
    return () => setAudioElement(null);
  }, [setAudioElement]);

  return (
    <LanguageProvider initialLanguage={initialLanguage}>
      <ServiceWorkerRegistration />
      <LiquidGlass />
      {children}
      <audio ref={audioRef} crossOrigin="anonymous" preload="metadata" hidden />
    </LanguageProvider>
  );
}
