"""Shared brand palette for server-rendered content."""

import json
from pathlib import Path

PALETTE = json.loads(Path(__file__).with_name("design-tokens.json").read_text())
