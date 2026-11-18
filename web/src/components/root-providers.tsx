"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { usePlayerStore } from "@/store/player-store";
import { installPlaybackController } from "@/lib/playback-controller";
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
    const disposePlaybackController = installPlaybackController(audioElement);
    return () => {
      disposePlaybackController();
      setAudioElement(null);
    };
  }, [setAudioElement]);

  useEffect(() => {
    let openTimer: ReturnType<typeof setTimeout> | undefined;
    let resetTimer: ReturnType<typeof setTimeout> | undefined;
    const onPointerOver = (event: PointerEvent) => {
      if (!(event.target instanceof Element) || !event.target.closest(".rail-btn[data-tip]")) return;
      if (event.relatedTarget instanceof Element && event.target.closest(".rail-btn[data-tip]") === event.relatedTarget.closest(".rail-btn[data-tip]")) return;
      clearTimeout(resetTimer);
      openTimer = setTimeout(() => document.documentElement.classList.add("tooltip-warm"), 300);
    };
    const onPointerOut = (event: PointerEvent) => {
      if (!(event.target instanceof Element) || !event.target.closest(".rail-btn[data-tip]")) return;
      if (event.relatedTarget instanceof Element && event.target.closest(".rail-btn[data-tip]") === event.relatedTarget.closest(".rail-btn[data-tip]")) return;
      clearTimeout(openTimer);
      resetTimer = setTimeout(() => document.documentElement.classList.remove("tooltip-warm"), 700);
    };
    document.addEventListener("pointerover", onPointerOver);
    document.addEventListener("pointerout", onPointerOut);
    return () => {
      clearTimeout(openTimer);
      clearTimeout(resetTimer);
      document.removeEventListener("pointerover", onPointerOver);
      document.removeEventListener("pointerout", onPointerOut);
      document.documentElement.classList.remove("tooltip-warm");
    };
  }, []);

  return (
    <LanguageProvider initialLanguage={initialLanguage}>
      <ServiceWorkerRegistration />
      <LiquidGlass />
      {children}
      <audio ref={audioRef} crossOrigin="anonymous" preload="metadata" playsInline hidden />
    </LanguageProvider>
  );
}
