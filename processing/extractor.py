import re
from typing import Dict, List


class DocumentExtractor:
    """
    Generic document extractor.

    Supports:
    - Invoice
    - Receipt
    - ID Card
    - Bank Statement
    - Generic Documents
    """

    def __init__(self):
        pass

    # DOCUMENT TYPE DETECTION

    def detect_document_type(self, text: str) -> str:

        t = text.lower()

        if "invoice" in t:
            return "invoice"

        elif "receipt" in t:
            return "receipt"

        elif "bank statement" in t:
            return "bank_statement"

        elif "aadhaar" in t:
            return "aadhaar"

        elif "passport" in t:
            return "passport"

        elif "driving licence" in t or "driving license" in t:
            return "driving_license"

        elif "pan" in t:
            return "pan"

        else:
            return "generic"

    # COMMON FIELD EXTRACTION

    def extract_dates(self, text: str) -> List[str]:

        pattern = r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b[A-Za-z]+\s+\d{1,2},\s+\d{4}\b"

        return re.findall(pattern, text)

    def extract_email(self, text: str):

        pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"

        match = re.search(pattern, text)

        return match.group() if match else None

    def extract_phone(self, text: str):

        pattern = r"\+?\d[\d\s\-]{8,15}"

        match = re.search(pattern, text)

        return match.group() if match else None

    def extract_amounts(self, text: str):

        pattern = r"(?:₹|\$|USD|INR|Rs\.?)\s?\d+[,\d]*(?:\.\d{2})?"

        return re.findall(pattern, text)


    # INVOICE

    def extract_invoice(self, text: str):

        data = {}

        invoice = re.search(
            r"Invoice\s*(?:Number|No\.?|#)?[:\s]*([A-Za-z0-9\-]+)",
            text,
            re.IGNORECASE,
        )

        total = re.search(
            r"Total[:\s]*(?:₹|\$|USD|INR)?\s*([\d,]+\.\d{2})",
            text,
            re.IGNORECASE,
        )

        data["invoice_number"] = invoice.group(1) if invoice else None
        data["total"] = total.group(1) if total else None

        return data

    # RECEIPT

    def extract_receipt(self, text):

        data = {}

        total = re.search(
            r"Total[:\s]*(?:₹|\$|USD|INR)?\s*([\d,]+\.\d{2})",
            text,
            re.IGNORECASE,
        )

        data["total"] = total.group(1) if total else None

        return data

    # AADHAAR

    def extract_aadhaar(self, text):

        aadhaar = re.search(r"\b\d{4}\s\d{4}\s\d{4}\b", text)

        return {
            "aadhaar_number":
            aadhaar.group() if aadhaar else None
        }

    # PAN

    def extract_pan(self, text):

        pan = re.search(r"[A-Z]{5}[0-9]{4}[A-Z]", text)

        return {
            "pan_number":
            pan.group() if pan else None
        }

    # PASSPORT

    def extract_passport(self, text):

        passport = re.search(r"\b[A-Z][0-9]{7}\b", text)

        return {
            "passport_number":
            passport.group() if passport else None
        }

    # MASTER EXTRACTION
 
    def extract(self, text: str) -> Dict:

        document = self.detect_document_type(text)

        result = {
            "document_type": document,
            "dates": self.extract_dates(text),
            "email": self.extract_email(text),
            "phone": self.extract_phone(text),
            "amounts": self.extract_amounts(text),
            "raw_text": text
        }

        if document == "invoice":
            result.update(self.extract_invoice(text))

        elif document == "receipt":
            result.update(self.extract_receipt(text))

        elif document == "aadhaar":
            result.update(self.extract_aadhaar(text))

        elif document == "pan":
            result.update(self.extract_pan(text))

        elif document == "passport":
            result.update(self.extract_passport(text))

        return result