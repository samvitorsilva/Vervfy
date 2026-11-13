"""Google OAuth foundation tests; all provider traffic is locally mocked."""

import asyncio
import base64
import hashlib
import json
import os
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx2
import redis
from fastapi.testclient import TestClient
from joserfc import jwk, jwt
from sqlalchemy import create_engine
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

import google_oauth
import server
from auth import hash_password


class MemoryRedis:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.values = {}
        self.lock = threading.Lock()

    def set(self, key, value, *, ex, nx):
        with self.lock:
            current = self.values.get(key)
            if current and current[1] > self.clock() and nx:
                return None
            self.values[key] = (value, self.clock() + ex)
            return True

    def eval(self, _script, key_count, key, *arguments):
        self.assert_one_key(key_count)
        with self.lock:
            value = self.values.get(key)
            if value is None or value[1] <= self.clock():
                self.values.pop(key, None)
                return None
            if arguments and json.loads(value[0]).get(
                "browser_binding"
            ) != arguments[0]:
                return None
            del self.values[key]
            return value[0]

    @staticmethod
    def assert_one_key(key_count):
        if key_count != 1:
            raise AssertionError("Expected one Redis key")


def oauth_config():
    return google_oauth.GoogleOAuthConfig(
        client_id="test-client",
        client_secret="test-secret",
        redirect_uri="http://localhost:3000/api/auth/google/callback",
        frontend_origin="http://localhost:3000",
        redis_url="redis://unused",
        identity_lookup_database_url="postgresql+psycopg://unused",
        test_user_email="verified@example.com",
    )


class TransactionTests(unittest.TestCase):
    def test_browser_binding_expiry_and_replay_are_single_use(self):
        now = [1000.0]
        redis_client = MemoryRedis(lambda: now[0])
        store = google_oauth.RedisOAuthTransactionStore(
            "", client=redis_client
        )
        transaction = {
            "purpose": "login",
            "browser_binding": store.binding_digest("browser-token"),
            "issued_at": 1000,
            "nonce": "nonce",
            "code_verifier": "verifier",
        }
        store.create("one-time-state", transaction)
        self.assertIsNone(store.consume("one-time-state", "other-browser-token"))
        self.assertIsNotNone(store.consume("one-time-state", "browser-token"))
        self.assertIsNone(store.consume("one-time-state", "browser-token"))

        store.create("expired-state", transaction)
        now[0] += store.TTL_SECONDS + 1
        self.assertIsNone(store.consume("expired-state", "browser-token"))

    def test_concurrent_callbacks_consume_at_most_once(self):
        store = google_oauth.RedisOAuthTransactionStore(
            "", client=MemoryRedis()
        )
        transaction = {
            "purpose": "login",
            "browser_binding": store.binding_digest("browser-token"),
            "issued_at": int(time.time()),
            "nonce": "nonce",
            "code_verifier": "verifier",
        }
        store.create("race-state", transaction)
        barrier = threading.Barrier(3)
        results = []

        def consume():
            barrier.wait()
            results.append(store.consume("race-state", "browser-token"))

        workers = [threading.Thread(target=consume) for _ in range(2)]
        for worker in workers:
            worker.start()
        barrier.wait()
        for worker in workers:
            worker.join()
        self.assertEqual(sum(result is not None for result in results), 1)

    def test_redis_errors_fail_closed_without_fallback(self):
        class BrokenRedis:
            def set(self, *_args, **_kwargs):
                raise redis.RedisError("offline")

            def eval(self, *_args, **_kwargs):
                raise redis.RedisError("offline")

        store = google_oauth.RedisOAuthTransactionStore(
            "", client=BrokenRedis()
        )
        with self.assertRaises(google_oauth.OAuthBackendUnavailable):
            store.create("state", {"purpose": "login"})
        with self.assertRaises(google_oauth.OAuthBackendUnavailable):
            store.consume("state", "browser-binding-token")

    def test_ephemeral_pending_state_and_proofs_are_single_use(self):
        now = [1000.0]
        store = google_oauth.RedisOAuthTransactionStore(
            "", client=MemoryRedis(lambda: now[0])
        )
        value = {"user_id": "account", "action": "password_add"}
        self.assertTrue(store.put_once("proof:password_add", "session", value, 300))
        self.assertFalse(store.put_once("proof:password_add", "session", value, 300))
        self.assertEqual(
            store.consume_once("proof:password_add", "session"), value
        )
        self.assertIsNone(store.consume_once("proof:password_add", "session"))
        self.assertTrue(store.put_once("signup", "browser", value, 600))
        now[0] += 601
        self.assertIsNone(store.consume_once("signup", "browser"))


