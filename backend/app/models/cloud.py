"""Durable sessions, source files and processing state for stateless functions."""
from sqlalchemy import ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class BrowserSession(Base):
    """Store hashed session tokens, credential version and expiration."""
    __tablename__ = "browser_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    credential_version: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[int] = mapped_column(Integer, index=True)


class LoginAttempt(Base):
    """Share rate limits across independently scaled function instances."""
    __tablename__ = "login_attempts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[int] = mapped_column(Integer, index=True)


class DocumentFile(Base):
    """Keep small private source images transactionally with their document."""
    __tablename__ = "document_files"
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    media_type: Mapped[str] = mapped_column(String(32))


class ProcessingJob(Base):
    """Persist terminal job status so polling works across instances."""
    __tablename__ = "processing_jobs"
    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[int] = mapped_column(Integer, index=True)
