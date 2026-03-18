from __future__ import annotations

import argparse
import base64
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from sqlalchemy import Engine, inspect, select

from app.db.base import Base
from app.db.session import build_engine


def database_backend_from_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    if parsed.scheme.startswith("sqlite"):
        return "sqlite"
    if parsed.scheme.startswith("postgresql") or parsed.scheme.startswith("postgres"):
        return "postgresql"
    return parsed.scheme or "unknown"


def _mask_database_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    if parsed.password is None:
        return database_url
    netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
    return urlunparse(parsed._replace(netloc=netloc))


def _serialize_value(value):
    if isinstance(value, Decimal):
        return {"__type": "decimal", "value": str(value)}
    if isinstance(value, datetime):
        return {"__type": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__type": "date", "value": value.isoformat()}
    if isinstance(value, bytes):
        return {"__type": "bytes", "value": base64.b64encode(value).decode("ascii")}
    if isinstance(value, dict):
        return {key: _serialize_value(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _deserialize_value(value):
    if isinstance(value, dict) and "__type" in value:
        if value["__type"] == "decimal":
            return Decimal(value["value"])
        if value["__type"] == "datetime":
            return datetime.fromisoformat(value["value"])
        if value["__type"] == "date":
            return date.fromisoformat(value["value"])
        if value["__type"] == "bytes":
            return base64.b64decode(value["value"].encode("ascii"))
    if isinstance(value, dict):
        return {key: _deserialize_value(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_deserialize_value(item) for item in value]
    return value


def export_database_payload(database_url: str) -> dict[str, object]:
    engine = build_engine(database_url)
    inspector = inspect(engine)
    payload_tables: dict[str, list[dict[str, object]]] = {}
    table_order: list[str] = []

    with engine.connect() as connection:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            statement = select(table)
            if table.primary_key.columns:
                statement = statement.order_by(*table.primary_key.columns)
            rows = connection.execute(statement).mappings().all()
            payload_tables[table.name] = [
                {column: _serialize_value(value) for column, value in row.items()} for row in rows
            ]
            table_order.append(table.name)

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_backend": database_backend_from_url(database_url),
        "source_database": _mask_database_url(database_url),
        "table_order": table_order,
        "tables": payload_tables,
    }


def snapshot_database(database_url: str, output_path: Path) -> dict[str, object]:
    payload = export_database_payload(database_url)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {
        "created_at": payload["exported_at"],
        "output_path": str(output_path),
        "backend": payload["source_backend"],
        "tables": {table_name: len(rows) for table_name, rows in payload["tables"].items()},
    }


def restore_snapshot(database_url: str, snapshot_path: Path, truncate: bool = False) -> dict[str, object]:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    engine = build_engine(database_url)
    Base.metadata.create_all(bind=engine)
    restored_counts: dict[str, int] = {}

    with engine.begin() as connection:
        if truncate:
            for table in reversed(Base.metadata.sorted_tables):
                connection.execute(table.delete())
        for table in Base.metadata.sorted_tables:
            rows = payload.get("tables", {}).get(table.name, [])
            if not rows:
                restored_counts[table.name] = 0
                continue
            decoded_rows = [{key: _deserialize_value(value) for key, value in row.items()} for row in rows]
            connection.execute(table.insert(), decoded_rows)
            restored_counts[table.name] = len(decoded_rows)

    return {
        "restored_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_path": str(snapshot_path),
        "target_database": _mask_database_url(database_url),
        "tables": restored_counts,
    }


def copy_database(source_database_url: str, target_database_url: str, truncate_target: bool = False) -> dict[str, object]:
    payload = export_database_payload(source_database_url)
    target_engine = build_engine(target_database_url)
    Base.metadata.create_all(bind=target_engine)
    copied_counts: dict[str, int] = {}

    with target_engine.begin() as connection:
        if truncate_target:
            for table in reversed(Base.metadata.sorted_tables):
                connection.execute(table.delete())
        for table in Base.metadata.sorted_tables:
            rows = payload.get("tables", {}).get(table.name, [])
            if not rows:
                copied_counts[table.name] = 0
                continue
            decoded_rows = [{key: _deserialize_value(value) for key, value in row.items()} for row in rows]
            connection.execute(table.insert(), decoded_rows)
            copied_counts[table.name] = len(decoded_rows)

    return {
        "copied_at": datetime.now(timezone.utc).isoformat(),
        "source_database": _mask_database_url(source_database_url),
        "target_database": _mask_database_url(target_database_url),
        "tables": copied_counts,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portable database snapshot and copy tooling.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot_parser = subparsers.add_parser("snapshot", help="Export a database into a JSON snapshot.")
    snapshot_parser.add_argument("--database-url", required=True, help="Source database URL.")
    snapshot_parser.add_argument("--output", required=True, help="Output JSON snapshot path.")

    restore_parser = subparsers.add_parser("restore", help="Restore a JSON snapshot into a database.")
    restore_parser.add_argument("--database-url", required=True, help="Target database URL.")
    restore_parser.add_argument("--snapshot", required=True, help="Input JSON snapshot path.")
    restore_parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing rows in the target database before restore.",
    )

    copy_parser = subparsers.add_parser("copy", help="Copy data directly from one database into another.")
    copy_parser.add_argument("--source-database-url", required=True, help="Source database URL.")
    copy_parser.add_argument("--target-database-url", required=True, help="Target database URL.")
    copy_parser.add_argument(
        "--truncate-target",
        action="store_true",
        help="Delete existing rows in the target database before copy.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "snapshot":
        result = snapshot_database(args.database_url, Path(args.output))
    elif args.command == "restore":
        result = restore_snapshot(args.database_url, Path(args.snapshot), truncate=args.truncate)
    else:
        result = copy_database(
            args.source_database_url,
            args.target_database_url,
            truncate_target=args.truncate_target,
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
