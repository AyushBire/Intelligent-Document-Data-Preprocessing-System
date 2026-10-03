import cv2
import numpy as np
import logging
import os
from pathlib import Path

logger = logging.getLogger("preprocessing")


class ImagePreprocessor:

    def __init__(self):
        pass

    # IMAGE LOADING

    def load_image(self, image_path: str) -> np.ndarray:
        """Load an image and bound dimensions before preprocessing and OCR.

        Args: image_path: Local image path. Returns: BGR image within configured limit.
        Raises: FileNotFoundError for undecodable images; ValueError for invalid size configuration.
        """
        try:
            image = cv2.imread(image_path)

            if image is None:
                raise FileNotFoundError(f"Unable to load image: {image_path}")

            max_side = max(256, int(os.getenv("OCR_MAX_SIDE_PX", "2400")))
            height, width = image.shape[:2]
            if max(height, width) > max_side:
                scale = max_side / max(height, width)
                image = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)

            logger.info(f"Loaded image: {image_path} shape={image.shape}")
            return image

        except Exception as e:
            logger.error(f"load_image failed for '{image_path}': {e}")
            raise

    # GRAYSCALE

    def convert_to_grayscale(self, image: np.ndarray) -> np.ndarray:
        try:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        except Exception as e:
            logger.error(f"convert_to_grayscale failed: {e}")
            raise

    # CONTRAST ENHANCEMENT

    def enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        try:
            # CLAHE improves local contrast without over-amplifying noise
            clahe = cv2.createCLAHE(
                clipLimit=2.0,
                tileGridSize=(8, 8)
            )
            return clahe.apply(image)
        except Exception as e:
            logger.error(f"enhance_contrast failed: {e}")
            raise

    # DENOISING

    def remove_noise(self, image: np.ndarray) -> np.ndarray:
        try:
            # Bilateral filter smooths noise while preserving text edges,
            # which works better than Gaussian Blur for OCR
            return cv2.bilateralFilter(
                image,
                d=9,
                sigmaColor=75,
                sigmaSpace=75
            )
        except Exception as e:
            logger.error(f"remove_noise failed: {e}")
            raise

    # BINARIZATION

    def apply_threshold(self, image: np.ndarray) -> np.ndarray:
        try:
            # Larger block size + lower C is gentler on small/thin text
            # than the original (31, 15), which was fragmenting table text
            threshold = cv2.adaptiveThreshold(
                image,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                41,
                10
            )
            return threshold
        except Exception as e:
            logger.error(f"apply_threshold failed: {e}")
            raise

    # MORPHOLOGICAL CLEANUP

    def morphology(self, image: np.ndarray) -> np.ndarray:
        try:
            kernel = np.ones((2, 2), np.uint8)

            # MORPH_OPEN removed: it was eroding thin table text into dots.
            # Only closing is kept, to fill small gaps in strokes.
            image = cv2.morphologyEx(
                image,
                cv2.MORPH_CLOSE,
                kernel
            )

            return image
        except Exception as e:
            logger.error(f"morphology failed: {e}")
            raise

    # DESKEW

    def deskew(self, image: np.ndarray) -> np.ndarray:
        """Correct a small text rotation across OpenCV angle conventions.

        Args: image: Grayscale input. Returns: Corrected image or original on failure.
        Raises: None; detection failures retain the input.
        """
        try:
            # Angle estimation needs a binary mask to work reliably.
            # If `image` is already binary this is a no-op; if it's grayscale
            # (the "clean document" path), Otsu gives us a throwaway mask
            # just for angle detection, while rotation is still applied to
            # the actual `image` passed in.
            _, mask = cv2.threshold(
                image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )

            coords = np.column_stack(np.where(mask > 0))[:, ::-1]

            if len(coords) == 0:
                logger.warning("deskew: no foreground pixels found, skipping")
                return image

            angle = cv2.minAreaRect(coords)[-1]

            if angle < -45:
                angle = 90 + angle
            elif angle > 45:
                angle -= 90

            if abs(angle) < 0.5:
                return image

            h, w = image.shape[:2]
            center = (w // 2, h // 2)

            M = cv2.getRotationMatrix2D(center, angle, 1.0)

            rotated = cv2.warpAffine(
                image,
                M,
                (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE
            )

            logger.info(f"deskew: corrected by {angle:.2f} degrees")
            return rotated

        except Exception as e:
            logger.error(f"deskew failed, returning original image: {e}")
            return image

    # DOCUMENT BOUNDARY / PERSPECTIVE CORRECTION

    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        # Sorts 4 corner points into consistent order: top-left, top-right,
        # bottom-right, bottom-left. Needed so the perspective warp maps
        # corners correctly regardless of the order contours returned them in.
        rect = np.zeros((4, 2), dtype="float32")

        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]  # top-left has smallest x+y
        rect[2] = pts[np.argmax(s)]  # bottom-right has largest x+y

        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]  # top-right has smallest y-x
        rect[3] = pts[np.argmax(diff)]  # bottom-left has largest y-x

        return rect

    def find_document_contour(self, image: np.ndarray):
        """
        Attempts to find a 4-point document boundary in the image
        (e.g. a page photographed on a table with visible background).

        Returns the 4 corner points if a confident boundary is found,
        or None if the image looks like it's already just the document
        (flat scan / digital doc filling the frame, no visible background).
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 50, 150)
            edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

            contours, _ = cv2.findContours(
                edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            if not contours:
                return None

            image_area = image.shape[0] * image.shape[1]

            # Only look at the largest few contours, sorted by area
            for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
                area = cv2.contourArea(contour)
                area_ratio = area / image_area

                # A real "document photographed with background" contour should
                # cover a meaningful chunk of the frame but NOT the whole frame.
                # If it covers ~95%+ of the image, the document already fills
                # the frame (flat scan / digital doc) and needs no correction.
                if area_ratio < 0.2 or area_ratio > 0.95:
                    continue

                perimeter = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)

                # Only accept a clean 4-point convex quadrilateral as a
                # document boundary; anything else is too ambiguous to trust.
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    return approx.reshape(4, 2).astype("float32")

            return None

        except Exception as e:
            logger.error(f"find_document_contour failed: {e}")
            return None

    def correct_perspective(self, image: np.ndarray) -> np.ndarray:
        """
        Detects a photographed document's boundary and warps it flat.
        Safe no-op: if no confident 4-point boundary is found (typical for
        flat scans or digital documents filling the whole frame), the
        original image is returned unchanged.
        """
        try:
            pts = self.find_document_contour(image)

            if pts is None:
                logger.info("correct_perspective: no document boundary detected, skipping")
                return image

            rect = self._order_points(pts)
            (tl, tr, br, bl) = rect

            width_a = np.linalg.norm(br - bl)
            width_b = np.linalg.norm(tr - tl)
            max_width = int(max(width_a, width_b))

            height_a = np.linalg.norm(tr - br)
            height_b = np.linalg.norm(tl - bl)
            max_height = int(max(height_a, height_b))

            # Guard against a degenerate/tiny detected region
            if max_width < 50 or max_height < 50:
                logger.warning("correct_perspective: detected region too small, skipping")
                return image

            dst = np.array([
                [0, 0],
                [max_width - 1, 0],
                [max_width - 1, max_height - 1],
                [0, max_height - 1],
            ], dtype="float32")

            M = cv2.getPerspectiveTransform(rect, dst)
            warped = cv2.warpPerspective(image, M, (max_width, max_height))

            logger.info("correct_perspective: document boundary corrected")
            return warped

        except Exception as e:
            # Any failure here should never break the pipeline -
            # fall back to the original, uncorrected image.
            logger.error(f"correct_perspective failed, returning original image: {e}")
            return image

    # BLUR DETECTION

    def is_blurry(self, gray_image: np.ndarray, threshold: float = 100.0) -> bool:
        """
        Flags an image as likely too blurry for reliable OCR, using the
        same Laplacian variance measure as is_clean_document(). This does
        not block processing - it only logs a warning so the cause of
        poor OCR results (blur vs. something else) is visible in debugging.
        """
        try:
            laplacian_var = cv2.Laplacian(gray_image, cv2.CV_64F).var()
            blurry = laplacian_var < threshold

            if blurry:
                logger.warning(
                    f"is_blurry: image may be too blurry for reliable OCR "
                    f"(laplacian_var={laplacian_var:.1f}, threshold={threshold})"
                )

            return blurry

        except Exception as e:
            logger.error(f"is_blurry failed: {e}")
            return False

    # NOISE / QUALITY DETECTION

    def is_clean_document(self, gray_image: np.ndarray) -> bool:
        """
        Heuristically decide whether an image is a clean, born-digital
        document (crisp text, low noise) versus a noisy scan/photo.

        Uses the Laplacian variance as a sharpness/noise proxy:
        - High variance + low noise-estimate  -> clean digital doc
        - Low variance or high noise-estimate  -> scanned/photographed doc
        """
        try:
            # Laplacian variance is a common, cheap sharpness measure.
            # Sharper edges (typed text) produce a higher variance.
            laplacian_var = cv2.Laplacian(gray_image, cv2.CV_64F).var()

            # Estimate noise by comparing the image to a blurred version of itself.
            # Larger differences suggest grain/noise typical of scans or photos.
            blurred = cv2.GaussianBlur(gray_image, (5, 5), 0)
            noise_estimate = np.mean(cv2.absdiff(gray_image, blurred))

            is_clean = laplacian_var > 150 and noise_estimate < 8

            logger.info(
                f"is_clean_document: laplacian_var={laplacian_var:.1f}, "
                f"noise_estimate={noise_estimate:.2f}, decision="
                f"{'clean' if is_clean else 'noisy'}"
            )
            return is_clean

        except Exception as e:
            # If detection itself fails, default to the safer/fuller pipeline
            logger.error(f"is_clean_document failed, defaulting to 'noisy': {e}")
            return False

    # SAVE

    def save_image(self, image: np.ndarray, output_path: str):
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_path), image)
            logger.info(f"Saved image to {output_path}")

        except Exception as e:
            logger.error(f"save_image failed for '{output_path}': {e}")
            raise

    # COMPLETE PIPELINE

    def process(self, image_path: str, mode: str = "auto") -> np.ndarray:
        """
        Complete preprocessing pipeline.

        mode:
            "auto"  - automatically pick clean vs. noisy pipeline (default)
            "clean" - force the light pipeline (grayscale + contrast + deskew)
            "noisy" - force the full pipeline (+ threshold + morphology)
        """
        try:
            image = self.load_image(image_path)

            # Perspective correction runs first, on the original color image.
            # It's a safe no-op: if no confident document boundary is found
            # (the normal case for flat scans / digital docs filling the
            # whole frame), `image` is returned completely unchanged.
            image = self.correct_perspective(image)

            gray = self.convert_to_grayscale(image)

            # Blur is only logged as a warning, never blocks processing -
            # a flat/digital doc will simply never trigger this.
            self.is_blurry(gray)

            contrast = self.enhance_contrast(gray)
            denoised = self.remove_noise(contrast)

            if mode == "auto":
                use_clean_path = self.is_clean_document(gray)
            elif mode == "clean":
                use_clean_path = True
            elif mode == "noisy":
                use_clean_path = False
            else:
                logger.warning(f"Unknown mode '{mode}', defaulting to 'auto'")
                use_clean_path = self.is_clean_document(gray)

            if use_clean_path:
                # Clean/digital documents: skip binarization + morphology,
                # since they destroy thin table text on crisp typed fonts.
                # EasyOCR performs its own internal thresholding better than
                # a one-way, irreversible binarization step can here.
                logger.info("Using light preprocessing path (clean document)")

                # Deskew is also skipped here. minAreaRect-based angle
                # estimation is unreliable on sparse, form-like layouts
                # (short header lines + a small table + few text blocks) -
                # it can compute a phantom tilt from how the text blocks are
                # scattered across the page, even when every line is dead
                # straight. Born-digital documents also have no real
                # scan-induced tilt to correct in the first place.
                return denoised
            else:
                # Scanned/photographed documents: binarize and clean up
                # to remove background noise, shadows, and paper texture.
                logger.info("Using full preprocessing path (noisy/scanned document)")
                binary = self.apply_threshold(denoised)
                result = self.morphology(binary)

                # Deskew only runs on the scanned/noisy path, where physical
                # capture (scanning or photographing) can genuinely introduce
                # rotation, and dense text gives minAreaRect a reliable signal.
                return self.deskew(result)

        except Exception as e:
            logger.error(f"process failed for '{image_path}': {e}")
            raise
