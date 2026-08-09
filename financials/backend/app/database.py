"""SQLite engine, session factory and schema versioning.

The database lives in HA's `/data` volume, so it is covered by Home Assistant
backups without any extra plumbing.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/financials.db")

if DATABASE_URL.startswith("sqlite:///"):
    Path(DATABASE_URL[len("sqlite:///"):]).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):
    """WAL keeps reads working while an import writes — a 9k-row import
    otherwise blocks the UI. `foreign_keys` is OFF by default in SQLite, which
    would silently let a deleted import batch leave orphaned transactions
    behind; the whole "delete a file and its transactions" feature depends on
    cascades actually firing.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 1 — initial schema
# 2 — tags: adds `tags` and `transaction_tags`, no changes to existing tables,
#     so `create_all` covers the upgrade on its own.
# 3 — accounts.kind_auto: a new *column*, which `create_all` will not add to an
#     existing table — needs the ALTER below.
# 4 — period_overrides: a new table only.
# 5 — rules gain provenance: origin, seed_batch, source_transaction_id, note.
# 6 — transaction_splits table + categories.variable_income column.
SCHEMA_VERSION = 6


def apply_migrations() -> None:
    """Forward-only schema versioning.

    `create_all` adds missing tables but never missing columns, so a released
    add-on needs somewhere to put "and then add this column". Version 1 is the
    initial schema; later versions append a branch here.
    """
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"))
        current = conn.execute(text("SELECT version FROM schema_version")).scalar()
        if current is None:
            conn.execute(text("INSERT INTO schema_version (version) VALUES (:v)"),
                         {"v": SCHEMA_VERSION})
            return
        if current > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema v{current} is newer than this add-on (v{SCHEMA_VERSION}). "
                "Downgrade is not supported — restore a backup or update the add-on."
            )

        if current < 3:
            _add_column_if_missing(
                conn, "accounts", "kind_auto",
                "BOOLEAN NOT NULL DEFAULT 1",
            )

        if current < 5:
            # Existing rules predate the provenance fields. Anything flagged
            # is_seed came from batch 1; the rest was made by hand.
            _add_column_if_missing(conn, "rules", "origin", "VARCHAR(20) NOT NULL DEFAULT 'manual'")
            _add_column_if_missing(conn, "rules", "seed_batch", "INTEGER")
            _add_column_if_missing(conn, "rules", "source_transaction_id", "INTEGER")
            _add_column_if_missing(conn, "rules", "note", "VARCHAR(200)")
            conn.execute(text(
                "UPDATE rules SET origin = 'seed', seed_batch = 1 "
                "WHERE is_seed = 1 AND seed_batch IS NULL"
            ))

        if current < 6:
            _add_column_if_missing(
                conn, "categories", "variable_income", "BOOLEAN NOT NULL DEFAULT 0"
            )

        conn.execute(text("UPDATE schema_version SET version = :v"), {"v": SCHEMA_VERSION})


def _add_column_if_missing(conn, table: str, column: str, definition: str) -> None:
    """`create_all` only creates missing *tables*, never missing columns — but
    on a fresh database it will already have made the column, so the ALTER
    would fail with 'duplicate column'. Check first."""
    existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
    if column not in existing:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
