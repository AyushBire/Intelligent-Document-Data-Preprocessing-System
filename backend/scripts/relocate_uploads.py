"""Validate and rebase stored image paths after moving a PostgreSQL deployment."""
import argparse
import asyncio
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.models.document import Document


async def relocate(apply: bool) -> int:
    """Rebase image paths only when every document has a valid destination image.

    Args: apply: Commit path changes when true; otherwise validate only.
    Returns: Document count. Raises: ValueError, OSError, SQLAlchemy errors.
    """
    settings = get_settings()
    if settings.database_url.get_backend_name() != "postgresql":
        raise ValueError("This maintenance command requires PostgreSQL.")
    root = Path(settings.UPLOAD_DIR).resolve()
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as connection:
            records = (await connection.execute(select(Document.id, Document.file_path).with_for_update())).all()
            paths = []
            for document_id, stored in records:
                filename = stored.replace("\\", "/").rsplit("/", 1)[-1]
                path = (root / filename).resolve()
                if path.parent != root or not path.is_file():
                    raise ValueError(f"Missing or unsafe source image for document {document_id}.")
                paths.append((document_id, str(path)))
            if apply:
                for document_id, path in paths:
                    await connection.execute(update(Document).where(Document.id == document_id).values(file_path=path))
            return len(paths)
    finally:
        await engine.dispose()


def main() -> None:
    """Parse maintenance options and print validation counts.

    Returns: None. Raises: Filesystem, validation or database errors.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Commit validated file path changes")
    args = parser.parse_args()
    count = asyncio.run(relocate(args.apply))
    print("Rebased" if args.apply else "Validated", count, "source-image paths")


if __name__ == "__main__":
    main()
