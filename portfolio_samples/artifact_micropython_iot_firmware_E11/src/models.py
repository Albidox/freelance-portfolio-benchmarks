"""Data contracts, models, and enums for ESP32 MicroPython IoT Firmware.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone


class DeviceState(str, Enum):
    BOOTING = "BOOTING"
    SENSING = "SENSING"
    CONNECTING = "CONNECTING"
    PUBLISHING = "PUBLISHING"
    SLEEPING = "SLEEPING"
    ERROR = "ERROR"


class SensorType(str, Enum):
    TEMPERATURE_HUMIDITY = "TEMP_HUMIDITY"
    VOLTAGE_ADC = "VOLTAGE_ADC"
    I2C_BUS = "I2C_BUS"


class MQTTQoS(int, Enum):
    AT_MOST_ONCE = 0
    AT_LEAST_ONCE = 1


@dataclass
class TelemetrySample:
    device_id: str
    sensor_type: SensorType
    temperature_c: float
    humidity_pct: float
    battery_mv: int
    sequence_num: int
    timestamp: int
    is_valid: bool = True
    error_flags: List[str] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate sample values against realistic physical operational bounds."""
        if not (-40.0 <= self.temperature_c <= 85.0):
            self.error_flags.append("TEMP_OUT_OF_BOUNDS")
            self.is_valid = False
        if not (0.0 <= self.humidity_pct <= 100.0):
            self.error_flags.append("HUMIDITY_OUT_OF_BOUNDS")
            self.is_valid = False
        if not (2000 <= self.battery_mv <= 4500):
            self.error_flags.append("BATTERY_VOLTAGE_INVALID")
            self.is_valid = False
        return self.is_valid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "sensor_type": self.sensor_type.value if hasattr(self.sensor_type, "value") else str(self.sensor_type),
            "temperature_c": round(self.temperature_c, 2),
            "humidity_pct": round(self.humidity_pct, 2),
            "battery_mv": self.battery_mv,
            "sequence_num": self.sequence_num,
            "timestamp": self.timestamp,
            "is_valid": self.is_valid,
            "error_flags": list(self.error_flags),
        }


@dataclass
class FirmwareConfig:
    device_uuid: str = "esp32-node-001"
    wifi_ssid: str = "IoT_Private_Net"
    wifi_password: str = "secret_wifi_key"
    mqtt_broker: str = "127.0.0.1"
    mqtt_port: int = 1883
    poll_interval_ms: int = 5000
    wdt_timeout_ms: int = 15000
    flash_queue_max_size: int = 500

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NetworkTelemetryRecord:
    rssi_dbm: int
    ip_address: str
    reconnect_count: int
    dropped_packets: int
    uptime_seconds: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SensorReading:
    sensor_id: str
    sensor_type: str
    value: float
    unit: str
    timestamp: float
    is_valid: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type,
            "value": round(self.value, 4),
            "unit": self.unit,
            "timestamp": self.timestamp,
            "is_valid": self.is_valid,
            "metadata": self.metadata,
        }


@dataclass
class DeviceTelemetry:
    device_id: str
    firmware_version: str
    uptime_sec: int
    readings: List[Dict[str, Any]] = field(default_factory=list)
    battery_mv: int = 3800
    free_heap_bytes: int = 114688
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "firmware_version": self.firmware_version,
            "uptime_sec": self.uptime_sec,
            "readings": self.readings,
            "battery_mv": self.battery_mv,
            "free_heap_bytes": self.free_heap_bytes,
            "timestamp": self.timestamp,
        }


@dataclass
class DisplayFrame:
    width: int
    height: int
    buffer_bytes: bytes = b""
    color_mode: str = "MONO"
    frame_seq: int = 0
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "buffer_size": len(self.buffer_bytes),
            "color_mode": self.color_mode,
            "frame_seq": self.frame_seq,
            "timestamp": self.timestamp,
        }


@dataclass
class NetworkConfig:
    ssid: str = "IoT_Net"
    password: str = ""
    use_dhcp: bool = True
    static_ip: str = "192.168.1.150"
    subnet_mask: str = "255.255.255.0"
    gateway: str = "192.168.1.1"
    dns_server: str = "8.8.8.8"
    captive_portal_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
