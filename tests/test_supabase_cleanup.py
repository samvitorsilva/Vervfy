import json
import unittest
import uuid

import httpx

from scripts.storage_cleanup_worker import CleanupStorageFailure
from storage_namespace import NamespaceBinding
from supabase_cleanup import SupabaseCleanupStorage


class SupabaseCleanupTests(unittest.TestCase):
    def setUp(self):
        self.namespace = uuid.UUID("00000000-0000-0000-0000-000000000001")
        self.subject = uuid.UUID("00000000-0000-0000-0000-000000000002")
        self.binding = NamespaceBinding(
            self.namespace, "production", "https://project.supabase.co", "songs"
        )
        self.path = (
            f"v2/{self.namespace}/tenant-a/audio/"
            "00000000-0000-0000-0000-000000000003.mp3"
        )

    def adapter(self, handler):
        return SupabaseCleanupStorage(
            self.binding,
            api_key="public-key",
            email="cleanup@example.invalid",
            password="private-password",
            subject=str(self.subject),
            transport=httpx.MockTransport(handler),
        )

    def test_auth_identity_and_one_exact_key_are_used(self):
        requests = []

        def handle(request):
            requests.append(request)
            if request.url.path == "/auth/v1/token":
                return httpx.Response(
                    200,
                    json={
                        "access_token": "short-lived-token",
                        "expires_in": 3600,
                        "user": {"id": str(self.subject)},
                    },
                )
            self.assertEqual(request.method, "DELETE")
            self.assertEqual(request.url.path, "/storage/v1/object/songs")
            self.assertEqual(request.headers["authorization"], "Bearer short-lived-token")
            self.assertEqual(request.headers["apikey"], "public-key")
            self.assertEqual(json.loads(request.content), {"prefixes": [self.path]})
            return httpx.Response(200, json={"data": []})

        self.adapter(handle).delete_if_present(self.path)
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].headers["apikey"], "public-key")
        self.assertEqual(
            json.loads(requests[0].content),
            {"email": "cleanup@example.invalid", "password": "private-password"},
        )

    def test_namespace_and_exact_key_validation_precedes_network_io(self):
        requests = []
        adapter = self.adapter(
            lambda request: (requests.append(request), httpx.Response(200))[1]
        )
        for path in (
            "legacy/shared.mp3",
            self.path + "*",
            self.path + "/child",
            self.path.replace(str(self.namespace), str(uuid.uuid4())),
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                adapter.delete_if_present(path)
        self.assertEqual(requests, [])

    def test_subject_mismatch_or_provider_denial_never_confirms_deletion(self):
        requests = []

        def wrong_subject(request):
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "access_token": "token",
                    "expires_in": 3600,
                    "user": {"id": str(uuid.uuid4())},
                },
            )

        with self.assertRaises(CleanupStorageFailure) as failure:
            self.adapter(wrong_subject).delete_if_present(self.path)
        self.assertEqual(failure.exception.code, "storage_rejected")
        self.assertEqual(len(requests), 1)

        def denied(request):
            if request.url.path == "/auth/v1/token":
                return httpx.Response(
                    200,
                    json={
                        "access_token": "token",
                        "expires_in": 3600,
                        "user": {"id": str(self.subject)},
                    },
                )
            return httpx.Response(403, text="provider detail must not escape")

        with self.assertRaises(CleanupStorageFailure) as failure:
            self.adapter(denied).delete_if_present(self.path)
        self.assertEqual(failure.exception.code, "storage_rejected")
        self.assertNotIn("provider detail", str(failure.exception))


if __name__ == "__main__":
    unittest.main()
