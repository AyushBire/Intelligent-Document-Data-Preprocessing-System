import easyocr
import cv2
import logging

logger = logging.getLogger("ocr")
logging.basicConfig(level=logging.INFO)


class OCRProcessor:
    """
    Handles OCR operations using EasyOCR.
    """

    def __init__(self):
        try:
            print("Loading EasyOCR model...")
            logger.info("Initializing EasyOCR reader (lang=en, gpu=False)")

            self.reader = easyocr.Reader(
                ["en"],
                gpu=False,
            )

        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR reader: {e}")
            raise

    def process(self, image):
        """
        Perform OCR once.

        Returns:
            EasyOCR raw results.
        """
        try:
            results = self.reader.readtext(image)
            logger.info(f"OCR detected {len(results)} text regions")
            return results

        except Exception as e:
            logger.error(f"OCR process failed: {e}")
            # Return empty results instead of crashing the whole pipeline
            return []

    def extract_text(self, ocr_results):
        """
        Convert OCR results into readable text.
        """
        try:
            text = []

            for _, detected_text, confidence in ocr_results:
                # Only keep text the model is reasonably confident about
                if confidence >= 0.30:
                    text.append(detected_text)

            return "\n".join(text)

        except Exception as e:
            logger.error(f"extract_text failed: {e}")
            return ""

    def extract_structured(self, ocr_results):
        """
        Convert OCR results into structured dictionaries.
        """
        try:
            structured = []

            for box, text, confidence in ocr_results:
                # Use the top-left corner of each box for reading-order sorting
                x = min(point[0] for point in box)
                y = min(point[1] for point in box)

                structured.append({
                    "text": text,
                    "confidence": round(confidence, 2),
                    "box": box,
                    "x": int(x),
                    "y": int(y),
                })

            # Sort top-to-bottom, then left-to-right to approximate reading order
            structured.sort(
                key=lambda item: (
                    item["y"],
                    item["x"],
                )
            )

            return structured

        except Exception as e:
            logger.error(f"extract_structured failed: {e}")
            return []

    def visualize_boxes(self, image, ocr_results):
        """
        Draw OCR bounding boxes.
        """
        try:
            output = image.copy()

            # Convert single-channel images to BGR so colored boxes/text are visible
            if len(output.shape) == 2:
                output = cv2.cvtColor(
                    output,
                    cv2.COLOR_GRAY2BGR,
                )

            for box, text, confidence in ocr_results:
                pts = [(int(x), int(y)) for x, y in box]

                for i in range(4):
                    cv2.line(
                        output,
                        pts[i],
                        pts[(i + 1) % 4],
                        (0, 255, 0),
                        2,
                    )

                cv2.putText(
                    output,
                    text,
                    (pts[0][0], pts[0][1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 0, 0),
                    1,
                )

            return output

        except Exception as e:
            logger.error(f"visualize_boxes failed: {e}")
            # Fall back to the original image so the UI still has something to show
            return image

    def get_ocr_results(self, image):
        """
        Compatibility wrapper.
        """
        return self.process(image)