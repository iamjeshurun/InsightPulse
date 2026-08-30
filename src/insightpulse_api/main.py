"""Local server entry point."""

from __future__ import annotations

import uvicorn


def run() -> None:
    uvicorn.run("insightpulse_api.app:create_app", factory=True, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
