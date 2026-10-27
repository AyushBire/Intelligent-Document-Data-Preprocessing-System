# Import every model so Base.metadata knows about all tables
from app.models.cloud import BrowserSession, DocumentFile, LoginAttempt, ProcessingJob  # noqa: F401
# (needed by Alembic autogenerate and create_all).
from app.models.document import (  # noqa: F401
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
