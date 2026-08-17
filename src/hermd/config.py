"""Engine configuration from environment / .env (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class LLMEndpoint:
    """One OpenAI-compatible endpoint in the failover chain."""

    base_url: str
    api_key: str
    model: str


@dataclass
class Config:
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720
    viewport_expansion: int = -1  # -1 = full page (see dom/extractor.js)
    llm_endpoints: list[LLMEndpoint] = field(default_factory=list)
    max_steps: int = 40
    step_delay: float = 0.5
    settle_timeout_ms: int = 3000  # per load-state wait after an action
    popup_grace_ms: int = 150  # event-channel pump so popups surface before settling
    dialog_policy: str = "dismiss"  # or "accept"

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()

        endpoints = []
        for slot in (1, 2, 3):
            base_url = os.getenv(f"LLM_{slot}_BASE_URL", "").strip()
            if not base_url:
                continue
            endpoints.append(
                LLMEndpoint(
                    base_url=base_url.rstrip("/"),
                    api_key=os.getenv(f"LLM_{slot}_API_KEY", "").strip(),
                    model=os.getenv(f"LLM_{slot}_MODEL", "").strip(),
                )
            )

        return cls(
            headless=os.getenv("BROWSER_HEADLESS", "true").lower() != "false",
            viewport_width=int(os.getenv("BROWSER_VIEWPORT_WIDTH", "1280")),
            viewport_height=int(os.getenv("BROWSER_VIEWPORT_HEIGHT", "720")),
            llm_endpoints=endpoints,
            max_steps=int(os.getenv("MAX_STEPS", "40")),
            step_delay=float(os.getenv("STEP_DELAY", "0.5")),
            settle_timeout_ms=int(os.getenv("SETTLE_TIMEOUT_MS", "3000")),
            popup_grace_ms=int(os.getenv("POPUP_GRACE_MS", "150")),
            dialog_policy=os.getenv("DIALOG_POLICY", "dismiss").strip().lower(),
        )
