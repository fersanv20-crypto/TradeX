"""
TradeX API entrypoint for production and PaaS (e.g. Render).

Port resolution (first match wins):
  1. PORT  — set by Render, Fly.io, Railway, etc.
  2. TRADEX_PORT — optional explicit override
  3. 10000 — local default

Usage:
  python run.py
  uvicorn main:app --host 0.0.0.0 --port 10000   # equivalent when PORT unset
"""

from __future__ import annotations

import os

import uvicorn


def _port() -> int:
    raw = os.environ.get("PORT") or os.environ.get("TRADEX_PORT") or "10000"
    try:
        p = int(raw)
    except ValueError:
        return 10000
    return max(1, min(65535, p))


def main() -> None:
    try:
        w = int(os.environ.get("WEB_CONCURRENCY") or "1")
    except ValueError:
        w = 1
    workers = max(1, min(32, w))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=_port(),
        proxy_headers=True,
        forwarded_allow_ips="*",
        access_log=True,
        workers=workers,
    )


if __name__ == "__main__":
    main()
