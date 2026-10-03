from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    document_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    ocr_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    report: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    invoice: Mapped["Invoice"] = relationship(
        back_populates="document", cascade="all, delete-orphan", uselist=False
    )
    receipt: Mapped["Receipt"] = relationship(
        back_populates="document", cascade="all, delete-orphan", uselist=False
    )
    aadhaar_card: Mapped["AadhaarCard"] = relationship(
        back_populates="document", cascade="all, delete-orphan", uselist=False
    )
    pan_card: Mapped["PanCard"] = relationship(
        back_populates="document", cascade="all, delete-orphan", uselist=False
    )
    passport: Mapped["Passport"] = relationship(
        back_populates="document", cascade="all, delete-orphan", uselist=False
    )
    driving_license: Mapped["DrivingLicense"] = relationship(
        back_populates="document", cascade="all, delete-orphan", uselist=False
    )
    bank_statement: Mapped["BankStatement"] = relationship(
        back_populates="document", cascade="all, delete-orphan", uselist=False
    )
    generic_document: Mapped["GenericDocument"] = relationship(
        back_populates="document", cascade="all, delete-orphan", uselist=False
    )
    confirmations: Mapped[list["DocumentConfirmation"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    invoice_number: Mapped[str] = mapped_column(String, default="")
    document: Mapped["Document"] = relationship(back_populates="invoice")


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    receipt_number: Mapped[str] = mapped_column(String, default="")
    document: Mapped["Document"] = relationship(back_populates="receipt")


class AadhaarCard(Base):
    __tablename__ = "aadhaar_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    aadhaar_number: Mapped[str] = mapped_column(String, default="")
    document: Mapped["Document"] = relationship(back_populates="aadhaar_card")


class PanCard(Base):
    __tablename__ = "pan_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    pan_number: Mapped[str] = mapped_column(String, default="")
    document: Mapped["Document"] = relationship(back_populates="pan_card")


class Passport(Base):
    __tablename__ = "passports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    passport_number: Mapped[str] = mapped_column(String, default="")
    document: Mapped["Document"] = relationship(back_populates="passport")


class DrivingLicense(Base):
    __tablename__ = "driving_licenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    license_number: Mapped[str] = mapped_column(String, default="")
    document: Mapped["Document"] = relationship(back_populates="driving_license")


class BankStatement(Base):
    __tablename__ = "bank_statements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    account_number: Mapped[str] = mapped_column(String, default="")
    document: Mapped["Document"] = relationship(back_populates="bank_statement")


class GenericDocument(Base):
    __tablename__ = "generic_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    document: Mapped["Document"] = relationship(back_populates="generic_document")


class DocumentConfirmation(Base):
    __tablename__ = "document_confirmations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_by: Mapped[str] = mapped_column(String, default="anonymous")
    notes: Mapped[str] = mapped_column(Text, default="")
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    document: Mapped["Document"] = relationship(back_populates="confirmations")