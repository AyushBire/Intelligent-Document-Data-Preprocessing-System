import json
import logging
from pathlib import Path

import cv2
import streamlit as st
from PIL import Image

from processing.pipeline import DocumentPipeline

logger = logging.getLogger("app")
logging.basicConfig(level=logging.INFO)

st.set_page_config(
    page_title="Intelligent Document Processing System",
    page_icon="📄",
    layout="wide",
)

st.title("📄 Intelligent Document Processing System")

st.markdown(
    """
Upload any document and let the system automatically:

- Detect the document type
- Extract text using OCR
- Understand the document using Grok
- Generate structured JSON
- Generate a professional report
"""
)

st.sidebar.title("IDPS")
st.sidebar.info(
    """
Supported formats

- JPG
- JPEG
- PNG
- BMP
- TIFF

Processing Flow

Image → Preprocessing → OCR → LLM → JSON + Report
"""
)

# Cache the pipeline so heavy models (EasyOCR, Gemini client) aren't reloaded on every rerun
@st.cache_resource
def load_pipeline():
    try:
        return DocumentPipeline()
    except Exception as e:
        logger.error(f"Failed to initialize DocumentPipeline: {e}")
        raise


try:
    pipeline = load_pipeline()
except Exception as e:
    st.error(f"Failed to start the processing pipeline.\n\n{e}")
    st.stop()

uploaded_file = st.file_uploader(
    "Upload Document",
    type=["jpg", "jpeg", "png", "bmp", "tiff", "pdf"],
)

if uploaded_file is not None:

    # Save the uploaded file to disk so downstream OpenCV/EasyOCR calls can read it by path
    try:
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)

        image_path = upload_dir / uploaded_file.name

        with open(image_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        original_image = Image.open(image_path)

    except Exception as e:
        logger.error(f"Failed to save/open uploaded file: {e}")
        st.error(f"Could not read the uploaded file.\n\n{e}")
        st.stop()

    st.subheader("Original Document")
    st.image(original_image, use_container_width=True)

    with st.spinner("Processing document..."):
        try:
            result = pipeline.process(
                str(image_path),
                save_outputs=False,
            )

        except Exception as e:
            logger.error(f"Pipeline processing failed for '{image_path}': {e}")
            st.error(f"Processing failed.\n\n{e}")
            st.stop()

    st.success("Document processed successfully.")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Preprocessed Image")

        try:
            st.image(
                result["clean_image"],
                clamp=True,
                use_container_width=True,
            )
        except Exception as e:
            logger.error(f"Failed to display clean_image: {e}")
            st.warning("Could not display the preprocessed image.")

    with col2:
        st.subheader("OCR Detection")

        try:
            # OpenCV uses BGR, Streamlit expects RGB, so convert before display
            boxed = cv2.cvtColor(
                result["boxed_image"],
                cv2.COLOR_BGR2RGB,
            )

            st.image(
                boxed,
                use_container_width=True,
            )
        except Exception as e:
            logger.error(f"Failed to display boxed_image: {e}")
            st.warning("Could not display the OCR detection image.")

    st.divider()

    st.subheader("Detected Document Type")
    st.success(result["document_type"])

    st.divider()

    st.subheader("Structured JSON")
    st.json(result["structured_data"])

    st.divider()

    st.subheader("Document Report")
    st.write(result["report"])

    st.divider()

    with st.expander("View Raw OCR Text"):
        st.text_area(
            "OCR Text",
            result["ocr_text"],
            height=300,
        )

    st.divider()

    st.subheader("Download Results")

    try:
        json_data = json.dumps(
            result["structured_data"],
            indent=4,
            ensure_ascii=False,
        )

        complete_output = json.dumps(
            {
                "document_type": result["document_type"],
                "structured_data": result["structured_data"],
                "report": result["report"],
            },
            indent=4,
            ensure_ascii=False,
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.download_button(
                "Download JSON",
                json_data,
                file_name="structured_data.json",
                mime="application/json",
            )

        with col2:
            st.download_button(
                "Download Report",
                result["report"],
                file_name="document_report.txt",
                mime="text/plain",
            )

        with col3:
            st.download_button(
                "Download Complete Output",
                complete_output,
                file_name="complete_output.json",
                mime="application/json",
            )

    except Exception as e:
        logger.error(f"Failed to prepare download buttons: {e}")
        st.warning("Could not prepare download files.")