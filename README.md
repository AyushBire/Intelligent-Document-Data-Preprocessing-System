# Intelligent Document Processing System (IDPS)

This project provides an end-to-end intelligent document processing application for uploading documents, preprocessing them, extracting text with OCR, and generating structured JSON and a report.

## Features

- Upload images or PDFs through a Streamlit interface
- Preprocess uploaded documents for better OCR accuracy
- Detect document type
- Extract text using OCR
- Generate structured JSON output
- Produce a report summary

## Project Structure

- app.py: Streamlit web application entry point
- processing/: document processing pipeline and supporting modules
- uploads/: uploaded files are stored here during processing
- outputs/: generated outputs
- notebooks/: experiment notebooks

## Setup

1. Create and activate a Python virtual environment
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   streamlit run IDPS/app.py
   ```

## Environment Variables

Create a .env file with any required API credentials or configuration values used by the processing pipeline.

## Notes

- Do not commit sensitive values such as API keys or secrets.
- The .gitignore file excludes common local environment and output files.
