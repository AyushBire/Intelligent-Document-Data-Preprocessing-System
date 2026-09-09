import json
import logging
from pathlib import Path

import cv2
import pandas as pd
import streamlit as st
from PIL import Image

from pipeline import DocumentPipeline
from processing.database import DatabaseManager

logger = logging.getLogger("app")
logging.basicConfig(level=logging.INFO)

st.set_page_config(
    page_title="IDPS",
    page_icon="📄",
    layout="wide",
)

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { min-width: 200px; max-width: 220px; }
    .stat-box {
        background: #1e2130;
        border: 1px solid #3a3f55;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        margin-bottom: 4px;
    }
    .stat-num {
        font-size: 1.8rem;
        font-weight: 700;
        line-height: 1.2;
        color: #ffffff;
        word-break: break-word;
    }
    .stat-lbl {
        font-size: 0.75rem;
        color: #a0a8c0;
        margin-top: 4px;
    }
    .field-label {
        font-size: 0.78rem;
        color: #a0a8c0;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 2px;
    }
    .field-value {
        font-size: 0.97rem;
        color: #ffffff;
        background: #1e2130;
        border: 1px solid #3a3f55;
        border-radius: 6px;
        padding: 7px 10px;
        margin-bottom: 10px;
        word-break: break-all;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

#  document type → default seed fields shown in the Insert form 
TYPE_SEED_FIELDS = {
    "invoice":         ["invoice_number", "vendor_name", "invoice_date", "due_date", "total_amount", "currency", "tax_amount"],
    "receipt":         ["receipt_number", "merchant_name", "date", "total_amount", "payment_method"],
    "aadhaar":         ["aadhaar_number", "name", "date_of_birth", "gender", "address"],
    "pan":             ["pan_number", "name", "father_name", "date_of_birth"],
    "passport":        ["passport_number", "surname", "given_names", "nationality", "date_of_birth", "date_of_issue", "date_of_expiry", "place_of_birth"],
    "driving_license": ["license_number", "name", "date_of_birth", "address", "issue_date", "expiry_date", "vehicle_class"],
    "bank_statement":  ["account_number", "account_holder", "bank_name", "statement_period", "opening_balance", "closing_balance"],
    "other":           [],
}

ALL_DOC_TYPES = list(TYPE_SEED_FIELDS.keys())


def pretty_label(key: str) -> str:
    return key.replace("_", " ").title()


# Resource caching 
@st.cache_resource
def load_pipeline():
    return DocumentPipeline()

@st.cache_resource
def load_db():
    return DatabaseManager()

try:
    pipeline = load_pipeline()
    db = load_db()
except Exception as e:
    st.error(f"Initialization failed: {e}")
    st.stop()

#  Sidebar navigation 
with st.sidebar:
    st.markdown("## 📄 IDPS")
    st.divider()
    page = st.radio(
        "Navigate",
        ["🔍 Process Document", "🗄️ Database Manager"],
        label_visibility="collapsed",
    )

#  PAGE 1 — PROCESS DOCUMENT

if page == "🔍 Process Document":

    st.markdown("### 🔍 Process Document")

    uploaded_file = st.file_uploader(
        "Upload document",
        type=["jpg", "jpeg", "png", "bmp", "tiff", "pdf"],
        label_visibility="collapsed",
    )

    if uploaded_file is None:
        st.info("Upload a document (JPG, PNG, BMP, TIFF, PDF) to begin.")
        st.stop()

    try:
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        image_path = upload_dir / uploaded_file.name
        with open(image_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        original_image = Image.open(image_path)
    except Exception as e:
        st.error(f"Could not read file: {e}")
        st.stop()

    with st.spinner("Processing…"):
        try:
            result = pipeline.process(str(image_path), save_outputs=False)
        except Exception as e:
            st.error(f"Processing failed: {e}")
            st.stop()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("Original")
        st.image(original_image, use_container_width=True)
    with c2:
        st.caption("Preprocessed")
        try:
            st.image(result["clean_image"], clamp=True, use_container_width=True)
        except Exception:
            st.warning("Unavailable")
    with c3:
        st.caption("OCR Detection")
        try:
            boxed = cv2.cvtColor(result["boxed_image"], cv2.COLOR_BGR2RGB)
            st.image(boxed, use_container_width=True)
        except Exception:
            st.warning("Unavailable")

    st.divider()
    st.markdown(f"**Detected type:** `{result['document_type']}`")

    # Show extracted fields as a clean table instead of raw JSON
    structured = result.get("structured_data", {})
    if structured:
        st.markdown("**Extracted Fields**")
        field_rows = [{"Field": pretty_label(k), "Value": str(v)} for k, v in structured.items()]
        st.dataframe(pd.DataFrame(field_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No structured data extracted.")

    with st.expander("Report"):
        st.write(result["report"] or "_No report generated._")
    with st.expander("Raw OCR Text"):
        st.text_area("", result["ocr_text"], height=180, label_visibility="collapsed")

    st.divider()

    save_col, dl_col = st.columns([1, 1])

    with save_col:
        st.markdown("**Save to Database**")
        if st.button("💾 Save", use_container_width=True):
            try:
                doc_id = db.save_document(
                    filename=uploaded_file.name,
                    file_path=str(image_path),
                    document_type=result["document_type"],
                    ocr_text=result["ocr_text"],
                    report=result["report"],
                    structured_data=result["structured_data"],
                )
                st.success(f"Saved — ID: **{doc_id}**")
            except Exception as e:
                st.error(f"Save failed: {e}")

    with dl_col:
        st.markdown("**Download Results**")
        try:
            json_data = json.dumps(result["structured_data"], indent=4, ensure_ascii=False)
            st.download_button("⬇ Structured JSON", json_data,
                               file_name="structured_data.json",
                               mime="application/json",
                               use_container_width=True)
            st.download_button("⬇ Report", result["report"] or "",
                               file_name="document_report.txt",
                               mime="text/plain",
                               use_container_width=True)
        except Exception as e:
            st.warning(f"Could not prepare downloads: {e}")


#  PAGE 2 — DATABASE MANAGER

elif page == "🗄️ Database Manager":

    st.markdown("### 🗄️ Database Manager")

    # Stats bar
    try:
        stats = db.get_stats()
        s1, s2 = st.columns(2)

        def stat_box(col, num, label):
            col.markdown(
                f'<div class="stat-box"><div class="stat-num">{num}</div>'
                f'<div class="stat-lbl">{label}</div></div>',
                unsafe_allow_html=True,
            )

        stat_box(s1, stats["total"], "Total Documents")
        top_type = stats["by_type"][0]["document_type"] if stats["by_type"] else "—"
        stat_box(s2, top_type, "Most Common Type")
    except Exception as e:
        st.warning(f"Could not load stats: {e}")

    st.divider()

    db_tab1, db_tab2, db_tab3, db_tab4 = st.tabs([
        "📋 View & Search",
        "➕ Insert",
        "✏️ Edit",
        "🗑️ Delete",
    ])

 
    #  TAB 1 — VIEW & SEARCH

    with db_tab1:
        f1, f2 = st.columns([2, 1])
        with f1:
            search_query = st.text_input(
                "Search",
                placeholder="Search filename, type, or OCR text…",
                label_visibility="collapsed",
            )
        with f2:
            try:
                all_types = ["All types"] + db.get_all_document_types()
            except Exception:
                all_types = ["All types"]
            type_filter = st.selectbox("Type", all_types, label_visibility="collapsed")

        try:
            if search_query:
                rows = db.search_documents(search_query)
            else:
                rows = db.list_documents(
                    document_type=None if type_filter == "All types" else type_filter,
                )
        except Exception as e:
            st.error(f"Query failed: {e}")
            rows = []

        if not rows:
            st.info("No documents found.")
        else:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.markdown("**View full record**")
            view_id = st.number_input(
                "Document ID", min_value=1, step=1,
                key="view_id", label_visibility="collapsed",
            )
            if st.button("🔎 Load Record", use_container_width=False):
                try:
                    doc = db.get_document_with_fields(int(view_id))
                    if not doc:
                        st.warning(f"No document with ID {int(view_id)}.")
                    else:
                        # Meta row 
                        m1, m2, m3, m4 = st.columns(4)
                        m1.markdown(f"<div class='field-label'>ID</div><div class='field-value'>{doc.get('id')}</div>", unsafe_allow_html=True)
                        m2.markdown(f"<div class='field-label'>Filename</div><div class='field-value'>{doc.get('filename')}</div>", unsafe_allow_html=True)
                        m3.markdown(f"<div class='field-label'>Type</div><div class='field-value'>{doc.get('document_type')}</div>", unsafe_allow_html=True)
                        m4.markdown(f"<div class='field-label'>Created</div><div class='field-value'>{doc.get('created_at')}</div>", unsafe_allow_html=True)

                        # Extracted fields from the type-specific table 
                        type_fields = doc.get("type_fields", {})
                        if type_fields:
                            st.markdown("**Document Fields** _(stored in database)_")
                            cols = st.columns(3)
                            for i, (k, v) in enumerate(type_fields.items()):
                                cols[i % 3].markdown(
                                    f"<div class='field-label'>{pretty_label(k)}</div>"
                                    f"<div class='field-value'>{v if v not in (None, '') else '—'}</div>",
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.info("No type-specific fields found for this document.")

                        with st.expander("Report"):
                            st.write(doc.get("report") or "_No report._")
                        with st.expander("Raw OCR Text"):
                            st.text(doc.get("ocr_text", ""))
                except Exception as e:
                    st.error(f"Load failed: {e}")

    #  TAB 2 — INSERT
    with db_tab2:
        st.markdown("Insert a document record manually. Fields are saved directly into the database.")

        i1, i2 = st.columns(2)
        with i1:
            ins_filename = st.text_input("Filename *", placeholder="e.g. invoice_001.jpg")
        with i2:
            ins_type = st.selectbox("Document type *", ALL_DOC_TYPES, key="ins_type_select")

        ins_filepath = st.text_input("File path", placeholder="/path/to/file.jpg")

        # Dynamic field form based on selected type
        seed_fields = TYPE_SEED_FIELDS.get(ins_type, [])
        st.markdown(f"**Fields for `{ins_type}`**")

        # Allow user to also add extra custom fields
        if "ins_extra_fields" not in st.session_state:
            st.session_state.ins_extra_fields = []

        field_values = {}
        if seed_fields:
            cols = st.columns(2)
            for idx, field in enumerate(seed_fields):
                val = cols[idx % 2].text_input(
                    pretty_label(field),
                    key=f"ins_field_{field}",
                    placeholder=f"Enter {pretty_label(field)}…",
                )
                field_values[field] = val
        else:
            st.info("Select a document type to see its fields, or add custom fields below.")

        # Extra custom fields
        with st.expander("➕ Add custom fields"):
            new_field_name = st.text_input("Field name (snake_case)", key="ins_new_field_name")
            new_field_val = st.text_input("Field value", key="ins_new_field_val")
            if st.button("Add field", key="ins_add_field_btn"):
                if new_field_name.strip():
                    st.session_state.ins_extra_fields.append(
                        (new_field_name.strip().lower().replace(" ", "_"), new_field_val.strip())
                    )
            for fname, fval in st.session_state.ins_extra_fields:
                field_values[fname] = fval
                st.markdown(f"• **{pretty_label(fname)}**: `{fval}`")

        ins_report = st.text_area("Report / Summary", height=80, placeholder="Optional…")
        ins_ocr    = st.text_area("OCR Text", height=80, placeholder="Optional…")

        if st.button("➕ Insert Record", use_container_width=False):
            if not ins_filename.strip():
                st.warning("Filename is required.")
            else:
                try:
                    # Strip empty strings so schema defaults take over
                    clean_fields = {k: v for k, v in field_values.items() if v != ""}
                    doc_id = db.save_document(
                        filename=ins_filename.strip(),
                        file_path=ins_filepath.strip(),
                        document_type=ins_type,
                        ocr_text=ins_ocr,
                        report=ins_report,
                        structured_data=clean_fields,
                    )
                    st.session_state.ins_extra_fields = []
                    st.success(f"Inserted successfully — ID: **{doc_id}**")
                except Exception as e:
                    st.error(f"Insert failed: {e}")

    #  TAB 3 — EDIT
    with db_tab3:
        st.markdown("Load a record by ID, edit its fields, then save back to the database.")

        edit_id = st.number_input(
            "Document ID to edit", min_value=1, step=1,
            key="edit_id", label_visibility="collapsed",
        )

        if "edit_doc" not in st.session_state:
            st.session_state.edit_doc = None

        if st.button("📂 Load for Editing"):
            try:
                doc = db.get_document_with_fields(int(edit_id))
                if doc:
                    st.session_state.edit_doc = doc
                else:
                    st.warning(f"No document with ID {int(edit_id)}.")
            except Exception as e:
                st.error(f"Load failed: {e}")

        if st.session_state.edit_doc:
            doc = st.session_state.edit_doc
            st.markdown(f"**Editing ID {doc['id']} — {doc['filename']}**")

            e1, e2 = st.columns(2)
            with e1:
                new_type = st.text_input(
                    "Document type",
                    value=doc.get("document_type", ""),
                    key="edit_type_input",
                )
            with e2:
                new_report = st.text_area(
                    "Report",
                    value=doc.get("report", ""),
                    height=100,
                    key="edit_report_input",
                )

            # Edit the actual type-specific fields
            type_fields = doc.get("type_fields", {})
            updated_fields = {}

            if type_fields:
                st.markdown("**Document Fields** _(edit below)_")
                cols = st.columns(2)
                for idx, (k, v) in enumerate(type_fields.items()):
                    new_val = cols[idx % 2].text_input(
                        pretty_label(k),
                        value=str(v) if v is not None else "",
                        key=f"edit_field_{k}",
                    )
                    updated_fields[k] = new_val
            else:
                st.info("No editable fields found for this document type.")

            if st.button("💾 Save Changes", use_container_width=False):
                try:
                    # Update documents table (type + report)
                    db.update_document(
                        int(doc["id"]),
                        document_type=new_type.strip() or None,
                        report=new_report,
                        structured_data=updated_fields if updated_fields else None,
                    )
                    # Update the type-specific table columns
                    if updated_fields:
                        db.update_type_table_fields(
                            int(doc["id"]),
                            new_type.strip() or doc.get("document_type", ""),
                            updated_fields,
                        )
                    st.success(f"Document {doc['id']} updated successfully.")
                    st.session_state.edit_doc = None
                except Exception as e:
                    st.error(f"Update failed: {e}")

    #  TAB 4 — DELETE
    
    with db_tab4:
        st.markdown("Delete records permanently. This cannot be undone.")

        del_mode = st.radio(
            "Delete mode",
            ["Single record", "Bulk by IDs", "All by type"],
            horizontal=True,
        )

        if del_mode == "Single record":
            del_id = st.number_input(
                "Document ID", min_value=1, step=1,
                key="del_single_id", label_visibility="collapsed",
            )
            # Preview before delete
            if st.button("👁 Preview Record"):
                try:
                    doc = db.get_document_with_fields(int(del_id))
                    if doc:
                        st.markdown(
                            f"**{doc.get('filename')}** · `{doc.get('document_type')}` · {doc.get('created_at')}"
                        )
                        type_fields = doc.get("type_fields", {})
                        if type_fields:
                            preview_rows = [{"Field": pretty_label(k), "Value": str(v)} for k, v in type_fields.items()]
                            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
                    else:
                        st.warning(f"No document with ID {int(del_id)}.")
                except Exception as e:
                    st.error(f"Preview failed: {e}")

            if st.button("🗑️ Delete Record", type="primary"):
                try:
                    doc = db.get_document(int(del_id))
                    if not doc:
                        st.warning(f"No document with ID {int(del_id)}.")
                    else:
                        db.delete_document(int(del_id))
                        st.success(f"Deleted document ID {int(del_id)}.")
                except Exception as e:
                    st.error(f"Delete failed: {e}")

        elif del_mode == "Bulk by IDs":
            bulk_input = st.text_input(
                "IDs (comma-separated)",
                placeholder="e.g. 1, 4, 7, 12",
            )
            if st.button("🗑️ Delete Selected", type="primary"):
                try:
                    ids = [int(x.strip()) for x in bulk_input.split(",") if x.strip().isdigit()]
                    if not ids:
                        st.warning("Enter at least one valid numeric ID.")
                    else:
                        db.delete_documents_bulk(ids)
                        st.success(f"Deleted {len(ids)} document(s): {ids}")
                except Exception as e:
                    st.error(f"Bulk delete failed: {e}")

        elif del_mode == "All by type":
            try:
                del_types = db.get_all_document_types()
            except Exception:
                del_types = []

            if not del_types:
                st.info("No document types found in database.")
            else:
                del_type = st.selectbox("Document type to delete", del_types)
                try:
                    count_rows = db.list_documents(document_type=del_type, limit=10000)
                    st.warning(
                        f"This will permanently delete **{len(count_rows)}** `{del_type}` record(s)."
                    )
                except Exception:
                    st.warning(f"This will delete all `{del_type}` records.")

                confirm_delete = st.checkbox(f'I understand — delete all "{del_type}" records')
                if st.button("🗑️ Delete All of This Type", type="primary"):
                    if not confirm_delete:
                        st.warning("Check the confirmation box first.")
                    else:
                        try:
                            rows = db.list_documents(document_type=del_type, limit=10000)
                            ids = [r["id"] for r in rows]
                            db.delete_documents_bulk(ids)
                            st.success(f"Deleted {len(ids)} `{del_type}` record(s).")
                        except Exception as e:
                            st.error(f"Delete failed: {e}")