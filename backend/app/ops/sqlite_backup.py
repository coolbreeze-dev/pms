from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def sqlite_path_from_url(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// database URLs are supported by the backup tooling.")
    return Path(database_url.removeprefix("sqlite:///")).expanduser()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_sqlite(source_path: Path, backup_path: Path) -> dict[str, object]:
    if not source_path.exists():
        raise FileNotFoundError(f"Source database not found: {source_path}")
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source_path) as source_connection, sqlite3.connect(backup_path) as backup_connection:
        source_connection.backup(backup_connection)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source_path),
        "backup_path": str(backup_path),
        "size_bytes": backup_path.stat().st_size,
        "sha256": _hash_file(backup_path),
    }
    manifest_path = backup_path.with_suffix(f"{backup_path.suffix}.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def restore_sqlite(backup_path: Path, target_path: Path) -> dict[str, object]:
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup database not found: {backup_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(backup_path) as backup_connection, sqlite3.connect(target_path) as target_connection:
        backup_connection.backup(target_connection)
    return {
        "restored_at": datetime.now(timezone.utc).isoformat(),
        "backup_path": str(backup_path),
        "target_path": str(target_path),
        "size_bytes": target_path.stat().st_size,
        "sha256": _hash_file(target_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backup or restore the portfolio SQLite database.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="Create a consistent SQLite backup copy.")
    backup_parser.add_argument("--source", required=True, help="Source SQLite database path.")
    backup_parser.add_argument("--output", required=True, help="Output backup path.")

    restore_parser = subparsers.add_parser("restore", help="Restore a backup into a SQLite target file.")
    restore_parser.add_argument("--backup", required=True, help="Backup SQLite database path.")
    restore_parser.add_argument("--target", required=True, help="Target SQLite database path.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "backup":
        manifest = backup_sqlite(Path(args.source), Path(args.output))
        print(json.dumps(manifest, indent=2))
        return
    result = restore_sqlite(Path(args.backup), Path(args.target))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
