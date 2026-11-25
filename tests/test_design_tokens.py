"""Verify cross-runtime palette generation and accessible brand pairings."""

import re
from pathlib import Path

import pytest

from design_tokens import PALETTE
from email_smtp import build_email_verification_message, build_password_reset_message
from scripts.generate_design_tokens import generate

ROOT = Path(__file__).resolve().parents[1]


def luminance(color):
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels
    ]
    return sum(v * weight for v, weight in zip(linear, [0.2126, 0.7152, 0.0722]))


@pytest.mark.parametrize(
    "background", ["background", "surface", "surfaceRaised", "surfaceHover", "deep"]
)
@pytest.mark.parametrize(
    "foreground", ["text", "secondary", "muted", "accent", "danger"]
)
def test_text_pairs_meet_aa(foreground, background):
    light, dark = sorted(
        [luminance(PALETTE[foreground]), luminance(PALETTE[background])], reverse=True
    )
    assert (light + 0.05) / (dark + 0.05) >= 4.5


def test_generated_tokens_are_current():
    paths = [
        ROOT / path
        for path in [
            "web/src/app/design-tokens.css",
            "web/public/design-tokens.css",
            "web/src/lib/design-tokens.ts",
            "apple/Vervfy/VervfyApp.swift",
            "web/public/offline.html",
        ]
    ]
    before = [path.read_bytes() for path in paths]
    generate()
    assert before == [path.read_bytes() for path in paths]


@pytest.mark.parametrize(
    "builder,url_key",
    [
        (build_password_reset_message, "reset_url"),
        (build_email_verification_message, "verification_url"),
    ],
)
def test_email_palette_is_inlined(builder, url_key):
    message = builder(
        to_email="audit@example.com",
        mail_from="Vervfy <no-reply@vervfy.com>",
        **{url_key: "https://vervfy.com/reset-password#token=audit"},
    )
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "var(--" not in html
    assert set(re.findall(r"#[\da-fA-F]{6}\b", html)) <= set(PALETTE.values())
    for role in ["background", "surface", "accent", "text", "secondary", "deep"]:
        assert PALETTE[role] in html


@pytest.mark.parametrize("fill", ["accent", "endpoint", "danger"])
@pytest.mark.parametrize("ink", ["background", "deep"])
def test_filled_action_text_meets_aa(fill, ink):
    assert (luminance(PALETTE[fill]) + 0.05) / (luminance(PALETTE[ink]) + 0.05) >= 4.5


def test_shared_accent_uses_exact_logo_gradient():
    logo = (ROOT / "web/public/gemini-svg.svg").read_text()
    stops = re.findall(r'<stop[^>]*stop-color="(#[0-9A-Fa-f]+)"', logo)
    assert PALETTE["accent"] == stops[0]
    assert PALETTE["endpoint"] == stops[-1]
    assert PALETTE["danger"] == "#FF6B7A"


@pytest.mark.parametrize("background", ["background", "surface"])
@pytest.mark.parametrize(
    "foreground,overlay,opacity",
    [
        ("muted", "highlight", 0.10),
        ("danger", "danger", 0.12),
        ("text", "accent", 0.10),
    ],
)
def test_text_on_controls_and_alerts_meets_aa(background, foreground, overlay, opacity):
    base, tint = PALETTE[background], PALETTE[overlay]
    mixed = "#" + "".join(
        f"{round(int(base[i : i + 2], 16) * (1 - opacity) + int(tint[i : i + 2], 16) * opacity):02x}"
        for i in (1, 3, 5)
    )
    assert (luminance(PALETTE[foreground]) + 0.05) / (luminance(mixed) + 0.05) >= 4.5
