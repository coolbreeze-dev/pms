from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings, normalize_database_url
from app.db.base import Base


def build_engine(database_url: str) -> Engine:
    normalized_url = normalize_database_url(database_url)
    connect_args: dict[str, object] = {}
    if normalized_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False, "timeout": 30}
    engine = create_engine(
        normalized_url,
        connect_args=connect_args,
        future=True,
        pool_pre_ping=not normalized_url.startswith("sqlite"),
    )

    if normalized_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA busy_timeout=30000;")
            cursor.close()

    return engine


settings = get_settings()
engine = build_engine(settings.portfolio_db_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema(engine)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def ping_database() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def ensure_runtime_schema(target_engine: Engine) -> None:
    if target_engine.dialect.name != "sqlite":
        return

    inspector = inspect(target_engine)
    runtime_columns = {
        "accounts": {
            "sync_provider": "VARCHAR(32)",
            "sync_external_id": "VARCHAR(128)",
            "sync_authorization_id": "VARCHAR(128)",
            "sync_status": "VARCHAR(32)",
            "last_synced_at": "DATETIME",
            "last_sync_error": "TEXT",
        },
        "holdings": {
            "sync_provider": "VARCHAR(32)",
            "sync_external_id": "VARCHAR(128)",
            "synced_at": "DATETIME",
        },
        "transactions": {
            "sync_provider": "VARCHAR(32)",
            "sync_external_id": "VARCHAR(128)",
            "synced_at": "DATETIME",
        },
    }

    with target_engine.begin() as connection:
        for table_name, columns in runtime_columns.items():
            if not inspector.has_table(table_name):
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, ddl in columns.items():
                if column_name in existing_columns:
                    continue
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))
