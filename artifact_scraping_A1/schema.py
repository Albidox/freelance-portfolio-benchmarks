"""Pydantic v2 schema for validated book records."""
from pydantic import BaseModel, Field, field_validator


class BookRecord(BaseModel):
    title: str = Field(..., min_length=1, description="Book title")
    price_gbp: float = Field(..., gt=0, description="Price in GBP")
    rating: int = Field(..., ge=1, le=5, description="Star rating 1-5")
    in_stock: bool = Field(..., description="Availability status")
    detail_url: str = Field(..., min_length=1, description="Relative URL to detail page")
    page_number: int = Field(..., ge=1, description="Source page number")

    @field_validator("rating", mode="before")
    @classmethod
    def parse_rating(cls, v):
        if isinstance(v, str):
            mapping = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
            return mapping.get(v.lower(), 0)
        return v
