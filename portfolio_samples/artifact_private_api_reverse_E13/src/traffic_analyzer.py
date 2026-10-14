"""Network flow inspector decoding HTTP/2 frames and extracting hidden Authorization headers.
Strict zero em dash policy enforced.
"""
import re
import time
import json
from typing import Dict, Any, List, Optional, Tuple
from src.models import (
    TrafficIntercept,
    BearerToken,
    ExtractedEndpoint,
    RequestAuthType
)


class TrafficAnalyzer:
    """Inspects network flow captures and decodes HTTP/2 frames and headers."""

    AUTH_HEADER_CANDIDATES = [
        "authorization",
        "x-auth-token",
        "x-access-token",
        "x-user-token",
        "x-api-key",
        "x-session-token",
        "bearer",
    ]

    def __init__(self):
        self.intercepted_flows: List[TrafficIntercept] = []
        self.discovered_tokens: List[BearerToken] = []
        self.cataloged_endpoints: Dict[str, ExtractedEndpoint] = {}

    def decode_http2_headers_frame(
        self,
        flow_id: str,
        frame_headers: Dict[str, str],
        client_ip: str = "127.0.0.1",
        payload: Optional[str] = None
    ) -> TrafficIntercept:
        """Decode pseudo-headers and standard headers from an HTTP/2 HEADERS frame."""
        # Normalize keys to lowercase for inspection
        normalized = {k.lower(): v for k, v in frame_headers.items()}
        
        method = normalized.get(":method", "GET").upper()
        path = normalized.get(":path", "/")
        authority = normalized.get(":authority", normalized.get("host", "unknown-host"))
        scheme = normalized.get(":scheme", "https")
        content_type = normalized.get("content-type")

        intercept = TrafficIntercept(
            flow_id=flow_id,
            timestamp=time.time(),
            client_ip=client_ip,
            server_host=authority,
            method=method,
            path=path,
            http_version="HTTP/2.0",
            headers=frame_headers,
            payload=payload,
            content_type=content_type
        )
        self.intercepted_flows.append(intercept)
        
        # Automatically extract token and catalog endpoint
        self.extract_hidden_authorization(intercept)
        self.catalog_endpoint_from_flow(intercept)
        return intercept

    def extract_hidden_authorization(self, flow: TrafficIntercept) -> Optional[BearerToken]:
        """Inspect headers to extract hidden bearer tokens or API keys."""
        headers_lower = {k.lower(): v for k, v in flow.headers.items()}
        
        for cand in self.AUTH_HEADER_CANDIDATES:
            if cand in headers_lower:
                val = headers_lower[cand].strip()
                token_type = "Bearer"
                token_val = val
                if val.lower().startswith("bearer "):
                    token_val = val[7:].strip()
                elif val.lower().startswith("token "):
                    token_val = val[6:].strip()
                    token_type = "Token"
                elif cand == "x-api-key":
                    token_type = "ApiKey"

                # Parse JWT claims if 3-part token
                claims = {}
                parts = token_val.split(".")
                if len(parts) == 3:
                    try:
                        import base64
                        padded = parts[1] + "=" * (-len(parts[1]) % 4)
                        decoded = base64.urlsafe_b64decode(padded)
                        claims = json.loads(decoded)
                    except Exception:
                        claims = {"raw_payload_segment": parts[1]}

                b_token = BearerToken(
                    token_value=token_val,
                    token_type=token_type,
                    extracted_from_header=cand,
                    claims=claims
                )
                self.discovered_tokens.append(b_token)
                return b_token
        return None

    def catalog_endpoint_from_flow(self, flow: TrafficIntercept) -> ExtractedEndpoint:
        """Catalog an observed route with its auth requirements and query parameters."""
        path_clean = flow.path.split("?")[0]
        query_params = []
        if "?" in flow.path:
            query_str = flow.path.split("?")[1]
            for pair in query_str.split("&"):
                if "=" in pair:
                    query_params.append(pair.split("=")[0])

        auth_type = RequestAuthType.CUSTOM_HEADER
        for k in flow.headers:
            if k.lower() == "authorization":
                auth_type = RequestAuthType.BEARER_JWT
                break
            elif "signature" in k.lower() or "sig" in k.lower():
                auth_type = RequestAuthType.HMAC_SIGNATURE
                break
            elif k.lower() == "cookie":
                auth_type = RequestAuthType.SESSION_COOKIE
                break

        key = f"{flow.method}:{path_clean}"
        endpoint = ExtractedEndpoint(
            path=path_clean,
            method=flow.method,
            auth_type=auth_type,
            required_headers=list(flow.headers.keys()),
            query_params=query_params
        )
        self.cataloged_endpoints[key] = endpoint
        return endpoint
