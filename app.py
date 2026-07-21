import json
import logging
from pathlib import Path

import cv2
import pandas as pd
import streamlit as st
from PIL import Image

from processing.pipeline import DocumentPipeline
from processing.database import DatabaseManager

logger = logging.getLogger("app")
logging.basicConfig(level=logging.INFO)

st.set_page_config(
    page_title="IDPS",
    page_icon="📄",
    layout="wide",
)

# Shared CSS 
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
    </style>
    """,
    unsafe_allow_html=True,
)

#  Resource caching 
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

    # Save file
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

    # Process
    with st.spinner("Processing…"):
        try:
            result = pipeline.process(str(image_path), save_outputs=False)
        except Exception as e:
            st.error(f"Processing failed: {e}")
            st.stop()

    # Images row 
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

    # Result tabs 
    st.markdown(f"**Detected type:** `{result['document_type']}`")

    tab_json, tab_report, tab_ocr = st.tabs(["Structured JSON", "Report", "Raw OCR"])
    with tab_json:
        st.json(result["structured_data"])
    with tab_report:
        st.write(result["report"] or "_No report generated._")
    with tab_ocr:
        st.text_area("", result["ocr_text"], height=220, label_visibility="collapsed")

    st.divider()

    # Actions row: Save + Downloads 
    save_col, dl_col = st.columns([1, 1])

    with save_col:
        st.markdown("**Save to Database**")

        if "document_id" not in st.session_state:
            st.session_state.document_id = None

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
                st.session_state.document_id = doc_id
                st.success(f"Saved — ID: **{doc_id}**")
            except Exception as e:
                st.error(f"Save failed: {e}")

        if st.session_state.document_id is not None:
            confirmed_by = st.text_input(
                "Your name",
                placeholder="optional",
                label_visibility="collapsed",
            )
            if st.button("✅ Confirm Record", use_container_width=True):
                try:
                    db.confirm_document(
                        st.session_state.document_id,
                        confirmed_by=confirmed_by,
                    )
                    st.success(f"Confirmed — ID: **{st.session_state.document_id}**")
                except Exception as e:
                    st.error(f"Confirm failed: {e}")

    with dl_col:
        st.markdown("**Download Results**")
        try:
            json_data = json.dumps(result["structured_data"], indent=4, ensure_ascii=False)
            complete_output = json.dumps(
                {
                    "document_type": result["document_type"],
                    "structured_data": result["structured_data"],
                    "report": result["report"],
                },
                indent=4,
                ensure_ascii=False,
            )
            st.download_button("⬇ JSON", json_data,
                               file_name="structured_data.json",
                               mime="application/json",
                               use_container_width=True)
            st.download_button("⬇ Report", result["report"],
                               file_name="document_report.txt",
                               mime="text/plain",
                               use_container_width=True)
            st.download_button("⬇ Complete Output", complete_output,
                               file_name="complete_output.json",
                               mime="application/json",
                               use_container_width=True)
        except Exception as e:
            st.warning(f"Could not prepare downloads: {e}")


#  PAGE 2 — DATABASE MANAGER
elif page == "🗄️ Database Manager":

    st.markdown("### 🗄️ Database Manager")

    # Stats bar 
    try:
        stats = db.get_stats()
        s1, s2, s3, s4 = st.columns(4)

        def stat_box(col, num, label):
            col.markdown(
                f'<div class="stat-box"><div class="stat-num">{num}</div>'
                f'<div class="stat-lbl">{label}</div></div>',
                unsafe_allow_html=True,
            )

        stat_box(s1, stats["total"], "Total Documents")
        stat_box(s2, stats["confirmed"], "Confirmed")
        stat_box(s3, stats["pending"], "Pending")
        top_type = stats["by_type"][0]["document_type"] if stats["by_type"] else "—"
        stat_box(s4, top_type, "Most Common Type")
    except Exception as e:
        st.warning(f"Could not load stats: {e}")

    st.divider()

    # Sub-tabs 
    db_tab1, db_tab2, db_tab3, db_tab4 = st.tabs([
        "📋 View & Search",
        "➕ Insert",
        "✏️ Edit",
        "🗑️ Delete",
    ])


    #  VIEW & SEARCH
    
    with db_tab1:
        #  Filter bar 
        f1, f2, f3 = st.columns([2, 1, 1])
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
        with f3:
            status_filter = st.selectbox(
                "Status",
                ["All statuses", "pending", "confirmed", "rejected"],
                label_visibility="collapsed",
            )

        # Fetch rows 
        try:
            if search_query:
                rows = db.search_documents(search_query)
            else:
                rows = db.list_documents(
                    document_type=None if type_filter == "All types" else type_filter,
                    status=None if status_filter == "All statuses" else status_filter,
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
                "Document ID",
                min_value=1,
                step=1,
                key="view_id",
                label_visibility="collapsed",
            )
            if st.button("🔎 Load Record", use_container_width=False):
                try:
                    doc = db.get_document(int(view_id))
                    if doc:
                        meta_col, data_col = st.columns([1, 1])
                        with meta_col:
                            st.markdown(
                                f"**ID:** {doc.get('id')}  \n"
                                f"**File:** {doc.get('filename')}  \n"
                                f"**Type:** `{doc.get('document_type')}`  \n"
                                f"**Status:** `{doc.get('status')}`  \n"
                                f"**Created:** {doc.get('created_at')}"
                            )
                        with data_col:
                            try:
                                parsed = json.loads(doc.get("raw_json", "{}"))
                                st.json(parsed)
                            except Exception:
                                st.text(doc.get("raw_json", ""))
                        with st.expander("Report"):
                            st.write(doc.get("report", ""))
                        with st.expander("OCR Text"):
                            st.text(doc.get("ocr_text", ""))

                        # Downloads 
                        st.markdown("**Download**")
                        try:
                            raw_json = doc.get("raw_json", "{}")
                            parsed_dl = json.loads(raw_json)
                            json_pretty = json.dumps(parsed_dl, indent=4, ensure_ascii=False)
                            complete = json.dumps(
                                {
                                    "document_type": doc.get("document_type"),
                                    "structured_data": parsed_dl,
                                    "report": doc.get("report", ""),
                                },
                                indent=4,
                                ensure_ascii=False,
                            )
                            fname = doc.get("filename", f"doc_{doc.get('id')}").rsplit(".", 1)[0]
                            d1, d2, d3 = st.columns(3)
                            d1.download_button(
                                "⬇ JSON",
                                json_pretty,
                                file_name=f"{fname}_data.json",
                                mime="application/json",
                                use_container_width=True,
                            )
                            d2.download_button(
                                "⬇ Report",
                                doc.get("report", ""),
                                file_name=f"{fname}_report.txt",
                                mime="text/plain",
                                use_container_width=True,
                            )
                            d3.download_button(
                                "⬇ Complete",
                                complete,
                                file_name=f"{fname}_complete.json",
                                mime="application/json",
                                use_container_width=True,
                            )
                        except Exception as e:
                            st.warning(f"Could not prepare downloads: {e}")
                    else:
                        st.warning(f"No document with ID {int(view_id)}.")
                except Exception as e:
                    st.error(f"Load failed: {e}")


    #  INSERT

    with db_tab2:
        st.markdown("Manually insert a document record without running the pipeline.")

        i1, i2 = st.columns(2)
        with i1:
            ins_filename = st.text_input("Filename", placeholder="e.g. invoice_001.jpg")
            ins_type = st.selectbox(
                "Document type",
                ["invoice", "receipt", "aadhaar", "pan", "passport",
                 "driving_license", "bank_statement", "other"],
            )
        with i2:
            ins_filepath = st.text_input("File path", placeholder="/path/to/file.jpg")
            ins_status = st.selectbox("Initial status", ["pending", "confirmed"])

        ins_report = st.text_area("Report", height=100, placeholder="Optional summary…")
        ins_ocr = st.text_area("OCR Text", height=100, placeholder="Extracted text…")
        ins_json_raw = st.text_area(
            "Structured Data (JSON)",
            height=120,
            placeholder='{"field": "value"}',
            value="{}",
        )

        if st.button("➕ Insert Record", use_container_width=False):
            if not ins_filename.strip():
                st.warning("Filename is required.")
            else:
                try:
                    structured = json.loads(ins_json_raw)
                    doc_id = db.save_document(
                        filename=ins_filename.strip(),
                        file_path=ins_filepath.strip(),
                        document_type=ins_type,
                        ocr_text=ins_ocr,
                        report=ins_report,
                        structured_data=structured,
                    )
                    if ins_status == "confirmed":
                        db.update_document(doc_id, status="confirmed")
                    st.success(f"Inserted — ID: **{doc_id}**")
                except json.JSONDecodeError:
                    st.error("Structured Data must be valid JSON.")
                except Exception as e:
                    st.error(f"Insert failed: {e}")

    #  EDIT
  
    with db_tab3:
        st.markdown("Load a record by ID, edit fields, then save.")

        edit_id = st.number_input(
            "Document ID to edit",
            min_value=1,
            step=1,
            key="edit_id",
            label_visibility="collapsed",
        )

        if "edit_doc" not in st.session_state:
            st.session_state.edit_doc = None

        if st.button("📂 Load for Editing"):
            try:
                doc = db.get_document(int(edit_id))
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
                new_type = st.text_input("Document type", value=doc.get("document_type", ""))
                new_status = st.selectbox(
                    "Status",
                    ["pending", "confirmed", "rejected"],
                    index=["pending", "confirmed", "rejected"].index(
                        doc.get("status", "pending")
                    ),
                )
            with e2:
                try:
                    current_json = json.dumps(
                        json.loads(doc.get("raw_json", "{}")),
                        indent=2,
                        ensure_ascii=False,
                    )
                except Exception:
                    current_json = "{}"
                new_json_raw = st.text_area(
                    "Structured Data (JSON)",
                    value=current_json,
                    height=150,
                )

            new_report = st.text_area(
                "Report", value=doc.get("report", ""), height=100
            )

            if st.button("💾 Save Changes", use_container_width=False):
                try:
                    new_structured = json.loads(new_json_raw)
                    db.update_document(
                        int(doc["id"]),
                        document_type=new_type.strip() or None,
                        report=new_report,
                        structured_data=new_structured,
                        status=new_status,
                    )
                    st.success(f"Document {doc['id']} updated.")
                    st.session_state.edit_doc = None
                except json.JSONDecodeError:
                    st.error("Structured Data must be valid JSON.")
                except Exception as e:
                    st.error(f"Update failed: {e}")

  
    #  DELETE
   
    with db_tab4:
        st.markdown("Delete records permanently. This cannot be undone.")

        del_mode = st.radio(
            "Delete mode",
            ["Single record", "Bulk by IDs", "All by type"],
            horizontal=True,
        )

        if del_mode == "Single record":
            del_id = st.number_input(
                "Document ID",
                min_value=1,
                step=1,
                key="del_single_id",
                label_visibility="collapsed",
            )
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
                st.warning(
                    f"This will delete **all** `{del_type}` records. "
                    "This action is irreversible."
                )
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