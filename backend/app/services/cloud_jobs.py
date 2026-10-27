"""Persist processing status independently of function-instance memory."""
import time
from sqlalchemy import delete
from app.db import AsyncSessionLocal
from app.models.cloud import ProcessingJob
from app.schemas.document import JobStatus


async def save_job(job: JobStatus) -> None:
    """Create or update durable processing state.

    Args: job: Current status. Returns: None. Raises: Database errors.
    """
    now = int(time.time())
    async with AsyncSessionLocal() as db:
        await db.execute(delete(ProcessingJob).where(ProcessingJob.expires_at < now - 86400))
        record = await db.get(ProcessingJob, job.job_id)
        if record is None:
            record = ProcessingJob(job_id=job.job_id)
            db.add(record)
        record.payload = job.model_dump_json()
        record.expires_at = now + (86400 if job.status in {"done", "error"} else 240)
        await db.commit()


async def get_cloud_job(job_id: str) -> JobStatus | None:
    """Read job state and detect a terminated invocation.

    Args: job_id: Identifier. Returns: Job or None. Raises: Database errors.
    """
    async with AsyncSessionLocal() as db:
        record = await db.get(ProcessingJob, job_id)
        if record is None:
            return None
        job = JobStatus.model_validate_json(record.payload)
        if record.expires_at < time.time():
            if job.status in {"processing", "pending"}:
                return JobStatus(job_id=job_id, status="error", error="Processing timed out. Please retry the upload.")
            return None
        return job
