"""MicroPython I2C/SPI display driver supporting SSD1306 and ST7789 with frame buffer rendering.
Strict zero em dash policy enforced.
"""
from typing import Optional, Tuple, Dict, Any
from enum import Enum
import time
from src.models import DisplayFrame


class DisplayType(str, Enum):
    SSD1306_I2C = "SSD1306_I2C"
    ST7789_SPI = "ST7789_SPI"


# Minimal 5x7 ASCII font lookup for common alphanumeric characters
FONT_5X7: Dict[str, Tuple[int, ...]] = {
    " ": (0x00, 0x00, 0x00, 0x00, 0x00),
    "0": (0x3E, 0x51, 0x49, 0x45, 0x3E),
    "1": (0x00, 0x42, 0x7F, 0x40, 0x00),
    "2": (0x42, 0x61, 0x51, 0x49, 0x46),
    "3": (0x21, 0x41, 0x45, 0x4B, 0x31),
    "4": (0x18, 0x14, 0x12, 0x7F, 0x10),
    "5": (0x27, 0x45, 0x45, 0x45, 0x39),
    "6": (0x3C, 0x4A, 0x49, 0x49, 0x30),
    "7": (0x01, 0x71, 0x09, 0x05, 0x03),
    "8": (0x36, 0x49, 0x49, 0x49, 0x36),
    "9": (0x06, 0x49, 0x49, 0x29, 0x1E),
    ":": (0x00, 0x36, 0x36, 0x00, 0x00),
    ".": (0x00, 0x60, 0x60, 0x00, 0x00),
    "-": (0x08, 0x08, 0x08, 0x08, 0x08),
    "A": (0x7E, 0x11, 0x11, 0x11, 0x7E),
    "B": (0x7F, 0x49, 0x49, 0x49, 0x36),
    "C": (0x3E, 0x41, 0x41, 0x41, 0x22),
    "E": (0x7F, 0x49, 0x49, 0x49, 0x41),
    "F": (0x7F, 0x09, 0x09, 0x09, 0x01),
    "I": (0x00, 0x41, 0x7F, 0x41, 0x00),
    "O": (0x3E, 0x41, 0x41, 0x41, 0x3E),
    "P": (0x7F, 0x09, 0x09, 0x09, 0x06),
    "R": (0x7F, 0x09, 0x19, 0x29, 0x46),
    "S": (0x46, 0x49, 0x49, 0x49, 0x31),
    "T": (0x01, 0x01, 0x7F, 0x01, 0x01),
}


class DisplayDriver:
    """Frame buffer renderer for embedded displays (SSD1306 monochrome & ST7789 16-bit color)."""

    def __init__(
        self,
        display_type: DisplayType = DisplayType.SSD1306_I2C,
        width: Optional[int] = None,
        height: Optional[int] = None,
        bus_addr: int = 0x3C,
    ):
        self.display_type = display_type
        self.bus_addr = bus_addr
        self.sleep_mode = False
        self.contrast_level = 128
        self.frame_seq = 0

        if self.display_type == DisplayType.SSD1306_I2C:
            self.width = width or 128
            self.height = height or 64
            self.bytes_per_pixel = 1  # Packed 1-bit monochrome
            self.buffer_size = (self.width * self.height) // 8
            self.color_mode = "MONO"
        else:
            self.width = width or 240
            self.height = height or 240
            self.bytes_per_pixel = 2  # RGB565 16-bit
            self.buffer_size = self.width * self.height * 2
            self.color_mode = "RGB565"

        self.buffer = bytearray(self.buffer_size)

    def clear(self, color: int = 0) -> None:
        """Clear entire frame buffer with default background color."""
        fill_byte = 0xFF if (color != 0 and self.color_mode == "MONO") else (color & 0xFF)
        for i in range(len(self.buffer)):
            self.buffer[i] = fill_byte

    def set_pixel(self, x: int, y: int, color: int = 1) -> None:
        """Set single pixel at coordinates (x, y) with bounds guarding."""
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return

        if self.display_type == DisplayType.SSD1306_I2C:
            index = x + (y // 8) * self.width
            bit_mask = 1 << (y % 8)
            if color:
                self.buffer[index] |= bit_mask
            else:
                self.buffer[index] &= ~bit_mask
        else:
            index = (y * self.width + x) * 2
            self.buffer[index] = (color >> 8) & 0xFF
            self.buffer[index + 1] = color & 0xFF

    def get_pixel(self, x: int, y: int) -> int:
        """Retrieve pixel value at (x, y)."""
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return 0

        if self.display_type == DisplayType.SSD1306_I2C:
            index = x + (y // 8) * self.width
            bit_mask = 1 << (y % 8)
            return 1 if (self.buffer[index] & bit_mask) else 0
        else:
            index = (y * self.width + x) * 2
            return (self.buffer[index] << 8) | self.buffer[index + 1]

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, color: int = 1) -> None:
        """Draw line using Bresenham line algorithm."""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            self.set_pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def draw_rect(self, x: int, y: int, w: int, h: int, color: int = 1, fill: bool = False) -> None:
        """Draw outline or filled rectangle."""
        if fill:
            for py in range(y, y + h):
                for px in range(x, x + w):
                    self.set_pixel(px, py, color)
        else:
            self.draw_line(x, y, x + w - 1, y, color)
            self.draw_line(x, y + h - 1, x + w - 1, y + h - 1, color)
            self.draw_line(x, y, x, y + h - 1, color)
            self.draw_line(x + w - 1, y, x + w - 1, y + h - 1, color)

    def draw_text(self, x: int, y: int, text: str, color: int = 1) -> None:
        """Render ASCII string into frame buffer using 5x7 font."""
        cursor_x = x
        for char in text.upper():
            glyph = FONT_5X7.get(char, FONT_5X7[" "])
            for col_idx, col_bits in enumerate(glyph):
                for row_idx in range(7):
                    if (col_bits >> row_idx) & 1:
                        self.set_pixel(cursor_x + col_idx, y + row_idx, color)
            cursor_x += 6

    def render_frame(self) -> DisplayFrame:
        """Snapshot current frame buffer into immutable DisplayFrame dataclass."""
        self.frame_seq += 1
        return DisplayFrame(
            width=self.width,
            height=self.height,
            buffer_bytes=bytes(self.buffer),
            color_mode=self.color_mode,
            frame_seq=self.frame_seq,
            timestamp=time.time(),
        )

    def flush_buffer(self) -> bytes:
        """Extract frame bytes for hardware bus transmission (I2C/SPI)."""
        return bytes(self.buffer)

    def power_save(self, sleep_mode: bool = True) -> None:
        """Set hardware sleep mode."""
        self.sleep_mode = sleep_mode

    def set_contrast(self, level: int) -> None:
        """Adjust display contrast or brightness (0-255)."""
        self.contrast_level = max(0, min(255, level))
