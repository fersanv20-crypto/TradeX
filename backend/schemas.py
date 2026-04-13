"""Pydantic request/response models."""

from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator


class TradeRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT", min_length=6, max_length=32)
    quantity_btc: Decimal = Field(
        gt=0,
        description="BTC amount; at execution price, notional must be at least 5 USDT (same floor as the auto-trader).",
    )


class PositionView(BaseModel):
    symbol: str
    quantity_btc: str
    avg_entry_price_usdt: str
    mark_price_usdt: str
    market_value_usdt: str
    unrealized_pnl_usdt: str
    unrealized_pnl_pct: str


class PortfolioResponse(BaseModel):
    balance_usdt: str
    positions_market_value_usdt: str
    total_equity_usdt: str
    total_unrealized_pnl_usdt: str
    total_realized_pnl_usdt: str
    positions: list[PositionView]


class TradeResponse(BaseModel):
    ok: bool
    side: str
    symbol: str
    quantity_btc: str
    price_usdt: str
    fee_usdt: str
    balance_usdt: str
    reason: str = ""
    venue: str | None = None
    exchange_order_id: str | None = None


class AISignalResponse(BaseModel):
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    source: Literal["tradex", "local", "local_fallback", "api_unavailable"]
    indicators: dict[str, Any] | None = None
    context: dict[str, Any] | None = None


ExecutionMode = Literal["signal_only", "confirm_before_trade", "full_auto"]


TradingVenue = Literal["paper", "binance_testnet", "binance_live"]


class AutoTradingStatus(BaseModel):
    auto_trading_enabled: bool
    signal_mode: Literal["tradex", "local", "api"]
    execution_mode: ExecutionMode
    emergency_stop: bool
    cooldown_seconds: int
    max_trade_fraction: str
    stop_loss_pct: str | None
    daily_loss_limit_pct: str | None
    equity_day_start_usdt: str | None
    equity_day_anchor_utc: str | None
    daily_loss_breached: bool
    last_trade_at: str | None
    trading_venue: TradingVenue = "paper"
    exchange_execution_enabled: bool = False
    exchange_keys_configured: bool = False
    exchange_mainnet_ack: bool = False
    exchange_max_trade_fraction_cap: str = "0.02"
    exchange_last_error: str | None = None


class AutoTradingUpdate(BaseModel):
    auto_trading_enabled: bool | None = None
    signal_mode: Literal["tradex", "local", "api"] | None = None
    execution_mode: ExecutionMode | None = None
    emergency_stop: bool | None = None
    trading_venue: TradingVenue | None = None
    exchange_execution_enabled: bool | None = None
    cooldown_seconds: int | None = Field(default=None, ge=30, le=3600)
    max_trade_fraction: Decimal | None = Field(default=None, ge=Decimal("0.01"), le=Decimal("1"))
    stop_loss_pct: Decimal | None = Field(
        default=None,
        description="Fraction e.g. 0.05 = 5% drawdown from entry; set null to disable",
    )
    daily_loss_limit_pct: Decimal | None = Field(
        default=None,
        description="Max fraction of day-start equity that may be lost in a UTC day; null disables",
    )

    @field_validator("stop_loss_pct")
    @classmethod
    def validate_stop_loss(cls, v: Decimal | None) -> Decimal | None:
        if v is None:
            return v
        if v < Decimal("0.001") or v > Decimal("0.99"):
            raise ValueError("stop_loss_pct must be between 0.001 and 0.99")
        return v

    @field_validator("daily_loss_limit_pct")
    @classmethod
    def validate_daily_loss(cls, v: Decimal | None) -> Decimal | None:
        if v is None:
            return v
        if v < Decimal("0.001") or v > Decimal("0.99"):
            raise ValueError("daily_loss_limit_pct must be between 0.001 and 0.99")
        return v


class PendingTradeEntry(BaseModel):
    id: int
    created_at: str
    symbol: str
    side: str
    quantity_btc: str
    price_usdt: str
    signal_reason: str
    confidence: float | None = None
    signal_source: str | None = None
    status: str
    indicators: dict[str, Any] | None = None


class AutoTradeLogEntry(BaseModel):
    id: int
    created_at: str
    signal_action: str
    signal_reason: str
    result: str
    quantity_btc: str | None
    price_usdt: str | None
    detail: str
    confidence: float | None = None
    signal_source: str | None = None
    # Parsed from DB `indicators_json` when present (rsi, sma_9, sma_21, trend, driver, …)
    indicators: dict[str, Any] | None = None


