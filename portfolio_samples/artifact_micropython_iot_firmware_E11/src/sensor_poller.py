"""Asynchronous sensor polling engine with moving average smoothing and outlier rejection.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Optional, Tuple
import time
import math
import asyncio
from src.models import SensorReading


class SensorPoller:
    """Sensor polling engine with rolling window smoothing and statistical outlier rejection."""

    def __init__(self, window_size: int = 5, outlier_sigma: float = 2.5):
        self.window_size = window_size
        self.outlier_sigma = outlier_sigma
        self.history: Dict[str, List[float]] = {}
        self.outlier_counts: Dict[str, int] = {}
        self.total_polled: Dict[str, int] = {}

    def _is_outlier(self, sensor_id: str, value: float) -> bool:
        """Check if reading deviates abnormally from existing sample window."""
        window = self.history.get(sensor_id, [])
        if len(window) < 3:
            return False

        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        std_dev = math.sqrt(variance)

        if std_dev < 1e-4:
            # Low variance baseline: flag if deviation is large (> 5.0 absolute units)
            return abs(value - mean) > 5.0

        z_score = abs(value - mean) / std_dev
        return z_score > self.outlier_sigma

    def ingest_reading(
        self,
        sensor_id: str,
        value: float,
        unit: str = "C",
        sensor_type: str = "ANALOG",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[SensorReading]:
        """Process incoming raw sensor reading with outlier rejection and window update."""
        if sensor_id not in self.history:
            self.history[sensor_id] = []
            self.outlier_counts[sensor_id] = 0
            self.total_polled[sensor_id] = 0

        self.total_polled[sensor_id] += 1

        if self._is_outlier(sensor_id, value):
            self.outlier_counts[sensor_id] += 1
            return None

        # Add to rolling window
        window = self.history[sensor_id]
        window.append(value)
        if len(window) > self.window_size:
            window.pop(0)

        smoothed = sum(window) / len(window)
        return SensorReading(
            sensor_id=sensor_id,
            sensor_type=sensor_type,
            value=round(smoothed, 4),
            unit=unit,
            timestamp=time.time(),
            is_valid=True,
            metadata=metadata or {},
        )

    def get_smoothed_value(self, sensor_id: str) -> Optional[float]:
        """Return current rolling average for given sensor."""
        window = self.history.get(sensor_id, [])
        if not window:
            return None
        return round(sum(window) / len(window), 4)

    def get_history(self, sensor_id: str) -> List[float]:
        """Return raw history window for sensor."""
        return list(self.history.get(sensor_id, []))

    def get_outlier_count(self, sensor_id: str) -> int:
        """Return total number of rejected outlier readings."""
        return self.outlier_counts.get(sensor_id, 0)

    async def poll_sensor_async(
        self,
        sensor_id: str,
        sample_provider_func,
        unit: str = "C",
        sensor_type: str = "I2C",
    ) -> Optional[SensorReading]:
        """Asynchronously invoke sensor callback and ingest reading."""
        raw_val = await sample_provider_func()
        return self.ingest_reading(sensor_id, raw_val, unit=unit, sensor_type=sensor_type)

    async def poll_all_async(
        self,
        sensor_providers: Dict[str, Any],
    ) -> Dict[str, Optional[SensorReading]]:
        """Asynchronously poll multiple sensors concurrently."""
        tasks = []
        sensor_ids = list(sensor_providers.keys())

        for s_id in sensor_ids:
            tasks.append(sensor_providers[s_id]())

        results = await asyncio.gather(*tasks, return_exceptions=True)
        readings: Dict[str, Optional[SensorReading]] = {}

        for s_id, res in zip(sensor_ids, results):
            if isinstance(res, (Exception, BaseException)):
                readings[s_id] = None
            else:
                try:
                    readings[s_id] = self.ingest_reading(s_id, float(res))  # type: ignore
                except (TypeError, ValueError):
                    readings[s_id] = None

        return readings

    def reset(self) -> None:
        """Clear all histories and counters."""
        self.history.clear()
        self.outlier_counts.clear()
        self.total_polled.clear()
