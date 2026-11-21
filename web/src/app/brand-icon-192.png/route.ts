import { brandIcon } from "@/lib/brand-icon";
export const runtime = "edge";
export function GET() { return brandIcon(192); }
