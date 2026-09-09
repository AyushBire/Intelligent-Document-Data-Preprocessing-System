import json
import logging
from typing import Any

from sqlalchemy import func, select, or_
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

# Map document_type string → child table model
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

# Map document_type → primary identifier column name on child table
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
    await db.flush()  # get doc.id before inserting child row

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
    dtype = document_type.lower().strip()
    model = TYPE_MODEL_MAP.get(dtype, None)
    id_field = TYPE_ID_FIELD.get(dtype)

    if model is None:
        child = GenericDocument(document_id=document_id)
    else:
        kwargs = {"document_id": document_id}
        if id_field:
            kwargs[id_field] = structured_data.get(id_field, "")
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
) -> list[Document]:
    stmt = select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)
    result = await db.execute(stmt)
    return list(result.scalars().all())


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

    if data.document_type is not None:
        doc.document_type = data.document_type
    if data.report is not None:
        doc.report = data.report
    if data.structured_data is not None:
        doc.raw_json = json.dumps(data.structured_data, ensure_ascii=False)

    await db.commit()
    await db.refresh(doc)
    logger.info(f"Updated document id={document_id}")
    return doc


async def delete_document(db: AsyncSession, document_id: int) -> bool:
    doc = await get_document(db, document_id)
    if not doc:
        return False
    await db.delete(doc)
    await db.commit()
    logger.info(f"Deleted document id={document_id}")
    return True


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

    return StatsResponse(total=total, by_type=by_type)


async def get_all_document_types(db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(Document.document_type).distinct().order_by(Document.document_type)
    )
    return [row[0] for row in result]