#!/usr/bin/env python3
"""
Lightweight Mock GraphQL Upstream Server.
Provides nested entity resolution: User -> Orders -> LineItems.
Supports intentional delays and partial error injection for resilience testing.
Zero em dashes used.
"""

import json
import logging
import re
import sys
import time
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger("mock_graphql_server")

PORT = 4000

# Mock database
USERS = {
    "USR-501": {
        "id": "USR-501",
        "name": "Alice Vance",
        "email": "alice.vance@example.com",
        "membershipTier": "PLATINUM",
        "registeredAt": "2024-01-15T08:00:00Z"
    },
    "USR-502": {
        "id": "USR-502",
        "name": "Bob Martinez",
        "email": "bob.martinez@example.com",
        "membershipTier": "GOLD",
        "registeredAt": "2024-03-22T10:30:00Z"
    },
    "USR-503": {
        "id": "USR-503",
        "name": "Carol Danvers",
        "email": "carol.danvers@example.com",
        "membershipTier": "SILVER",
        "registeredAt": "2024-06-11T12:00:00Z"
    }
}

ORDERS = {
    "ORD-1001": {
        "id": "ORD-1001",
        "status": "CONFIRMED",
        "totalAmount": 249.99,
        "currency": "USD",
        "createdAt": "2026-10-10T14:32:00Z",
        "userId": "USR-501",
        "shippingAddress": "123 Industrial Way, Seattle, WA",
        "lineItems": [
            {"id": "LI-101", "sku": "SKU-WDG-01", "productName": "Industrial Hub Sensor", "quantity": 2, "unitPrice": 89.99, "subtotal": 179.98},
            {"id": "LI-102", "sku": "SKU-CBL-04", "productName": "Shielded Cat6A Cable", "quantity": 1, "unitPrice": 25.01, "subtotal": 25.01},
            {"id": "LI-103", "sku": "SKU-PWR-09", "productName": "Redundant DIN Rail PSU", "quantity": 1, "unitPrice": 45.00, "subtotal": 45.00}
        ]
    },
    "ORD-1002": {
        "id": "ORD-1002",
        "status": "SHIPPED",
        "totalAmount": 89.50,
        "currency": "USD",
        "createdAt": "2026-10-09T09:15:00Z",
        "userId": "USR-502",
        "shippingAddress": "456 Market St, San Francisco, CA",
        "lineItems": [
            {"id": "LI-201", "sku": "SKU-OPT-12", "productName": "Fiber Optical Transceiver", "quantity": 1, "unitPrice": 89.50, "subtotal": 89.50}
        ]
    },
    "ORD-1003": {
        "id": "ORD-1003",
        "status": "DELIVERED",
        "totalAmount": 540.00,
        "currency": "USD",
        "createdAt": "2026-10-08T16:45:00Z",
        "userId": "USR-503",
        "shippingAddress": "789 Tech Ridge, Austin, TX",
        "lineItems": [
            {"id": "LI-301", "sku": "SKU-SRV-01", "productName": "1U Rackmount Server Chassis", "quantity": 2, "unitPrice": 220.00, "subtotal": 440.00},
            {"id": "LI-302", "sku": "SKU-FAN-05", "productName": "High Static Pressure Fan", "quantity": 4, "unitPrice": 25.00, "subtotal": 100.00}
        ]
    }
}


def get_or_generate_order(order_id: str) -> Optional[Dict[str, Any]]:
    if order_id in ORDERS:
        return ORDERS[order_id]
    
    # Deterministic generation for arbitrary IDs (e.g. ORD-1004 to ORD-9999)
    if order_id.startswith("ORD-") and order_id[4:].isdigit():
        num = int(order_id[4:])
        user_key = f"USR-50{(num % 3) + 1}"
        items_count = (num % 5) + 1
        items = []
        total = 0.0
        for i in range(1, items_count + 1):
            price = round(20.0 + (num * 3.7 + i * 5.5) % 100.0, 2)
            qty = (i % 3) + 1
            subtotal = round(price * qty, 2)
            total = round(total + subtotal, 2)
            items.append({
                "id": f"LI-{num}-{i}",
                "sku": f"SKU-GEN-{i:02d}",
                "productName": f"Generated Component {i}",
                "quantity": qty,
                "unitPrice": price,
                "subtotal": subtotal
            })
        status_opts = ["CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED"]
        return {
            "id": order_id,
            "status": status_opts[num % len(status_opts)],
            "totalAmount": total,
            "currency": "USD",
            "createdAt": "2026-10-10T12:00:00Z",
            "userId": user_key,
            "shippingAddress": f"{100 + num} Commerce Blvd, Suite {num}",
            "lineItems": items
        }
    return None


class GraphQLRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Silent standard logger to reduce console noise during high-throughput verification
        pass

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"status": "UP", "service": "mock-graphql-upstream"})
            return
        
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/graphql":
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)
        
        try:
            payload = json.loads(body_bytes.decode("utf-8"))
        except Exception as e:
            self._send_json(400, {"errors": [{"message": f"Malformed JSON: {str(e)}"}]})
            return

        query = payload.get("query", "")
        variables = payload.get("variables", {})
        
        # Check for simulated timeout/delay
        delay_header = self.headers.get("X-Mock-Delay")
        delay_sec = 0.0
        if delay_header:
            try:
                delay_sec = float(delay_header)
            except ValueError:
                pass
        
        order_id = variables.get("id") or variables.get("orderId")
        if not order_id:
            # Try regex parsing from query
            match = re.search(r'id:\s*"([^"]+)"', query)
            if match:
                order_id = match.group(1)

        # Timeout probe trigger
        if order_id == "ORD-TIMEOUT" or delay_sec > 0.0:
            sleep_time = delay_sec if delay_sec > 0.0 else 5.0
            time.sleep(sleep_time)

        # Partial error probe trigger
        partial_error_header = self.headers.get("X-Mock-Partial-Error")
        if order_id == "ORD-PARTIAL-ERROR" or partial_error_header == "true":
            response_payload = {
                "data": {
                    "order": {
                        "id": order_id if order_id else "ORD-PARTIAL-ERROR",
                        "status": "PARTIAL",
                        "totalAmount": 150.00,
                        "user": None,
                        "lineItems": None
                    }
                },
                "errors": [
                    {
                        "message": "User resolution failed: upstream profile service unreachable",
                        "locations": [{"line": 4, "column": 5}],
                        "path": ["order", "user"],
                        "extensions": {
                            "code": "DOWNSTREAM_SERVICE_UNAVAILABLE",
                            "service": "user-microservice",
                            "severity": "WARNING"
                        }
                    }
                ]
            }
            self._send_json(200, response_payload)
            return

        # Entity resolution
        order = get_or_generate_order(order_id) if order_id else None
        if not order:
            response_payload = {
                "data": {
                    "order": None
                },
                "errors": [
                    {
                        "message": f"Order with ID '{order_id}' not found",
                        "locations": [{"line": 2, "column": 3}],
                        "path": ["order"],
                        "extensions": {
                            "code": "ENTITY_NOT_FOUND"
                        }
                    }
                ]
            }
            self._send_json(200, response_payload)
            return

        # Resolve nested user
        user = USERS.get(order["userId"], {
            "id": order["userId"],
            "name": f"Customer {order['userId']}",
            "email": "customer@example.com",
            "membershipTier": "STANDARD"
        })

        # Resolve GraphQL response based on requested fields
        order_data: Dict[str, Any] = {
            "id": order["id"],
            "status": order["status"],
            "totalAmount": order["totalAmount"]
        }
        
        # User field resolution
        if "user" in query:
            user_data: Dict[str, Any] = {}
            if "name" in query:
                user_data["name"] = user["name"]
            if "email" in query:
                user_data["email"] = user["email"]
            if "membershipTier" in query:
                user_data["membershipTier"] = user["membershipTier"]
            order_data["user"] = user_data

        # Line items resolution
        if "lineItems" in query:
            items_list = []
            for item in order["lineItems"]:
                item_obj: Dict[str, Any] = {"id": item["id"]}
                if "sku" in query:
                    item_obj["sku"] = item["sku"]
                if "productName" in query:
                    item_obj["productName"] = item["productName"]
                if "quantity" in query:
                    item_obj["quantity"] = item["quantity"]
                if "unitPrice" in query:
                    item_obj["unitPrice"] = item["unitPrice"]
                if "subtotal" in query:
                    item_obj["subtotal"] = item["subtotal"]
                items_list.append(item_obj)
            order_data["lineItems"] = items_list

        response_payload = {
            "data": {
                "order": order_data
            }
        }

        self._send_json(200, response_payload)


def run_server(port: int = PORT) -> None:
    ThreadingHTTPServer.allow_reuse_address = True
    ThreadingHTTPServer.request_queue_size = 128
    server = ThreadingHTTPServer(("0.0.0.0", port), GraphQLRequestHandler)
    logger.info(f"Mock GraphQL Server running on http://127.0.0.1:{port}/graphql")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down mock GraphQL server...")
        server.server_close()


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    run_server(port_arg)
