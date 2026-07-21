import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger("database")
logging.basicConfig(level=logging.INFO)

DB_PATH = Path("Database") / "db" / "idps.sqlite3"
SCHEMA_PATH = Path("Database") / "schema.sql"

TABLE_MAP = {
    "invoice": "invoices",
    "receipt": "receipts",
    "aadhaar": "aadhaar_cards",
    "aadhaar_card": "aadhaar_cards",
    "pan": "pan_cards",
    "pan_card": "pan_cards",
    "passport": "passports",
    "driving_license": "driving_licenses",
    "driving licence": "driving_licenses",
    "bank_statement": "bank_statements",
}


class DatabaseManager:

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        logger.info(f"Database initialized at {self.db_path}")

    # ── Column helpers ────────────────────────────────────────────────────────

    def get_columns(self, table):
        with self._connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            return [row["name"] for row in rows]

    def add_missing_columns(self, table, data):
        existing_columns = self.get_columns(table)
        with self._connect() as conn:
            for field in data.keys():
                if field not in existing_columns:
                    logger.info(f"Adding column '{field}' to {table}")
                    conn.execute(
                        f'ALTER TABLE {table} ADD COLUMN "{field}" TEXT DEFAULT \'\''
                    )

    # ── INSERT ────────────────────────────────────────────────────────────────

    def save_relative_document(self, document_id, document_type, structured_data):
        table = TABLE_MAP.get(document_type.lower(), "generic_documents")
        self.add_missing_columns(table, structured_data)

        columns = ["document_id"] + list(structured_data.keys())
        values = [document_id] + list(structured_data.values())
        placeholders = ",".join(["?"] * len(values))
        quoted_columns = ",".join([f'"{col}"' for col in columns])

        query = f"INSERT INTO {table} ({quoted_columns}) VALUES ({placeholders})"

        with self._connect() as conn:
            conn.execute(query, values)

        logger.info(f"Inserted document {document_id} into {table}")

    def save_document(
        self,
        filename,
        file_path,
        document_type,
        ocr_text,
        report,
        structured_data,
    ):
        raw_json = json.dumps(structured_data, ensure_ascii=False)

        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO documents
                    (filename, file_path, document_type, ocr_text, report, raw_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (filename, file_path, document_type, ocr_text, report, raw_json),
            )
            document_id = cur.lastrowid

        self.save_relative_document(document_id, document_type, structured_data)
        logger.info(f"Saved document {document_id}")
        return document_id

    # ── READ ──────────────────────────────────────────────────────────────────

    def get_document(self, document_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            return dict(row) if row else {}

    def list_documents(self, limit=100, document_type=None, status=None):
        """
        List documents with optional filters for type and status.
        """
        conditions = []
        params = []

        if document_type:
            conditions.append("document_type = ?")
            params.append(document_type)

        if status:
            conditions.append("status = ?")
            params.append(status)

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, filename, document_type, status, created_at
                FROM documents
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
            return [dict(row) for row in rows]

    def get_all_document_types(self):
        """Return distinct document types present in the database."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT document_type FROM documents ORDER BY document_type"
            ).fetchall()
            return [row["document_type"] for row in rows]

    def search_documents(self, query: str, limit: int = 100):
        """
        Full-text search across filename, document_type, and ocr_text.
        """
        like = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, filename, document_type, status, created_at
                FROM documents
                WHERE filename LIKE ?
                   OR document_type LIKE ?
                   OR ocr_text LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (like, like, like, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    # ── UPDATE ────────────────────────────────────────────────────────────────

    def confirm_document(
        self,
        document_id,
        confirmed_by="anonymous",
        notes="",
        confirmed=True,
    ):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO document_confirmations
                    (document_id, confirmed, confirmed_by, notes)
                VALUES (?, ?, ?, ?)
                """,
                (document_id, int(confirmed), confirmed_by, notes),
            )
            conn.execute(
                """
                UPDATE documents
                SET status = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                ("confirmed" if confirmed else "rejected", document_id),
            )
        logger.info(f"Document {document_id} {'confirmed' if confirmed else 'rejected'}.")

    def update_document(
        self,
        document_id: int,
        document_type: str = None,
        report: str = None,
        structured_data: dict = None,
        status: str = None,
    ):
        """
        Update editable fields of a document record.
        Only non-None arguments are applied.
        """
        fields = []
        values = []

        if document_type is not None:
            fields.append("document_type = ?")
            values.append(document_type)

        if report is not None:
            fields.append("report = ?")
            values.append(report)

        if structured_data is not None:
            fields.append("raw_json = ?")
            values.append(json.dumps(structured_data, ensure_ascii=False))

        if status is not None:
            fields.append("status = ?")
            values.append(status)

        if not fields:
            logger.warning("update_document called with nothing to update.")
            return

        fields.append("updated_at = datetime('now')")
        values.append(document_id)

        with self._connect() as conn:
            conn.execute(
                f"UPDATE documents SET {', '.join(fields)} WHERE id = ?",
                values,
            )

        logger.info(f"Updated document {document_id}: {[f.split(' =')[0] for f in fields[:-1]]}")

    # ── DELETE ────────────────────────────────────────────────────────────────

    def delete_document(self, document_id: int):
        """
        Delete a document and its related type-specific record.
        Cascades via FK if schema defines ON DELETE CASCADE,
        otherwise deletes from the type table manually first.
        """
        # Fetch type so we can clean up the type-specific table
        doc = self.get_document(document_id)
        document_type = doc.get("document_type", "")
        table = TABLE_MAP.get(document_type.lower(), "generic_documents")

        with self._connect() as conn:
            # Remove from type-specific table
            try:
                conn.execute(
                    f"DELETE FROM {table} WHERE document_id = ?",
                    (document_id,),
                )
            except Exception as e:
                logger.warning(f"Could not delete from {table}: {e}")

            # Remove confirmations
            try:
                conn.execute(
                    "DELETE FROM document_confirmations WHERE document_id = ?",
                    (document_id,),
                )
            except Exception as e:
                logger.warning(f"Could not delete confirmations: {e}")

            # Remove master record
            conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))

        logger.info(f"Deleted document {document_id} from documents and {table}")

    def delete_documents_bulk(self, document_ids: list):
        """Delete multiple documents by ID list."""
        for doc_id in document_ids:
            self.delete_document(doc_id)
        logger.info(f"Bulk deleted {len(document_ids)} documents.")

    # ── STATS ─────────────────────────────────────────────────────────────────

    def get_stats(self):
        """Return summary counts for the dashboard."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            confirmed = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE status = 'confirmed'"
            ).fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE status = 'pending'"
            ).fetchone()[0]
            by_type = conn.execute(
                """
                SELECT document_type, COUNT(*) AS cnt
                FROM documents
                GROUP BY document_type
                ORDER BY cnt DESC
                """
            ).fetchall()
        return {
            "total": total,
            "confirmed": confirmed,
            "pending": pending,
            "by_type": [dict(r) for r in by_type],
        }