import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import (
    AadhaarCard,
    BankStatement,
    Document,
    DocumentConfirmation,
    DrivingLicense,
    GenericDocument,
    Invoice,
    PanCard,
    Passport,
    Receipt,
)
from app.schemas.document import (
    ConfirmationCreate,
    DocumentCreate,
    DocumentUpdate,
    StatsResponse,
    TypeCount,
)

logger = logging.getLogger("document_service")

# document_type string → child table model
TYPE_MODEL_MAP: dict[str, Any] = {
    "invoice": Invoice,
    "receipt": Receipt,
    "aadhaar": AadhaarCard,
    "aadhaar_card": AadhaarCard,
    "pan": PanCard,
    "pan_card": PanCard,
    "passport": Passport,
    "driving_license": DrivingLicense,
    "driving_licence": DrivingLicense,
    "bank_statement": BankStatement,
}

# document_type → identifier column on the child table
TYPE_ID_FIELD: dict[str, str] = {
    "invoice": "invoice_number",
    "receipt": "receipt_number",
    "aadhaar": "aadhaar_number",
    "aadhaar_card": "aadhaar_number",
    "pan": "pan_number",
    "pan_card": "pan_number",
    "passport": "passport_number",
    "driving_license": "license_number",
    "driving_licence": "license_number",
    "bank_statement": "account_number",
}

ALL_CHILD_MODELS = (
    Invoice, Receipt, AadhaarCard, PanCard, Passport,
    DrivingLicense, BankStatement, GenericDocument,
)


def _normalize_type(document_type: str) -> str:
    return document_type.strip().lower().replace(" ", "_")


async def create_document(db: AsyncSession, data: DocumentCreate) -> Document:
    raw_json = json.dumps(data.structured_data, ensure_ascii=False)

    doc = Document(
        filename=data.filename,
        file_path=data.file_path,
        document_type=data.document_type,
        ocr_text=data.ocr_text,
        report=data.report,
        raw_json=raw_json,
    )
    db.add(doc)
    await db.flush()  # get doc.id before inserting the child row

    _attach_child(db, doc.id, data.document_type, data.structured_data)

    await db.commit()
    await db.refresh(doc)
    logger.info(f"Created document id={doc.id} type={doc.document_type}")
    return doc


def _attach_child(
    db: AsyncSession,
    document_id: int,
    document_type: str,
    structured_data: dict,
) -> None:
    """Insert the type-specific child row."""
    dtype = _normalize_type(document_type)
    model = TYPE_MODEL_MAP.get(dtype)
    id_field = TYPE_ID_FIELD.get(dtype)

    if model is None:
        child = GenericDocument(document_id=document_id)
    else:
        kwargs: dict[str, Any] = {"document_id": document_id}
        if id_field:
            value = structured_data.get(id_field, "")
            kwargs[id_field] = "" if value is None else str(value)
        child = model(**kwargs)

    db.add(child)


async def get_document(db: AsyncSession, document_id: int) -> Document | None:
    result = await db.execute(select(Document).where(Document.id == document_id))
    return result.scalar_one_or_none()


