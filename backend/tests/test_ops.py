from __future__ import annotations

import sqlite3

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
