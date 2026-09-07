"""Local server entry point."""

from __future__ import annotations

import os

import uvicorn


def run() -> None:
    uvicorn.run(
        "insightpulse_api.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )


if __name__ == "__main__":
    run()
