"""Staging audio leases must never alter immutable storage or deletion barriers."""
import json
import os
from unittest.mock import patch

import httpx
import pytest

import audio_security
import audio_store


def test_production_canary_requires_an_explicit_matching_account():
    with patch.dict(os.environ, {"VERVFY_AUDIO_SECURITY_HARDENING": "canary", "VERVFY_AUDIO_SECURITY_CANARY_USERS": "synthetic-only", "VERVFY_ENVIRONMENT": "production"}):
        assert audio_security.enabled("synthetic-only")
        assert not audio_security.enabled("existing-user")
        assert not audio_security.enabled()
    with patch.dict(os.environ, {"VERVFY_AUDIO_SECURITY_HARDENING": "0"}):
        assert not audio_security.enabled("synthetic-only")
    with patch.dict(os.environ, {"VERVFY_AUDIO_SECURITY_HARDENING": "invalid"}):
        with pytest.raises(RuntimeError):
            audio_security.enabled()


def test_upload_policy_is_restrictive_only_for_trial_audio():
    with patch.dict(os.environ, {"VERVFY_AUDIO_SECURITY_HARDENING": "1", "VERVFY_ENVIRONMENT": "test"}):
        for kind in ("audio", "staged-audio"):
            assert audio_security.upload_cache_control(f"v2/namespace/user/{kind}/object.wav") == audio_security.AUDIO_CACHE_CONTROL
        assert audio_security.upload_cache_control("v2/namespace/user/track-cover/object.jpg") == "max-age=31536000"


def test_canary_does_not_change_other_accounts_upload_cache_policy():
    with patch.dict(os.environ, {"VERVFY_ENVIRONMENT": "production", "VERVFY_AUDIO_SECURITY_HARDENING": "canary", "VERVFY_AUDIO_SECURITY_CANARY_USERS": "synthetic-only"}):
        assert "no-store" in audio_security.upload_cache_control("v2/namespace/synthetic-only/audio/new.wav")
        assert audio_security.upload_cache_control("v2/namespace/existing-user/audio/new.wav") == "max-age=31536000"


def test_900_second_leases_refresh_before_minimum_validity_without_writes():
    clock = [100.0]
    calls = []

    def handler(request):
        assert request.method == "POST"
        assert "/object/sign/" in request.url.path
        assert json.loads(request.content) == {"expiresIn": 900}
        calls.append(True)
        return httpx.Response(200, json={"signedURL": f"/object/sign/songs/user/track.wav?token={len(calls)}"})

    with httpx.Client(base_url="https://project.supabase.co/storage/v1", transport=httpx.MockTransport(handler)) as client, \
         patch.object(audio_store, "_client", return_value=client), \
         patch.object(audio_store.time, "monotonic", side_effect=lambda: clock[0]), \
         patch.object(audio_store.time, "time", return_value=1000), \
         patch.dict(os.environ, {"SUPABASE_URL": "https://project.supabase.co", "SUPABASE_BUCKET": "songs"}):
        audio_store._signed_url_cache.clear()
        try:
            first = audio_store.create_audio_lease("user/track.wav")
            assert first["expiresAt"] - first["serverTime"] == 900
            clock[0] += 650
            second = audio_store.create_audio_lease("user/track.wav")
            assert second["url"] == first["url"]
            assert second["expiresAt"] - second["serverTime"] == 250
            clock[0] += 11
            third = audio_store.create_audio_lease("user/track.wav")
            assert third["url"] != first["url"]
            assert third["expiresAt"] - third["serverTime"] == 900
            assert len(calls) == 2
        finally:
            audio_store._signed_url_cache.clear()


def test_signing_does_not_bypass_managed_namespace_validation():
    with patch.object(audio_store, "_guard_managed_read", side_effect=audio_store.StorageError("namespace denied")), \
         patch.object(audio_store, "_client") as client:
        with pytest.raises(audio_store.StorageError, match="namespace denied"):
            audio_store.create_audio_lease("v2/invalid/user/audio/object.wav")
        client.assert_not_called()


def test_all_physical_deletion_entry_points_remain_disabled():
    for function, args in ((audio_store.delete, ("path",)), (audio_store.delete_quietly, ("path",)), (audio_store.delete_many, (["path"],))):
        with pytest.raises(audio_store.StorageError, match="hard-disabled"):
            function(*args)
