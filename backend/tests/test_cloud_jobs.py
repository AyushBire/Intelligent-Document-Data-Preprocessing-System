"""Verify durable job status and interrupted invocation handling."""
import asyncio
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.db import Base
from app.models.cloud import ProcessingJob
from app.schemas.document import JobStatus
from app.services import cloud_jobs


def test_job_survives_memory_loss_and_reports_timeout(tmp_path, monkeypatch):
    """Exercise persisted jobs and expiry. Args: tmp_path: Temporary path; monkeypatch: Overrides. Returns: None. Raises: AssertionError on regression."""
    async def exercise():
        """Run an isolated database workflow. Returns: None. Raises: Database or assertion errors."""
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        monkeypatch.setattr(cloud_jobs, "AsyncSessionLocal", sessions)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await cloud_jobs.save_job(JobStatus(job_id="fixture", status="processing"))
        assert (await cloud_jobs.get_cloud_job("fixture")).status == "processing"
        async with sessions() as db:
            await db.execute(update(ProcessingJob).values(expires_at=0))
            await db.commit()
        assert (await cloud_jobs.get_cloud_job("fixture")).status == "error"
        await cloud_jobs.save_job(JobStatus(job_id="fixture", status="done", document_id=123))
        assert (await cloud_jobs.get_cloud_job("fixture")).document_id == 123
        assert await cloud_jobs.get_cloud_job("missing") is None
        await engine.dispose()
    asyncio.run(exercise())
