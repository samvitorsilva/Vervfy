"""Bound request bytes before FastAPI's multipart/JSON parsing."""
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestSizeLimitMiddleware:
    def __init__(self, app: ASGIApp, *, audio_bytes: int, image_bytes: int, overhead: int):
        self.app = app
        self.audio_bytes = audio_bytes
        self.image_bytes = image_bytes
        self.overhead = overhead

    def limit_for(self, path: str) -> int:
        if path == "/api/library/upload":
            return self.audio_bytes + self.overhead
        if path in {"/api/account/photo", "/api/artists/photo"} or (
            path.startswith("/api/tracks/") and path.endswith("/cover")
        ):
            return self.image_bytes + self.overhead
        if path in {"/login", "/register", "/logout"}:
            return 16 * 1024
        if path.startswith("/api/account/passkeys/"):
            if path.endswith("/complete"):
                return 64 * 1024
            return 16 * 1024
        if path in {
            "/api/account/password",
            "/api/account/email",
            "/api/account/logout-all",
        }:
            return 16 * 1024
        return 16 * 1024 * 1024

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}:
            await self.app(scope, receive, send)
            return
        limit = self.limit_for(scope["path"])
        declared = Headers(scope=scope).get("content-length")
        if declared is not None:
            if not declared.isascii() or not declared.isdecimal():
                await self.reject(scope, receive, send, 400, "Invalid request size")
                return
            normalized = declared.lstrip("0") or "0"
            if len(normalized) > 12 or int(normalized) > limit:
                await self.reject(scope, receive, send, 413, "Request exceeds the configured size limit")
                return
        received = 0

        async def bounded_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # FastAPI preserves HTTPException during body parsing;
                    # Starlette closes multipart temporary files on exceptions.
                    raise HTTPException(413, "Request exceeds the configured size limit")
            return message

        await self.app(scope, bounded_receive, send)

    @staticmethod
    async def reject(scope: Scope, receive: Receive, send: Send, status: int, detail: str) -> None:
        response = JSONResponse({"detail": detail}, status_code=status, headers={
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        })
        await response(scope, receive, send)
