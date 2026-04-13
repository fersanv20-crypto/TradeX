"""TradeX API — price feed + simulated portfolio."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from config import get_settings
from database import Base, engine, ensure_sqlite_schema, get_db, mark_schema_initialized_externally
from deps import get_current_user
from models import (  # noqa: F401 — register ORM tables
    Account,
    AutoTradeLog,
    BotConfig,
    PendingTradeSuggestion,
    Position,
    Trade,
    User,
)
from schemas import (
    AISignalResponse,
    AuthLoginRequest,
    AuthSignupRequest,
    AuthTokenResponse,
    AutoTradeLogEntry,
    AutoTradingStatus,
    AutoTradingUpdate,
    ExchangeConnectRequest,
    ExchangeMainnetAckRequest,
    ExchangeStatusResponse,
    IntegrationStatusResponse,
    BacktestClosedTradeEntry,
    BacktestEquityPoint,
    BacktestFillEntry,
    BacktestRequest,
    BacktestRunResponse,
    BacktestSafetyEventEntry,
    BotEventSnapshot,
    BotsStatusResponse,
    BotStatusResponse,
    CandleBar,
    ChartBundleResponse,
    ChatRequest,
    ChatResponse,
    MarketIndicatorsResponse,
    OllamaProbePayload,
    PendingTradeEntry,
    PerformanceSummaryResponse,
    PortfolioResponse,
    PositionView,
    TradeHistoryEntry,
    TradeRequest,
    TradeResponse,
    UserBotSummary,
    UserMeResponse,
    UserPreferencesPatch,
)
from services import trading as trading_service
from services.ai_bot import run_trading_signal
from services.auth_service import login_user, register_user
from services.auto_trader import _update_last_trade_at, auto_trading_loop
from services.bot_runner import normalize_bot_type
from services.execution_modes import normalize_execution_mode
from services.bot_status import get_bot_status
from services.chat import run_chat
from services.indicators import compute_ohlcv_indicator_bundle, snapshot_from_closes
from services.backtest import run_backtest
from services.market_data import fetch_closes, fetch_ohlc_bars, fetch_ohlc_bars_range
from services.pending_trades import (
    approve_pending,
    list_pending,
    pending_to_dict,
    reject_pending,
)
from services.ollama_client import probe_ollama
from services.pricing import fetch_btc_usdt_price
from services.integration_snapshot import build_integration_status
from services.user_accounts import ensure_account_for_user, ensure_bot_config_for_user
from services.exchange_crypto import encryption_ready, encrypt_secret
from services.exchange_execution import (
    approve_pending_exchange,
    normalize_trading_venue,
    probe_exchange_keys,
    user_binance_client,
    exchange_equity_usdt,
)

logger = logging.getLogger("tradex.api")

CurrentUser = Annotated[User, Depends(get_current_user)]


def _exchange_keys_configured(user: User) -> bool:
    return bool(getattr(user, "exchange_api_key_cipher", None) and getattr(user, "exchange_secret_cipher", None))


def _parse_user_preferences(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        p = json.loads(raw)
        return p if isinstance(p, dict) else {}
    except json.JSONDecodeError:
        return {}


def _user_me_response(db: Session, user: User) -> UserMeResponse:
    account = ensure_account_for_user(db, user)
    cfg = ensure_bot_config_for_user(db, user)
    sm = normalize_bot_type(getattr(cfg, "signal_mode", None))
    em = normalize_execution_mode(getattr(cfg, "execution_mode", None))
    return UserMeResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at.isoformat() + "Z",
        last_login_at=user.last_login_at.isoformat() + "Z" if user.last_login_at else None,
        preferences=_parse_user_preferences(user.preferences_json),
        paper_balance_usdt=str(account.balance_usdt),
        bot=UserBotSummary(
            signal_mode=sm,  # type: ignore[arg-type]
            execution_mode=em,  # type: ignore[arg-type]
            emergency_stop=bool(getattr(cfg, "emergency_stop", False)),
            auto_trading_enabled=bool(cfg.auto_trading_enabled),
            cooldown_seconds=int(cfg.cooldown_seconds),
            max_trade_fraction=str(cfg.max_trade_fraction),
            stop_loss_pct=str(cfg.stop_loss_pct) if cfg.stop_loss_pct is not None else None,
            daily_loss_limit_pct=str(cfg.daily_loss_limit_pct) if cfg.daily_loss_limit_pct is not None else None,
            trading_venue=normalize_trading_venue(getattr(cfg, "trading_venue", None)),  # type: ignore[arg-type]
            exchange_execution_enabled=bool(getattr(cfg, "exchange_execution_enabled", False)),
        ),
    )


def _auto_status(db: Session, cfg: BotConfig, account: Account, user: User) -> AutoTradingStatus:
    sm = normalize_bot_type(getattr(cfg, "signal_mode", None))
    em = normalize_execution_mode(getattr(cfg, "execution_mode", None))
    venue = normalize_trading_venue(getattr(cfg, "trading_venue", None))
    daily_breached = False
    if cfg.daily_loss_limit_pct is not None and cfg.equity_day_start_usdt is not None:
        if venue == "paper":
            raw = trading_service.build_portfolio(db, account)
            eq = Decimal(str(raw["total_equity_usdt"]))
            start = cfg.equity_day_start_usdt
            if start > 0:
                daily_breached = (eq - start) / start <= -cfg.daily_loss_limit_pct
        else:
            cl = user_binance_client(user, venue)
            if cl is not None:
                try:
                    mk = Decimal(str(fetch_btc_usdt_price()))
                    eq = exchange_equity_usdt(cl, mk)
                    start = cfg.equity_day_start_usdt
                    if start > 0:
                        daily_breached = (eq - start) / start <= -cfg.daily_loss_limit_pct
                except (httpx.HTTPError, TypeError, ValueError, ZeroDivisionError):
                    daily_breached = False
    settings = get_settings()
    return AutoTradingStatus(
        auto_trading_enabled=cfg.auto_trading_enabled,
        signal_mode=sm,  # type: ignore[arg-type]
        execution_mode=em,  # type: ignore[arg-type]
        emergency_stop=bool(getattr(cfg, "emergency_stop", False)),
        cooldown_seconds=cfg.cooldown_seconds,
        max_trade_fraction=str(cfg.max_trade_fraction),
        stop_loss_pct=str(cfg.stop_loss_pct) if cfg.stop_loss_pct is not None else None,
        daily_loss_limit_pct=str(cfg.daily_loss_limit_pct)
        if getattr(cfg, "daily_loss_limit_pct", None) is not None
        else None,
        equity_day_start_usdt=str(cfg.equity_day_start_usdt)
        if getattr(cfg, "equity_day_start_usdt", None) is not None
        else None,
        equity_day_anchor_utc=getattr(cfg, "equity_day_anchor_utc", None),
        daily_loss_breached=daily_breached,
        last_trade_at=cfg.last_trade_at.isoformat() + "Z" if cfg.last_trade_at else None,
        trading_venue=venue,  # type: ignore[arg-type]
        exchange_execution_enabled=bool(getattr(cfg, "exchange_execution_enabled", False)),
        exchange_keys_configured=_exchange_keys_configured(user),
        exchange_mainnet_ack=bool(getattr(user, "exchange_mainnet_ack", False)),
        exchange_max_trade_fraction_cap=str(settings.exchange_max_trade_fraction),
        exchange_last_error=getattr(user, "exchange_last_error", None),
    )


def _build_exchange_status(db: Session, user: User) -> ExchangeStatusResponse:
    cfg = ensure_bot_config_for_user(db, user)
    db.refresh(user)
    venue = normalize_trading_venue(getattr(cfg, "trading_venue", None))
    keys = _exchange_keys_configured(user)
    probe_ok: bool | None = None
    probe_msg: str | None = None
    if keys and encryption_ready():
        try:
            probe_exchange_keys(user, "binance_testnet")
            probe_ok = True
        except Exception as exc:  # noqa: BLE001
            probe_ok = False
            probe_msg = str(exc)[:800]
    return ExchangeStatusResponse(
        encryption_ready=encryption_ready(),
        keys_configured=keys,
        trading_venue=venue,  # type: ignore[arg-type]
        exchange_execution_enabled=bool(getattr(cfg, "exchange_execution_enabled", False)),
        exchange_mainnet_ack=bool(getattr(user, "exchange_mainnet_ack", False)),
        exchange_last_error=getattr(user, "exchange_last_error", None),
        testnet_probe_ok=probe_ok,
        testnet_probe_message=probe_msg,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.environment == "production" and not (settings.jwt_secret or "").strip():
        raise RuntimeError("TRADEX_JWT_SECRET is required when TRADEX_ENVIRONMENT=production")
    log_level = getattr(logging, (settings.log_level or "INFO").upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema()
    mark_schema_initialized_externally()
    task = asyncio.create_task(auto_trading_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="TradeX API", version="0.17.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return JSON 500 for unexpected errors; never take down the ASGI worker."""
    if isinstance(exc, RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": exc.errors()})
    if isinstance(exc, HTTPException):
        detail: object = exc.detail
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    settings = get_settings()
    safe = settings.environment == "production"
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error" if safe else str(exc)},
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _market_indicators_payload(interval: str, limit: int) -> MarketIndicatorsResponse:
    closes = fetch_closes(symbol="BTCUSDT", interval=interval, limit=limit)
    price = fetch_btc_usdt_price()
    snap = snapshot_from_closes(closes)
    tr = snap["trend"]
    if tr not in ("up", "down", "neutral"):
        tr = "neutral"
    rsi_v = snap.get("rsi")
    return MarketIndicatorsResponse(
        interval=interval,
        updated_at=_utc_now_iso(),
        price_usdt=str(price),
        rsi=float(rsi_v) if rsi_v is not None else None,
        sma_9=float(snap["sma_fast"]) if snap["sma_fast"] is not None else None,
        sma_21=float(snap["sma_slow"]) if snap["sma_slow"] is not None else None,
        trend=tr,  # type: ignore[arg-type]
    )

def _apply_cors(application: FastAPI) -> None:
    s = get_settings()
    if s.cors_allow_all:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        return
    kw: dict[str, object] = {
        "allow_origins": s.cors_origin_list(),
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    rx = (s.cors_origin_regex or "").strip()
    vercel_rx = r"https://[\w.-]+\.vercel\.app"
    if getattr(s, "cors_allow_vercel_hosts", False):
        rx = f"({rx})|({vercel_rx})" if rx else vercel_rx
    if rx:
        kw["allow_origin_regex"] = rx
    application.add_middleware(CORSMiddleware, **kw)


_apply_cors(app)


@app.post("/auth/signup", response_model=AuthTokenResponse)
def post_auth_signup(body: AuthSignupRequest, db: Session = Depends(get_db)):
    try:
        _, token = register_user(
            db,
            email=body.email,
            password=body.password,
            display_name=body.display_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuthTokenResponse(access_token=token)


@app.post("/auth/login", response_model=AuthTokenResponse)
def post_auth_login(body: AuthLoginRequest, db: Session = Depends(get_db)):
    try:
        _, token = login_user(db, email=body.email, password=body.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return AuthTokenResponse(access_token=token)


@app.post("/auth/logout")
def post_auth_logout():
    """Client should discard the JWT; included for symmetry with login."""
    return {"ok": True}


@app.get("/auth/me", response_model=UserMeResponse)
def get_auth_me(user: CurrentUser, db: Session = Depends(get_db)):
    return _user_me_response(db, user)


@app.patch("/auth/me/preferences", response_model=UserMeResponse)
def patch_auth_me_preferences(
    body: UserPreferencesPatch,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    cur = _parse_user_preferences(user.preferences_json)
    cur.update(body.preferences)
    user.preferences_json = json.dumps(cur)
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("user_preferences_updated user_id=%s keys=%s", user.id, list(body.preferences.keys()))
    return _user_me_response(db, user)


@app.get("/auto-trading/logs", response_model=list[AutoTradeLogEntry])
def get_auto_trading_logs(
    user: CurrentUser,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    try:
        rows = (
            db.query(AutoTradeLog)
            .filter(AutoTradeLog.user_id == user.id)
            .order_by(AutoTradeLog.created_at.desc())
            .limit(limit)
            .all()
        )
    except Exception as exc:
        logger.exception("auto-trading logs query failed")
        raise HTTPException(status_code=502, detail=f"Logs unavailable: {exc}") from exc
    out: list[AutoTradeLogEntry] = []
    for r in rows:
        ind_raw = getattr(r, "indicators_json", None)
        indicators = None
        if ind_raw:
            try:
                parsed = json.loads(ind_raw)
                indicators = parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                indicators = None
        out.append(
            AutoTradeLogEntry(
                id=r.id,
                created_at=r.created_at.isoformat() + "Z",
                signal_action=r.signal_action,
                signal_reason=r.signal_reason,
                result=r.result,
                quantity_btc=str(r.quantity_btc) if r.quantity_btc is not None else None,
                price_usdt=str(r.price_usdt) if r.price_usdt is not None else None,
                detail=r.detail or "",
                confidence=getattr(r, "confidence", None),
                signal_source=getattr(r, "signal_source", None),
                indicators=indicators,
            )
        )
    return out


@app.get("/trades", response_model=list[TradeHistoryEntry])
def get_trade_history(
    user: CurrentUser,
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
):
    """Paper trade ledger (manual + bot fills)."""
    account = ensure_account_for_user(db, user)
    try:
        rows = (
            db.query(Trade)
            .filter(Trade.account_id == account.id)
            .order_by(Trade.created_at.desc())
            .limit(limit)
            .all()
        )
    except Exception as exc:
        logger.exception("trades query failed")
        raise HTTPException(status_code=502, detail=f"Trades unavailable: {exc}") from exc
    out: list[TradeHistoryEntry] = []
    for t in rows:
        src = getattr(t, "source", None) or "manual"
        reason = getattr(t, "reason", None) or ""
        out.append(
            TradeHistoryEntry(
                id=t.id,
                created_at=t.created_at.isoformat() + "Z",
                symbol=t.symbol,
                side=t.side,
                quantity_btc=str(t.quantity_btc),
                price_usdt=str(t.price_usdt),
                fee_usdt=str(t.fee_usdt),
                source=src,
                reason=reason,
                bot_source=getattr(t, "bot_source", None),
            )
        )
    return out


@app.get("/performance", response_model=PerformanceSummaryResponse)
def get_performance(user: CurrentUser, db: Session = Depends(get_db)):
    """Paper KPIs: balance, equity, P/L, positions, trade count."""
    account = ensure_account_for_user(db, user)
    try:
        raw = trading_service.build_performance_summary(db, account)
        return PerformanceSummaryResponse(
            balance_usdt=raw["balance_usdt"],
            total_equity_usdt=raw["total_equity_usdt"],
            total_unrealized_pnl_usdt=raw["total_unrealized_pnl_usdt"],
            total_realized_pnl_usdt=raw["total_realized_pnl_usdt"],
            total_pnl_usdt=raw["total_pnl_usdt"],
            open_positions_count=raw["open_positions_count"],
            total_trades=raw["total_trades"],
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Price feed error: {exc}") from exc
    except Exception as exc:
        logger.exception("performance summary failed")
        raise HTTPException(status_code=502, detail=f"Performance error: {exc}") from exc


@app.get("/auto-trading", response_model=AutoTradingStatus)
def get_auto_trading(user: CurrentUser, db: Session = Depends(get_db)):
    """Auto-trading settings (paper + optional Binance)."""
    try:
        account = ensure_account_for_user(db, user)
        cfg = ensure_bot_config_for_user(db, user)
        db.refresh(user)
        return _auto_status(db, cfg, account, user)
    except Exception as exc:
        logger.exception("get auto-trading failed")
        raise HTTPException(status_code=502, detail=f"Auto-trading settings error: {exc}") from exc


@app.patch("/auto-trading", response_model=AutoTradingStatus)
def patch_auto_trading(body: AutoTradingUpdate, user: CurrentUser, db: Session = Depends(get_db)):
    """Update auto-trading settings (paper and optional Binance execution)."""
    try:
        account = ensure_account_for_user(db, user)
        cfg = ensure_bot_config_for_user(db, user)
        updates = body.model_dump(exclude_unset=True)
        if "trading_venue" in updates:
            nv = normalize_trading_venue(str(updates["trading_venue"]))
            if nv != "paper" and not _exchange_keys_configured(user):
                raise HTTPException(status_code=400, detail="Save API keys on Connect Exchange before leaving paper.")
            if nv == "binance_testnet":
                try:
                    probe_exchange_keys(user, "binance_testnet")
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
            if nv == "binance_live":
                if not getattr(user, "exchange_mainnet_ack", False):
                    raise HTTPException(
                        status_code=400,
                        detail="Mainnet requires acknowledging real-funds risk on the Exchange page.",
                    )
                try:
                    probe_exchange_keys(user, "binance_live")
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
            cfg.trading_venue = nv
            if nv == "paper":
                cfg.exchange_execution_enabled = False
        if "exchange_execution_enabled" in updates:
            want = bool(updates["exchange_execution_enabled"])
            if want and normalize_trading_venue(getattr(cfg, "trading_venue", None)) == "paper":
                raise HTTPException(
                    status_code=400,
                    detail="Switch trading venue to Binance testnet (or live) before enabling exchange orders.",
                )
            if want and not _exchange_keys_configured(user):
                raise HTTPException(status_code=400, detail="Connect API keys before enabling exchange execution.")
            cfg.exchange_execution_enabled = want
        if "auto_trading_enabled" in updates:
            cfg.auto_trading_enabled = bool(updates["auto_trading_enabled"])
        if "signal_mode" in updates:
            sm = normalize_bot_type(str(updates["signal_mode"]))
            if sm not in ("tradex", "local", "api"):
                raise HTTPException(
                    status_code=400,
                    detail="signal_mode must be 'tradex', 'local', or 'api'",
                )
            cfg.signal_mode = sm
            if sm == "local":
                probe = probe_ollama()
                if not probe.get("available"):
                    logger.warning(
                        "ollama_unreachable_signal_mode_local user_id=%s err=%s",
                        user.id,
                        str(probe.get("error") or "")[:240],
                    )
        if "cooldown_seconds" in updates:
            cfg.cooldown_seconds = int(updates["cooldown_seconds"])
        if "max_trade_fraction" in updates:
            cfg.max_trade_fraction = updates["max_trade_fraction"]
        if "stop_loss_pct" in updates:
            cfg.stop_loss_pct = updates["stop_loss_pct"]
        if "execution_mode" in updates:
            cfg.execution_mode = normalize_execution_mode(str(updates["execution_mode"]))
        if "emergency_stop" in updates:
            cfg.emergency_stop = bool(updates["emergency_stop"])
        if "daily_loss_limit_pct" in updates:
            cfg.daily_loss_limit_pct = updates["daily_loss_limit_pct"]
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
        db.refresh(user)
        logger.info(
            "bot_config_updated user_id=%s auto=%s signal_mode=%s execution_mode=%s venue=%s keys=%s",
            user.id,
            cfg.auto_trading_enabled,
            getattr(cfg, "signal_mode", None),
            getattr(cfg, "execution_mode", None),
            getattr(cfg, "trading_venue", None),
            list(updates.keys()),
        )
        return _auto_status(db, cfg, account, user)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("patch auto-trading failed")
        raise HTTPException(status_code=502, detail=f"Could not save settings: {exc}") from exc


@app.get("/auto-trading/pending", response_model=list[PendingTradeEntry])
def get_pending_trades(user: CurrentUser, db: Session = Depends(get_db)):
    """Paper trades awaiting approval (confirm_before_trade mode)."""
    rows = list_pending(db, user.id)
    out: list[PendingTradeEntry] = []
    for r in rows:
        d = pending_to_dict(r)
        out.append(
            PendingTradeEntry(
                id=int(d["id"]),
                created_at=str(d["created_at"]),
                symbol=str(d["symbol"]),
                side=str(d["side"]),
                quantity_btc=str(d["quantity_btc"]),
                price_usdt=str(d["price_usdt"]),
                signal_reason=str(d["signal_reason"]),
                confidence=d.get("confidence") if isinstance(d.get("confidence"), (int, float)) else None,
                signal_source=str(d["signal_source"]) if d.get("signal_source") else None,
                status=str(d["status"]),
                indicators=d.get("indicators") if isinstance(d.get("indicators"), dict) else None,
            )
        )
    return out


@app.post("/auto-trading/pending/{pending_id}/approve", response_model=TradeResponse)
def post_approve_pending(pending_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    """Execute a queued trade (paper or Binance, depending on trading venue)."""
    account = ensure_account_for_user(db, user)
    cfg = ensure_bot_config_for_user(db, user)
    venue = normalize_trading_venue(getattr(cfg, "trading_venue", None))
    try:
        if venue == "paper":
            trade, account = approve_pending(db, pending_id, account)
        else:
            out = approve_pending_exchange(db, pending_id, user, cfg)
            _update_last_trade_at(db, user.id)
            db.refresh(user)
            return TradeResponse(
                ok=bool(out["ok"]),
                side=str(out["side"]),
                symbol=str(out["symbol"]),
                quantity_btc=str(out["quantity_btc"]),
                price_usdt=str(out["price_usdt"]),
                fee_usdt=str(out["fee_usdt"]),
                balance_usdt=str(out["balance_usdt"]),
                reason=str(out["reason"]),
                venue=str(out["venue"]),
                exchange_order_id=str(out["exchange_order_id"]) if out.get("exchange_order_id") else None,
            )
    except ValueError as exc:
        user.exchange_last_error = str(exc)[:500]
        db.add(user)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Price feed: {exc}") from exc
    _update_last_trade_at(db, user.id)
    user.exchange_last_error = None
    db.add(user)
    db.commit()
    return TradeResponse(
        ok=True,
        side=trade.side,
        symbol=trade.symbol,
        quantity_btc=str(trade.quantity_btc),
        price_usdt=str(trade.price_usdt),
        fee_usdt=str(trade.fee_usdt),
        balance_usdt=str(account.balance_usdt),
        reason=getattr(trade, "reason", None) or "",
        venue="paper",
        exchange_order_id=None,
    )


@app.post("/auto-trading/pending/{pending_id}/reject")
def post_reject_pending(pending_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    """Dismiss a pending suggestion without trading."""
    try:
        reject_pending(db, pending_id, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.get("/exchange/status", response_model=ExchangeStatusResponse)
def get_exchange_status(user: CurrentUser, db: Session = Depends(get_db)):
    """Connection state, venue, and last probe (testnet) — never returns raw keys."""
    return _build_exchange_status(db, user)


@app.post("/exchange/connect", response_model=ExchangeStatusResponse)
def post_exchange_connect(body: ExchangeConnectRequest, user: CurrentUser, db: Session = Depends(get_db)):
    """Store Binance Spot *testnet* keys (encrypted). Keys must be from https://testnet.binance.vision ."""
    if not encryption_ready():
        raise HTTPException(
            status_code=503,
            detail="Server is not configured for encrypted storage (set TRADEX_EXCHANGE_FERNET_KEY).",
        )
    ensure_bot_config_for_user(db, user)
    try:
        user.exchange_api_key_cipher = encrypt_secret(body.api_key.strip())
        user.exchange_secret_cipher = encrypt_secret(body.secret_key.strip())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        probe_exchange_keys(user, "binance_testnet")
    except ValueError as exc:
        user.exchange_api_key_cipher = None
        user.exchange_secret_cipher = None
        user.exchange_last_error = str(exc)[:900]
        db.add(user)
        db.commit()
        raise HTTPException(status_code=400, detail=f"Testnet key check failed: {exc}") from exc
    user.exchange_last_error = None
    db.add(user)
    db.commit()
    return _build_exchange_status(db, user)


@app.delete("/exchange/disconnect", response_model=ExchangeStatusResponse)
def delete_exchange_disconnect(user: CurrentUser, db: Session = Depends(get_db)):
    """Remove stored keys and reset venue to paper-only."""
    cfg = ensure_bot_config_for_user(db, user)
    user.exchange_api_key_cipher = None
    user.exchange_secret_cipher = None
    user.exchange_mainnet_ack = False
    user.exchange_last_error = None
    cfg.trading_venue = "paper"
    cfg.exchange_execution_enabled = False
    db.add(user)
    db.add(cfg)
    db.commit()
    return _build_exchange_status(db, user)


@app.get("/integration/status", response_model=IntegrationStatusResponse)
def get_integration_status(request: Request, user: CurrentUser, db: Session = Depends(get_db)):
    """Dev / support: one JSON snapshot of connectivity, bot, market, paper portfolio (no secrets)."""
    try:
        return build_integration_status(db, user, server_version=request.app.version)
    except Exception as exc:
        logger.exception("integration snapshot failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/exchange/ack-mainnet", response_model=ExchangeStatusResponse)
def post_exchange_ack_mainnet(body: ExchangeMainnetAckRequest, user: CurrentUser, db: Session = Depends(get_db)):
    """Explicit acknowledgement before mainnet venue is allowed (real funds)."""
    _ = body.model_dump()
    user.exchange_mainnet_ack = True
    db.add(user)
    db.commit()
    return _build_exchange_status(db, user)


@app.get("/bot-status", response_model=BotStatusResponse)
def get_bot_status_endpoint(user: CurrentUser, db: Session = Depends(get_db)):
    """Paper bot: toggle state, latest tick log, latest simulated fill."""
    try:
        raw = get_bot_status(db, user)
    except Exception as exc:
        logger.exception("bot-status failed")
        raise HTTPException(status_code=502, detail=f"Bot status error: {exc}") from exc

    def _evt(d: dict | None) -> BotEventSnapshot | None:
        if not d:
            return None
        return BotEventSnapshot(
            created_at=d.get("created_at"),
            signal_action=d.get("signal_action"),
            signal_reason=d.get("signal_reason"),
            result=d.get("result"),
            quantity_btc=d.get("quantity_btc"),
            price_usdt=d.get("price_usdt"),
            detail=d.get("detail") or "",
            confidence=d.get("confidence") if isinstance(d.get("confidence"), (int, float)) else None,
            signal_source=d.get("signal_source") if isinstance(d.get("signal_source"), str) else None,
        )

    return BotStatusResponse(
        auto_trading_enabled=raw["auto_trading_enabled"],
        signal_mode=raw["signal_mode"],
        execution_mode=raw["execution_mode"],
        emergency_stop=raw["emergency_stop"],
        daily_loss_breached=raw["daily_loss_breached"],
        last_event=_evt(raw.get("last_event")),
        last_fill=_evt(raw.get("last_fill")),
    )


@app.get("/bots/status", response_model=BotsStatusResponse)
def get_bots_status(user: CurrentUser, db: Session = Depends(get_db)):
    """Configured signal bot + Ollama HTTP reachability (paper / dev)."""
    cfg = ensure_bot_config_for_user(db, user)
    sm = normalize_bot_type(getattr(cfg, "signal_mode", None))
    raw = probe_ollama()
    return BotsStatusResponse(
        signal_mode=sm,  # type: ignore[arg-type]
        ollama=OllamaProbePayload(
            available=bool(raw["available"]),
            base_url=str(raw["base_url"]),
            model=str(raw["model"]),
            error=str(raw["error"]) if raw.get("error") else None,
        ),
    )


@app.get("/ai-signal", response_model=AISignalResponse)
def get_ai_signal(
    user: CurrentUser,
    db: Session = Depends(get_db),
    mode: str | None = Query(
        None,
        description="tradex | local | api — defaults to server bot selection (legacy basic/ollama accepted)",
    ),
):
    """Trading signal via unified bot runner (TradeX rules, local Ollama, or future API)."""
    cfg = ensure_bot_config_for_user(db, user)
    use = normalize_bot_type(mode or getattr(cfg, "signal_mode", None))
    try:
        raw = run_trading_signal(use)
        ind = raw.get("indicators")
        ctx = raw.get("context")
        return AISignalResponse(
            action=raw["action"],  # type: ignore[arg-type]
            confidence=float(raw["confidence"]),
            reason=str(raw["reason"]),
            source=raw["source"],  # type: ignore[arg-type]
            indicators=ind if isinstance(ind, dict) else None,
            context=ctx if isinstance(ctx, dict) else None,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Market data error: {exc}") from exc
    except Exception as exc:
        logger.exception("ai-signal failed")
        raise HTTPException(status_code=502, detail=f"Signal error: {exc}") from exc


@app.post("/chat", response_model=ChatResponse)
def post_chat(body: ChatRequest, user: CurrentUser, db: Session = Depends(get_db)):
    """Stateless assistant: uses bot signal_mode (TradeX templates or Ollama + context)."""
    try:
        cfg = ensure_bot_config_for_user(db, user)
        bt = normalize_bot_type(getattr(cfg, "signal_mode", None))
        out = run_chat(db, user, body.message, bt)
        logger.info(
            "chat_completed user_id=%s source=%s chars_in=%s chars_out=%s",
            user.id,
            out.get("source"),
            len(body.message or ""),
            len(str(out.get("reply", ""))),
        )
        return ChatResponse(reply=out["reply"], source=out["source"])
    except Exception as exc:
        logger.exception("chat failed")
        raise HTTPException(status_code=502, detail=f"Chat error: {exc}") from exc


@app.get("/price")
def get_btc_usdt_price():
    """Latest BTC price (Binance when possible; Coinbase/CoinGecko fallbacks)."""
    try:
        price = fetch_btc_usdt_price()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Price feed error: {exc}") from exc
    return {"symbol": "BTCUSDT", "price": price}


@app.get("/market/klines", response_model=list[CandleBar])
def get_market_klines(
    interval: str = Query("1h", description="Binance-style interval e.g. 1h, 4h, 1d"),
    limit: int = Query(200, ge=20, le=500),
):
    """OHLCV candles for charts (server-side fetch — avoids browser CORS on Binance)."""
    try:
        bars = fetch_ohlc_bars(symbol="BTCUSDT", interval=interval, limit=limit)
        return [CandleBar(**{**dict(b), "volume": float(b.get("volume", 0) or 0)}) for b in bars]
    except Exception as exc:
        logger.exception("market klines failed")
        raise HTTPException(status_code=502, detail=f"Klines error: {exc}") from exc


@app.get("/market/indicators", response_model=MarketIndicatorsResponse)
def get_market_indicators(
    interval: str = Query("1h", description="Same interval as the paper bot / chart"),
    limit: int = Query(200, ge=50, le=500),
):
    """RSI / SMA / trend snapshot from the same close series as the bot (paper)."""
    try:
        return _market_indicators_payload(interval=interval, limit=limit)
    except Exception as exc:
        logger.exception("market indicators failed")
        raise HTTPException(status_code=502, detail=f"Indicators error: {exc}") from exc


@app.get("/market/chart-bundle", response_model=ChartBundleResponse)
def get_market_chart_bundle(
    interval: str = Query("1h", description="Binance-style interval e.g. 1h, 15m"),
    limit: int = Query(200, ge=20, le=500),
):
    """OHLCV + per-bar RSI/SMA series — single payload for live chart + dashboard (paper)."""
    try:
        raw = fetch_ohlc_bars(symbol="BTCUSDT", interval=interval, limit=limit)
        price = fetch_btc_usdt_price()
        bundle = compute_ohlcv_indicator_bundle(raw)
        snap = bundle["snapshot"]
        assert isinstance(snap, dict)
        tr = snap.get("trend", "neutral")
        if tr not in ("up", "down", "neutral"):
            tr = "neutral"
        rsi_v = snap.get("rsi")
        status = MarketIndicatorsResponse(
            interval=interval,
            updated_at=_utc_now_iso(),
            price_usdt=str(price),
            rsi=float(rsi_v) if rsi_v is not None else None,
            sma_9=float(snap["sma_fast"]) if snap.get("sma_fast") is not None else None,
            sma_21=float(snap["sma_slow"]) if snap.get("sma_slow") is not None else None,
            trend=tr,  # type: ignore[arg-type]
        )
        bars_out: list[CandleBar] = []
        for b in raw:
            d = dict(b)
            d["volume"] = float(d.get("volume", 0) or 0)
            bars_out.append(CandleBar(**d))
        rsi_s = bundle["rsi_series"]
        s9 = bundle["sma_9_series"]
        s21 = bundle["sma_21_series"]
        assert isinstance(rsi_s, list) and isinstance(s9, list) and isinstance(s21, list)
        return ChartBundleResponse(
            status=status,
            bars=bars_out,
            rsi_series=[float(x) if x is not None else None for x in rsi_s],
            sma_9_series=[float(x) if x is not None else None for x in s9],
            sma_21_series=[float(x) if x is not None else None for x in s21],
        )
    except Exception as exc:
        logger.exception("chart bundle failed")
        raise HTTPException(status_code=502, detail=f"Chart bundle error: {exc}") from exc


@app.get("/portfolio", response_model=PortfolioResponse)
def get_portfolio(user: CurrentUser, db: Session = Depends(get_db)):
    """Paper account: balance, positions, equity, and P/L (mark-to-market)."""
    account = ensure_account_for_user(db, user)
    try:
        raw = trading_service.build_portfolio(db, account)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Price feed error: {exc}") from exc
    except Exception as exc:
        logger.exception("portfolio build failed")
        raise HTTPException(status_code=502, detail=f"Portfolio error: {exc}") from exc
    return PortfolioResponse(
        balance_usdt=raw["balance_usdt"],
        positions_market_value_usdt=raw["positions_market_value_usdt"],
        total_equity_usdt=raw["total_equity_usdt"],
        total_unrealized_pnl_usdt=raw["total_unrealized_pnl_usdt"],
        total_realized_pnl_usdt=raw["total_realized_pnl_usdt"],
        positions=[PositionView(**p) for p in raw["positions"]],
    )


@app.post("/buy", response_model=TradeResponse)
def post_buy(body: TradeRequest, user: CurrentUser, db: Session = Depends(get_db)):
    """Simulated market buy at latest Binance BTC/USDT price."""
    symbol = body.symbol.strip().upper()
    account = ensure_account_for_user(db, user)
    try:
        trade, account = trading_service.execute_trade(
            db, account, side="buy", symbol=symbol, quantity_btc=body.quantity_btc
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Price feed error: {exc}") from exc
    except Exception as exc:
        logger.exception("buy failed")
        raise HTTPException(status_code=502, detail=f"Trade error: {exc}") from exc
    logger.info(
        "manual_paper_trade user_id=%s side=buy symbol=%s qty_btc=%s price_usdt=%s balance_usdt=%s",
        user.id,
        trade.symbol,
        str(trade.quantity_btc),
        str(trade.price_usdt),
        str(account.balance_usdt),
    )
    return TradeResponse(
        ok=True,
        side="buy",
        symbol=trade.symbol,
        quantity_btc=str(trade.quantity_btc),
        price_usdt=str(trade.price_usdt),
        fee_usdt=str(trade.fee_usdt),
        balance_usdt=str(account.balance_usdt),
        reason=getattr(trade, "reason", None) or "",
        venue="paper",
        exchange_order_id=None,
    )


@app.post("/sell", response_model=TradeResponse)
def post_sell(body: TradeRequest, user: CurrentUser, db: Session = Depends(get_db)):
    """Simulated market sell at latest Binance BTC/USDT price."""
    symbol = body.symbol.strip().upper()
    account = ensure_account_for_user(db, user)
    try:
        trade, account = trading_service.execute_trade(
            db, account, side="sell", symbol=symbol, quantity_btc=body.quantity_btc
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Price feed error: {exc}") from exc
    except Exception as exc:
        logger.exception("sell failed")
        raise HTTPException(status_code=502, detail=f"Trade error: {exc}") from exc
    logger.info(
        "manual_paper_trade user_id=%s side=sell symbol=%s qty_btc=%s price_usdt=%s balance_usdt=%s",
        user.id,
        trade.symbol,
        str(trade.quantity_btc),
        str(trade.price_usdt),
        str(account.balance_usdt),
    )
    return TradeResponse(
        ok=True,
        side="sell",
        symbol=trade.symbol,
        quantity_btc=str(trade.quantity_btc),
        price_usdt=str(trade.price_usdt),
        fee_usdt=str(trade.fee_usdt),
        balance_usdt=str(account.balance_usdt),
        reason=getattr(trade, "reason", None) or "",
        venue="paper",
        exchange_order_id=None,
    )


@app.post("/backtest/run", response_model=BacktestRunResponse)
def post_backtest_run(body: BacktestRequest):
    """
    Replay paper rules on historical OHLCV with optional safety limits.
    TradeX uses deterministic RSI+MA; local runs Ollama per bar (capped window); API stub returns HOLD.
    """
    symbol = body.symbol.strip().upper()
    interval = body.interval.strip()
    try:
        bars = fetch_ohlc_bars_range(
            symbol=symbol,
            interval=interval,
            start_ts=body.start_ts,
            end_ts=body.end_ts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("backtest candle fetch failed")
        raise HTTPException(status_code=502, detail=f"Historical data error: {exc}") from exc

    params = {
        "symbol": symbol,
        "interval": interval,
        "starting_balance_usdt": str(body.starting_balance_usdt),
        "signal_mode": body.signal_mode,
        "execution_mode": body.execution_mode,
        "cooldown_seconds": body.cooldown_seconds,
        "max_trade_fraction": str(body.max_trade_fraction),
        "stop_loss_pct": str(body.stop_loss_pct) if body.stop_loss_pct is not None else None,
        "daily_loss_limit_pct": str(body.daily_loss_limit_pct) if body.daily_loss_limit_pct is not None else None,
        "emergency_stop": body.emergency_stop,
    }
    try:
        raw = run_backtest(bars, params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("backtest simulation failed")
        raise HTTPException(status_code=502, detail=f"Backtest error: {exc}") from exc

    fills_out = [BacktestFillEntry(**f) for f in raw["fills"]]
    closed_out = [BacktestClosedTradeEntry(**c) for c in raw["closed_trades"]]
    curve_out = [BacktestEquityPoint(**p) for p in raw["equity_curve"]]
    safety_out = [
        BacktestSafetyEventEntry(
            bar_time=int(s["bar_time"]),
            event_type=str(s["event_type"]),
            detail=str(s["detail"]),
            price_usdt=s.get("price_usdt"),
            signal_action=s.get("signal_action"),
        )
        for s in raw["safety_events"]
    ]

    logger.info(
        "backtest_run symbol=%s interval=%s bars_used=%s fills=%s signal_mode=%s execution_mode=%s",
        symbol,
        interval,
        int(raw["bars_used"]),
        int(raw["total_fills"]),
        body.signal_mode,
        body.execution_mode,
    )

    return BacktestRunResponse(
        symbol=symbol,
        interval=interval,
        start_ts=body.start_ts,
        end_ts=body.end_ts,
        bars_used=int(raw["bars_used"]),
        signal_mode=body.signal_mode,
        execution_mode=str(body.execution_mode),
        strategy_note=str(raw.get("strategy_note") or ""),
        confirm_mode_note=str(raw.get("confirm_mode_note") or ""),
        starting_balance_usdt=str(body.starting_balance_usdt),
        ending_balance_usdt=str(raw["ending_balance_usdt"]),
        ending_equity_usdt=str(raw["ending_equity_usdt"]),
        ending_qty_btc=str(raw["ending_qty_btc"]),
        total_return_pct=str(raw["total_return_pct"]),
        total_fills=int(raw["total_fills"]),
        total_sells=int(raw["total_sells"]),
        winning_sells=int(raw["winning_sells"]),
        win_rate_pct=str(raw["win_rate_pct"]),
        max_drawdown_pct=str(raw["max_drawdown_pct"]),
        best_trade_usdt=raw.get("best_trade_usdt"),
        worst_trade_usdt=raw.get("worst_trade_usdt"),
        fills=fills_out,
        closed_trades=closed_out,
        equity_curve=curve_out,
        safety_events=safety_out,
    )


@app.get("/health")
def health():
    """Liveness: version, environment, and service id for load balancers and deployments."""
    s = get_settings()
    return {
        "status": "ok",
        "service": "tradex-api",
        "version": app.version,
        "environment": s.environment,
    }
