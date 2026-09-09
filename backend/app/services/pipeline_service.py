"""
Wraps the existing DocumentPipeline so it can run inside
FastAPI BackgroundTasks without blocking the event loop.

The pipeline (EasyOCR + CV2 + Gemini) is CPU/IO-bound,
so we run it in a thread pool via asyncio.to_thread().
"""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Callable

from app.schemas.document import JobStatus

logger = logging.getLogger("pipeline_service")

# In-memory job store  {job_id: JobStatus}
# Fine for a single-process server; swap for Redis if you scale out.
_jobs: dict[str, JobStatus] = {}


def create_job() -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = JobStatus(job_id=job_id, status="pending", stage="", progress=0)
    return job_id


def get_job(job_id: str) -> JobStatus | None:
    return _jobs.get(job_id)


def _update_job(job_id: str, **kwargs) -> None:
    job = _jobs.get(job_id)
    if job:
        for k, v in kwargs.items():
            setattr(job, k, v)


async def run_pipeline(
    job_id: str,
    image_path: str,
    save_to_db: Callable,          # async callable: (result_dict) -> document_id
    notify: Callable | None = None,  # optional async callable for WebSocket push
) -> None:
    """
    Runs the full pipeline in a background thread, updating job status at each
    stage so the frontend can track progress via polling or WebSocket.
    """

    async def push(stage: str, progress: int, **extra):
        _update_job(job_id, stage=stage, progress=progress, status="processing", **extra)
        if notify:
            try:
                await notify(get_job(job_id))
            except Exception:
                pass

    try:
        _update_job(job_id, status="processing", stage="preprocessing", progress=5)

        # --- Stage 1: preprocessing (CPU-bound, run in thread) ---
        await push("preprocessing", 10)
        from processing.pipeline import DocumentPipeline  # lazy import

        pipeline = _get_pipeline()

        def _preprocess():
            from processing.preprocessing import ImagePreprocessor
            preprocessor = ImagePreprocessor()
            return preprocessor.process(image_path)

        clean_image = await asyncio.to_thread(_preprocess)
        await push("preprocessing", 25)

        # --- Stage 2: OCR ---
        await push("ocr", 30)

        def _ocr():
            ocr_results = pipeline.ocr.process(clean_image)
            ocr_text = pipeline.ocr.extract_text(ocr_results)
            boxed = pipeline.visualizer.draw_boxes(
                clean_image, ocr_results, show_text=False, show_confidence=False
            )
            return ocr_results, ocr_text, boxed

        ocr_results, ocr_text, boxed_image = await asyncio.to_thread(_ocr)
        await push("ocr", 55)

        # --- Stage 3: LLM ---
        await push("llm", 60)

        def _llm():
            return pipeline.llm.process(ocr_text)

        llm_output = await asyncio.to_thread(_llm)
        await push("llm", 80)

        # --- Stage 4: Save to DB ---
        await push("saving", 85)

        result = {
            "clean_image": clean_image,
            "boxed_image": boxed_image,
            "ocr_results": ocr_results,
            "ocr_text": ocr_text,
            "document_type": llm_output.get("document_type", "unknown"),
            "structured_data": llm_output.get("structured_data", {}),
            "report": llm_output.get("report", ""),
        }

        document_id = await save_to_db(result, Path(image_path).name, image_path)

        _update_job(
            job_id,
            status="done",
            stage="done",
            progress=100,
            document_id=document_id,
        )
        if notify:
            await notify(get_job(job_id))

        logger.info(f"Job {job_id} completed → document_id={document_id}")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        _update_job(job_id, status="error", error=str(e))
        if notify:
            await notify(get_job(job_id))


# ── Singleton pipeline (loaded once per process) ───────────────────────────────

_pipeline_instance = None


def _get_pipeline():
    global _pipeline_instance
    if _pipeline_instance is None:
        from processing.pipeline import DocumentPipeline
        _pipeline_instance = DocumentPipeline()
        logger.info("DocumentPipeline loaded (singleton)")
    return _pipeline_instance