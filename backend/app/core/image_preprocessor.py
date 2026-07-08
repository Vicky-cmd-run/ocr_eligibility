"""
Image preprocessing pipeline using OpenCV.
Applies auto-rotation, deskewing, denoising, contrast enhancement,
perspective correction, and adaptive thresholding.
"""
import logging
import math
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """
    Full preprocessing pipeline for marksheet images.
    Each step is optional and can be toggled.
    """

    def __init__(
        self,
        auto_rotate: bool = True,
        deskew: bool = True,
        denoise: bool = True,
        enhance_contrast: bool = True,
        adaptive_threshold: bool = False,
        perspective_correct: bool = True,
        target_width: int = 2000,
    ):
        self.auto_rotate = auto_rotate
        self.deskew = deskew
        self.denoise = denoise
        self.enhance_contrast = enhance_contrast
        self.adaptive_threshold = adaptive_threshold
        self.perspective_correct = perspective_correct
        self.target_width = target_width

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Run the full preprocessing pipeline on a BGR image.
        Returns a preprocessed BGR image ready for OCR.
        """
        img = image.copy()

        # 1. Resize if needed
        img = self._resize(img)

        # 2. Perspective correction (photographed docs)
        if self.perspective_correct:
            img = self._correct_perspective(img)

        # 3. Convert to grayscale for processing
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 4. Auto-rotation using EXIF or text orientation
        if self.auto_rotate:
            gray = self._auto_rotate(gray)

        # 5. Deskew
        if self.deskew:
            gray = self._deskew(gray)

        # 6. Denoise
        if self.denoise:
            gray = self._denoise(gray)

        # 7. Contrast enhancement with CLAHE
        if self.enhance_contrast:
            gray = self._enhance_contrast(gray)

        # 8. Adaptive thresholding (optional — for very noisy docs)
        if self.adaptive_threshold:
            gray = self._adaptive_threshold(gray)

        # Convert back to BGR for PaddleOCR (which expects BGR)
        result = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        return result

    def _resize(self, img: np.ndarray) -> np.ndarray:
        """Resize image so width = target_width, preserving aspect ratio."""
        h, w = img.shape[:2]
        if w < self.target_width:
            scale = self.target_width / w
            new_w = self.target_width
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        return img

    def _auto_rotate(self, gray: np.ndarray) -> np.ndarray:
        """
        Detect and correct 90/180/270 degree rotations using
        variance of horizontal projections as a heuristic.
        Returns the best-orientation grayscale image.
        """
        best_var = -1
        best_img = gray

        for angle in [0, 90, 180, 270]:
            if angle == 0:
                rotated = gray
            else:
                center = (gray.shape[1] // 2, gray.shape[0] // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(
                    gray, M, (gray.shape[1], gray.shape[0]),
                    flags=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REPLICATE,
                )

            # Use horizontal projection profile variance as quality metric
            projection = np.sum(rotated < 128, axis=1).astype(float)
            var = float(np.var(projection))
            if var > best_var:
                best_var = var
                best_img = rotated

        return best_img

    def _deskew(self, gray: np.ndarray) -> np.ndarray:
        """
        Detect and correct small skew angles (< 45°) using
        Hough line detection on edge-detected image.
        """
        try:
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(
                edges, 1, np.pi / 180, threshold=100,
                minLineLength=gray.shape[1] // 4,
                maxLineGap=20,
            )

            if lines is None or len(lines) == 0:
                return gray

            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if x2 - x1 == 0:
                    continue
                angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
                if -45 < angle < 45:
                    angles.append(angle)

            if not angles:
                return gray

            median_angle = float(np.median(angles))

            if abs(median_angle) < 0.5:
                return gray

            h, w = gray.shape
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
            deskewed = cv2.warpAffine(
                gray, M, (w, h),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REPLICATE,
            )
            return deskewed
        except Exception as e:
            logger.warning(f"Deskew failed: {e}")
            return gray

    def _denoise(self, gray: np.ndarray) -> np.ndarray:
        """Apply non-local means denoising."""
        try:
            return cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)
        except Exception as e:
            logger.warning(f"Denoising failed: {e}")
            return gray

    def _enhance_contrast(self, gray: np.ndarray) -> np.ndarray:
        """Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)."""
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(gray)

    def _adaptive_threshold(self, gray: np.ndarray) -> np.ndarray:
        """
        Apply adaptive thresholding to binarize the image.
        Useful for very low-contrast or uneven-lighting documents.
        """
        return cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=31,
            C=10,
        )

    def _correct_perspective(self, img: np.ndarray) -> np.ndarray:
        """
        Detect and correct perspective distortion (photographed documents).
        Uses contour detection to find the largest quadrilateral.
        Returns corrected image or original if no quadrilateral is found.
        """
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edged = cv2.Canny(blurred, 50, 150)

            contours, _ = cv2.findContours(
                edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if not contours:
                return img

            # Sort by area descending
            contours = sorted(contours, key=cv2.contourArea, reverse=True)

            for cnt in contours[:5]:
                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

                if len(approx) == 4:
                    # Found a quadrilateral — apply perspective transform
                    pts = approx.reshape(4, 2).astype(np.float32)
                    pts = _order_points(pts)
                    warped = _four_point_transform(img, pts)

                    # Only use if the warped image is reasonably large
                    h, w = warped.shape[:2]
                    orig_h, orig_w = img.shape[:2]
                    if w > orig_w * 0.3 and h > orig_h * 0.3:
                        return warped

            return img
        except Exception as e:
            logger.warning(f"Perspective correction failed: {e}")
            return img


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order points as [top-left, top-right, bottom-right, bottom-left]."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _four_point_transform(img: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Apply a perspective transform given four corner points."""
    (tl, tr, br, bl) = pts

    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = max(int(width_a), int(width_b))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = max(int(height_a), int(height_b))

    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1],
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(pts, dst)
    return cv2.warpPerspective(img, M, (max_width, max_height))


def load_image(file_path: str) -> np.ndarray:
    """Load an image file as a BGR numpy array."""
    img = cv2.imread(file_path)
    if img is None:
        # Try via Pillow for broader format support
        pil = Image.open(file_path).convert("RGB")
        import numpy as np
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    return img


# Default preprocessor instance
default_preprocessor = ImagePreprocessor()