class ConfigurationTests(unittest.TestCase):
    def test_oauth_is_disabled_by_default_and_incomplete_enablement_fails(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(google_oauth.GoogleOAuthConfig.from_environment())
        with patch.dict(
            os.environ, {"GOOGLE_OAUTH_ENABLED": "1"}, clear=True
        ), self.assertRaises(google_oauth.OAuthConfigurationError):
            google_oauth.GoogleOAuthConfig.from_environment()

    def test_enabled_requires_exactly_one_valid_test_email(self):
        invalid_emails = (
            "",
            "not-an-email",
            "a@example.com,b@example.com",
            "a@example.com;b@example.com",
            "Name <a@example.com>",
            "a@-example.com",
            "a..b@example.com",
            "a@example.com\nb@example.com",
        )
        for email in invalid_emails:
            with (
                self.subTest(email=email),
                patch.dict(
                    os.environ,
                    {
                        "GOOGLE_OAUTH_ENABLED": "1",
                        "GOOGLE_OAUTH_TEST_USER_EMAIL": email,
                    },
                    clear=True,
                ),
                self.assertRaisesRegex(
                    google_oauth.OAuthConfigurationError,
                    "GOOGLE_OAUTH_TEST_USER_EMAIL",
                ),
            ):
                google_oauth.GoogleOAuthConfig.from_environment()

    def test_https_configuration_uses_host_cookie_and_separate_lookup_role(self):
        values = {
            "GOOGLE_OAUTH_ENABLED": "1",
            "GOOGLE_CLIENT_ID": "client-id",
            "GOOGLE_OAUTH_TEST_USER_EMAIL": " Verified@Example.COM ",
            "GOOGLE_CLIENT_SECRET": "client-secret",
            "GOOGLE_REDIRECT_URI": (
                "https://app.example/api/auth/google/callback"
            ),
            "GOOGLE_FRONTEND_ORIGIN": "https://app.example",
            "GOOGLE_IDENTITY_LOOKUP_DATABASE_URL": (
                "postgresql+psycopg://lookup:secret@db.example/app"
            ),
            "DATABASE_URL": "postgresql+psycopg://app:secret@db.example/app",
            "REDIS_URL": "redis://redis.example/0",
            "VERVFY_ENVIRONMENT": "production",
        }
        with patch.dict(os.environ, values, clear=True):
            config = google_oauth.GoogleOAuthConfig.from_environment()
        self.assertEqual(config.browser_cookie_name, "__Host-vervfy_google_oauth")
        self.assertTrue(config.cookie_secure)
        self.assertEqual(config.test_user_email, "verified@example.com")


class GoogleTokenTests(unittest.TestCase):
    def setUp(self):
        self.key = jwk.generate_key("RSA", 2048, auto_kid=True)
        self.other_key = jwk.generate_key("RSA", 2048, auto_kid=True)
        self.redis = MemoryRedis()
        self.lookup_engine = create_engine("sqlite://")
        self.addCleanup(self.lookup_engine.dispose)

    def service_for(self, signed_claim_changes=None, signing_key=None):
        metadata = {
            "issuer": google_oauth.GOOGLE_ISSUER,
            "authorization_endpoint": google_oauth.GOOGLE_AUTHORIZATION_ENDPOINT,
            "token_endpoint": google_oauth.GOOGLE_TOKEN_ENDPOINT,
            "jwks_uri": google_oauth.GOOGLE_JWKS_URI,
            "id_token_signing_alg_values_supported": ["RS256", "RS512"],
            "jwks": {"keys": [self.key.as_dict(private=False)]},
            "_loaded_at": time.time(),
        }

        async def handler(request):
            body = parse_qs((await request.aread()).decode())
            self.assertEqual(body.get("grant_type"), ["authorization_code"])
            self.assertEqual(body.get("code"), ["authorization-code"])
            self.assertEqual(body.get("redirect_uri"), [oauth_config().redirect_uri])
            self.assertEqual(body.get("code_verifier"), [expected_verifier[0]])
            claims = {
                "iss": google_oauth.GOOGLE_ISSUER,
                "sub": "google-subject",
                "aud": "test-client",
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
                "nonce": expected_nonce[0],
            }
            claims.update(signed_claim_changes or {})
            token = jwt.encode(
                {"alg": "RS256", "kid": (signing_key or self.key).kid},
                claims,
                signing_key or self.key,
                algorithms=["RS256"],
            )
            return httpx2.Response(
                200,
                json={
                    "access_token": "mock-access-token",
                    "token_type": "Bearer",
                    "expires_in": 300,
                    "id_token": token,
                },
            )

        expected_verifier = [None]
        expected_nonce = [None]

        def client_factory(**kwargs):
            return google_oauth.AsyncOAuth2Client(
                **kwargs, transport=httpx2.MockTransport(handler)
            )

        service = google_oauth.GoogleOAuthService(
            oauth_config(),
            transaction_store=google_oauth.RedisOAuthTransactionStore(
                "", client=self.redis
            ),
            identity_engine=self.lookup_engine,
            oauth_client_factory=client_factory,
        )
        service._oidc_app.server_metadata = metadata
        return service, expected_verifier, expected_nonce

    def start_and_consume(self, service, verifier, nonce):
        browser = "browser-binding-token-12345678901234567890"
        authorization_url = asyncio.run(service.create_authorization_url(browser))
        query = parse_qs(urlsplit(authorization_url).query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        state = query["state"][0]
        transaction = asyncio.run(service.consume_transaction(state, browser))
        verifier[0] = transaction["code_verifier"]
        nonce[0] = transaction["nonce"]
        self.assertNotIn(verifier[0], authorization_url)
        return authorization_url, transaction

    def test_authorization_code_pkce_and_id_token_validation(self):
        service, verifier, nonce = self.service_for()
        authorization_url, transaction = self.start_and_consume(
            service, verifier, nonce
        )
        query = parse_qs(urlsplit(authorization_url).query)
        expected_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier[0].encode()).digest()
        ).rstrip(b"=").decode()
        self.assertEqual(query["code_challenge"][0], expected_challenge)
        claims = asyncio.run(
            service.exchange_and_validate("authorization-code", transaction)
        )
        self.assertEqual(claims["sub"], "google-subject")
        self.assertEqual(claims["nonce"], nonce[0])

    def test_real_authlib_preserves_signed_auth_time_and_rejects_missing_freshness(self):
        now = int(time.time())
        for value in (None, now, now - 600):
            with self.subTest(auth_time=value):
                service, verifier, nonce = self.service_for(
                    {} if value is None else {"auth_time": value}
                )
                _, transaction = self.start_and_consume(service, verifier, nonce)
                claims = asyncio.run(service.exchange_and_validate(
                    "authorization-code", transaction
                ))
                if value is None:
                    self.assertNotIn("auth_time", claims)
                else:
                    self.assertEqual(claims["auth_time"], value)
                if value == now:
                    self.assertEqual(service.require_fresh_authentication(claims), now)
                else:
                    # A fresh, correctly signed iat is not authentication evidence.
                    with self.assertRaises(google_oauth.GoogleTokenError):
                        service.require_fresh_authentication(claims)

    def test_sensitive_authorization_requests_documented_auth_time_claim(self):
        service, _, _ = self.service_for()
        browser = "browser-binding-token-12345678901234567890"
        authorization_url = asyncio.run(
            service.create_authorization_url(
                browser,
                purpose="link",
                context={
                    "user_id": "user-1",
                    "session_id": "session-1",
                    "session_version": 2,
                    "password_verified_at": int(time.time()),
                },
            )
        )
        query = parse_qs(urlsplit(authorization_url).query)
        self.assertNotIn("prompt", query)
        self.assertEqual(query["max_age"], ["300"])
        self.assertEqual(
            json.loads(query["claims"][0]),
            {"id_token": {"auth_time": {"essential": True}}},
        )
        transaction = asyncio.run(
            service.consume_transaction(query["state"][0], browser)
        )
        self.assertEqual(transaction["purpose"], "link")
        self.assertEqual(transaction["user_id"], "user-1")

    def test_fresh_authentication_rejects_missing_stale_and_future_times(self):
        service, _, _ = self.service_for()
        service._clock = lambda: 1000
        self.assertEqual(
            service.require_fresh_authentication({"auth_time": 700}), 700
        )
        with self.assertRaises(google_oauth.GoogleTokenError):
            service.require_fresh_authentication({})
        with self.assertRaises(google_oauth.GoogleTokenError):
            service.require_fresh_authentication(
                {"auth_time": 699}
            )
        with self.assertRaises(google_oauth.GoogleTokenError):
            service.require_fresh_authentication(
                {"auth_time": 1061}
            )
        for invalid_time in (True, 1000.0, "1000"):
            with self.subTest(auth_time=invalid_time), self.assertRaises(
                google_oauth.GoogleTokenError
            ):
                service.require_fresh_authentication(
                    {"auth_time": invalid_time}
                )

    def test_wrong_audience_and_signature_are_rejected(self):
        for changes, key in (
            ({"aud": "another-client"}, None),
            ({"iss": "https://attacker.example"}, None),
            ({"nonce": "different-nonce"}, None),
            ({"exp": int(time.time()) - 600}, None),
            ({"exp": float("nan")}, None),
            ({"iat": float("inf")}, None),
            ({}, self.other_key),
        ):
            with self.subTest(changes=changes, bad_signature=key is not None):
                service, verifier, nonce = self.service_for(
                    changes, signing_key=key
                )
                _, transaction = self.start_and_consume(
                    service, verifier, nonce
                )
                with self.assertRaises(google_oauth.GoogleTokenError):
                    asyncio.run(
                        service.exchange_and_validate(
                            "authorization-code", transaction
                        )
                    )


