"""Engine configuration from environment / .env (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Config:
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720
    viewport_expansion: int = -1  # -1 = full page (see dom/extractor.js)

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        return cls(
            headless=os.getenv("BROWSER_HEADLESS", "true").lower() != "false",
            viewport_width=int(os.getenv("BROWSER_VIEWPORT_WIDTH", "1280")),
            viewport_height=int(os.getenv("BROWSER_VIEWPORT_HEIGHT", "720")),
        )
