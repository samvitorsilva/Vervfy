"use client";

import { useState } from "react";

export default function ResilientImage({
  src,
  fallbackSrc,
  className,
}: {
  src: string;
  fallbackSrc: string;
  className?: string;
}) {
  const [imageSrc, setImageSrc] = useState(src);
  const [retried, setRetried] = useState(false);
  const [loaded, setLoaded] = useState(false);

  return (
    <img
      className={`${className ?? ""} media-image${loaded ? " media-image-ready" : ""}`}
      src={imageSrc}
      alt=""
      loading="lazy"
      decoding="async"
      onLoad={() => setLoaded(true)}
      onError={() => {
        if (imageSrc === fallbackSrc) {
          setLoaded(true);
          return;
        }
        if (!retried) {
          setRetried(true);
          try {
            const retryUrl = new URL(src, window.location.href);
            retryUrl.searchParams.set("vervfy-retry", String(Date.now()));
            setImageSrc(retryUrl.href);
          } catch {
            setImageSrc(fallbackSrc);
          }
          return;
        }
        setImageSrc(fallbackSrc);
      }}
    />
  );
}
