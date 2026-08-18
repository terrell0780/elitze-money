"""Database engine and session factory."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from urllib.parse import unquote

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from ..config import Settings


def _ensure_sqlite_dir(url: str) -> None:
    """Create the parent directory for a relative/absolute SQLite file URL."""
    # Handles sqlite:///relative.db and sqlite:////abs/path.db
    path_part = url[len("sqlite:///"):] if url.startswith("sqlite:///") else url
    path_part = path_part.split("?")[0]
    path = Path(unquote(path_part))
    if not path.is_absolute() and str(path) not in ("", ":memory:"):
        parent = path.parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
    elif path.is_absolute():
        path.parent.mkdir(parents=True, exist_ok=True)


def build_engine(settings: Settings) -> Engine:
    """Build a SQLAlchemy engine from settings.

    SQLite gets foreign-key + WAL pragmas for safe concurrent use; anything
    else (PostgreSQL, ...) is passed through to SQLAlchemy directly.
    """
    url = settings.resolved_database_url
    if url.startswith("sqlite"):
        _ensure_sqlite_dir(url)
    kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _record):  # type: ignore[no-untyped-def]
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


class Database:
    """Thin wrapper exposing engine + sessionmaker for the repositories."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine = build_engine(settings)
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False, future=True
        )

    def create_all(self) -> None:
        from .orm import Base

        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self.session_factory()

    def dispose(self) -> None:
        self.engine.dispose()


def session_scope(db: Database) -> Iterator[Session]:
    """Context manager yielding a session, committing/rolling back cleanly."""
    session = db.session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
