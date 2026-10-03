"""
Runs the DocumentPipeline for one uploaded file, in a worker thread, while
reporting progress through an in-memory job store.

NOTE: the job store is per-process. Run uvicorn with a SINGLE worker until it is
moved to Redis / a DB table.
"""

import asyncio
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

from app.config import get_settings
from app.schemas.document import JobStatus

logger = logging.getLogger("pipeline_service")
settings = get_settings()

JOB_TTL_SECONDS = 3600  # finished jobs are forgotten after 1 hour

_jobs: dict[str, JobStatus] = {}
_job_created: dict[str, float] = {}
_semaphore: asyncio.Semaphore | None = None


# ── Job store ──────────────────────────────────────────────────────────────────

def _purge_expired() -> None:
    cutoff = time.time() - JOB_TTL_SECONDS
    expired = [
        job_id
        for job_id, created in _job_created.items()
        if created < cutoff and _jobs.get(job_id) and _jobs[job_id].status in ("done", "error")
    ]
    for job_id in expired:
        _jobs.pop(job_id, None)
        _job_created.pop(job_id, None)


def create_job() -> str:
    _purge_expired()
    job_id = str(uuid.uuid4())
    _jobs[job_id] = JobStatus(job_id=job_id, status="pending", stage="", progress=0)
    _job_created[job_id] = time.time()
    return job_id


def get_job(job_id: str) -> JobStatus | None:
    return _jobs.get(job_id)


def _update_job(job_id: str, **kwargs) -> None:
    job = _jobs.get(job_id)
    if job:
        for k, v in kwargs.items():
            setattr(job, k, v)


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_JOBS)
    return _semaphore


# ── Pipeline singleton ─────────────────────────────────────────────────────────

_pipeline_instance = None
_pipeline_lock = threading.Lock()


def _get_pipeline():
    global _pipeline_instance
    with _pipeline_lock:
        if _pipeline_instance is None:
            from processing.pipeline import DocumentPipeline

            _pipeline_instance = DocumentPipeline()
            logger.info("DocumentPipeline loaded (singleton)")
    return _pipeline_instance


def pipeline_ready() -> bool:
    return _pipeline_instance is not None


async def preload_pipeline() -> None:
    """Called from the FastAPI lifespan so the first user doesn't pay the model-load cost."""
    await asyncio.to_thread(_get_pipeline)


def _run_ocr(pipeline, image):
    ocr_results = pipeline.ocr.process(image)
    ocr_text = pipeline.ocr.extract_text(ocr_results)
    return ocr_text


# ── Job runner ─────────────────────────────────────────────────────────────────

async def run_pipeline(
    job_id: str,
    image_path: str,
    save_to_db: Callable,             # async (result, stored_name, file_path) -> document_id
    notify: Callable | None = None,   # async, pushes JobStatus to WebSocket clients
) -> None:
    """Run extraction and persist usable results while publishing progress.

    Args: job_id: Job identifier; image_path: Stored image; save_to_db: Async save callback;
        notify: Optional async status callback.
    Returns: None. Raises: None; processing failures update job state and remove failed uploads.
    """
    async def push(stage: str, progress: int) -> None:
        """Publish processing progress without failing on disconnected listeners.

        Args: stage: Pipeline step; progress: Percentage. Returns: None. Raises: None.
        """
        _update_job(job_id, stage=stage, progress=progress, status="processing")
        if notify:
            try:
                await notify(get_job(job_id))
            except Exception:
                pass  # a dead WebSocket must never fail the job

    try:
        # Only MAX_CONCURRENT_JOBS pipelines run at once; others wait as "pending"
        async with _get_semaphore():
            await push("preprocessing", 10)
            pipeline = await asyncio.to_thread(_get_pipeline)
            clean_image = await asyncio.to_thread(pipeline.preprocessor.process, image_path)

            await push("ocr", 30)
            ocr_text = await asyncio.to_thread(_run_ocr, pipeline, clean_image)
            if not ocr_text.strip():
                raise ValueError("No readable text detected")

            await push("llm", 60)
            llm_output = await asyncio.to_thread(pipeline.llm.process, ocr_text)
            if llm_output.get("error") or not isinstance(llm_output.get("structured_data"), dict) or not llm_output.get("structured_data"):
                raise ValueError("AI extraction returned no usable data")

            await push("saving", 85)

        result = {
            "ocr_text": ocr_text,
            "document_type": llm_output.get("document_type", "unknown"),
            "structured_data": llm_output.get("structured_data", {}),
            "report": llm_output.get("report", ""),
        }
        document_id = await save_to_db(result, Path(image_path).name, image_path)

        _update_job(job_id, status="done", stage="done", progress=100, document_id=document_id)
        if notify:
            try:
                await notify(get_job(job_id))
            except Exception:
                logger.warning("Completion notification could not be delivered")
        logger.info(f"Job {job_id} completed → document_id={document_id}")

    except Exception:
        logger.exception(f"Job {job_id} failed")
        # Generic message to the client; details stay in the server log
        _update_job(
            job_id,
            status="error",
            error="Processing failed. Please try again or upload a clearer image.",
        )
        Path(image_path).unlink(missing_ok=True)  # don't keep files for failed jobs
        if notify:
            try:
                await notify(get_job(job_id))
            except Exception:
                pass
