"""Structural checks for the isolated, OAuth-disabled Render staging proposal."""

import unittest
from pathlib import Path

import yaml


class StagingRenderProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "render.staging.proposal.yaml"
        with path.open(encoding="utf-8") as proposal:
            cls.blueprint = yaml.safe_load(proposal)
        cls.services = cls.blueprint["projects"][0]["environments"][0]["services"]
        cls.by_name = {service["name"]: service for service in cls.services}

    def test_defines_only_the_two_isolated_staging_services(self):
        self.assertEqual(
            set(self.by_name),
            {
                "vervfy-staging-api",
                "vervfy-staging-web",
            },
        )
        self.assertNotIn("databases", self.blueprint)
        self.assertNotIn("keyvalue", {service["type"] for service in self.services})
        self.assertTrue(
            all(service["region"] == "virginia" for service in self.services)
        )

    def test_api_uses_a_staging_redis_secret_and_keeps_oauth_disabled(self):
        api = self.by_name["vervfy-staging-api"]
        variables = {item["key"]: item for item in api["envVars"]}
        self.assertEqual(
            api["rootDir"],
            "release-artifacts/vervfy-staging-upstash-rediss-rc/source",
        )
        self.assertEqual(
            variables["PGSSLROOTCERT"]["value"],
            "/etc/secrets/prod-ca-2021.crt",
        )
        self.assertEqual(variables["GOOGLE_OAUTH_ENABLED"]["value"], "0")
        self.assertIs(variables["VERVFY_STAGING_REDIS_HOST"]["sync"], False)
        self.assertNotIn("value", variables["VERVFY_STAGING_REDIS_HOST"])
        self.assertIs(variables["REDIS_URL"]["sync"], False)
        self.assertNotIn("value", variables["REDIS_URL"])
        self.assertNotIn("GOOGLE_CLIENT_SECRET", variables)
        self.assertNotIn("GOOGLE_IDENTITY_LOOKUP_DATABASE_URL", variables)
        self.assertNotIn(
            "REDIS_URL",
            {item["key"] for item in self.by_name["vervfy-staging-web"]["envVars"]},
        )
        self.assertEqual(
            self.by_name["vervfy-staging-web"]["rootDir"],
            api["rootDir"] + "/web",
        )

    def test_frontend_points_only_to_staging_origins(self):
        web = self.by_name["vervfy-staging-web"]
        variables = {item["key"]: item for item in web["envVars"]}
        self.assertEqual(
            variables["BACKEND_URL"]["value"],
            "https://vervfy-staging-api.onrender.com",
        )
        self.assertEqual(
            variables["SITE_URL"]["value"],
            "https://vervfy-staging-web.onrender.com",
        )


if __name__ == "__main__":
    unittest.main()
