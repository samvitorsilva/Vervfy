from pathlib import Path

import yaml


def test_render_backend_declares_safe_proxy_and_passkey_feature_settings():
    blueprint = yaml.safe_load(
        (Path(__file__).parents[1] / "render.yaml").read_text(encoding="utf-8")
    )
    backend = next(
        service
        for service in blueprint["services"]
        if service.get("name") == "vervfy-api"
    )
    environment = {
        variable["key"]: variable.get("value")
        for variable in backend["envVars"]
    }

    assert environment["VERVFY_TRUSTED_PROXY_HOPS"] == "1"
    assert environment["VERVFY_WEBAUTHN_ENABLED"] == "0"
