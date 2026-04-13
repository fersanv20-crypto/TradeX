"""Database engine and session (SQLite by default; set TRADEX_DATABASE_URL for Postgres, etc.)."""

import os
import threading
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Store DB next to package so cwd does not matter as much
_DATA_DIR = Path(__file__).resolve().parent / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_DEFAULT_SQLITE = f"sqlite:///{_DATA_DIR / 'tradex.db'}"


def _normalize_database_url(url: str) -> str:
    """Use psycopg v3 for bare postgres:// / postgresql:// URLs (Render, Railway, etc.)."""
    u = url.strip()
    if not u:
        return u
    lower = u.lower()
    if lower.startswith("sqlite"):
        return u
    if lower.startswith("postgres://"):
        return "postgresql+psycopg://" + u[len("postgres://") :]
    if lower.startswith("postgresql://"):
        scheme_end = u.find("://")
        if scheme_end == -1:
            return u
        scheme = u[:scheme_end].lower()
        if "+" in scheme:
            return u
        return "postgresql+psycopg://" + u[scheme_end + 3 :]
    return u


def _resolve_database_url() -> str:
    """Prefer TRADEX_DATABASE_URL, then DATABASE_URL (Render Postgres), Settings, else SQLite."""
    env_url = (os.environ.get("TRADEX_DATABASE_URL") or os.environ.get("DATABASE_URL") or "").strip()
    if env_url:
        return _normalize_database_url(env_url)
    try:
        from config import get_settings

        cfg_url = (get_settings().database_url or "").strip()
        if cfg_url:
            return _normalize_database_url(cfg_url)
    except Exception:  # noqa: BLE001 — import/settings must never block engine creation
        pass
    return _DEFAULT_SQLITE


DATABASE_URL = _resolve_database_url()