class TradeHistoryEntry(BaseModel):
    """One simulated fill (manual or bot)."""

    id: int
    created_at: str
    symbol: str
    side: str
    quantity_btc: str
    price_usdt: str
    fee_usdt: str
    source: str
    reason: str
    bot_source: str | None = None


class CandleBar(BaseModel):
    """Unix time (seconds) + OHLCV for charting."""

    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class MarketIndicatorsResponse(BaseModel):
    """Live snapshot (same closes feed as the paper bot)."""

    interval: str
    updated_at: str
    price_usdt: str
    rsi: float | None = None
    sma_9: float | None = None
    sma_21: float | None = None
    trend: Literal["up", "down", "neutral"] = "neutral"


class ChartBundleResponse(BaseModel):
    """OHLCV bars + per-bar indicator series + same `status` shape as GET /market/indicators."""

    status: MarketIndicatorsResponse
    bars: list[CandleBar]
    rsi_series: list[float | None]
    sma_9_series: list[float | None]
    sma_21_series: list[float | None]


class PerformanceSummaryResponse(BaseModel):
    balance_usdt: str
    total_equity_usdt: str
    total_unrealized_pnl_usdt: str
    total_realized_pnl_usdt: str
    total_pnl_usdt: str
    open_positions_count: int
    total_trades: int


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    reply: str
    source: Literal["tradex", "local", "local_fallback", "api_unavailable"]


class BotEventSnapshot(BaseModel):
    created_at: str | None = None
    signal_action: str | None = None
    signal_reason: str | None = None
    result: str | None = None
    quantity_btc: str | None = None
    price_usdt: str | None = None
    detail: str = ""
    confidence: float | None = None
    signal_source: str | None = None


class BotStatusResponse(BaseModel):
    """Paper auto-trader: toggle state + latest log-derived signal and fill."""

    auto_trading_enabled: bool
    signal_mode: Literal["tradex", "local", "api"]
    execution_mode: ExecutionMode
    emergency_stop: bool
    daily_loss_breached: bool
    last_event: BotEventSnapshot | None
    last_fill: BotEventSnapshot | None


class BacktestRequest(BaseModel):
    """Replay RSI+MA strategy on historical OHLCV (paper)."""

    symbol: str = Field(default="BTCUSDT", min_length=6, max_length=32)
    interval: str = Field(default="1h", description="1m, 5m, 15m, 1h, 4h, 1d")
    start_ts: int = Field(..., description="Range start (Unix seconds UTC, candle open times)")
    end_ts: int = Field(..., description="Range end (Unix seconds UTC)")
    starting_balance_usdt: Decimal = Field(default=Decimal("100000"), gt=Decimal("0"))
    signal_mode: Literal["tradex", "local", "api"] = "tradex"
    execution_mode: ExecutionMode = "confirm_before_trade"
    cooldown_seconds: int = Field(default=120, ge=0, le=86400 * 7)
    max_trade_fraction: Decimal = Field(default=Decimal("0.10"), ge=Decimal("0.01"), le=Decimal("1"))
    stop_loss_pct: Decimal | None = Field(
        default=None,
        description="Optional fraction unrealized loss from avg entry to force exit",
    )
    daily_loss_limit_pct: Decimal | None = Field(
        default=None,
        description="Optional max loss vs UTC day-start equity (same as live bot)",
    )
    emergency_stop: bool = False

    @model_validator(mode="after")
    def check_range(self) -> "BacktestRequest":
        if self.end_ts <= self.start_ts:
            raise ValueError("end_ts must be greater than start_ts")
        max_span = 86400 * 400
        if self.end_ts - self.start_ts > max_span:
            raise ValueError("Time range too large (max ~400 days)")
        return self

    @field_validator("stop_loss_pct", "daily_loss_limit_pct")
    @classmethod
    def validate_pct(cls, v: Decimal | None) -> Decimal | None:
        if v is None:
            return v
        if v < Decimal("0.001") or v > Decimal("0.99"):
            raise ValueError("percentage must be between 0.001 and 0.99")
        return v


class BacktestFillEntry(BaseModel):
    time: int
    side: str
    quantity_btc: str
    price_usdt: str
    fee_usdt: str
    reason: str
    driver: str = ""
    realized_pnl_usdt: str | None = None
    indicators: dict[str, Any] | None = None
    signal_source: str | None = None
    signal_confidence: float | None = None
    safety: str | None = None


class BacktestClosedTradeEntry(BaseModel):
    entry_time: int
    exit_time: int
    quantity_btc: str
    entry_avg_price_usdt: str
    exit_price_usdt: str
    realized_pnl_usdt: str
    reason: str
    driver: str = ""
    indicators: dict[str, Any] | None = None
    signal_source: str | None = None
    signal_confidence: float | None = None
    safety: str | None = None


