import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";

export const alt = "Vervfy — your personal music library";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function SocialImage() {
  const icon = await readFile(join(process.cwd(), "public/icon-192.png"));
  return new ImageResponse(
    <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", width: "100%", height: "100%", padding: 90, background: "#0c0e14", color: "#f2f3f7" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
        {/* ImageResponse renders this existing brand asset to PNG. */}
        <img src={`data:image/png;base64,${icon.toString("base64")}`} width={112} height={112} alt="" />
        <span style={{ fontSize: 96, fontWeight: 700 }}>Vervfy</span>
      </div>
      <div style={{ display: "flex", marginTop: 44, fontSize: 42, color: "#54e8d4" }}>Your personal music library.</div>
      <div style={{ display: "flex", marginTop: 18, fontSize: 28, color: "#c0c5d1" }}>Upload, organize, and listen to your music.</div>
    </div>,
    size,
  );
}
