import ast
from pathlib import Path
from unittest.mock import patch
import pytest
from staging_session_guard import validate

BASE = dict(VERVFY_ENVIRONMENT="staging", GOOGLE_OAUTH_ENABLED="0", VERVFY_ASYNC_UPLOADS="0")

def test_valid():
    validate(BASE)

@pytest.mark.parametrize("key,value", [("REDIS_URL", ""), ("REDIS_URL", "redis://production"), ("GOOGLE_OAUTH_ENABLED", "1"), ("VERVFY_ASYNC_UPLOADS", "1"), ("WEB_CONCURRENCY", "2")])
def test_reject(key, value):
    with pytest.raises(RuntimeError):
        validate(dict(BASE, **{key: value}))

def test_memory_sessions_without_database_import():
    # Execute the actual standalone store classes without importing DB modules.
    import secrets, threading, time
    tree = ast.parse((Path(__file__).parents[1] / "auth.py").read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in {"SessionStore", "RequestThrottle"}]
    ns = dict(secrets=secrets, threading=threading, time=time)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "auth.py", "exec"), ns)
    store = ns["SessionStore"]()
    token = store.create("alice")
    assert store.is_valid(token, "alice")
    assert not store.is_valid(token, "bob")
    assert not store.is_valid("forged", "alice")
    assert not ns["SessionStore"]().is_valid(token, "alice")
    store.revoke(token)
    assert not store.is_valid(token, "alice")
    token = store.create("alice")
    store.revoke_user("alice")
    assert not store.is_valid(token, "alice")
    token = store.create("alice")
    with patch.object(time, "time", return_value=time.time() + store.TTL_SECONDS + 1):
        assert not store.is_valid(token, "alice")
    limiter = ns["RequestThrottle"]()
    assert limiter.allow("login", 1, 60)
    assert not limiter.allow("login", 1, 60)
