"""Add durable cloud sessions, job state and private source image tables."""
from alembic import op
import sqlalchemy as sa

revision = "0002_cloud_runtime"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create cloud runtime storage. Returns: None. Raises: Database migration errors."""
    op.create_table("browser_sessions", sa.Column("token_hash", sa.String(64), primary_key=True), sa.Column("credential_version", sa.String(64), nullable=False), sa.Column("expires_at", sa.Integer(), nullable=False))
    op.create_index("ix_browser_sessions_expires_at", "browser_sessions", ["expires_at"])
    op.create_table("login_attempts", sa.Column("key", sa.String(64), primary_key=True), sa.Column("count", sa.Integer(), nullable=False), sa.Column("expires_at", sa.Integer(), nullable=False))
    op.create_index("ix_login_attempts_expires_at", "login_attempts", ["expires_at"])
    op.create_table("document_files", sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True), sa.Column("content", sa.LargeBinary(), nullable=False), sa.Column("media_type", sa.String(32), nullable=False))
    op.create_table("processing_jobs", sa.Column("job_id", sa.String(36), primary_key=True), sa.Column("payload", sa.Text(), nullable=False), sa.Column("expires_at", sa.Integer(), nullable=False))
    op.create_index("ix_processing_jobs_expires_at", "processing_jobs", ["expires_at"])


def downgrade() -> None:
    """Remove cloud runtime tables. Returns: None. Raises: Database migration errors."""
    op.drop_table("processing_jobs")
    op.drop_table("document_files")
    op.drop_table("login_attempts")
    op.drop_table("browser_sessions")
