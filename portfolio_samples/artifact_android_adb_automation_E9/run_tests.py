"""Standalone deterministic test harness for E9 Android Automation Bot with 26 assertions.
Runs natively on Windows without Linux shell dependencies.
Enforces zero em dash policy.
"""
import os
import sys
import tracemalloc
import numpy as np
import cv2

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from src.models import (
    DeviceState,
    ActionType,
    Point,
    BoundingBox,
    MatchResult,
    ActionStep,
    WorkflowRun
)
from src.config import ADBBotConfig
from src.adb_controller import ADBController
from src.screen_analyzer import ScreenAnalyzer
from src.action_engine import ActionEngine
from src.storage import ADBBotStorage


def test_models_and_enums():
    print("Testing models and contracts...")
    pt = Point(x=100, y=200)

    # Assertion 1: Point coordinates match
    assert pt.x == 100 and pt.y == 200

    # Assertion 2: BoundingBox center calculation
    box = BoundingBox(x=50, y=100, width=80, height=40, confidence=0.92)
    center = box.center
    assert center.x == 90 and center.y == 120, f"Expected (90, 120), got ({center.x}, {center.y})"

    # Assertion 3: DeviceState enum values
    assert DeviceState.CONNECTED.value == "CONNECTED"
    assert DeviceState.DISCONNECTED.value == "DISCONNECTED"

    # Assertion 4: ActionType enum values
    assert ActionType.TAP.value == "TAP"
    assert ActionType.SWIPE.value == "SWIPE"

    # Assertion 5: WorkflowRun dictionary serialization
    run = WorkflowRun(
        run_id="run_001",
        workflow_name="login_flow",
        total_steps=5,
        successful_steps=5,
        status="COMPLETED"
    )
    d = run.to_dict()
    assert d["run_id"] == "run_001"
    assert d["workflow_name"] == "login_flow"
    assert d["total_steps"] == 5


def test_adb_controller_commands():
    print("Testing ADB controller CLI builder and device parsers...")
    cfg = ADBBotConfig()
    controller = ADBController(cfg)

    # Assertion 6: Tap command structure
    tap_cmd = controller.build_tap_command(Point(300, 450))
    assert tap_cmd == ["adb", "-s", "emulator-5554", "shell", "input", "tap", "300", "450"]

    # Assertion 7: Swipe command structure
    swipe_cmd = controller.build_swipe_command(Point(100, 500), Point(100, 200), duration_ms=400)
    assert swipe_cmd == [
        "adb", "-s", "emulator-5554", "shell", "input", "swipe", "100", "500", "100", "200", "400"
    ]

    # Assertion 8: Text input command escapes spaces as %s
    text_cmd = controller.build_text_command("Hello World 2026")
    assert text_cmd[-1] == "Hello%sWorld%s2026"

    # Assertion 9: Parse device list with connected device
    sample_out = "List of devices attached\nemulator-5554\tdevice\nemulator-5556\toffline\n"
    devs = controller.parse_device_list(sample_out)
    assert len(devs) == 2
    assert devs[0] == ("emulator-5554", "device")
    assert devs[1] == ("emulator-5556", "offline")

    # Assertion 10: Check connection recognizes CONNECTED device
    st = controller.check_connection(simulated_output=sample_out)
    assert st == DeviceState.CONNECTED

    # Assertion 11: Check connection recognizes DISCONNECTED state
    empty_out = "List of devices attached\n\n"
    st_empty = controller.check_connection(simulated_output=empty_out)
    assert st_empty == DeviceState.DISCONNECTED


def test_computer_vision_and_template_matching():
    print("Testing OpenCV template matching and NMS on synthetic images...")
    analyzer = ScreenAnalyzer(default_threshold=0.85)

    # Create synthetic screen with background texture
    screen = np.zeros((400, 400, 3), dtype=np.uint8)
    screen[10:390, 10:390] = 50

    # Draw button with distinct border and inner circle at (150, 150)
    cv2.rectangle(screen, (150, 150), (250, 200), (0, 255, 0), -1)
    cv2.circle(screen, (200, 175), 15, (0, 0, 255), -1)

    # Create template sliced from the button (100x50)
    template = screen[150:200, 150:250].copy()

    # Assertion 12: Perfect template match yields confidence > 0.99
    res = analyzer.match_template(screen, template)
    assert res.found is True, "Template match failed to locate synthetic button"
    assert res.confidence >= 0.99, f"Expected confidence >= 0.99, got {res.confidence}"

    # Assertion 13: Bounding box coordinates match button location (150, 150)
    assert res.bbox is not None
    assert res.bbox.x == 150 and res.bbox.y == 150

    # Assertion 14: Center point computed at (200, 175)
    assert res.center is not None
    assert res.center.x == 200 and res.center.y == 175

    # Assertion 15: Missing template returns found=False
    missing_template = np.zeros((30, 30, 3), dtype=np.uint8)
    missing_template[:, :] = (255, 0, 0)
    cv2.line(missing_template, (0, 0), (29, 29), (0, 255, 255), 2)
    res_miss = analyzer.match_template(screen, missing_template)
    assert res_miss.found is False, "Missing template must not be found"

    # Assertion 16: Multi-scale template matching detects resized template
    scaled_tmpl = cv2.resize(template, (80, 40))
    res_multi = analyzer.multi_scale_match(screen, scaled_tmpl, scales=[0.8, 1.0, 1.25], threshold=0.80)
    assert res_multi.found is True, "Multi-scale match should find element"


