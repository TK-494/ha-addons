import os
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/finance.db")

# Make sure the parent dir exists before SQLite tries to create the file.
# sqlite:///foo.db → relative "foo.db"; sqlite:////data/foo.db → absolute "/data/foo.db".
if DATABASE_URL.startswith("sqlite:///"):
    db_path = Path(DATABASE_URL[len("sqlite:///"):])
    db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_lightweight_migrations() -> None:
    """Add columns that newer model versions expect but older DBs don't have.
    SQLAlchemy's create_all only creates missing tables, not missing columns —
    so existing finance.db files from earlier installs need this nudge.
    """
    insp = inspect(engine)
    if "transactions" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("transactions")}
        if "is_transfer" not in cols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE transactions ADD COLUMN is_transfer BOOLEAN NOT NULL DEFAULT 0"
                ))
