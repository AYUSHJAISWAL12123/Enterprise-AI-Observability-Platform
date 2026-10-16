"""Entry point for running the gateway with uvicorn.

This module is intentionally thin — it only constructs the app and hands
it to uvicorn.  All configuration is loaded inside the lifespan.
"""

import uvicorn

from gateway.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "gateway.main:app",
        host="0.0.0.0",  # noqa: S104 — intentional; container networking
        port=8080,
        log_config=None,  # structlog handles logging; disable uvicorn's config
    )
