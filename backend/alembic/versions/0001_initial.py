"""Create the original IDPS document schema.

Revision ID: 0001_initial
Revises: None
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

CHILD_TABLES = (
    ("invoices", "invoice_number"), ("receipts", "receipt_number"),
    ("aadhaar_cards", "aadhaar_number"), ("pan_cards", "pan_number"),
    ("passports", "passport_number"), ("driving_licenses", "license_number"),
    ("bank_statements", "account_number"), ("generic_documents", None),
)


def upgrade() -> None:
    """Create document, child and confirmation tables with indexes.

    Returns: None. Raises: SQLAlchemyError if schema creation fails.
    """
    op.create_table("documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("document_type", sa.String(), nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=False),
        sa.Column("report", sa.Text(), nullable=False),
        sa.Column("raw_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_documents_document_type", "documents", ["document_type"])
    op.create_index("ix_documents_created_at", "documents", ["created_at"])
    for table, identifier in CHILD_TABLES:
        columns = [sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
                   sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False)]
        if identifier:
            columns.append(sa.Column(identifier, sa.String(), nullable=False))
        op.create_table(table, *columns)
    op.create_table("document_confirmations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("confirmed_by", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    """Remove the initial schema in dependency order.

    Returns: None. Raises: SQLAlchemyError if schema removal fails.
    """
    op.drop_table("document_confirmations")
    for table, _ in reversed(CHILD_TABLES):
        op.drop_table(table)
    op.drop_index("ix_documents_created_at", table_name="documents")
    op.drop_index("ix_documents_document_type", table_name="documents")
    op.drop_table("documents")
