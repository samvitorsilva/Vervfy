"""OAuth-only startup must not load the optional passkey stack."""
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("flag", [None, "0", "1", "invalid"])
def test_optional_passkey_import_boundary(flag):
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": "/tmp",
        "DATABASE_URL": "sqlite://",
        "VERVFY_SECRET_KEY": "isolated-startup-test",
        "VERVFY_ENVIRONMENT": "development",
        "GOOGLE_OAUTH_ENABLED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if flag is not None:
        env["VERVFY_WEBAUTHN_ENABLED"] = flag
    result = subprocess.run(
        [sys.executable, "-c", '''
import importlib.abc
import sys
class DenyOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {
            'account_transactions', 'passkeys', 'passkey_schema',
            'passkey_enrollment', 'webauthn',
        }:
            raise ImportError('optional stack deliberately absent')
sys.meta_path.insert(0, DenyOptional())
import server
assert server.passkey_config is None
assert server.google_oauth_config is None
assert any(route.path == '/login' for route in server.app.routes)
'''],
        cwd=Path(__file__).parents[1], env=env, capture_output=True,
        text=True, timeout=15,
    )
    if flag in (None, "0"):
        assert result.returncode == 0, result.stderr
    elif flag == "1":
        assert result.returncode != 0
        assert "optional stack deliberately absent" in result.stderr
    else:
        assert result.returncode != 0
        assert "Invalid WebAuthn enable flag" in result.stderr
