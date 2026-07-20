import json
import os
import logging

from dotenv import load_dotenv
import google.generativeai as genai

logger = logging.getLogger("llm_processor")
logging.basicConfig(level=logging.INFO)


class LLMProcessor:
    """
    Uses Gemini to understand OCR text and generate:

    1. Document type
    2. Structured JSON
    3. Human-readable report
    """

    def __init__(self):
        try:
            load_dotenv()

            api_key = os.getenv("GEMINI_API_KEY")

            if not api_key:
                raise ValueError(
                    "GEMINI_API_KEY not found. Please add it to your .env file."
                )

            genai.configure(api_key=api_key)

            self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=(
                    "You are an expert Intelligent Document Processing assistant."
                ),
            )

            logger.info(f"LLMProcessor initialized with model '{self.model_name}'")

        except Exception as e:
            logger.error(f"LLMProcessor initialization failed: {e}")
            raise

    def process(self, ocr_text: str):
        """
        Sends OCR text to Gemini and returns:
        - document_type
        - structured_data
        - report
        """

        # Guard against empty OCR text before spending an API call on it
        if not ocr_text or not ocr_text.strip():
            logger.warning("process called with empty OCR text, skipping LLM call")
            return {
                "document_type": "Unknown",
                "structured_data": {},
                "report": "",
                "error": "Empty OCR text",
            }

        prompt = f"""
You are an Intelligent Document Processing System.

Your task is to analyse OCR text extracted from ANY document.

The document may be:

- Invoice
- Receipt
- Passport
- Aadhaar Card
- PAN Card
- Driving License
- Resume
- Medical Report
- Bank Statement
- Utility Bill
- Certificate
- Agreement
- Letter
- Identity Card
- Marksheet
- Any other document

Read the OCR carefully.

Ignore OCR mistakes whenever possible.

Understand the actual meaning.

Return ONLY valid JSON.

The JSON MUST follow exactly this structure:

{{
    "document_type": "...",

    "structured_data":
    {{
        "dynamic_fields": {{
            "field_name": "value"
        }}
    }},

    "report": "A professional readable summary of the complete document including every important piece of information."
}}

Rules:

1. Detect the document type.
2. Generate meaningful JSON keys.
3. Include ALL important information.
4. Use nested JSON whenever appropriate.
5. Ignore OCR garbage.
6. Missing values should be null.
7. Do not explain anything.
8. Do not use markdown.
9. Return ONLY JSON.

OCR TEXT:

{ocr_text}
"""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )

            output = response.text.strip()

            # Gemini sometimes wraps JSON in markdown fences despite the instruction not to
            output = output.replace("```json", "")
            output = output.replace("```", "")
            output = output.strip()

            try:
                parsed = json.loads(output)
            except json.JSONDecodeError as parse_error:
                # Keep the raw output for debugging instead of losing it silently
                logger.error(f"Failed to parse Gemini JSON output: {parse_error}")
                logger.debug(f"Raw Gemini output: {output}")
                return {
                    "document_type": "Unknown",
                    "structured_data": {},
                    "report": "",
                    "error": f"JSON parse error: {parse_error}",
                }

            logger.info(
                f"LLM processed OCR text: document_type="
                f"{parsed.get('document_type', 'Unknown')}"
            )
            return parsed

        except Exception as e:
            logger.error(f"LLM generate_content call failed: {e}")
            return {
                "document_type": "Unknown",
                "structured_data": {},
                "report": "",
                "error": str(e),
            }