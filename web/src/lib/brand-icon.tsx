import { ImageResponse } from "next/og";

/** Rasterize the same official V mark used by /gemini-svg.svg for PWA and Apple icons. */
export function brandIcon(size: number): ImageResponse {
  return new ImageResponse(
    (
      <svg width={size} height={size} viewBox="0 0 329 333" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="mint" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#08E7BE" />
            <stop offset="1" stopColor="#02DFB6" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="329" height="333" fill="#08E7BE" />
        <rect x="1" y="1" width="327" height="331" rx="91" fill="url(#mint)" />
        <path fill="#030B12" d="M46 81 L119 239 L128 251 L142 260 L170 262 L194 246 L203 227 L230 133 L254 144 L274 171 L279 166 L284 149 L279 115 L262 94 L240 82 L221 80 L218 83 L185 192 L160 184 L119 96 L111 87 L96 80 Z" />
      </svg>
    ),
    { width: size, height: size, headers: { "Cache-Control": "public, max-age=3600" } },
  );
}
