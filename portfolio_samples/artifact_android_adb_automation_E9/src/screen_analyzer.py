"""OpenCV multi-scale template matching engine with non-maximum suppression (NMS).
Enforces zero em dash policy.
"""
import cv2
import numpy as np
from typing import List, Optional, Tuple
from src.models import Point, BoundingBox, MatchResult


class ScreenAnalyzer:
    """Computer vision engine performing template matching and non-maximum suppression."""

    def __init__(self, default_threshold: float = 0.85):
        self.default_threshold = default_threshold
        self.frames_analyzed: int = 0

    @staticmethod
    def non_maximum_suppression(
        boxes: List[BoundingBox],
        overlap_threshold: float = 0.3
    ) -> List[BoundingBox]:
        """Filter overlapping detections retaining highest confidence matches."""
        if not boxes:
            return []

        # Sort descending by confidence
        sorted_boxes = sorted(boxes, key=lambda b: b.confidence, reverse=True)
        picked: List[BoundingBox] = []

        while sorted_boxes:
            current = sorted_boxes.pop(0)
            picked.append(current)

            remaining = []
            for b in sorted_boxes:
                # Calculate Intersection over Union (IoU)
                xx1 = max(current.x, b.x)
                yy1 = max(current.y, b.y)
                xx2 = min(current.x + current.width, b.x + b.width)
                yy2 = min(current.y + current.height, b.y + b.height)

                w = max(0, xx2 - xx1)
                h = max(0, yy2 - yy1)
                intersection = w * h

                area_curr = current.width * current.height
                area_b = b.width * b.height
                union = area_curr + area_b - intersection

                iou = intersection / union if union > 0 else 0.0
                if iou < overlap_threshold:
                    remaining.append(b)

            sorted_boxes = remaining

        return picked

    def normalize_grayscale(self, image: np.ndarray) -> np.ndarray:
        """Convert multi-channel image to single-channel normalized grayscale."""
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image

    def match_template(
        self,
        screen_img: np.ndarray,
        template_img: np.ndarray,
        threshold: Optional[float] = None
    ) -> MatchResult:
        """Execute template matching via normalized cross-correlation (TM_CCOEFF_NORMED)."""
        self.frames_analyzed += 1
        thresh = threshold if threshold is not None else self.default_threshold

        if screen_img.shape[0] < template_img.shape[0] or screen_img.shape[1] < template_img.shape[1]:
            return MatchResult(found=False, confidence=0.0)

        # Convert to grayscale if 3-channel
        gray_screen = self.normalize_grayscale(screen_img)
        gray_tmpl = self.normalize_grayscale(template_img)

        result = cv2.matchTemplate(gray_screen, gray_tmpl, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= thresh:
            w, h = gray_tmpl.shape[1], gray_tmpl.shape[0]
            bbox = BoundingBox(
                x=max_loc[0],
                y=max_loc[1],
                width=w,
                height=h,
                confidence=float(max_val)
            )
            return MatchResult(
                found=True,
                confidence=float(max_val),
                center=bbox.center,
                bbox=bbox
            )

        return MatchResult(found=False, confidence=float(max_val))

    def multi_scale_match(
        self,
        screen_img: np.ndarray,
        template_img: np.ndarray,
        scales: Optional[List[float]] = None,
        threshold: Optional[float] = None
    ) -> MatchResult:
        """Multi-scale template matching across varied screen resolutions."""
        if scales is None:
            scales = [0.75, 1.0, 1.25]

        best_match = MatchResult(found=False, confidence=0.0)
        thresh = threshold if threshold is not None else self.default_threshold

        for s in scales:
            w = int(template_img.shape[1] * s)
            h = int(template_img.shape[0] * s)
            if w <= 0 or h <= 0 or w > screen_img.shape[1] or h > screen_img.shape[0]:
                continue

            scaled_tmpl = cv2.resize(template_img, (w, h), interpolation=cv2.INTER_AREA)
            res = self.match_template(screen_img, scaled_tmpl, threshold=thresh)
            if res.found and res.confidence > best_match.confidence:
                res.scale = s
                best_match = res

        return best_match
