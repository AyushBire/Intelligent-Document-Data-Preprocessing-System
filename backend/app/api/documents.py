import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ws import broadcast_job
from app.config import get_settings
from app.db import AsyncSessionLocal, get_db
from app.models.document import Document
from app.schemas.document import (
    ConfirmationCreate,
    ConfirmationResponse,
    DocumentCreate,
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

# Trust file CONTENT, not the client-supplied Content-Type header.
_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"BM", ".bmp"),
    (b"II*\x00", ".tiff"),
    (b"MM\x00*", ".tiff"),
]


def _detect_ext(head: bytes) -> str | None:
    for signature, ext in _SIGNATURES:
        if head.startswith(signature):
            return ext
    return None


def _to_response(doc: Document) -> DocumentResponse:
    # raw_json (str) is parsed into structured_data by the schema validator
    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        document_type=doc.document_type,
        ocr_text=doc.ocr_text,
        report=doc.report,
        structured_data=doc.raw_json,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


# ── Upload & process ───────────────────────────────────────────────────────────

@router.post("/upload", status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Accept a document image, store it under a generated name, and start the
    pipeline in the background. Returns a job_id to poll / subscribe to.
    """
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # Read in chunks and abort as soon as the limit is exceeded
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max {settings.MAX_UPLOAD_SIZE_MB} MB.",
            )
        chunks.append(chunk)
    contents = b"".join(chunks)

    ext = _detect_ext(contents[:16])
    if ext is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a JPG, PNG, BMP or TIFF image.",
        )

    # The original name is only a display label; never used as a path
    original_name = Path(file.filename or f"upload{ext}").name[:255]

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{uuid.uuid4().hex}{ext}"
    dest.write_bytes(contents)

    job_id = create_job()

    async def _save_to_db(result: dict, _stored_name: str, file_path: str) -> int:
        # Own session: the request-scoped one is closed once the response is sent
        async with AsyncSessionLocal() as session:
            doc = await svc.create_document(
                session,
                DocumentCreate(
                    filename=original_name,
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

    return {"job_id": job_id, "filename": original_name}


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
        return await svc.search_documents(db, search, limit=limit)
    return await svc.list_documents(db, document_type=document_type, limit=limit, offset=offset)


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
    return _to_response(doc)


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    body: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
):
    doc = await svc.update_document(db, document_id, body)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _to_response(doc)


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: int, db: AsyncSession = Depends(get_db)):
    file_path = await svc.delete_document(db, document_id)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Document not found")
    # Remove the stored upload too — no orphaned PII on disk
    if file_path:
        Path(file_path).unlink(missing_ok=True)


@router.delete("", status_code=204)
async def bulk_delete(
    ids: list[int] = Query(..., max_length=100),
    db: AsyncSession = Depends(get_db),
):
    for doc_id in ids:
        file_path = await svc.delete_document(db, doc_id)
        if file_path:
            Path(file_path).unlink(missing_ok=True)


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
