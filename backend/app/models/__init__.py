# Import every model so Base.metadata knows about all tables
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