class CallbackTests(unittest.TestCase):
    def setUp(self):
        self.config = oauth_config()
        self.client = TestClient(server.app, follow_redirects=False)

    def _flow(
        self,
        claims=None,
        user_id="mapped-user",
        error=None,
        purpose="login",
        context=None,
    ):
        class FakeFlow:
            def __init__(self):
                self.lookup_calls = []
                self.stored_proofs = []
                self.pending_signup = None
                self.purpose = purpose
                self.context = context or {}

            async def create_authorization_url(
                self, browser_binding, **kwargs
            ):
                self.browser_binding = browser_binding
                self.purpose = kwargs.get("purpose", self.purpose)
                self.context = kwargs.get("context", self.context)
                return "https://accounts.google.com/mock"

            async def consume_transaction(self, state, browser_binding):
                if state != "one-time-state" or browser_binding != self.browser_binding:
                    raise google_oauth.OAuthTransactionError("invalid")
                return {
                    "purpose": self.purpose,
                    "nonce": "n",
                    "code_verifier": "v",
                    **self.context,
                }

            async def exchange_and_validate(self, code, transaction):
                if error:
                    raise error
                verified_claims = {
                    "iss": google_oauth.GOOGLE_ISSUER,
                    "sub": "subject-a",
                    "aud": "test-client",
                    "email": "verified@example.com",
                    "email_verified": True,
                }
                verified_claims.update(claims or {})
                return verified_claims

            def lookup_identity(self, verified_claims):
                self.lookup_calls.append(verified_claims)
                return user_id

            def require_fresh_authentication(self, verified_claims):
                auth_time = verified_claims.get("auth_time")
                if (
                    not isinstance(auth_time, int)
                    or isinstance(auth_time, bool)
                    or time.time() - auth_time > 300
                    or auth_time > time.time() + 60
                ):
                    raise google_oauth.GoogleTokenError("stale authentication")
                return auth_time

            def store_reauthentication_proof(
                self, session_id, proof_purpose, proof
            ):
                self.stored_proofs.append((session_id, proof_purpose, proof))
                return True

            def store_pending_signup(self, browser_binding, verified_claims):
                self.pending_signup = (browser_binding, verified_claims)
                return True

        return FakeFlow()

    def test_https_proxy_headers_cannot_change_oauth_redirect_or_cookie_scope(self):
        from dataclasses import replace
        from http.cookies import SimpleCookie

        config = replace(
            self.config,
            frontend_origin="https://app.example",
            redirect_uri="https://app.example/api/auth/google/callback",
        )
        flow = self._flow()
        proxied_app = ProxyHeadersMiddleware(
            server.app, trusted_hosts="127.0.0.1"
        )
        client = TestClient(
            proxied_app,
            base_url="http://app.example",
            follow_redirects=False,
            client=("127.0.0.1", 12345),
        )
        with (
            patch.object(server, "google_oauth_config", config),
            patch.object(server, "google_oauth_service", flow),
            patch.object(server.request_throttle, "allow", return_value=True),
        ):
            response = client.get(
                "/api/auth/google/start",
                headers={
                    "host": "attacker.example",
                    "x-forwarded-host": "attacker.example",
                    "x-forwarded-proto": "https",
                },
            )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "https://accounts.google.com/mock")
        self.assertNotIn("attacker.example", response.headers["location"])
        self.assertIn("no-store", response.headers["cache-control"])
        cookie = SimpleCookie(response.headers["set-cookie"])[
            "__Host-vervfy_google_oauth"
        ]
        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "lax")
        self.assertEqual(cookie["path"], "/")
        self.assertFalse(cookie["domain"])

    def test_disallowed_google_claims_never_reach_identity_lookup(self):
        for purpose in google_oauth.GOOGLE_FLOW_PURPOSES:
            for claims in (
                {"email": "other@example.com", "email_verified": True},
                {"email": "verified@example.com", "email_verified": False},
                {"email": "verified@example.com", "email_verified": "true"},
                {"email": "verified@example.com", "email_verified": None},
                {"email": None, "email_verified": True},
            ):
                with self.subTest(purpose=purpose, claims=claims):
                    flow = self._flow(claims=claims, purpose=purpose)
                    flow.browser_binding = "test-browser-binding"
                    request = SimpleNamespace(
                        query_params={"state": "one-time-state", "code": "code"},
                        cookies={self.config.browser_cookie_name: flow.browser_binding},
                    )
                    with (
                        patch.object(server, "google_oauth_config", self.config),
                        patch.object(server, "google_oauth_service", flow),
                        patch.object(server.user_store, "create_google_user") as create_user,
                        patch.object(server.session_store, "create") as create_session,
                    ):
                        response = asyncio.run(server.google_oauth_callback(request))
                    self.assertEqual(response.status_code, 303)
                    self.assertEqual(flow.lookup_calls, [])
                    self.assertIsNone(flow.pending_signup)
                    self.assertEqual(flow.stored_proofs, [])
                    create_user.assert_not_called()
                    create_session.assert_not_called()

    def test_onboarding_rechecks_current_test_email_before_creation(self):
        for email in (None, "previous-test-user@example.com"):
            with self.subTest(email=email):
                flow = SimpleNamespace(consume_pending_signup=lambda _: {
                    "issuer": google_oauth.GOOGLE_ISSUER,
                    "subject": "pending-subject", "email": email,
                })
                request = SimpleNamespace(cookies={}, headers={}, client=None)
                with (
                    patch.object(server, "google_oauth_config", self.config),
                    patch.object(server, "google_oauth_service", flow),
                    patch.object(server.auth, "client_ip", return_value="127.0.0.1"),
                    patch.object(server.signup_throttle, "is_limited", return_value=False),
                    patch.object(server.user_store, "create_google_user") as create_user,
                    self.assertRaises(server.HTTPException) as rejected,
                ):
                    server.google_account_onboarding(
                        server.GoogleOnboardingRequest(username="new-user"), request,
                    )
                self.assertEqual(rejected.exception.status_code, 400)
                create_user.assert_not_called()

    def test_callback_authenticates_only_verified_subject_and_issues_session(self):
        flow = self._flow(
            claims={
                "email": "VERIFIED@EXAMPLE.COM",
                "email_verified": True,
            }
        )
        user = {
            "id": "mapped-user",
            "session_version": 9,
            "email": "unrelated-profile@example.com",
        }
        with (
            patch.object(server, "google_oauth_config", self.config),
            patch.object(server, "google_oauth_service", flow),
            patch.object(server.user_store, "get_by_id", return_value=user) as get_user,
            patch.object(server.session_store, "create", return_value="new-session") as create_session,
            patch.object(server.session_store, "revoke") as revoke_session,
        ):
            start = self.client.get("/api/auth/google/start")
            self.assertEqual(start.status_code, 303)
            self.assertIn("vervfy_google_oauth", start.cookies)
            set_cookie = start.headers["set-cookie"].lower()
            self.assertIn("httponly", set_cookie)
            self.assertIn("samesite=lax", set_cookie)
            self.assertIn("max-age=600", set_cookie)
            self.assertIn("path=/", set_cookie)
            callback_request = SimpleNamespace(
                query_params={
                    "state": "one-time-state",
                    "code": "authorization-code",
                },
                cookies={
                    self.config.browser_cookie_name: start.cookies.get(
                        self.config.browser_cookie_name
                    )
                },
                session={"user_id": "old-user", "sid": "old-session", "sv": 2},
            )
            callback = asyncio.run(
                server.google_oauth_callback(callback_request)
            )
        self.assertEqual(callback.status_code, 303)
        self.assertEqual(callback.headers["location"], "/")
        self.assertIn("no-store", callback.headers["cache-control"])
        self.assertEqual(flow.lookup_calls[0]["sub"], "subject-a")
        get_user.assert_called_once_with("mapped-user")
        create_session.assert_called_once_with("mapped-user")
        revoke_session.assert_called_once_with("old-session")
        self.assertEqual(
            callback_request.session,
            {"user_id": "mapped-user", "sv": 9, "sid": "new-session"},
        )

    def test_invalid_token_never_reaches_identity_lookup(self):
        flow = self._flow(error=google_oauth.GoogleTokenError("invalid token"))
        with (
            patch.object(server, "google_oauth_config", self.config),
            patch.object(server, "google_oauth_service", flow),
        ):
            self.client.get("/api/auth/google/start")
            response = self.client.get(
                "/api/auth/google/callback",
                params={"state": "one-time-state", "code": "invalid"},
            )
        self.assertEqual(response.status_code, 303)
        self.assertIn("google=failed", response.headers["location"])
        self.assertEqual(flow.lookup_calls, [])

    def test_unlinked_identity_cannot_create_or_select_an_account(self):
        flow = self._flow(user_id=None)
        with (
            patch.object(server, "google_oauth_config", self.config),
            patch.object(server, "google_oauth_service", flow),
            patch.object(server.user_store, "get_by_id") as get_user,
            patch.object(server.session_store, "create") as create_session,
        ):
            self.client.get("/api/auth/google/start")
            response = self.client.get(
                "/api/auth/google/callback",
                params={"state": "one-time-state", "code": "authorization-code"},
            )
        self.assertIn("google=failed", response.headers["location"])
        get_user.assert_not_called()
        create_session.assert_not_called()

    def test_signup_callback_stages_identity_until_username_selection(self):
        flow = self._flow(user_id=None, purpose="signup")
        flow.browser_binding = "browser-binding-token-12345678901234567890"
        request = SimpleNamespace(
            query_params={
                "state": "one-time-state",
                "code": "authorization-code",
            },
            cookies={
                self.config.browser_cookie_name: flow.browser_binding,
            },
            session={},
        )
        with (
            patch.object(server, "google_oauth_config", self.config),
            patch.object(server, "google_oauth_service", flow),
            patch.object(server.user_store, "create_google_user") as create_user,
        ):
            response = asyncio.run(server.google_oauth_callback(request))
        self.assertEqual(response.headers["location"], "/register?google=complete")
        self.assertEqual(flow.pending_signup[0], flow.browser_binding)
        self.assertEqual(flow.pending_signup[1]["sub"], "subject-a")
        create_user.assert_not_called()

    def test_signup_callback_conflict_retry_and_completion(self):
        from dataclasses import replace
        from http.cookies import SimpleCookie

        self.config = replace(
            self.config,
            frontend_origin="https://testserver",
            redirect_uri="https://testserver/api/auth/google/callback",
        )
        client = TestClient(server.app, base_url="https://testserver", follow_redirects=False)
        service = google_oauth.GoogleOAuthService.__new__(google_oauth.GoogleOAuthService)
        service._clock = time.time
        service.transactions = google_oauth.RedisOAuthTransactionStore("", client=MemoryRedis())
        flow = self._flow(user_id=None, purpose="signup", claims={
            "sub": "synthetic-subject", "email": "verified@example.com", "email_verified": True,
        })
        binding = "synthetic-browser-binding-12345678901234567890"
        flow.browser_binding = binding
        flow.store_pending_signup = service.store_pending_signup
        flow.consume_pending_signup = service.consume_pending_signup
        client.cookies.set(self.config.browser_cookie_name, binding)
        csrf = client.get("/api/csrf").json()["csrf_token"]
        with (
            patch.object(server, "google_oauth_config", self.config),
            patch.object(server, "google_oauth_service", flow),
            patch.object(server.signup_throttle, "is_limited", return_value=False),
            patch.object(server.signup_throttle, "record_success"),
            patch.object(server.user_store, "create_google_user", side_effect=[
                ValueError("Username unavailable"), {"id": "synthetic-user"},
            ]) as create_user,
            patch.object(server.user_store, "get_by_id", return_value={"id": "synthetic-user", "session_version": 0}),
            patch.object(server.session_store, "create", return_value="synthetic-session") as session_create,
        ):
            callback = client.get("/api/auth/google/callback?state=one-time-state&code=synthetic-code")
            self.assertEqual(callback.status_code, 303)
            self.assertEqual(callback.headers["location"], "/register?google=complete")
            cookies = SimpleCookie(callback.headers["set-cookie"])
            cookie = cookies[self.config.browser_cookie_name]
            self.assertEqual(cookie["max-age"], "600")
            self.assertTrue(cookie["secure"])
            self.assertTrue(cookie["httponly"])
            self.assertEqual(cookie["samesite"], "lax")
            self.assertEqual(cookie["path"], "/")
            self.assertFalse(cookie["domain"])
            create_user.assert_not_called()
            headers = {"X-CSRF-Token": csrf}
            failed = client.post("/api/auth/google/onboarding", json={"username": "taken-name"}, headers=headers)
            self.assertEqual(failed.status_code, 409)
            session_create.assert_not_called()
            success = client.post("/api/auth/google/onboarding", json={"username": "available-name"}, headers=headers)
            self.assertEqual(success.status_code, 303)
            self.assertEqual(success.headers["location"], "/")
            create_user.assert_called_with("available-name", "verified@example.com", "synthetic-subject")
            session_create.assert_called_once_with("synthetic-user")
            self.assertIn("Max-Age=0", success.headers["set-cookie"])
            self.assertIsNone(service.consume_pending_signup(binding))

    def test_onboarding_consumes_pending_identity_with_csrf_and_creates_session(self):
        class PendingSignup:
            def __init__(self):
                self.binding = None

            def consume_pending_signup(self, browser_binding):
                self.binding = browser_binding
                return {
                    "issuer": google_oauth.GOOGLE_ISSUER,
                    "subject": "new-google-subject",
                    "email": "verified@example.com",
                }

        flow = PendingSignup()
        csrf = self.client.get("/api/csrf").json()["csrf_token"]
        binding = "browser-binding-token-12345678901234567890"
        self.client.cookies.set(self.config.browser_cookie_name, binding)
        user = {
            "id": "new-account",
            "session_version": 0,
        }
        with (
            patch.object(server, "google_oauth_config", self.config),
            patch.object(server, "google_oauth_service", flow),
            patch.object(server.signup_throttle, "is_limited", return_value=False),
            patch.object(server.signup_throttle, "record_success"),
            patch.object(
                server.user_store,
                "create_google_user",
                return_value={
                    "id": "new-account",
                    "username": "new-user",
                    "email": "verified@example.com",
                },
            ) as create_user,
            patch.object(server.user_store, "get_by_id", return_value=user),
            patch.object(server.session_store, "create", return_value="fresh-session"),
        ):
            response = self.client.post(
                "/api/auth/google/onboarding",
                json={"username": "new-user"},
                headers={"X-CSRF-Token": csrf},
            )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/")
        self.assertEqual(flow.binding, binding)
        create_user.assert_called_once_with(
            "new-user", "verified@example.com", "new-google-subject"
        )

    def test_google_onboarding_rejects_replayed_pending_identity(self):
        class ExpiredSignup:
            def consume_pending_signup(self, _browser_binding):
                return None

        csrf = self.client.get("/api/csrf").json()["csrf_token"]
        self.client.cookies.set(
            self.config.browser_cookie_name,
            "browser-binding-token-12345678901234567890",
        )
        with (
            patch.object(server, "google_oauth_config", self.config),
            patch.object(server, "google_oauth_service", ExpiredSignup()),
            patch.object(server.signup_throttle, "is_limited", return_value=False),
            patch.object(server.user_store, "create_google_user") as create_user,
        ):
            response = self.client.post(
                "/api/auth/google/onboarding",
                json={"username": "new-user"},
                headers={"X-CSRF-Token": csrf},
            )
        self.assertEqual(response.status_code, 400)
        create_user.assert_not_called()

    def test_link_callback_requires_bound_account_and_rotates_sessions(self):
        user = {
            "id": "password-user",
            "session_version": 4,
            "password_hash": "hash",
        }
        context = {
            "user_id": "password-user",
            "session_id": "active-session",
            "session_version": 4,
            "password_verified_at": int(time.time()),
        }
        flow = self._flow(
            claims={
                "iss": google_oauth.GOOGLE_ISSUER,
                "sub": "new-google-subject",
                "auth_time": int(time.time()),
            },
            user_id=None,
            purpose="link",
            context=context,
        )
        flow.browser_binding = "browser-binding-token-12345678901234567890"
        request = SimpleNamespace(
            query_params={
                "state": "one-time-state",
                "code": "authorization-code",
            },
            cookies={
                self.config.browser_cookie_name: flow.browser_binding,
            },
            session={
                "user_id": "password-user",
                "sid": "active-session",
                "sv": 4,
            },
        )
        with (
            patch.object(server, "google_oauth_config", self.config),
            patch.object(server, "google_oauth_service", flow),
            patch.object(server, "current_user_row", return_value=user),
            patch.object(
                server.user_store,
                "account_security",
                return_value={"has_password": True, "google_linked": False},
            ),
            patch.object(
                server.user_store, "link_google_identity", return_value=5
            ) as link,
            patch.object(server.session_store, "revoke_user") as revoke,
            patch.object(server.session_store, "create", return_value="rotated"),
        ):
            response = asyncio.run(server.google_oauth_callback(request))
        self.assertEqual(
            response.headers["location"], "/?view=account&google_link=success"
        )
        link.assert_called_once_with("password-user", "new-google-subject")
        revoke.assert_called_once_with("password-user")
        self.assertEqual(
            request.session,
            {"user_id": "password-user", "sv": 5, "sid": "rotated"},
        )

    def test_google_only_reauthentication_stores_action_bound_proof(self):
        user = {
            "id": "google-user",
            "session_version": 2,
            "password_hash": None,
        }
        context = {
            "user_id": "google-user",
            "session_id": "active-session",
            "session_version": 2,
        }
        flow = self._flow(
            claims={
                "iss": google_oauth.GOOGLE_ISSUER,
                "sub": "linked-google-subject",
                "auth_time": int(time.time()),
            },
            user_id="google-user",
            purpose="password_add",
            context=context,
        )
        flow.browser_binding = "browser-binding-token-12345678901234567890"
        request = SimpleNamespace(
            query_params={
                "state": "one-time-state",
                "code": "authorization-code",
            },
            cookies={
                self.config.browser_cookie_name: flow.browser_binding,
            },
            session={
                "user_id": "google-user",
                "sid": "active-session",
                "sv": 2,
            },
        )
        with (
            patch.object(server, "google_oauth_config", self.config),
            patch.object(server, "google_oauth_service", flow),
            patch.object(server, "current_user_row", return_value=user),
            patch.object(
                server.user_store,
                "account_security",
                return_value={"has_password": False, "google_linked": True},
            ),
        ):
            response = asyncio.run(server.google_oauth_callback(request))
        self.assertIn("google_action=password_add", response.headers["location"])
        self.assertEqual(flow.stored_proofs[0][0], "active-session")
        self.assertEqual(flow.stored_proofs[0][1], "password_add")
        proof = flow.stored_proofs[0][2]
        self.assertEqual(proof["user_id"], "google-user")
        self.assertEqual(proof["session_version"], 2)
        self.assertEqual(proof["auth_time"], flow.lookup_calls[0]["auth_time"])
        self.assertLessEqual(abs(proof["verified_at"] - time.time()), 2)

    def test_missing_auth_time_callback_rejects_without_storing_proof(self):
        user = {
            "id": "google-user",
            "session_version": 2,
            "password_hash": None,
        }
        context = {
            "user_id": "google-user",
            "session_id": "active-session",
            "session_version": 2,
        }
        flow = self._flow(
            claims={
                "iss": google_oauth.GOOGLE_ISSUER,
                "sub": "linked-google-subject",
            },
            user_id="google-user",
            purpose="password_add",
            context=context,
        )
        flow.browser_binding = "browser-binding-token-12345678901234567890"
        request = SimpleNamespace(
            query_params={
                "state": "one-time-state",
                "code": "authorization-code",
            },
            cookies={
                self.config.browser_cookie_name: flow.browser_binding,
            },
            session={
                "user_id": "google-user",
                "sid": "active-session",
                "sv": 2,
            },
        )
        with (
            patch.object(server, "google_oauth_config", self.config),
            patch.object(server, "google_oauth_service", flow),
            patch.object(server, "current_user_row", return_value=user),
            patch.object(
                server.user_store,
                "account_security",
                return_value={"has_password": False, "google_linked": True},
            ),
        ):
            response = asyncio.run(server.google_oauth_callback(request))
        self.assertIn("google_reauth=failed", response.headers["location"])
        self.assertEqual(flow.stored_proofs, [])
        self.assertEqual(request.session["sid"], "active-session")

    def test_missing_auth_time_email_change_rejects_without_storing_proof(self):
        user = {
            "id": "google-user",
            "session_version": 2,
            "password_hash": None,
        }
        context = {
            "user_id": "google-user",
            "session_id": "active-session",
            "session_version": 2,
        }
        flow = self._flow(
            claims={
                "iss": google_oauth.GOOGLE_ISSUER,
                "sub": "linked-google-subject",
            },
            user_id="google-user",
            purpose="email_change",
            context=context,
        )
        flow.browser_binding = "browser-binding-token-12345678901234567890"
        request = SimpleNamespace(
            query_params={
                "state": "one-time-state",
                "code": "authorization-code",
            },
            cookies={
                self.config.browser_cookie_name: flow.browser_binding,
            },
            session={
                "user_id": "google-user",
                "sid": "active-session",
                "sv": 2,
            },
        )
        with (
            patch.object(server, "google_oauth_config", self.config),
            patch.object(server, "google_oauth_service", flow),
            patch.object(server, "current_user_row", return_value=user),
            patch.object(
                server.user_store,
                "account_security",
                return_value={"has_password": False, "google_linked": True},
            ),
        ):
            response = asyncio.run(server.google_oauth_callback(request))
        self.assertIn("google_reauth=failed", response.headers["location"])
        self.assertEqual(flow.stored_proofs, [])
        self.assertEqual(request.session["sid"], "active-session")

    def test_google_routes_are_not_exposed_while_disabled(self):
        with (
            patch.object(server, "google_oauth_config", None),
            patch.object(server, "google_oauth_service", None),
        ):
            response = self.client.get("/api/auth/google/start")
        self.assertEqual(response.status_code, 404)

    def test_existing_password_login_still_issues_session(self):
        password_hash = hash_password("existing-password")
        request = SimpleNamespace(
            session={"csrf_token": "csrf"},
            client=None,
        )
        with (
            patch.object(
                server.user_store,
                "get_by_username",
                return_value={
                    "id": "password-user",
                    "password_hash": password_hash,
                    "session_version": 4,
                },
            ),
            patch.object(server.login_throttle, "is_locked", return_value=False),
            patch.object(server.login_throttle, "clear"),
            patch.object(server.session_store, "create", return_value="sid"),
        ):
            response = server.login_submit(
                request, "existing", "existing-password", "csrf"
            )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(request.session["user_id"], "password-user")
        self.assertEqual(request.session["sid"], "sid")

    def test_existing_registration_still_creates_password_account(self):
        request = SimpleNamespace(
            session={"csrf_token": "csrf"},
            client=None,
            app=SimpleNamespace(state=SimpleNamespace(is_first_account=True)),
        )
        with (
            patch.object(server.signup_throttle, "is_limited", return_value=False),
            patch.object(server.signup_throttle, "record_success"),
            patch.object(
                server.user_store,
                "create_user",
                return_value={"id": "new-password-user"},
            ) as create_user,
            patch.object(server.session_store, "create", return_value="new-sid"),
        ):
            response = server.register_submit(
                request,
                "new-user",
                "valid-password",
                "",
                "csrf",
            )
        self.assertEqual(response.status_code, 303)
        create_user.assert_called_once_with("new-user", None, "valid-password")
        self.assertEqual(request.session["user_id"], "new-password-user")
        self.assertEqual(request.session["sid"], "new-sid")


if __name__ == "__main__":
    unittest.main()
