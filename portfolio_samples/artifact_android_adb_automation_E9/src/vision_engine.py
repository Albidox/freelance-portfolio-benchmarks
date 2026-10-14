"""OpenCV multi-scale template matching vision engine.
Enforces zero em dash policy.
"""
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
from src.models import Point, BoundingBox, MatchResult, TemplateTarget
from src.screen_analyzer import ScreenAnalyzer


class VisionEngine(ScreenAnalyzer):
    """Production OpenCV computer vision engine for Android UI automation."""

    def __init__(self, default_threshold: float = 0.85):
        super().__init__(default_threshold=default_threshold)

    def locate_target(
        self,
        screen_img: np.ndarray,
        target: TemplateTarget,
        template_img: np.ndarray
    ) -> MatchResult:
        """Locate target on screen using multi-scale matching and target thresholds."""
        return self.multi_scale_match(
            screen_img=screen_img,
            template_img=template_img,
            scales=target.scales,
            threshold=target.threshold
        )

    def locate_all_instances(
        self,
        screen_img: np.ndarray,
        template_img: np.ndarray,
        threshold: Optional[float] = None,
        overlap_threshold: float = 0.3
    ) -> List[BoundingBox]:
        """Locate all matching instances on screen using NMS."""
        import cv2

        thresh = threshold if threshold is not None else self.default_threshold
        gray_screen = self.normalize_grayscale(screen_img)
        gray_tmpl = self.normalize_grayscale(template_img)

        w, h = gray_tmpl.shape[1], gray_tmpl.shape[0]
        if gray_screen.shape[0] < h or gray_screen.shape[1] < w:
            return []

        res = cv2.matchTemplate(gray_screen, gray_tmpl, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= thresh)

        boxes: List[BoundingBox] = []
        for pt in zip(*loc[::-1]):
            score = float(res[pt[1], pt[0]])
            boxes.append(BoundingBox(x=int(pt[0]), y=int(pt[1]), width=w, height=h, confidence=score))

        return self.non_maximum_suppression(boxes, overlap_threshold=overlap_threshold)
