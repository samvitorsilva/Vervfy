"""Local Playwright fixture: real API/auth/SQLite, synthetic storage, no providers.

Run only with: .venv/bin/python tests/readiness_backend.py
Never deploy this fixture. It does not load project environment files.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import uvicorn


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="vervfy-readiness-") as directory:
        for key in ("REDIS_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "AURALIS_HTTPS_ONLY"):
            os.environ.pop(key, None)
        os.environ.update({
            "DATABASE_URL": f"sqlite:///{directory}/audit.sqlite",
            "VERVFY_ENVIRONMENT": "development",
            "ENVIRONMENT": "development",
            "VERVFY_HTTPS_ONLY": "0",
            "VERVFY_COOKIE_SAME_SITE": "lax",
            "VERVFY_SECRET_KEY": "synthetic-local-audit-session-secret",
            "VERVFY_ASYNC_UPLOADS": "0",
        })
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import server
        from db import Base, engine

        def startup():
            Base.metadata.create_all(engine)

        server.startup = startup
        server.schedule_cover_resolution = lambda *args, **kwargs: None
        server.audio_store.enabled = lambda: False
        server.audio_store.upload = lambda *args, **kwargs: None
        server.audio_store.delete = lambda *args, **kwargs: None
        server.audio_store.delete_many = lambda *args, **kwargs: None
        server.audio_store.create_signed_url = lambda *args, **kwargs: "https://storage.example.test/synthetic-audio"
        uvicorn.run(server.app, host="127.0.0.1", port=8101, access_log=False)


if __name__ == "__main__":
    main()
