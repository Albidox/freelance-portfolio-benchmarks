"""Humanized gesture simulator, ANR dialogue detector, and workflow executor.
Enforces zero em dash policy.
"""
import random
import time
from typing import List, Dict, Any, Tuple, Optional
from src.models import Point, BoundingBox, ActionStep, ActionType


class ActionEngine:
    """Action simulation engine with humanized spatial jitter and ANR crash detection."""

    def __init__(self, jitter_radius_px: int = 12):
        self.jitter_radius_px = jitter_radius_px
        self.total_actions_executed: int = 0
        self.anr_events_caught: int = 0

    def calculate_humanized_point(self, bbox: BoundingBox) -> Point:
        """Apply Gaussian-distributed random spatial jitter inside bounding box."""
        center = bbox.center
        max_dx = max(1, min(self.jitter_radius_px, bbox.width // 4))
        max_dy = max(1, min(self.jitter_radius_px, bbox.height // 4))

        jitter_x = int(random.gauss(0, max_dx / 2))
        jitter_y = int(random.gauss(0, max_dy / 2))

        # Clamp strictly within box boundaries
        clamped_x = max(bbox.x + 2, min(bbox.x + bbox.width - 2, center.x + jitter_x))
        clamped_y = max(bbox.y + 2, min(bbox.y + bbox.height - 2, center.y + jitter_y))

        return Point(x=clamped_x, y=clamped_y)

    def detect_anr_dialogue(self, window_dump_text: str) -> bool:
        """Detect Application Not Responding (ANR) or crash modal in Android dumpsys."""
        keywords = ["Application Not Responding", "isn't responding", "Close app", "Wait"]
        for kw in keywords:
            if kw.lower() in window_dump_text.lower():
                self.anr_events_caught += 1
                return True
        return False
