"""Human-like touch curve generator adding Bezier randomized jitter to prevent bot detection.
Enforces zero em dash policy.
"""
import random
import math
from typing import List, Tuple
from src.models import Point, BoundingBox


class GestureHumanizer:
    """Generates natural human-like gesture paths using Bezier curves and spatial jitter."""

    def __init__(self, jitter_radius_px: int = 12):
        self.jitter_radius_px = jitter_radius_px

    def humanize_point(self, bbox: BoundingBox) -> Point:
        """Calculate humanized touch coordinate with Gaussian jitter inside target bounding box."""
        center = bbox.center
        max_dx = max(1, min(self.jitter_radius_px, bbox.width // 4))
        max_dy = max(1, min(self.jitter_radius_px, bbox.height // 4))

        jitter_x = int(random.gauss(0, max_dx / 2))
        jitter_y = int(random.gauss(0, max_dy / 2))

        clamped_x = max(bbox.x + 2, min(bbox.x + bbox.width - 2, center.x + jitter_x))
        clamped_y = max(bbox.y + 2, min(bbox.y + bbox.height - 2, center.y + jitter_y))

        return Point(x=clamped_x, y=clamped_y)

    def generate_bezier_curve(
        self,
        start: Point,
        end: Point,
        steps: int = 25,
        deviation_px: int = 20
    ) -> List[Point]:
        """Generate cubic Bezier curve points simulating natural finger motion."""
        # Calculate random control points perpendicular to straight path
        dx = end.x - start.x
        dy = end.y - start.y
        dist = math.hypot(dx, dy)
        if dist < 1.0:
            return [start, end]

        # Normalized perpendicular vectors
        nx = -dy / dist
        ny = dx / dist

        offset1 = random.uniform(-deviation_px, deviation_px)
        offset2 = random.uniform(-deviation_px, deviation_px)

        ctrl1_x = start.x + dx * 0.33 + nx * offset1
        ctrl1_y = start.y + dy * 0.33 + ny * offset1

        ctrl2_x = start.x + dx * 0.66 + nx * offset2
        ctrl2_y = start.y + dy * 0.66 + ny * offset2

        curve_points: List[Point] = []
        for i in range(steps + 1):
            t = i / steps
            # Cubic Bezier formula: (1-t)^3*P0 + 3(1-t)^2*t*P1 + 3(1-t)*t^2*P2 + t^3*P3
            x = ((1 - t) ** 3 * start.x +
                 3 * (1 - t) ** 2 * t * ctrl1_x +
                 3 * (1 - t) * t ** 2 * ctrl2_x +
                 t ** 3 * end.x)
            y = ((1 - t) ** 3 * start.y +
                 3 * (1 - t) ** 2 * t * ctrl1_y +
                 3 * (1 - t) * t ** 2 * ctrl2_y +
                 t ** 3 * end.y)

            # Add subtle jitter to intermediate points
            micro_jitter_x = random.gauss(0, 0.5) if (0 < i < steps) else 0.0
            micro_jitter_y = random.gauss(0, 0.5) if (0 < i < steps) else 0.0

            curve_points.append(Point(x=int(round(x + micro_jitter_x)), y=int(round(y + micro_jitter_y))))

        return curve_points

    def random_delay_sec(self, min_ms: int = 150, max_ms: int = 450) -> float:
        """Generate natural human reaction delay in seconds."""
        return random.randint(min_ms, max_ms) / 1000.0
