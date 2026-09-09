import cv2
import numpy as np
from pathlib import Path


class OCRVisualizer:
    """
    Visualizes OCR detection results by drawing bounding boxes
    and optional text labels on the document image.
    """

    def __init__(
        self,
        box_color=(0, 255, 0),
        text_color=(0, 0, 255),
        thickness=2,
        font_scale=0.5,
    ):
        self.box_color = box_color
        self.text_color = text_color
        self.thickness = thickness
        self.font_scale = font_scale

    def draw_boxes(
        self,
        image: np.ndarray,
        ocr_results,
        show_text=True,
        show_confidence=True,
    ) -> np.ndarray:
        """
        Draw bounding boxes around detected text.
        
        Parameters
        ----------
        image : np.ndarray
            Input image.

        ocr_results : list
            EasyOCR output.

        show_text : bool
            Display detected text.

        show_confidence : bool
            Display OCR confidence score.

        Returns
        -------
        np.ndarray
            Image with OCR visualization.
        """

        output = image.copy()

        # Convert grayscale image to color for drawing
        if len(output.shape) == 2:
            output = cv2.cvtColor(output, cv2.COLOR_GRAY2BGR)

        for bbox, text, confidence in ocr_results:

            points = np.array(bbox, dtype=np.int32)

            # Draw bounding polygon
            cv2.polylines(
                output,
                [points],
                isClosed=True,
                color=self.box_color,
                thickness=self.thickness,
            )

            if show_text:

                x = int(points[0][0])
                y = int(points[0][1]) - 8

                if y < 20:
                    y = int(points[0][1]) + 20

                if show_confidence:
                    label = f"{text} ({confidence:.2f})"
                else:
                    label = text

                cv2.putText(
                    output,
                    label,
                    (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    self.font_scale,
                    self.text_color,
                    1,
                    cv2.LINE_AA,
                )

        return output

    def save_image(
        self,
        image: np.ndarray,
        output_path: str,
    ) -> None:
        
        """
        Save the visualized image.
        """

        output_path = Path(output_path)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        cv2.imwrite(str(output_path), image)