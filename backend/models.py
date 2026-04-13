"""ORM models: users, paper account, trades, positions, bot."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # JSON: chatbot / UI preferences (e.g. {"chat_compact": false})
    preferences_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Encrypted Binance API credentials (Fernet). Null = not connected.
    exchange_api_key_cipher: Mapped[str | None] = mapped_column(Text, nullable=True)
    exchange_secret_cipher: Mapped[str | None] = mapped_column(Text, nullable=True)
    # User explicitly allows mainnet (real money) API host — default False; never implied by keys alone.
    exchange_mainnet_ack: Mapped[bool] = mapped_column(Boolean, default=False)
    # Last exchange API / order error (for UI); cleared on successful connect probe.
    exchange_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped["Account | None"] = relationship(back_populates="user", uselist=False)
    bot_config: Mapped["BotConfig | None"] = relationship(back_populates="user", uselist=False)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True, index=True)
    # USDT cash balance (simulated)
    balance_usdt: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("100000"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User | None"] = relationship(back_populates="account")
    trades: Mapped[list["Trade"]] = relationship(back_populates="account")


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("account_id", "symbol", name="uq_positions_account_symbol"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    quantity_btc: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    avg_entry_price_usdt: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))  # buy | sell
    quantity_btc: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    price_usdt: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    quote_usdt: Mapped[Decimal] = mapped_column(Numeric(24, 8))  # notional (gross)
    fee_usdt: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    realized_pnl_usdt: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Paper only: manual UI vs auto-trader
    source: Mapped[str] = mapped_column(String(16), default="manual", index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    # Which signal engine produced the decision (tradex, local, local_fallback, stop_loss, …); null for manual
    bot_source: Mapped[str | None] = mapped_column(String(32), nullable=True)

    account: Mapped["Account"] = relationship(back_populates="trades")


class BotConfig(Base):
    """Per-user auto-trading settings (paper only)."""

    __tablename__ = "bot_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True, index=True)
    auto_trading_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    cooldown_seconds: Mapped[int] = mapped_column(default=120)
    max_trade_fraction: Mapped[Decimal] = mapped_column(Numeric(12, 8), default=Decimal("0.02"))
    # e.g. 0.05 = exit when unrealized loss reaches -5%; None = disabled
    stop_loss_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    last_trade_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # tradex | local | api (legacy basic/ollama migrated on read)
    signal_mode: Mapped[str] = mapped_column(String(16), default="tradex")
    # signal_only | confirm_before_trade | full_auto — default confirm for safety
    execution_mode: Mapped[str] = mapped_column(String(32), default="confirm_before_trade")
    emergency_stop: Mapped[bool] = mapped_column(Boolean, default=False)
    # Max fraction of day-start equity that can be lost in a UTC day (e.g. 0.05 = 5%); None = off
    daily_loss_limit_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    equity_day_start_usdt: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    equity_day_anchor_utc: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # paper | binance_testnet | binance_live — live uses real funds; default paper only
    trading_venue: Mapped[str] = mapped_column(String(24), default="paper")
    # When venue is not paper, must be True before any order is sent to Binance
    exchange_execution_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Bot-tracked BTC on exchange (for stop-loss % vs avg entry when venue != paper)
    exchange_tracked_qty_btc: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    exchange_avg_entry_usdt: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)

    user: Mapped["User | None"] = relationship(back_populates="bot_config")


class PendingTradeSuggestion(Base):
    """Queued paper trade awaiting user approval (confirm_before_trade mode)."""

    __tablename__ = "pending_trade_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))  # buy | sell
    quantity_btc: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    price_usdt: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    signal_reason: Mapped[str] = mapped_column(String(512), default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    indicators_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    signal_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # pending | approved_executed | rejected | superseded
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)


class AutoTradeLog(Base):
    __tablename__ = "auto_trade_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    signal_action: Mapped[str] = mapped_column(String(8))
    signal_reason: Mapped[str] = mapped_column(String(512))
    result: Mapped[str] = mapped_column(String(32))
    quantity_btc: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    price_usdt: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # JSON: rsi, sma_9, sma_21, trend, driver, rule_reason — same snapshot the bot used
    indicators_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    signal_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
