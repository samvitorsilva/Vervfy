"use client";

import { useEffect } from "react";

export default function ServiceWorkerRegistration() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    if (process.env.NODE_ENV === "development") {
      const cleanDevelopmentCaches = async () => {
        const registration = await navigator.serviceWorker.getRegistration();
        if (registration) await registration.unregister();

        const cacheNames = await caches.keys();
        await Promise.all(
          cacheNames
            .filter((name) => name.startsWith("vervfy-next-shell-"))
            .map((name) => caches.delete(name)),
        );

        if (navigator.serviceWorker.controller) window.location.reload();
      };
      void cleanDevelopmentCaches().catch((error: unknown) => {
        console.error("Could not disable the Vervfy service worker in development.", error);
      });
      return;
    }

    navigator.serviceWorker
      .register("/sw.js", { scope: "/", updateViaCache: "none" })
      .catch((error: unknown) => {
        console.error("Could not register the Vervfy offline shell.", error);
      });
  }, []);

  return null;
}
