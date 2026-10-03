from pathlib import Path
import json
import logging

from processing.preprocessing import ImagePreprocessor
from processing.ocr import OCRProcessor
from processing.visualizer import OCRVisualizer
from processing.llm_processor import LLMProcessor

logger = logging.getLogger("pipeline")


class DocumentPipeline:
    """
    Complete Intelligent Document Processing Pipeline.

    Workflow
    --------
    Upload Image
        ↓
    Image Preprocessing
        ↓
    OCR
        ↓
    OCR Visualization
        ↓
    LLM Processing
        ↓
    Document Type
    Structured JSON
    Human-readable Report
    """

    def __init__(self):
        try:
            self.preprocessor = ImagePreprocessor()
            self.ocr = OCRProcessor()
            self.visualizer = OCRVisualizer()
            self.llm = LLMProcessor()
        except Exception as e:
            logger.error(f"DocumentPipeline initialization failed: {e}")
            raise

    def process(
        self,
        image_path: str,
        save_outputs: bool = False,
        output_dir: str = "outputs",
    ):
        """
        Complete document processing pipeline.
        """

        # Preprocess image
        try:
            clean_image = self.preprocessor.process(image_path)
        except Exception as e:
            logger.error(f"Preprocessing stage failed for '{image_path}': {e}")
            raise

        # OCR
        try:
            ocr_results = self.ocr.process(clean_image)
            ocr_text = self.ocr.extract_text(ocr_results)
        except Exception as e:
            logger.error(f"OCR stage failed for '{image_path}': {e}")
            # Continue with empty OCR output rather than crashing the whole pipeline
            ocr_results = []
            ocr_text = ""

        # Draw OCR bounding boxes
        try:
            boxed_image = self.visualizer.draw_boxes(
                clean_image,
                ocr_results,
                show_text=False,
                show_confidence=False,
            )
        except Exception as e:
            logger.error(f"Visualization stage failed: {e}")
            # Fall back to the clean image if box drawing fails
            boxed_image = clean_image

        # LLM Processing
        try:
            llm_output = self.llm.process(ocr_text)
        except Exception as e:
            logger.error(f"LLM stage failed: {e}")
            llm_output = {}

        document_type = llm_output.get(
            "document_type",
            "Unknown",
        )

        structured_data = llm_output.get(
            "structured_data",
            {},
        )

        report = llm_output.get(
            "report",
            "",
        )

        # Save outputs
        if save_outputs:
            try:
                output_path = Path(output_dir)

                output_path.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                self.preprocessor.save_image(
                    clean_image,
                    output_path / "clean_image.png",
                )

                self.visualizer.save_image(
                    boxed_image,
                    output_path / "boxed_image.png",
                )

                with open(
                    output_path / "ocr_text.txt",
                    "w",
                    encoding="utf-8",
                ) as file:
                    file.write(ocr_text)

                with open(
                    output_path / "report.txt",
                    "w",
                    encoding="utf-8",
                ) as file:
                    file.write(report)

                with open(
                    output_path / "structured_data.json",
                    "w",
                    encoding="utf-8",
                ) as file:
                    json.dump(
                        structured_data,
                        file,
                        indent=4,
                        ensure_ascii=False,
                    )

                logger.info(f"Saved outputs to '{output_dir}'")

            except Exception as e:
                # Saving is a convenience step, don't fail the whole request over it
                logger.error(f"Saving outputs failed: {e}")

        return {
            "clean_image": clean_image,
            "boxed_image": boxed_image,
            "ocr_results": ocr_results,
            "ocr_text": ocr_text,
            "document_type": document_type,
            "structured_data": structured_data,
            "report": report,
        }
