"""Local structural checks for the isolated staging Render Blueprint."""

from pathlib import Path
import unittest

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


ROOT = Path(__file__).resolve().parents[1]


def _environment(service):
    return {entry["key"]: entry for entry in service.get("envVars", [])}


@unittest.skipIf(yaml is None, "PyYAML is not installed")
class StagingRenderBlueprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.staging = yaml.safe_load(
            (ROOT / "render.staging.proposal.yaml").read_text(encoding="utf-8")
        )
        cls.production = yaml.safe_load(
            (ROOT / "render.yaml").read_text(encoding="utf-8")
        )

    def test_isolated_postgres_and_key_value_resources(self):
        self.assertEqual(len(self.staging["databases"]), 1)
        database = self.staging["databases"][0]
        self.assertEqual(database["databaseName"], "vervfy_oauth_staging")
        self.assertEqual(database["postgresMajorVersion"], "18")
        self.assertEqual(database["connectionPool"], "none")
        self.assertEqual(database["ipAllowList"], [])

        services = self.staging["services"]
        key_value = [service for service in services if service["type"] == "keyvalue"]
        self.assertEqual(len(key_value), 1)
        self.assertEqual(key_value[0]["plan"], "free")
        self.assertEqual(key_value[0]["maxmemoryPolicy"], "noeviction")
        self.assertEqual(key_value[0]["persistenceMode"], "off")
        self.assertEqual(key_value[0]["ipAllowList"], [])

    def test_web_services_have_separate_build_start_health_and_https_inputs(self):
        services = {
            service["name"]: service
            for service in self.staging["services"]
            if service["type"] == "web"
        }
        api = services["vervfy-staging-api"]
        web = services["vervfy-staging-web"]
        self.assertEqual(api["runtime"], "python")
        self.assertEqual(web["runtime"], "node")
        self.assertTrue(api["buildCommand"])
        self.assertTrue(web["buildCommand"])
        self.assertIn("--lifespan on", api["startCommand"])
        self.assertEqual(api["healthCheckPath"], "/healthz")
        self.assertEqual(web["healthCheckPath"], "/manifest.webmanifest")
        self.assertEqual(api["autoDeployTrigger"], "off")
        self.assertEqual(web["autoDeployTrigger"], "off")

        api_env = _environment(api)
        web_env = _environment(web)
        self.assertEqual(api_env["GOOGLE_OAUTH_ENABLED"]["value"], "0")
        self.assertEqual(api_env["DATABASE_URL"]["sync"], False)
        self.assertEqual(web_env["BACKEND_URL"]["sync"], False)
        self.assertEqual(web_env["SITE_URL"]["sync"], False)
        self.assertNotIn("GOOGLE_CLIENT_SECRET", api_env)
        self.assertNotIn("GOOGLE_IDENTITY_LOOKUP_DATABASE_URL", api_env)

    def test_service_references_are_staging_only(self):
        services = self.staging["services"]
        api = next(service for service in services if service["name"] == "vervfy-staging-api")
        redis_reference = _environment(api)["REDIS_URL"]["fromService"]
        self.assertEqual(redis_reference["type"], "keyvalue")
        self.assertEqual(redis_reference["name"], "vervfy-staging-valkey")
        names = {service["name"] for service in services}
        production_names = {
            service["name"] for service in self.production["services"]
        }
        self.assertFalse(names & production_names)
        self.assertEqual(
            {service["plan"] for service in services} | {
                self.staging["databases"][0]["plan"]
            },
            {"free"},
        )


if __name__ == "__main__":
    unittest.main()
