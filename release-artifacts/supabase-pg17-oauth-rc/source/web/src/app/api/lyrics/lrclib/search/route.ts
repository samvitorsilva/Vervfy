import { forwardLrclibRequest } from "@/lib/lrclib-proxy";

export function GET(request: Request) {
  return forwardLrclibRequest(request, "search");
}
