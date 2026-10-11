#!/usr/bin/env python3
"""
mock_server.py
Lightweight FastAPI mock server providing dynamic realistic responses
matching OpenAPI 3.0 schema contracts with simulated network latency.
Supports RFC 7807 problem details error schemas.
"""

import argparse
import asyncio
import os
import random
import sys
import uvicorn
from datetime import datetime, timezone
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional


app = FastAPI(
    title="E-Commerce Mock API Server",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None
)

# Simulated latency range in seconds (50ms to 120ms)
MIN_LATENCY = float(os.getenv("MOCK_MIN_LATENCY", "0.050"))
MAX_LATENCY = float(os.getenv("MOCK_MAX_LATENCY", "0.120"))
MUTATE_CONTRACT = os.getenv("MOCK_MUTATE_CONTRACT", "false").lower() == "true"


async def simulate_network_latency():
    latency = random.uniform(MIN_LATENCY, MAX_LATENCY)
    await asyncio.sleep(latency)


def rfc7807_problem(status_code: int, title: str, detail: str, instance: str) -> JSONResponse:
    content = {
        "type": f"https://api.example.com/errors/{title.lower().replace(' ', '-')}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance
    }
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={"Content-Type": "application/problem+json"}
    )


# In-memory product catalog
CATALOG_DB = {
    "prod_001": {
        "id": "prod_001",
        "name": "Mechanical Gaming Keyboard",
        "price": 129.99,
        "stock": 42,
        "category": "Electronics",
        "sku": "KB-MECH-RGB-01",
        "currency": "USD"
    },
    "prod_002": {
        "id": "prod_002",
        "name": "Wireless Ergonomic Mouse",
        "price": 79.50,
        "stock": 18,
        "category": "Electronics",
        "sku": "MS-ERGO-WL-02",
        "currency": "USD"
    },
    "prod_003": {
        "id": "prod_003",
        "name": "Ultra-Wide Gaming Monitor 34-inch",
        "price": 499.00,
        "stock": 9,
        "category": "Electronics",
        "sku": "MN-34-UW-144",
        "currency": "USD"
    }
}


# Models
class LoginPayload(BaseModel):
    email: str
    password: str


class CartItemPayload(BaseModel):
    product_id: str
    quantity: int = Field(ge=1)


class ShippingAddressModel(BaseModel):
    street: str
    city: str
    postal_code: str
    country: str


class CheckoutPayload(BaseModel):
    cart_id: str
    shipping_address: ShippingAddressModel
    payment_method: str


@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "e-commerce-mock-api",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/api/v1/auth/login")
async def login(payload: LoginPayload, request: Request):
    await simulate_network_latency()

    if not payload.email or not payload.password:
        return rfc7807_problem(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Invalid Credentials",
            detail="Email and password cannot be empty.",
            instance="/api/v1/auth/login"
        )

    # Simulated authentication response
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c3JfODkyMWEiLCJyb2xlIjoiY3VzdG9tZXIifQ.mock_signature",
            "token_type": "Bearer",
            "expires_in": 3600,
            "user_id": "usr_8921a"
        },
        headers={"Content-Type": "application/json"}
    )


@app.get("/api/v1/products")
async def list_products(
    request: Request,
    limit: int = 10,
    category: Optional[str] = None
):
    await simulate_network_latency()

    # Check for contract mutation drill (Round 2)
    mutate = MUTATE_CONTRACT or (request.query_params.get("mutate") == "true")
    if mutate:
        # Schema drift: omit required 'price' field, convert integer 'stock' to string
        mutated_items = [
            {
                "id": "prod_001",
                "name": "Mechanical Gaming Keyboard",
                # 'price' omitted intentionally to violate contract
                "stock": "in_stock_plenty",  # string instead of integer
                "category": "Electronics"
            }
        ]
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "items": mutated_items,
                "total": "one",  # string instead of integer
                "page": 1
            },
            headers={"Content-Type": "application/json"}
        )

    items = list(CATALOG_DB.values())
    if category:
        items = [p for p in items if p["category"].lower() == category.lower()]
    items = items[:limit]

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "items": items,
            "total": len(items),
            "page": 1
        },
        headers={"Content-Type": "application/json"}
    )


@app.get("/api/v1/products/{product_id}")
async def get_product(product_id: str):
    await simulate_network_latency()

    if product_id not in CATALOG_DB:
        return rfc7807_problem(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Product Not Found",
            detail=f"Product with identifier '{product_id}' was not found in catalog.",
            instance=f"/api/v1/products/{product_id}"
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=CATALOG_DB[product_id],
        headers={"Content-Type": "application/json"}
    )


@app.post("/api/v1/cart/items")
async def add_cart_item(
    payload: CartItemPayload,
    authorization: Optional[str] = Header(None)
):
    await simulate_network_latency()

    if not authorization or not authorization.startswith("Bearer "):
        return rfc7807_problem(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail="Missing or malformed Authorization header.",
            instance="/api/v1/cart/items"
        )

    token = authorization.split("Bearer ", 1)[1].strip()
    if token == "expired_token":
        return rfc7807_problem(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Token Expired",
            detail="The provided authentication token has expired.",
            instance="/api/v1/cart/items"
        )

    if token == "forbidden_token" or token == "insufficient_scope":
        return rfc7807_problem(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail="The credentials supplied do not have sufficient permissions.",
            instance="/api/v1/cart/items"
        )

    product = CATALOG_DB.get(payload.product_id, CATALOG_DB["prod_001"])
    unit_price = product["price"]
    subtotal = round(unit_price * payload.quantity, 2)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "cart_id": "cart_9901",
            "items": [
                {
                    "product_id": product["id"],
                    "name": product["name"],
                    "unit_price": unit_price,
                    "quantity": payload.quantity,
                    "subtotal": subtotal
                }
            ],
            "total_items": payload.quantity,
            "subtotal": subtotal
        },
        headers={"Content-Type": "application/json"}
    )


@app.post("/api/v1/orders/checkout")
async def checkout(
    payload: CheckoutPayload,
    authorization: Optional[str] = Header(None)
):
    await simulate_network_latency()

    if not authorization or not authorization.startswith("Bearer "):
        return rfc7807_problem(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Unauthorized",
            detail="Authorization bearer token required for order checkout.",
            instance="/api/v1/orders/checkout"
        )

    token = authorization.split("Bearer ", 1)[1].strip()
    if token == "expired_token":
        return rfc7807_problem(
            status_code=status.HTTP_401_UNAUTHORIZED,
            title="Token Expired",
            detail="The provided authentication token has expired.",
            instance="/api/v1/orders/checkout"
        )

    if token == "forbidden_token" or token == "insufficient_scope":
        return rfc7807_problem(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Forbidden",
            detail="The credentials supplied do not have permission to execute checkout.",
            instance="/api/v1/orders/checkout"
        )

    order_id = "ord_77102"
    total_amount = 259.98
    created_at = datetime.now(timezone.utc).isoformat()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "order_id": order_id,
            "cart_id": payload.cart_id,
            "status": "confirmed",
            "total_amount": total_amount,
            "payment_status": "paid",
            "created_at": created_at
        },
        headers={"Content-Type": "application/json"}
    )


def run_server(host: str = "127.0.0.1", port: int = 8000):
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E-Commerce Mock API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host binding")
    parser.add_argument("--port", type=int, default=8000, help="Port binding")
    parser.add_argument("--mutate", action="store_true", help="Enable contract mutation drift")
    args = parser.parse_args()

    if args.mutate:
        MUTATE_CONTRACT = True

    run_server(host=args.host, port=args.port)
