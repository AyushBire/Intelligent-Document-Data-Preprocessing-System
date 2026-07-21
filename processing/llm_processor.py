import json
import logging
import os

from dotenv import load_dotenv
import google.generativeai as genai

logger = logging.getLogger("llm_processor")
logging.basicConfig(level=logging.INFO)


class LLMProcessor:
    """
    Uses Gemini to:
    1. Detect document type
    2. Extract structured fields
    3. Generate a report
    """

    def __init__(self):

        try:

            load_dotenv()

            api_key = os.getenv(
                "GEMINI_API_KEY"
            )

            if not api_key:

                raise ValueError(
                    "GEMINI_API_KEY "
                    "not found."
                )

            genai.configure(
                api_key=api_key
            )

            self.model_name = os.getenv(
                "GEMINI_MODEL",
                "gemini-2.5-flash-lite",
            )

            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=(
                    "You are an expert "
                    "Intelligent Document "
                    "Processing assistant."
                ),
            )

            logger.info(
                f"LLM initialized "
                f"with {self.model_name}"
            )

        except Exception as e:

            logger.error(
                f"LLM initialization "
                f"failed: {e}"
            )

            raise

    # Normalize document type
    def normalize_document_type(
        self,
        document_type,
    ):

        mapping = {
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

        return mapping.get(
            document_type.lower().strip(),
            document_type.lower().replace(
                " ",
                "_",
            ),
        )

    def process(
        self,
        ocr_text,
    ):

        if not ocr_text.strip():

            return {
                "document_type": "unknown",
                "structured_data": {},
                "report": "",
            }

        prompt = f"""
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

{{
    "document_type":"invoice",

    "structured_data":
    {{
        "field_name":"value"
    }},

    "report":
    "Professional summary."
}}

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

{ocr_text}
"""

        try:

            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    response_mime_type=(
                        "application/json"
                    ),
                ),
            )

            output = (
                response.text
                .replace(
                    "```json",
                    "",
                )
                .replace(
                    "```",
                    "",
                )
                .strip()
            )

            parsed = json.loads(
                output
            )

            document_type = (
                self.normalize_document_type(
                    parsed.get(
                        "document_type",
                        "unknown",
                    )
                )
            )

            structured_data = (
                parsed.get(
                    "structured_data",
                    {},
                )
            )

            if not isinstance(
                structured_data,
                dict,
            ):

                structured_data = {}

            report = parsed.get(
                "report",
                "",
            )

            logger.info(
                f"Detected document: "
                f"{document_type}"
            )

            return {
                "document_type":
                document_type,

                "structured_data":
                structured_data,

                "report":
                report,
            }

        except Exception as e:

            logger.error(
                f"LLM processing "
                f"failed: {e}"
            )

            return {
                "document_type":
                "unknown",

                "structured_data":
                {},

                "report":
                "",

                "error":
                str(e),
            }