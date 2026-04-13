"""Smoke-test TradeX API routes (no running server required). Run from backend/: python verify_api.py"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from main import app


def main() -> None:
    failures: list[str] = []
    with TestClient(app) as client:
        # Public routes
        for path in (
            "/health",
            "/price",
            "/market/klines?interval=1h&limit=50",
            "/market/indicators?interval=1h&limit=200",
            "/market/chart-bundle?interval=1h&limit=50",
        ):
            r = client.get(path)
            if r.status_code >= 500:
                failures.append(f"GET {path} -> {r.status_code} {r.text[:200]}")
            if path == "/health" and r.status_code == 200:
                h = r.json()
                if h.get("status") != "ok":
                    failures.append("GET /health: status not ok")
                if "environment" not in h:
                    failures.append("GET /health: missing environment field")

        r = client.get("/portfolio")
        if r.status_code != 401:
            failures.append(f"GET /portfolio without auth -> expected 401, got {r.status_code}")

        email = f"verify_{int(time.time() * 1000)}@example.com"
        r = client.post(
            "/auth/signup",
            json={"email": email, "password": "testpass12", "display_name": "Verify"},
        )
        if r.status_code != 200:
            failures.append(f"POST /auth/signup -> {r.status_code} {r.text[:300]}")
        token = r.json().get("access_token") if r.status_code == 200 else None
        if not token:
            failures.append("signup response missing access_token")
        else:
            auth = {"Authorization": f"Bearer {token}"}

            for path in (
                "/portfolio",
                "/performance",
                "/trades?limit=5",
                "/auto-trading",
                "/auto-trading/pending",
                "/auto-trading/logs?limit=3",
                "/bot-status",
                "/bots/status",
                "/ai-signal",
                "/auth/me",
            ):
                r = client.get(path, headers=auth)
                if r.status_code >= 500:
                    failures.append(f"GET {path} (auth) -> {r.status_code} {r.text[:200]}")
                if r.status_code == 401:
                    failures.append(f"GET {path} (auth) -> unexpected 401")

            r = client.post("/chat", json={"message": "Say OK in one word."}, headers=auth)
            if r.status_code >= 500:
                failures.append(f"POST /chat -> {r.status_code} {r.text[:200]}")

            r = client.post("/auth/login", json={"email": email, "password": "testpass12"})
            if r.status_code != 200:
                failures.append(f"POST /auth/login -> {r.status_code} {r.text[:200]}")

            r = client.patch(
                "/auto-trading",
                headers={**auth, "Content-Type": "application/json"},
                json={"auto_trading_enabled": True},
            )
            if r.status_code != 200:
                failures.append(f"PATCH /auto-trading enable -> {r.status_code} {r.text[:200]}")
            r = client.patch(
                "/auto-trading",
                headers={**auth, "Content-Type": "application/json"},
                json={
                    "auto_trading_enabled": False,
                    "signal_mode": "tradex",
                    "execution_mode": "confirm_before_trade",
                },
            )
            if r.status_code != 200:
                failures.append(f"PATCH /auto-trading reset -> {r.status_code} {r.text[:200]}")

            r = client.get("/ai-signal?mode=tradex", headers=auth)
            if r.status_code != 200:
                failures.append(f"GET /ai-signal?mode=tradex -> {r.status_code} {r.text[:200]}")

            r = client.post(
                "/buy",
                headers={**auth, "Content-Type": "application/json"},
                json={"symbol": "BTCUSDT", "quantity_btc": "0.001"},
            )
            if r.status_code not in (200, 400):
                failures.append(f"POST /buy -> unexpected {r.status_code} {r.text[:200]}")

            r = client.patch(
                "/auth/me/preferences",
                headers={**auth, "Content-Type": "application/json"},
                json={"preferences": {"verify_api": True}},
            )
            if r.status_code != 200:
                failures.append(f"PATCH /auth/me/preferences -> {r.status_code} {r.text[:200]}")
            else:
                prefs = r.json().get("preferences") or {}
                if prefs.get("verify_api") is not True:
                    failures.append("preferences patch did not persist verify_api flag")

        end_ts = int(time.time())
        start_ts = end_ts - 14 * 24 * 3600
        r = client.post(
            "/backtest/run",
            json={
                "symbol": "BTCUSDT",
                "interval": "1h",
                "start_ts": start_ts,
                "end_ts": end_ts,
                "starting_balance_usdt": "100000",
                "signal_mode": "tradex",
                "execution_mode": "full_auto",
                "cooldown_seconds": 3600,
                "max_trade_fraction": "0.1",
                "emergency_stop": False,
            },
        )
        if r.status_code >= 500:
            failures.append(f"POST /backtest/run -> {r.status_code} {r.text[:200]}")
        if r.status_code == 200:
            data = r.json()
            if "equity_curve" not in data or "closed_trades" not in data:
                failures.append("POST /backtest/run missing keys in JSON")

        r = client.get(
            "/health",
            headers={"Origin": "http://localhost:3002"},
        )
        if r.status_code != 200:
            failures.append(f"CORS health with Origin localhost:3002 -> {r.status_code}")
        acao = r.headers.get("access-control-allow-origin")
        if not acao:
            failures.append("Missing Access-Control-Allow-Origin for dev Origin header")

    if failures:
        print("FAIL:\n", "\n".join(failures))
        raise SystemExit(1)
    print("verify_api: all checks passed.")


if __name__ == "__main__":
    main()