_engine_kw: dict[str, object] = {}
if DATABASE_URL.startswith("sqlite"):
    _engine_kw["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kw)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


_schema_init_lock = threading.Lock()
_schema_initialized = False


def mark_schema_initialized_externally() -> None:
    """Call from app lifespan after create_all + ensure_sqlite_schema so get_db() skips duplicate work."""
    global _schema_initialized
    with _schema_init_lock:
        _schema_initialized = True


def _ensure_app_schema() -> None:
    """Create tables + run SQLite migrations before first ORM use (covers TestClient without lifespan)."""
    global _schema_initialized
    if _schema_initialized:
        return
    with _schema_init_lock:
        if _schema_initialized:
            return
        Base.metadata.create_all(bind=engine)
        ensure_sqlite_schema()
        _schema_initialized = True


def get_db():
    _ensure_app_schema()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_sqlite_schema() -> None:
    """Lightweight migrations for SQLite (add missing columns)."""
    insp = inspect(engine)
    with engine.connect() as conn:
        if insp.has_table("users"):
            uc = {c["name"] for c in insp.get_columns("users")}
            if "exchange_api_key_cipher" not in uc:
                conn.execute(text("ALTER TABLE users ADD COLUMN exchange_api_key_cipher TEXT"))
                conn.commit()
            if "exchange_secret_cipher" not in uc:
                conn.execute(text("ALTER TABLE users ADD COLUMN exchange_secret_cipher TEXT"))
                conn.commit()
            if "exchange_mainnet_ack" not in uc:
                conn.execute(text("ALTER TABLE users ADD COLUMN exchange_mainnet_ack BOOLEAN DEFAULT 0"))
                conn.commit()
            if "exchange_last_error" not in uc:
                conn.execute(text("ALTER TABLE users ADD COLUMN exchange_last_error TEXT"))
                conn.commit()

        if not insp.has_table("bot_config"):
            _migrate_positions_composite_unique(conn, insp)
            return

        cols = {c["name"] for c in insp.get_columns("bot_config")}
        if "signal_mode" not in cols:
            conn.execute(
                text("ALTER TABLE bot_config ADD COLUMN signal_mode VARCHAR(16) DEFAULT 'basic'")
            )
            conn.commit()
        if insp.has_table("trades"):
            tc = {c["name"] for c in insp.get_columns("trades")}
            if "source" not in tc:
                conn.execute(text("ALTER TABLE trades ADD COLUMN source VARCHAR(16) DEFAULT 'manual'"))
                conn.commit()
            tc = {c["name"] for c in insp.get_columns("trades")}
            if "reason" not in tc:
                conn.execute(text("ALTER TABLE trades ADD COLUMN reason TEXT DEFAULT ''"))
                conn.commit()
        cols_bc = {c["name"] for c in insp.get_columns("bot_config")}
        if "execution_mode" not in cols_bc:
            conn.execute(
                text("ALTER TABLE bot_config ADD COLUMN execution_mode VARCHAR(32) DEFAULT 'full_auto'")
            )
            conn.commit()
        cols_bc = {c["name"] for c in insp.get_columns("bot_config")}
        if "emergency_stop" not in cols_bc:
            conn.execute(text("ALTER TABLE bot_config ADD COLUMN emergency_stop BOOLEAN DEFAULT 0"))
            conn.commit()
        cols_bc = {c["name"] for c in insp.get_columns("bot_config")}
        if "daily_loss_limit_pct" not in cols_bc:
            conn.execute(text("ALTER TABLE bot_config ADD COLUMN daily_loss_limit_pct NUMERIC(12,8)"))
            conn.commit()
        cols_bc = {c["name"] for c in insp.get_columns("bot_config")}
        if "equity_day_start_usdt" not in cols_bc:
            conn.execute(text("ALTER TABLE bot_config ADD COLUMN equity_day_start_usdt NUMERIC(24,8)"))
            conn.commit()
        cols_bc = {c["name"] for c in insp.get_columns("bot_config")}
        if "equity_day_anchor_utc" not in cols_bc:
            conn.execute(text("ALTER TABLE bot_config ADD COLUMN equity_day_anchor_utc VARCHAR(16)"))
            conn.commit()
        if insp.has_table("auto_trade_logs"):
            ac = {c["name"] for c in insp.get_columns("auto_trade_logs")}
            if "confidence" not in ac:
                conn.execute(text("ALTER TABLE auto_trade_logs ADD COLUMN confidence FLOAT"))
                conn.commit()
            ac = {c["name"] for c in insp.get_columns("auto_trade_logs")}
            if "indicators_json" not in ac:
                conn.execute(text("ALTER TABLE auto_trade_logs ADD COLUMN indicators_json TEXT"))
                conn.commit()
            ac = {c["name"] for c in insp.get_columns("auto_trade_logs")}
            if "signal_source" not in ac:
                conn.execute(text("ALTER TABLE auto_trade_logs ADD COLUMN signal_source VARCHAR(32)"))
                conn.commit()
        if insp.has_table("trades"):
            tc = {c["name"] for c in insp.get_columns("trades")}
            if "bot_source" not in tc:
                conn.execute(text("ALTER TABLE trades ADD COLUMN bot_source VARCHAR(32)"))
                conn.commit()
        if insp.has_table("pending_trade_suggestions"):
            pc = {c["name"] for c in insp.get_columns("pending_trade_suggestions")}
            if "signal_source" not in pc:
                conn.execute(text("ALTER TABLE pending_trade_suggestions ADD COLUMN signal_source VARCHAR(32)"))
                conn.commit()
            pc = {c["name"] for c in insp.get_columns("pending_trade_suggestions")}
            if "user_id" not in pc:
                conn.execute(text("ALTER TABLE pending_trade_suggestions ADD COLUMN user_id INTEGER REFERENCES users(id)"))
                conn.commit()

        if insp.has_table("accounts"):
            acols = {c["name"] for c in insp.get_columns("accounts")}
            if "user_id" not in acols:
                conn.execute(text("ALTER TABLE accounts ADD COLUMN user_id INTEGER REFERENCES users(id)"))
                conn.commit()

        if insp.has_table("bot_config"):
            cols_bc = {c["name"] for c in insp.get_columns("bot_config")}
            if "user_id" not in cols_bc:
                conn.execute(text("ALTER TABLE bot_config ADD COLUMN user_id INTEGER REFERENCES users(id)"))
                conn.commit()

        if insp.has_table("auto_trade_logs"):
            ac = {c["name"] for c in insp.get_columns("auto_trade_logs")}
            if "user_id" not in ac:
                conn.execute(text("ALTER TABLE auto_trade_logs ADD COLUMN user_id INTEGER REFERENCES users(id)"))
                conn.commit()

        if insp.has_table("bot_config"):
            cols_bc = {c["name"] for c in insp.get_columns("bot_config")}
            if "trading_venue" not in cols_bc:
                conn.execute(
                    text("ALTER TABLE bot_config ADD COLUMN trading_venue VARCHAR(24) DEFAULT 'paper'")
                )
                conn.commit()
            if "exchange_execution_enabled" not in cols_bc:
                conn.execute(
                    text("ALTER TABLE bot_config ADD COLUMN exchange_execution_enabled BOOLEAN DEFAULT 0")
                )
                conn.commit()
            if "exchange_tracked_qty_btc" not in cols_bc:
                conn.execute(text("ALTER TABLE bot_config ADD COLUMN exchange_tracked_qty_btc NUMERIC(24, 8)"))
                conn.commit()
            if "exchange_avg_entry_usdt" not in cols_bc:
                conn.execute(text("ALTER TABLE bot_config ADD COLUMN exchange_avg_entry_usdt NUMERIC(24, 8)"))
                conn.commit()
            conn.execute(text("UPDATE bot_config SET trading_venue = 'paper' WHERE trading_venue IS NULL"))
            conn.commit()
            conn.execute(
                text("UPDATE bot_config SET exchange_execution_enabled = 0 WHERE exchange_execution_enabled IS NULL")
            )
            conn.commit()

        _migrate_positions_composite_unique(conn, insp)


def _migrate_positions_composite_unique(conn, insp) -> None:
    """Legacy DB had UNIQUE(symbol) only; per-user accounts need UNIQUE(account_id, symbol)."""
    if not insp.has_table("positions"):
        return
    for ix in insp.get_indexes("positions"):
        cols = ix.get("column_names") or []
        if ix.get("unique") and set(cols) == {"account_id", "symbol"}:
            return
    conn.execute(text("PRAGMA foreign_keys=OFF"))
    conn.commit()
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS positions_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol VARCHAR(32) NOT NULL,
                quantity_btc NUMERIC(24, 8) NOT NULL,
                avg_entry_price_usdt NUMERIC(24, 8) NOT NULL,
                account_id INTEGER NOT NULL REFERENCES accounts(id),
                UNIQUE(account_id, symbol)
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO positions_new (id, symbol, quantity_btc, avg_entry_price_usdt, account_id)
            SELECT id, symbol, quantity_btc, avg_entry_price_usdt, account_id FROM positions
            """
        )
    )
    conn.execute(text("DROP TABLE positions"))
    conn.execute(text("ALTER TABLE positions_new RENAME TO positions"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_positions_account_id ON positions(account_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_positions_symbol ON positions(symbol)"))
    conn.commit()
    conn.execute(text("PRAGMA foreign_keys=ON"))
    conn.commit()
