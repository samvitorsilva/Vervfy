from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from sqlalchemy.engine import make_url

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import db


class DatabaseConnectionSecurityTests(unittest.TestCase):
    def test_production_postgres_requires_tls_when_sslmode_is_missing(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VERVFY_ENVIRONMENT": "production",
                "DATABASE_URL": "postgresql://app:secret@db.example.test/app",
            },
        ):
            parsed_url = make_url(db.database_url())

        self.assertEqual(parsed_url.query["sslmode"], "require")
        self.assertEqual(parsed_url.password, "secret")

    def test_production_postgres_preserves_stronger_sslmode(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VERVFY_ENVIRONMENT": "production",
                "DATABASE_URL": (
                    "postgresql://app:secret@db.example.test/app?sslmode=verify-full"
                ),
            },
        ):
            parsed_url = make_url(db.database_url())

        self.assertEqual(parsed_url.query["sslmode"], "verify-full")

    def test_non_production_database_url_is_not_rewritten(self) -> None:
        original_url = "postgresql://app:secret@db.example.test/app"
        with patch.dict(
            os.environ,
            {
                "VERVFY_ENVIRONMENT": "development",
                "DATABASE_URL": original_url,
            },
        ):
            normalized_url = db.database_url()

        self.assertEqual(normalized_url, db.normalize_database_url(original_url))
        self.assertNotIn("sslmode", make_url(normalized_url).query)
