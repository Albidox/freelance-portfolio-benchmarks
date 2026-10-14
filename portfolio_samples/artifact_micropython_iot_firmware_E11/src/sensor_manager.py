"""Sensor manager with I2C bus simulation, CRC-8 validation, and Exponential Moving Average filtering.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, Tuple, Optional
import time
from src.models import TelemetrySample, SensorType


class SensorManager:
    """I2C sensor interface supporting CRC-8 data integrity and jitter smoothing."""

    def __init__(self, i2c_bus_addr: int = 0x38, ema_alpha: float = 0.2):
        self.i2c_bus_addr = i2c_bus_addr
        self.ema_alpha = ema_alpha
        self.last_filtered_temp: Optional[float] = None
        self.last_filtered_humidity: Optional[float] = None
        self.bus_hung = False
        self.bus_reset_count = 0
        self.crc_error_count = 0

    @staticmethod
    def calculate_crc8(data: bytes, polynomial: int = 0x31, init_val: int = 0xFF) -> int:
        """Calculate CRC-8 checksum over bytes matching Sensirion / AHT20 hardware specifications."""
        crc = init_val
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ polynomial) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF
        return crc

    def read_raw_sensors(self, raw_bytes: Optional[bytes] = None) -> Tuple[float, float, int]:
        """Simulate hardware I2C sensor read with CRC verification."""
        if self.bus_hung:
            raise OSError("I2C_BUS_HUNG: Bus lockup detected on SDA/SCL lines")

        # Default simulated payload: 2 bytes temp, 2 bytes humidity, 1 byte CRC
        if raw_bytes is None:
            # Simulated 25.4C, 55.2% RH, 3850mV
            return 25.4, 55.2, 3850

        if len(raw_bytes) < 5:
            self.crc_error_count += 1
            raise ValueError("Incomplete I2C payload: expected 5 bytes")

        payload = raw_bytes[:4]
        received_crc = raw_bytes[4]
        computed_crc = self.calculate_crc8(payload)

        if computed_crc != received_crc:
            self.crc_error_count += 1
            raise ValueError(f"CRC mismatch: expected {computed_crc}, received {received_crc}")

        # Parse raw integer 16-bit big-endian representation
        raw_t = (payload[0] << 8) | payload[1]
        raw_h = (payload[2] << 8) | payload[3]
        temp = (raw_t / 100.0) - 40.0
        humidity = raw_h / 100.0
        battery = 3800
        return round(temp, 2), round(humidity, 2), battery

    def filter_telemetry(self, raw_temp: float, raw_hum: float) -> Tuple[float, float]:
        """Apply Exponential Moving Average (EMA) to prevent sensor jitter."""
        if self.last_filtered_temp is None or self.last_filtered_humidity is None:
            self.last_filtered_temp = raw_temp
            self.last_filtered_humidity = raw_hum
        else:
            self.last_filtered_temp = (self.ema_alpha * raw_temp) + ((1.0 - self.ema_alpha) * self.last_filtered_temp)
            self.last_filtered_humidity = (self.ema_alpha * raw_hum) + ((1.0 - self.ema_alpha) * self.last_filtered_humidity)
        return round(self.last_filtered_temp, 2), round(self.last_filtered_humidity, 2)

    def recover_i2c_bus(self) -> bool:
        """Execute hardware 9-clock I2C bus unjamming pulse sequence."""
        self.bus_hung = False
        self.bus_reset_count += 1
        return True

    def sample(self, device_id: str, sequence_num: int, raw_bytes: Optional[bytes] = None) -> TelemetrySample:
        """Full sensing routine: read, CRC check, filter, bounds check, and package."""
        t_raw, h_raw, batt = self.read_raw_sensors(raw_bytes)
        t_filt, h_filt = self.filter_telemetry(t_raw, h_raw)
        sample = TelemetrySample(
            device_id=device_id,
            sensor_type=SensorType.TEMPERATURE_HUMIDITY,
            temperature_c=t_filt,
            humidity_pct=h_filt,
            battery_mv=batt,
            sequence_num=sequence_num,
            timestamp=int(time.time()),
        )
        sample.validate()
        return sample
