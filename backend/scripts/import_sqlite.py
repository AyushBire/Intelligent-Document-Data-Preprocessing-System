"""Import an existing IDPS SQLite database into empty, migrated PostgreSQL."""
import argparse
import asyncio
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Boolean, DateTime, func, select, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.exc import SQLAlchemyError

import app.models  # noqa: F401
from app.config import get_settings
from app.db import Base


def snapshot(source: Path, backup: Path) -> dict[str, int]:
    """Back up a source consistently and validate its schema.

    Args: source: SQLite file; backup: New backup filename.
    Returns: Counts per supported table. Raises: ValueError, FileExistsError, SQLite errors.
    """
    if not source.is_file():
        raise ValueError("Source SQLite database does not exist.")
    backup.parent.mkdir(parents=True, exist_ok=True)
    with backup.open("xb"):
        pass
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original:
        with sqlite3.connect(backup) as copy:
            original.backup(copy)
    with sqlite3.connect(backup) as copy:
        if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed.")
        counts = {}
        for table in Base.metadata.sorted_tables:
            columns = {row[1] for row in copy.execute(f'PRAGMA table_info("{table.name}")')}
            if not set(table.columns.keys()).issubset(columns):
                raise ValueError(f"Incompatible source schema: {table.name}")
            counts[table.name] = copy.execute(f'SELECT count(*) FROM "{table.name}"').fetchone()[0]
        return counts


async def import_database(backup: Path, source_uploads: Path | None, dry_run: bool) -> dict[str, int]:
    """Import all rows atomically, retaining IDs and repairing PostgreSQL sequences.

    Args: backup: SQLite snapshot; source_uploads: Original upload directory; dry_run: Validate only.
    Returns: Verified source counts. Raises: ValueError, OSError, SQLAlchemy errors.
    """
    settings = get_settings()
    if settings.database_url.get_backend_name() != "postgresql":
        raise ValueError("The destination must be PostgreSQL.")
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    copied: list[Path] = []
    counts: dict[str, int] = {}
    try:
        with sqlite3.connect(backup.as_uri() + "?mode=ro", uri=True) as source:
            source.row_factory = sqlite3.Row
            async with engine.begin() as target:
                if (await target.execute(text("SELECT version_num FROM alembic_version"))).scalar_one() != "0001_initial":
                    raise ValueError("Run alembic upgrade head before importing.")
                names = ', '.join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
                await target.execute(text(f"LOCK TABLE {names} IN ACCESS EXCLUSIVE MODE"))
                for table in Base.metadata.sorted_tables:
                    if (await target.execute(select(func.count()).select_from(table))).scalar_one():
                        raise ValueError("Destination is not empty; import refuses to overwrite or merge records.")
                for table in Base.metadata.sorted_tables:
                    cursor = source.execute(f'SELECT * FROM "{table.name}" ORDER BY id')
                    counts[table.name] = 0
                    while batch := cursor.fetchmany(500):
                        records = []
                        for row in batch:
                            record = {column.name: row[column.name] for column in table.columns}
                            for column in table.columns:
                                value = record[column.name]
                                if isinstance(column.type, DateTime) and value is not None:
                                    parsed = datetime.fromisoformat(value)
                                    record[column.name] = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
                                elif isinstance(column.type, Boolean) and value is not None:
                                    record[column.name] = bool(value)
                            if table.name == "documents":
                                if source_uploads is None:
                                    raise ValueError("Documents exist; supply --source-uploads to preserve source images.")
                                filename = str(record["file_path"]).replace("\\", "/").rsplit("/", 1)[-1]
                                original = (source_uploads / filename).resolve()
                                destination = (Path(settings.UPLOAD_DIR) / filename).resolve()
                                if original.parent != source_uploads.resolve() or not original.is_file():
                                    raise ValueError(f"Source image missing or unsafe for document {record['id']}.")
                                if destination.parent != Path(settings.UPLOAD_DIR).resolve() or destination.exists():
                                    raise ValueError(f"Destination image already exists or is unsafe for document {record['id']}.")
                                if not dry_run:
                                    destination.parent.mkdir(parents=True, exist_ok=True)
                                    with original.open("rb") as incoming, destination.open("xb") as outgoing:
                                        copied.append(destination)
                                        shutil.copyfileobj(incoming, outgoing)
                                record["file_path"] = str(destination)
                            records.append(record)
                        if not dry_run:
                            await target.execute(table.insert(), records)
                        counts[table.name] += len(records)
                    if not dry_run:
                        actual = (await target.execute(select(func.count()).select_from(table))).scalar_one()
                        if actual != counts[table.name]:
                            raise ValueError(f"Count verification failed for {table.name}.")
                        maximum = (await target.execute(select(func.max(table.c.id)))).scalar_one()
                        await target.execute(text("SELECT setval(pg_get_serial_sequence(:table, 'id'), :value, :called)"),
                                             {"table": table.name, "value": maximum or 1, "called": maximum is not None})
        return counts
    except BaseException:
        for path in copied:
            path.unlink(missing_ok=True)
        raise
    finally:
        await engine.dispose()


def main() -> None:
    """Parse maintenance arguments and report counts without document contents.

    Returns: None. Raises: Import validation, filesystem or database errors.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--backup", required=True, type=Path)
    parser.add_argument("--source-uploads", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    expected = snapshot(args.source.resolve(), args.backup.resolve())
    actual = asyncio.run(import_database(args.backup.resolve(), args.source_uploads, args.dry_run))
    if expected != actual:
        raise ValueError("Source count verification failed.")
    print("Validated" if args.dry_run else "Imported", actual)


if __name__ == "__main__":
    try:
        main()
    except (SQLAlchemyError, sqlite3.Error) as error:
        raise SystemExit(f"Database import failed ({type(error).__name__}). Review schema, constraints and destination state before retrying.") from None