class OllamaProbePayload(BaseModel):
    available: bool
    base_url: str
    model: str
    error: str | None = None


class BotsStatusResponse(BaseModel):
    """Active bot selection + local LLM reachability (paper only)."""

    signal_mode: Literal["tradex", "local", "api"]
    ollama: OllamaProbePayload


class BacktestEquityPoint(BaseModel):
    time: int
    equity_usdt: str


class BacktestSafetyEventEntry(BaseModel):
    bar_time: int
    event_type: str
    detail: str
    price_usdt: str | None = None
    signal_action: str | None = None


class AuthSignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=256)
    display_name: str | None = Field(default=None, max_length=128)


class AuthLoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=256)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserBotSummary(BaseModel):
    signal_mode: Literal["tradex", "local", "api"]
    execution_mode: ExecutionMode
    emergency_stop: bool
    auto_trading_enabled: bool
    cooldown_seconds: int
    max_trade_fraction: str
    stop_loss_pct: str | None
    daily_loss_limit_pct: str | None
    trading_venue: TradingVenue = "paper"
    exchange_execution_enabled: bool = False


class UserMeResponse(BaseModel):
    id: int
    email: str
    display_name: str | None
    created_at: str
    last_login_at: str | None
    preferences: dict[str, Any]
    paper_balance_usdt: str
    bot: UserBotSummary


class UserPreferencesPatch(BaseModel):
    preferences: dict[str, Any] = Field(default_factory=dict)


class BacktestRunResponse(BaseModel):
    symbol: str
    interval: str
    start_ts: int
    end_ts: int
    bars_used: int
    signal_mode: str
    execution_mode: str
    strategy_note: str = ""
    confirm_mode_note: str = ""
    starting_balance_usdt: str
    ending_balance_usdt: str
    ending_equity_usdt: str
    ending_qty_btc: str
    total_return_pct: str
    total_fills: int
    total_sells: int
    winning_sells: int
    win_rate_pct: str
    max_drawdown_pct: str
    best_trade_usdt: str | None
    worst_trade_usdt: str | None
    fills: list[BacktestFillEntry]
    closed_trades: list[BacktestClosedTradeEntry]
    equity_curve: list[BacktestEquityPoint]
    safety_events: list[BacktestSafetyEventEntry]


class ExchangeConnectRequest(BaseModel):
    api_key: str = Field(..., min_length=8, max_length=256)
    secret_key: str = Field(..., min_length=8, max_length=256)
    """Keys must be from Binance Spot Testnet (https://testnet.binance.vision)."""
    confirm_testnet_keys: bool = Field(
        default=False,
        description="Must be true: confirms keys are testnet keys, not mainnet.",
    )

    @model_validator(mode="after")
    def _require_testnet_confirm(self) -> Self:
        if not self.confirm_testnet_keys:
            raise ValueError("confirm_testnet_keys must be true (connect only with Binance Spot testnet keys)")
        return self


class ExchangeStatusResponse(BaseModel):
    encryption_ready: bool
    keys_configured: bool
    trading_venue: TradingVenue
    exchange_execution_enabled: bool
    exchange_mainnet_ack: bool
    exchange_last_error: str | None
    testnet_probe_ok: bool | None = None
    testnet_probe_message: str | None = None


class ExchangeMainnetAckRequest(BaseModel):
    """Explicit opt-in before mainnet venue is allowed."""

    acknowledge_risk_of_real_funds: bool = Field(
        default=False,
        description="Must be true to set exchange_mainnet_ack on the account.",
    )

    @model_validator(mode="after")
    def _require_ack(self) -> Self:
        if not self.acknowledge_risk_of_real_funds:
            raise ValueError("acknowledge_risk_of_real_funds must be true")
        return self


class IntegrationStatusResponse(BaseModel):
    """Single-call snapshot for dev / integration debugging (no secrets)."""

    server_version: str
    environment: str
    user_email: str | None = None
    partial_errors: list[str] = Field(default_factory=list)
    price_usdt: str | None = None
    total_equity_usdt: str | None = None
    bot_signal_mode: str | None = None
    bot_execution_mode: str | None = None
    bot_auto_trading: bool | None = None
    bot_emergency_stop: bool | None = None
    trading_venue: str | None = None
    exchange_execution_enabled: bool | None = None
    exchange_keys_configured: bool = False
    encryption_ready: bool = False
    exchange_last_error: str | None = None
    ollama_available: bool | None = None
    ollama_error: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    latest_bot_tick: dict[str, Any] | None = None
    recent_trades_count: int = 0
