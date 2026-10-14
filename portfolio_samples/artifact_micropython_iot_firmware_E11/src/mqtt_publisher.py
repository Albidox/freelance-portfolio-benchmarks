"""Lightweight MQTT v3.1.1 protocol packet builder with QoS 1 acknowledgment tracking.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Optional
import json
import time


class MQTTPublisher:
    """Lightweight MQTT client emulator for MicroPython constrained targets."""

    def __init__(self, client_id: str = "esp32-001", broker: str = "127.0.0.1", port: int = 1883):
        self.client_id = client_id
        self.broker = broker
        self.port = port
        self.packet_id_counter = 1
        self.unacknowledged_packets: Dict[int, Dict[str, Any]] = {}
        self.published_count = 0
        self.connected = False

    def connect(self) -> bool:
        """Establish logical connection to MQTT broker."""
        self.connected = True
        return True

    def disconnect(self) -> None:
        """Terminate logical connection."""
        self.connected = False

    def build_publish_packet(self, topic: str, payload_dict: Dict[str, Any], qos: int = 1) -> Dict[str, Any]:
        """Construct MQTT PUBLISH frame representation."""
        packet_id = self.packet_id_counter
        self.packet_id_counter = (self.packet_id_counter % 65535) + 1

        packet = {
            "packet_id": packet_id,
            "topic": topic,
            "payload": json.dumps(payload_dict),
            "qos": qos,
            "timestamp": time.time(),
        }
        if qos == 1:
            self.unacknowledged_packets[packet_id] = packet
        return packet

    def receive_puback(self, packet_id: int) -> bool:
        """Process PUBACK response from broker."""
        if packet_id in self.unacknowledged_packets:
            del self.unacknowledged_packets[packet_id]
            self.published_count += 1
            return True
        return False

    def get_pending_retry_count(self) -> int:
        """Count unacknowledged QoS 1 packets."""
        return len(self.unacknowledged_packets)

    def resend_unacknowledged(self) -> List[Dict[str, Any]]:
        """Retrieve list of packets requiring retransmission."""
        return list(self.unacknowledged_packets.values())
