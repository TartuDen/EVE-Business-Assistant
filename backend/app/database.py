from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .config import settings
from .models import PortfolioPosition, PortfolioPositionCreate, SettingsPayload


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db_path() -> Path:
    return Path(settings.database_path)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                type_id INTEGER,
                quantity INTEGER NOT NULL,
                buy_price REAL NOT NULL,
                sell_price_target REAL NOT NULL,
                sold_price REAL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS character_tokens (
                character_id INTEGER PRIMARY KEY,
                character_name TEXT NOT NULL,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                scopes TEXT NOT NULL,
                token_type TEXT NOT NULL DEFAULT 'Bearer',
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS oauth_states (
                state TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_skill_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER,
                character_name TEXT NOT NULL,
                profile_id TEXT NOT NULL,
                plan_name TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        defaults = {
            "total_liquid_isk": "365000000",
            "broker_fee_rate": str(settings.broker_fee_rate),
            "sales_tax_rate": str(settings.sales_tax_rate),
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
                (key, value),
            )


def _position_from_row(row: sqlite3.Row) -> PortfolioPosition:
    sold_price = row["sold_price"]
    quantity = row["quantity"]
    buy_price = row["buy_price"]
    profit_loss = 0.0
    if sold_price is not None:
        profit_loss = (sold_price - buy_price) * quantity

    return PortfolioPosition(
        id=row["id"],
        item_name=row["item_name"],
        type_id=row["type_id"],
        quantity=quantity,
        buy_price=buy_price,
        sell_price_target=row["sell_price_target"],
        sold_price=sold_price,
        notes=row["notes"],
        status="closed" if sold_price is not None else "open",
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        profit_loss=profit_loss,
    )


def list_positions() -> list[PortfolioPosition]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM portfolio_positions ORDER BY updated_at DESC"
        ).fetchall()
    return [_position_from_row(row) for row in rows]


def create_position(payload: PortfolioPositionCreate) -> PortfolioPosition:
    now = utc_now()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO portfolio_positions
            (item_name, type_id, quantity, buy_price, sell_price_target, sold_price, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.item_name,
                payload.type_id,
                payload.quantity,
                payload.buy_price,
                payload.sell_price_target,
                payload.sold_price,
                payload.notes,
                now,
                now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM portfolio_positions WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return _position_from_row(row)


def update_position(position_id: int, payload: PortfolioPositionCreate) -> PortfolioPosition | None:
    now = utc_now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE portfolio_positions
            SET item_name = ?, type_id = ?, quantity = ?, buy_price = ?, sell_price_target = ?,
                sold_price = ?, notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.item_name,
                payload.type_id,
                payload.quantity,
                payload.buy_price,
                payload.sell_price_target,
                payload.sold_price,
                payload.notes,
                now,
                position_id,
            ),
        )
        row = conn.execute(
            "SELECT * FROM portfolio_positions WHERE id = ?",
            (position_id,),
        ).fetchone()
    return _position_from_row(row) if row else None


def delete_position(position_id: int) -> bool:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM portfolio_positions WHERE id = ?", (position_id,))
    return cursor.rowcount > 0


def get_settings() -> SettingsPayload:
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    values = {row["key"]: float(row["value"]) for row in rows}
    return SettingsPayload(
        total_liquid_isk=values.get("total_liquid_isk", 365_000_000),
        broker_fee_rate=values.get("broker_fee_rate", settings.broker_fee_rate),
        sales_tax_rate=values.get("sales_tax_rate", settings.sales_tax_rate),
    )


def save_settings(payload: SettingsPayload) -> SettingsPayload:
    with connect() as conn:
        for key, value in payload.model_dump().items():
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
    return payload


def save_oauth_state(state: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO oauth_states (state, created_at) VALUES (?, ?)",
            (state, utc_now()),
        )


def consume_oauth_state(state: str) -> bool:
    with connect() as conn:
        row = conn.execute("SELECT state FROM oauth_states WHERE state = ?", (state,)).fetchone()
        if row:
            conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
    return row is not None


def save_character_token(
    character_id: int,
    character_name: str,
    access_token: str,
    refresh_token: str,
    expires_at: str,
    scopes: list[str],
    token_type: str = "Bearer",
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO character_tokens
            (character_id, character_name, access_token, refresh_token, expires_at, scopes, token_type, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                character_id,
                character_name,
                access_token,
                refresh_token,
                expires_at,
                " ".join(scopes),
                token_type,
                utc_now(),
            ),
        )


def get_character_token(character_id: int | None = None) -> sqlite3.Row | None:
    with connect() as conn:
        if character_id is not None:
            return conn.execute(
                "SELECT * FROM character_tokens WHERE character_id = ?",
                (character_id,),
            ).fetchone()
        return conn.execute(
            "SELECT * FROM character_tokens ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()


def list_character_tokens() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT character_id, character_name, expires_at, scopes, updated_at FROM character_tokens ORDER BY updated_at DESC"
        ).fetchall()


def delete_character_token(character_id: int) -> bool:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM character_tokens WHERE character_id = ?", (character_id,))
    return cursor.rowcount > 0


def list_saved_plans() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM saved_skill_plans ORDER BY updated_at DESC").fetchall()


def create_saved_plan(character_id: int | None, character_name: str, profile_id: str, plan_name: str, notes: str) -> sqlite3.Row:
    now = utc_now()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO saved_skill_plans
            (character_id, character_name, profile_id, plan_name, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (character_id, character_name, profile_id, plan_name, notes, now, now),
        )
        return conn.execute("SELECT * FROM saved_skill_plans WHERE id = ?", (cursor.lastrowid,)).fetchone()


def delete_saved_plan(plan_id: int) -> bool:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM saved_skill_plans WHERE id = ?", (plan_id,))
    return cursor.rowcount > 0