def test_non_maximum_suppression():
    print("Testing Non-Maximum Suppression overlapping box filtering...")
    # Overlapping boxes around the same target
    b1 = BoundingBox(x=100, y=100, width=50, height=50, confidence=0.95)
    b2 = BoundingBox(x=102, y=102, width=50, height=50, confidence=0.88)
    b3 = BoundingBox(x=300, y=300, width=50, height=50, confidence=0.92)  # Disjoint box

    boxes = [b1, b2, b3]
    picked = ScreenAnalyzer.non_maximum_suppression(boxes, overlap_threshold=0.3)

    # Assertion 17: NMS suppresses overlapping b2 and retains b1 and b3
    assert len(picked) == 2, f"Expected 2 suppressed boxes, got {len(picked)}"

    # Assertion 18: Highest confidence box b1 preserved
    assert picked[0].confidence == 0.95
    assert picked[1].confidence == 0.92


def test_action_engine_and_jitter():
    print("Testing action engine, Gaussian jitter, and ANR crash detection...")
    engine = ActionEngine(jitter_radius_px=10)
    box = BoundingBox(x=100, y=100, width=60, height=40, confidence=0.90)

    # Assertion 19: Jittered point remains strictly within bounding box
    for _ in range(50):
        pt = engine.calculate_humanized_point(box)
        assert box.x <= pt.x <= box.x + box.width, f"X {pt.x} outside box ({box.x}, {box.x+box.width})"
        assert box.y <= pt.y <= box.y + box.height, f"Y {pt.y} outside box ({box.y}, {box.y+box.height})"

    # Assertion 20: ANR dialogue detector catches 'Application Not Responding'
    dump_anr = "mCurrentFocus=Window{4a921fe u0 Application Not Responding: com.example.app}"
    assert engine.detect_anr_dialogue(dump_anr) is True

    # Assertion 21: ANR dialogue detector catches 'Close app'
    dump_close = "Window contains dialog: Close app or Wait"
    assert engine.detect_anr_dialogue(dump_close) is True

    # Assertion 22: ANR detector returns False on normal window focus
    dump_normal = "mCurrentFocus=Window{8b191ae u0 com.example.app/MainActivity}"
    assert engine.detect_anr_dialogue(dump_normal) is False


def test_config_and_storage_ddl():
    print("Testing config defaults and PostgreSQL 18 DDL...")
    cfg = ADBBotConfig()

    # Assertion 23: Native PostgreSQL port 5433 configured
    assert cfg.db_port == 5433, f"Expected port 5433, got {cfg.db_port}"

    # Assertion 24: Schema is e9_android_bot
    assert cfg.db_schema == "e9_android_bot"

    # Assertion 25: Storage DDL contains schema and table statements
    storage = ADBBotStorage(cfg)
    ddl = storage.get_postgres_schema_ddl()
    assert "CREATE SCHEMA IF NOT EXISTS e9_android_bot;" in ddl
    assert "e9_android_bot.workflow_runs" in ddl


def main():
    print("=" * 70)
    print("STARTING E9 ANDROID MOBILE AUTOMATION BOT DETERMINISTIC SUITE")
    print("=" * 70)
    tracemalloc.start()

    test_models_and_enums()
    test_adb_controller_commands()
    test_computer_vision_and_template_matching()
    test_non_maximum_suppression()
    test_action_engine_and_jitter()
    test_config_and_storage_ddl()

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak_mem / (1024 * 1024)
    print(f"Memory Diagnostics: Peak memory consumed: {peak_mb:.2f} MB")

    # Assertion 26: Strict memory footprint ceiling under 250MB
    assert peak_mb < 250.0, f"Memory footprint exceeded 250MB: {peak_mb:.2f} MB"

    print("=" * 70)
    print("ALL 26 ASSERTIONS PASSED WITH ZERO MOCKS OR PHANTOM DAEMONS")
    print("=" * 70)


if __name__ == "__main__":
    main()
