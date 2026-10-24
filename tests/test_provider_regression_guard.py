from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git",
    ".next",
    ".pytest_cache",
    ".venv",
    "venv",
    "__pycache__",
    "alembic",
    "docs",
    "node_modules",
    "tests",
    "test-results",
}
SOURCE_SUFFIXES = {
    ".css",
    ".env",
    ".example",
    ".js",
    ".md",
    ".mjs",
    ".py",
    ".svg",
    ".ts",
    ".tsx",
    ".yml",
    ".yaml",
}
ALLOWED_EXTERNAL_HOSTS = {
    "ajvitanza.com",
    "archive.org",
    "coverartarchive.org",
    "creativecommons.org",
    "en.wikipedia.org",
    "eslint.org",
    "feross.org",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "github.com",
    "jairproducoes.com.br",
    "kaimalachi.com",
    "linktr.ee",
    "localhost",
    "lrclib.net",
    "musicbrainz.org",
    "nextjs.org",
    "obros.eu",
    "opencollective.org",
    "opencollective.com",
    "patreon.com",
    "registry.npmjs.org",
    "r2.theaudiodb.com",
    "tidelift.com",
    "theaudiodb.com",
    "vercel.com",
    "vervfy-app.onrender.com",
    "www.josephobrienmusic.com",
    "www.mielsanmarcos.org",
    "www.stringsandheart.com",
    "www.tatemcrae.com",
    "www.theaudiodb.com",
    "www.viclucas.com",
    "www.w3.org",
    "www.wassupgio.com",
    "www.wikipedia.org",
    "www.youtube.com",
    "commons.wikimedia.org",
    "upload.wikimedia.org",
    "wikipedia.org",
    "127.0.0.1",
    "your-public-app.example.com",
}
URL_HOST = re.compile(r"https?://([A-Za-z0-9._-]+)", re.IGNORECASE)
FORBIDDEN_CATALOG_HOSTS = (
    "deezer.com",
    "dzcdn.net",
    "itunes.apple.com",
    "mzstatic.com",
    "api.spotify.com",
    "spotify.com",
    "discogs.com",
    "last.fm",
    "allmusic.com",
    "tidal.com",
    "qobuz.com",
    "music.apple.com",
)


def source_files():
    for path in ROOT.rglob("*"):
        if (
            not path.is_file()
            or path.suffix.lower() not in SOURCE_SUFFIXES
            or path.name == Path(__file__).name
            or any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
        ):
            continue
        yield path


class ProviderRegressionGuardTests(unittest.TestCase):
    def test_no_disallowed_catalog_hosts_or_unreviewed_external_hosts(self) -> None:
        violations: list[str] = []
        for path in source_files():
            content = path.read_text(encoding="utf-8", errors="ignore")
            relative_path = path.relative_to(ROOT)
            for host in FORBIDDEN_CATALOG_HOSTS:
                if host in content.lower():
                    violations.append(f"{relative_path}: forbidden provider host {host}")
            for raw_host in URL_HOST.findall(content):
                host = raw_host.lower().rstrip(".")
                if not host:
                    continue
                if host in ALLOWED_EXTERNAL_HOSTS or host.endswith(".supabase.co"):
                    continue
                violations.append(f"{relative_path}: unreviewed external host {host}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
