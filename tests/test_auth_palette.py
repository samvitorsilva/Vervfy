"""Historical auth palette, isolation, and contrast regressions."""

import re
from pathlib import Path

import pytest
from test_design_tokens import luminance

ROOT = Path(__file__).resolve().parents[1]
TOKENS = (ROOT / "web/src/app/auth-tokens.css").read_text()
BASE_TOKENS = (ROOT / "web/src/app/design-tokens.css").read_text()
VALUES = dict(re.findall(r"(--[\w-]+):([^;]+);", BASE_TOKENS + TOKENS))


def resolved(name):
    value = VALUES[name]
    alias = re.fullmatch(r"var\((--[\w-]+)\)", value)
    return resolved(alias[1]) if alias else value


def test_auth_reuses_original_navy_and_exact_logo_accent():
    # Navy values from fde57bd; auth treatments from b56a6a5; logo accent from SVG.
    expected = {
        "--bg": "#0C0E14",
        "--bg-2": "#12151E",
        "--text": "#F2F3F7",
        "--text-mid": "#C0C5D1",
        "--text-dim": "#A0A8BA",
        "--blue": "#08E7BE",
        "--cyan": "#08E7BE",
        "--auth-input-border": "#838B9B",
        "--auth-submit-gradient": "linear-gradient(125deg,var(--action-accent),var(--action-end))",
        "--accent": "#08E7BE",
        "--accent-end": "#02DFB6",
        "--ink": "#080A10",
    }
    for key, value in expected.items():
        assert resolved(key) == value
    assert VALUES["--auth-bg"] == "var(--bg)"
    assert VALUES["--auth-surface"] == "var(--bg-2)"
    assert ":root" not in TOKENS
    assert ".auth-page" in TOKENS


@pytest.mark.parametrize(
    "foreground", ["--text", "--text-mid", "--text-dim", "--blue", "--cyan", "--danger"]
)
@pytest.mark.parametrize("background", ["--bg", "--bg-2"])
def test_auth_text_meets_aa(foreground, background):
    assert (luminance(resolved(foreground)) + 0.05) / (
        luminance(resolved(background)) + 0.05
    ) >= 4.5


@pytest.mark.parametrize("background", ["--action-accent", "--action-end"])
def test_gradient_button_text_meets_aa(background):
    assert (luminance(resolved(background)) + 0.05) / (
        luminance(resolved("--ink")) + 0.05
    ) >= 4.5


def test_all_auth_routes_use_shared_scope_and_player_does_not():
    for component in [
        "auth-form.tsx",
        "forgot-password-form.tsx",
        "reset-password-form.tsx",
    ]:
        assert (
            'className="auth-page"'
            in (ROOT / "web/src/components/auth" / component).read_text()
        )
    assert (
        'className="auth-page"'
        not in (ROOT / "web/src/components/library-app.tsx").read_text()
    )
    theme = (ROOT / "web/src/app/theme.css").read_text()
    assert ".auth-submit" not in theme
    assert ".auth-page" not in theme
