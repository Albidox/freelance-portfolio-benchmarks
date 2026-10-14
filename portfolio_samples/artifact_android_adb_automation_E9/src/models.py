"""Data contracts, models, and enums for Android ADB and OpenCV Automation Bot.
Enforces zero em dash policy.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone


class DeviceState(str, Enum):
    CONNECTED = "CONNECTED"
    OFFLINE = "OFFLINE"
    UNAUTHORIZED = "UNAUTHORIZED"
    DISCONNECTED = "DISCONNECTED"


# Alias for compatibility with external specifications
DeviceStatus = DeviceState


class ActionType(str, Enum):
    TAP = "TAP"
    SWIPE = "SWIPE"
    INPUT_TEXT = "INPUT_TEXT"
    KEY_EVENT = "KEY_EVENT"
    WAIT = "WAIT"
    ASSERT_TEMPLATE = "ASSERT_TEMPLATE"


# Alias for compatibility with external specifications
TouchAction = ActionType


@dataclass
class Point:
    x: int
    y: int

    def to_tuple(self) -> Tuple[int, int]:
        return (self.x, self.y)


@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int
    confidence: float

    @property
    def center(self) -> Point:
        return Point(x=self.x + self.width // 2, y=self.y + self.height // 2)

    def contains(self, point: Point) -> bool:
        return (self.x <= point.x <= self.x + self.width and
                self.y <= point.y <= self.y + self.height)


@dataclass
class MatchResult:
    found: bool
    confidence: float
    center: Optional[Point] = None
    bbox: Optional[BoundingBox] = None
    scale: float = 1.0


@dataclass
class TemplateTarget:
    name: str
    image_path: Optional[str] = None
    threshold: float = 0.85
    scales: List[float] = field(default_factory=lambda: [0.75, 1.0, 1.25])
    grayscale: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionStep:
    step_id: str
    action_type: ActionType
    target_template: Optional[str] = None
    coordinates: Optional[Point] = None
    text_payload: Optional[str] = None
    key_code: Optional[int] = None
    delay_after_ms: int = 500


@dataclass
class WorkflowRun:
    run_id: str
    workflow_name: str
    total_steps: int
    successful_steps: int
    status: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ended_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow_name": self.workflow_name,
            "total_steps": self.total_steps,
            "successful_steps": self.successful_steps,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at
        }
