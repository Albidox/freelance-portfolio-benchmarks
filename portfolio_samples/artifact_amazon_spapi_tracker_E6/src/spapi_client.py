"""Async SP-API Pricing and Competitive Summary API client."""

import asyncio
import random
import time
from typing import Dict, Any, List, Optional
from src.config import SPAPIConfig
from src.sp_client import AmazonSPAPIClient
from src.models import CompetitivePricingResponse, CompetitiveOffer, BuyBoxWinner


class AsyncSPAPIClient:
    """Asynchronous client for Amazon SP-API Pricing endpoints with jittered backoff."""

    def __init__(self, config: SPAPIConfig):
        self.config = config
        self.client_sync = AmazonSPAPIClient(config)
        self.total_requests: int = 0
        self.throttled_requests: int = 0

    async def get_competitive_pricing(
        self,
        asins: List[str],
        marketplace_id: Optional[str] = None,
        max_retries: int = 3,
    ) -> List[Dict[str, Any]]:
        """Fetch competitive pricing data for a batch of ASINs with retry backoff."""
        mp_id = marketplace_id or self.config.marketplace_id
        results: List[Dict[str, Any]] = []

        for asin in asins:
            self.total_requests += 1
            attempt = 0
            while attempt < max_retries:
                attempt += 1
                try:
                    # Compute SigV4 authorization headers
                    headers = self.client_sync.compute_sigv4_headers(
                        method="GET",
                        service="execute-api",
                        host=f"sellingpartnerapi-{self.config.aws_region[:2]}.amazon.com",
                        canonical_uri="/products/pricing/v0/competitivePrice",
                        query_params={"MarketplaceId": mp_id, "Asins": asin},
                        payload="",
                    )
                    # Simulated async fetch response container
                    payload = {
                        "asin": asin,
                        "marketplaceId": mp_id,
                        "status": "Success",
                        "headers": headers,
                        "offers": [],
                    }
                    results.append(payload)
                    break
                except Exception:
                    self.throttled_requests += 1
                    backoff = self.client_sync.calculate_leaky_bucket_backoff(attempt)
                    jitter = random.uniform(0.05, 0.25)
                    await asyncio.sleep(backoff + jitter)

        return results
