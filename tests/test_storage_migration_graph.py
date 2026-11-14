import unittest
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


ROOT = Path(__file__).resolve().parents[1]


class StorageMigrationGraphTests(unittest.TestCase):
    def test_web_authn_and_storage_histories_join_at_one_forward_only_head(self):
        scripts = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
        self.assertEqual(scripts.get_heads(), ["0033_cleanup_activation_gate"])

        merge = scripts.get_revision("0032_merge_storage_webauthn")
        self.assertEqual(
            set(merge.down_revision),
            {"0028_webauthn_enrollment", "0031_operator_revocation"},
        )
        self.assertEqual(
            scripts.get_revision("0027_webauthn_foundation").down_revision,
            "0026_application_runtime_grants",
        )
        self.assertEqual(
            scripts.get_revision("0027_storage_lifecycle").down_revision,
            "0026_application_runtime_grants",
        )
