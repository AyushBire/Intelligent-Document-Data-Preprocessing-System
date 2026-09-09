import json
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ws import broadcast_job
from app.config import get_settings
from app.db import get_db
from app.schemas.document import (
    ConfirmationCreate,
    ConfirmationResponse,
    DocumentListItem,
    DocumentResponse,
    DocumentUpdate,
    JobStatus,
    StatsResponse,
)
from app.services import document_service as svc
from app.services.pipeline_service import create_job, get_job, run_pipeline

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger("api.documents")
settings = get_settings()


# ── Upload & process ───────────────────────────────────────────────────────────

@router.post("/upload", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Accept a document image, save it to disk, and kick off the pipeline
    as a background task. Returns a job_id immediately so the client can
    track progress via GET /jobs/{job_id} or the WebSocket.
    """
    # Validate file type
    allowed = {"image/jpeg", "image/png", "image/bmp", "image/tiff", "application/pdf"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {file.content_type}")

    # Validate size
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    # Save to uploads/
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(exist_ok=True)
    dest = upload_dir / file.filename
    dest.write_bytes(contents)

    # Create job and start background task
    job_id = create_job()

    async def _save_to_db(result: dict, filename: str, file_path: str) -> int:
        from app.schemas.document import DocumentCreate
        doc = await svc.create_document(
            db,
            DocumentCreate(
                filename=filename,
                file_path=file_path,
                document_type=result["document_type"],
                ocr_text=result["ocr_text"],
                report=result["report"],
                structured_data=result["structured_data"],
            ),
        )
        return doc.id

    async def _notify(job: JobStatus):
        await broadcast_job(job_id, job.model_dump())

    background_tasks.add_task(
        run_pipeline,
        job_id=job_id,
        image_path=str(dest),
        save_to_db=_save_to_db,
        notify=_notify,
    )

    return {"job_id": job_id, "filename": file.filename}


# ── Job status (polling fallback) ──────────────────────────────────────────────

@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ── CRUD ───────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[DocumentListItem])
async def list_documents(
    document_type: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    if search:
        docs = await svc.search_documents(db, search, limit=limit)
    else:
        docs = await svc.list_documents(db, document_type=document_type, limit=limit, offset=offset)
    return docs


@router.get("/types", response_model=list[str])
async def get_document_types(db: AsyncSession = Depends(get_db)):
    return await svc.get_all_document_types(db)


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    return await svc.get_stats(db)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    doc = await svc.get_document(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Build response — structured_data from raw_json
    data = doc.__dict__.copy()
    try:
        data["structured_data"] = json.loads(doc.raw_json)
    except Exception:
        data["structured_data"] = {}

    return DocumentResponse(**data)


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    body: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
):
    doc = await svc.update_document(db, document_id, body)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    data = doc.__dict__.copy()
    try:
        data["structured_data"] = json.loads(doc.raw_json)
    except Exception:
        data["structured_data"] = {}

    return DocumentResponse(**data)


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: int, db: AsyncSession = Depends(get_db)):
    deleted = await svc.delete_document(db, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")


@router.delete("", status_code=204)
async def bulk_delete(
    ids: list[int] = Query(...),
    db: AsyncSession = Depends(get_db),
):
    for doc_id in ids:
        await svc.delete_document(db, doc_id)


# ── Confirmations ──────────────────────────────────────────────────────────────

@router.post("/{document_id}/confirm", response_model=ConfirmationResponse)
async def confirm_document(
    document_id: int,
    body: ConfirmationCreate,
    db: AsyncSession = Depends(get_db),
):
    confirmation = await svc.confirm_document(db, document_id, body)
    if not confirmation:
        raise HTTPException(status_code=404, detail="Document not found")
    return confirmation