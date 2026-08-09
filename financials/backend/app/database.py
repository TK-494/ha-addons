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


SCHEMA_VERSION = 1


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
        # if current < SCHEMA_VERSION: apply ordered upgrade steps here.
        conn.execute(text("UPDATE schema_version SET version = :v"), {"v": SCHEMA_VERSION})
