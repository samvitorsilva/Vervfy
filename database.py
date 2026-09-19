"""Backward-compatible database module alias for older deploy configs.

The app has standardized on ``db.py`` as the canonical module, but older
Render/startup configs and migration scripts may still import
``from database import Base, engine``. Re-export the current symbols here so
both import paths keep working.
"""

from __future__ import annotations

from db import (
    Base,
    DATABASE_URL,
    Favorite,
    Playlist,
    PlaylistTrack,
    SessionLocal,
    TrackRecord,
    User,
    engine,
)

__all__ = [
    "Base",
    "DATABASE_URL",
    "Favorite",
    "Playlist",
    "PlaylistTrack",
    "SessionLocal",
    "TrackRecord",
    "User",
    "engine",
]
