from __future__ import annotations

import sqlite3

from app.core.config import normalize_database_url
from app.db.base import Base
from app.db.session import build_engine
from app.ops.database_portability import copy_database, snapshot_database
from app.ops.sqlite_backup import backup_sqlite, restore_sqlite


def test_sqlite_backup_and_restore_round_trip(tmp_path):
    source_path = tmp_path / "source.db"
    backup_path = tmp_path / "backup.db"
    restore_path = tmp_path / "restore.db"

    with sqlite3.connect(source_path) as connection:
        connection.execute("CREATE TABLE positions (ticker TEXT PRIMARY KEY, shares REAL)")
        connection.execute("INSERT INTO positions (ticker, shares) VALUES ('AAPL', 12.5)")
        connection.commit()

    backup_manifest = backup_sqlite(source_path, backup_path)
    assert backup_manifest["size_bytes"] > 0
    assert backup_path.exists()
    assert backup_path.with_suffix(".db.json").exists()

    with sqlite3.connect(source_path) as connection:
        connection.execute("DELETE FROM positions")
        connection.commit()

    restore_manifest = restore_sqlite(backup_path, restore_path)
    assert restore_manifest["size_bytes"] > 0
    assert restore_path.exists()

    with sqlite3.connect(restore_path) as connection:
        row = connection.execute("SELECT ticker, shares FROM positions").fetchone()
    assert row == ("AAPL", 12.5)


def test_portable_snapshot_and_copy_round_trip(tmp_path):
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    snapshot_path = tmp_path / "snapshot.json"
    source_url = f"sqlite:///{source_path}"
    target_url = f"sqlite:///{target_path}"

    source_engine = build_engine(source_url)
    Base.metadata.create_all(bind=source_engine)
    with source_engine.begin() as connection:
        connection.execute(
            Base.metadata.tables["accounts"].insert(),
            [
                {
                    "id": 1,
                    "name": "Primary",
                    "account_type": "taxable",
                    "category": "brokerage",
                    "brokerage": "Vanguard",
                }
            ],
        )

    snapshot_manifest = snapshot_database(source_url, snapshot_path)
    assert snapshot_manifest["backend"] == "sqlite"
    assert snapshot_path.exists()

    copy_manifest = copy_database(source_url, target_url, truncate_target=True)
    assert copy_manifest["tables"]["accounts"] == 1

    with sqlite3.connect(target_path) as connection:
        row = connection.execute("SELECT id, name FROM accounts").fetchone()
    assert row == (1, "Primary")


def test_normalize_database_url_supports_neon_and_postgres_aliases():
    assert normalize_database_url("postgres://user:pass@db.neon.tech/app") == (
        "postgresql+psycopg://user:pass@db.neon.tech/app?sslmode=require"
    )
    assert normalize_database_url("postgresql://user:pass@example.com/app") == (
        "postgresql+psycopg://user:pass@example.com/app"
    )