async def list_documents(
    db: AsyncSession,
    document_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
    search: str | None = None,
) -> list[Document]:
    """Return filtered documents, ordered deterministically for pagination.

    Args: db: Session; document_type: Exact type; limit: Page size;
        offset: Rows to skip; search: Optional text query.
    Returns: Matching document rows. Raises: SQLAlchemyError on database failure.
    """
    stmt = _filter_documents(select(Document), document_type, search)
    stmt = stmt.order_by(Document.created_at.desc(), Document.id.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _filter_documents(stmt, document_type: str | None, search: str | None):
    """Apply shared predicates to a select or count statement.

    Args: stmt: SQL statement; document_type: Type filter; search: Literal query.
    Returns: Filtered statement. Raises: None.
    """
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        stmt = stmt.where(or_(Document.filename.ilike(like, escape="\\"),
                              Document.document_type.ilike(like, escape="\\"),
                              Document.ocr_text.ilike(like, escape="\\")))
    return stmt


async def count_documents(db: AsyncSession, document_type: str | None = None,
                          search: str | None = None) -> int:
    """Count rows using the same filters as the paginated list.

    Args: db: Session; document_type: Type filter; search: Text query.
    Returns: Matching row count. Raises: SQLAlchemyError on database failure.
    """
    result = await db.execute(_filter_documents(select(func.count()).select_from(Document), document_type, search))
    return result.scalar_one()


async def search_documents(
    db: AsyncSession,
    query: str,
    limit: int = 100,
) -> list[Document]:
    like = f"%{query}%"
    stmt = (
        select(Document)
        .where(
            or_(
                Document.filename.ilike(like),
                Document.document_type.ilike(like),
                Document.ocr_text.ilike(like),
            )
        )
        .order_by(Document.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_document(
    db: AsyncSession,
    document_id: int,
    data: DocumentUpdate,
) -> Document | None:
    doc = await get_document(db, document_id)
    if not doc:
        return None

    resync_child = False

    if data.document_type is not None:
        doc.document_type = _normalize_type(data.document_type)
        resync_child = True
    if data.report is not None:
        doc.report = data.report
    if data.structured_data is not None:
        doc.raw_json = json.dumps(data.structured_data, ensure_ascii=False)
        resync_child = True

    if resync_child:
        # Keep the type-specific table consistent with the edited type / fields
        for model in ALL_CHILD_MODELS:
            await db.execute(
                delete(model)
                .where(model.document_id == doc.id)
                .execution_options(synchronize_session=False)
            )
        try:
            structured = json.loads(doc.raw_json)
        except Exception:
            structured = {}
        _attach_child(db, doc.id, doc.document_type, structured if isinstance(structured, dict) else {})

    await db.commit()
    await db.refresh(doc)
    logger.info(f"Updated document id={document_id}")
    return doc


async def delete_document(db: AsyncSession, document_id: int) -> str | None:
    """Delete a document. Returns its stored file_path (so the caller can remove
    the file from disk), or None if the document does not exist."""
    doc = await get_document(db, document_id)
    if not doc:
        return None
    file_path = doc.file_path or ""
    await db.delete(doc)
    await db.commit()
    logger.info(f"Deleted document id={document_id}")
    return file_path


async def confirm_document(
    db: AsyncSession,
    document_id: int,
    data: ConfirmationCreate,
) -> DocumentConfirmation | None:
    doc = await get_document(db, document_id)
    if not doc:
        return None

    confirmation = DocumentConfirmation(
        document_id=document_id,
        confirmed=data.confirmed,
        confirmed_by=data.confirmed_by,
        notes=data.notes,
    )
    db.add(confirmation)
    await db.commit()
    await db.refresh(confirmation)
    return confirmation


async def get_stats(db: AsyncSession) -> StatsResponse:
    """Return total, UTC calendar-day count and type distribution.

    Args: db: Active session. Returns: Statistics.
    Raises: SQLAlchemyError on database failure.
    """
    total_result = await db.execute(select(func.count()).select_from(Document))
    total = total_result.scalar_one()

    by_type_result = await db.execute(
        select(Document.document_type, func.count().label("cnt"))
        .group_by(Document.document_type)
        .order_by(func.count().desc())
    )
    by_type = [
        TypeCount(document_type=row.document_type, count=row.cnt)
        for row in by_type_result
    ]

    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today = await db.execute(select(func.count()).select_from(Document).where(
        Document.created_at >= start, Document.created_at < start + timedelta(days=1)))
    return StatsResponse(total=total, by_type=by_type, today=today.scalar_one())


async def get_all_document_types(db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(Document.document_type).distinct().order_by(Document.document_type)
    )
    return [row[0] for row in result]
