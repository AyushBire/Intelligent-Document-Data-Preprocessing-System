"""Verify PostgreSQL configuration and transactional legacy imports."""
import asyncio
import os
import sqlite3
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db import Base
from app.models.document import Document, DocumentConfirmation, Invoice
from scripts import import_sqlite


def test_postgres_password_is_not_interpolated():
    """Preserve reserved password characters. Returns: None. Raises: AssertionError."""
    settings = Settings(_env_file=None, DATABASE_URL=None, GEMINI_API_KEY="test",
                        POSTGRES_PASSWORD="p@ss:/?#%word")
    assert settings.database_url.drivername == "postgresql+asyncpg"
    assert settings.database_url.password == "p@ss:/?#%word"
    assert Settings.model_fields["AUTO_CREATE_TABLES"].default is False
    assert "p@ss" not in repr(settings)


def test_hosted_postgres_url_uses_async_driver():
    """Normalize provider URLs. Returns: None. Raises: AssertionError."""
    settings = Settings(_env_file=None, GEMINI_API_KEY="test", DATABASE_URL="postgresql://idps:secret@localhost/idps?ssl=require")
    assert settings.database_url.drivername == "postgresql+asyncpg"
    assert settings.database_url.query["ssl"] == "require"


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL")
def test_postgres_import_preserves_relations_and_sequences(tmp_path, monkeypatch):
    """Test a real PostgreSQL import, rollback guard and future IDs.

    Args: tmp_path: Fixture directory; monkeypatch: Settings override fixture.
    Returns: None. Raises: AssertionError or database errors.
    """
    source_path = tmp_path / "source.sqlite3"
    source_engine = create_engine(f"sqlite:///{source_path}")
    Base.metadata.create_all(source_engine)
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "fixture.png").write_bytes(b"synthetic-image")
    now = datetime.now(timezone.utc)
    with source_engine.begin() as connection:
        connection.execute(Document.__table__.insert(), dict(id=41, filename="fixture.png", file_path="uploads/fixture.png",
                           document_type="invoice", ocr_text="test", report="report", raw_json="{}", created_at=now, updated_at=now))
        connection.execute(Invoice.__table__.insert(), dict(id=27, document_id=41, invoice_number="INV-TEST"))
        connection.execute(DocumentConfirmation.__table__.insert(), dict(id=12, document_id=41, confirmed=True,
                           confirmed_by="test", notes="", confirmed_at=now))
    source_engine.dispose()
    settings = Settings(_env_file=None, GEMINI_API_KEY="test", DATABASE_URL=os.environ["TEST_POSTGRES_URL"],
                        UPLOAD_DIR=str(tmp_path / "outgoing"))
    monkeypatch.setattr(import_sqlite, "get_settings", lambda: settings)
    backup = tmp_path / "backup.sqlite3"
    expected = import_sqlite.snapshot(source_path, backup)

    async def verify():
        """Run import assertions against migrated PostgreSQL.

        Returns: None. Raises: AssertionError or database errors.
        """
        engine = create_async_engine(settings.database_url)
        try:
            assert await import_sqlite.import_database(backup, incoming, True) == expected
            assert not (tmp_path / "outgoing").exists()
            with sqlite3.connect(backup) as broken:
                broken.execute("UPDATE invoices SET document_id = 999")
            with pytest.raises(IntegrityError):
                await import_sqlite.import_database(backup, incoming, False)
            assert not (tmp_path / "outgoing" / "fixture.png").exists()
            async with engine.connect() as connection:
                assert (await connection.execute(select(Document.id))).first() is None
            with sqlite3.connect(backup) as repaired:
                repaired.execute("UPDATE invoices SET document_id = 41")
            assert await import_sqlite.import_database(backup, incoming, False) == expected
            async with engine.begin() as connection:
                assert (await connection.execute(select(Invoice.document_id))).scalar_one() == 41
                assert (await connection.execute(select(DocumentConfirmation.confirmed))).scalar_one() is True
                result = await connection.execute(Document.__table__.insert().values(filename="next.png", file_path="next.png",
                                                  document_type="generic", ocr_text="", report="", raw_json="{}").returning(Document.id))
                assert result.scalar_one() == 42
            with pytest.raises(ValueError, match="not empty"):
                await import_sqlite.import_database(backup, incoming, False)
        finally:
            async with engine.begin() as connection:
                for table in reversed(Base.metadata.sorted_tables):
                    await connection.execute(table.delete())
            await engine.dispose()
    asyncio.run(verify())
    with sqlite3.connect(source_path) as source:
        assert source.execute("SELECT count(*) FROM documents").fetchone()[0] == 1
