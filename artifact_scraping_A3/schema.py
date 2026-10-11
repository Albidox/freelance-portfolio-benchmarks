"""Pydantic v2 schema for validated quote records."""
from typing import List
from pydantic import BaseModel, Field, field_validator


class QuoteRecord(BaseModel):
    text: str = Field(..., min_length=1, description="The quote text")
    author: str = Field(..., min_length=1, description="Author name")
    author_url: str = Field(default="", description="Relative URL to author detail page")
    tags: List[str] = Field(default_factory=list, description="List of tags")
    page_number: int = Field(..., ge=1, description="Source page number")

    @field_validator("text", mode="before")
    @classmethod
    def clean_text(cls, v):
        if isinstance(v, str):
            # Remove surrounding unicode quotes if present
            v = v.strip().strip("\u201c\u201d\u00ab\u00bb\"'")
            return v.strip()
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v):
        if isinstance(v, str):
            return [t.strip() for t in v.split(",") if t.strip()]
        return v
