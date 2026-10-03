import json
import logging
import os
import time

import google.generativeai as genai
from dotenv import load_dotenv

logger = logging.getLogger("llm_processor")

DOCUMENT_TYPE_MAP = {
    "invoice": "invoice",
    "receipt": "receipt",
    "aadhaar": "aadhaar",
    "aadhaar card": "aadhaar",
    "pan": "pan",
    "pan card": "pan",
    "passport": "passport",
    "driving license": "driving_license",
    "driving licence": "driving_license",
    "bank statement": "bank_statement",
}

PROMPT = """
You are an Intelligent Document Processing System.

Analyze the OCR text.

Your tasks:

1. Detect document type.
2. Extract ALL fields.
3. Ignore OCR mistakes.
4. Generate a professional report.

Supported examples:

- Invoice
- Receipt
- Aadhaar Card
- PAN Card
- Passport
- Driving License
- Bank Statement
- Resume
- Certificate
- Agreement
- Utility Bill
- Medical Report
- Any other document

Return ONLY valid JSON.

STRICT FORMAT:

{
    "document_type": "invoice",
    "structured_data": {
        "field_name": "value"
    },
    "report": "Professional summary."
}

Rules:

1. Use snake_case field names.
2. Include ALL fields.
3. Missing values should be null.
4. No markdown.
5. No explanations.
6. Return JSON only.
7. Keep structured_data flat.
8. Never use dynamic_fields.

OCR TEXT:

__OCR_TEXT__
"""


class LLMProcessor:
    """
    Uses Gemini to:
    1. Detect document type
    2. Extract structured fields
    3. Generate a report

    Calls have a timeout and are retried with exponential backoff.
    """

    def __init__(self, timeout: int | None = None, max_retries: int | None = None):
        load_dotenv()

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found.")

        genai.configure(api_key=api_key)

        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.timeout = timeout or int(os.getenv("GEMINI_TIMEOUT_S", "60"))
        self.max_retries = max_retries or int(os.getenv("GEMINI_MAX_RETRIES", "3"))

        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction="You are an expert Intelligent Document Processing assistant.",
        )
        logger.info(f"LLM initialized with {self.model_name}")

    def normalize_document_type(self, document_type) -> str:
        value = str(document_type or "unknown").lower().strip()
        return DOCUMENT_TYPE_MAP.get(value, value.replace(" ", "_"))

    @staticmethod
    def _parse(text: str) -> dict:
        cleaned = text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("LLM did not return a JSON object")
        return parsed

    def process(self, ocr_text: str) -> dict:
        if not ocr_text.strip():
            return {"document_type": "unknown", "structured_data": {}, "report": ""}

        prompt = PROMPT.replace("__OCR_TEXT__", ocr_text)
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                    ),
                    request_options={"timeout": self.timeout},
                )
                parsed = self._parse(response.text)

                document_type = self.normalize_document_type(parsed.get("document_type"))
                structured_data = parsed.get("structured_data", {})
                if not isinstance(structured_data, dict):
                    structured_data = {}

                logger.info(f"Detected document: {document_type}")
                return {
                    "document_type": document_type,
                    "structured_data": structured_data,
                    "report": parsed.get("report", "") or "",
                }

            except Exception as e:
                last_error = e
                logger.warning(f"LLM attempt {attempt}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)  # 2s, 4s, ...

        logger.error(f"LLM processing failed after {self.max_retries} attempts: {last_error}")
        return {
            "document_type": "unknown",
            "structured_data": {},
            "report": "",
            "error": str(last_error),
        }
