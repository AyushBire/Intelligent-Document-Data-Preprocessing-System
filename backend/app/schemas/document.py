import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class DocumentBase(BaseModel):
    filename: str
    file_path: str
    document_type: str
    ocr_text: str = ""
    report: str = ""


class DocumentCreate(DocumentBase):
    structured_data: dict[str, Any] = {}


class DocumentUpdate(BaseModel):
    document_type: str | None = None
    report: str | None = None
    structured_data: dict[str, Any] | None = None


class DocumentResponse(BaseModel):
    """Public API shape. file_path is intentionally NOT exposed (server path leak)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    document_type: str
    ocr_text: str
    report: str
    structured_data: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    @field_validator("structured_data", mode="before")
    @classmethod
    def parse_raw_json(cls, v: Any) -> dict:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        if isinstance(v, dict):
            return v
        return {}


class DocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    document_type: str
    created_at: datetime


class ConfirmationCreate(BaseModel):
    confirmed: bool = True
    confirmed_by: str = "anonymous"
    notes: str = ""


class ConfirmationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    confirmed: bool
    confirmed_by: str
    notes: str
    confirmed_at: datetime


class JobStatus(BaseModel):
    job_id: str
    status: str
    stage: str = ""
    progress: int = 0
    document_id: int | None = None
    error: str | None = None


class TypeCount(BaseModel):
    document_type: str
    count: int


class StatsResponse(BaseModel):
    total: int
    by_type: list[TypeCount]
