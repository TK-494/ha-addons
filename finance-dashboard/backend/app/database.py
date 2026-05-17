import os
from pathlib import Path
from sqlalchemy import create_engine
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
