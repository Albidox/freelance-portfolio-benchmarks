"""Unit tests for schema.py validating Pydantic v2 BookRecord data contract."""
import pytest
from pydantic import ValidationError

from schema import BookRecord


def test_valid_book_record_with_string_rating():
    record = BookRecord(
        title="Test Book",
        price_gbp=12.50,
        rating="Three",
        in_stock=True,
        detail_url="test-book_1/index.html",
        page_number=1,
    )
    assert record.title == "Test Book"
    assert record.price_gbp == 12.50
    assert record.rating == 3
    assert record.in_stock is True
    assert record.detail_url == "test-book_1/index.html"
    assert record.page_number == 1


def test_all_rating_word_mappings():
    mappings = {
        "One": 1,
        "two": 2,
        "THREE": 3,
        "Four": 4,
        "five": 5,
    }
    for word, expected_val in mappings.items():
        rec = BookRecord(
            title="Book",
            price_gbp=10.0,
            rating=word,
            in_stock=True,
            detail_url="/url",
            page_number=1,
        )
        assert rec.rating == expected_val


def test_empty_title_raises_validation_error():
    with pytest.raises(ValidationError):
        BookRecord(
            title="",
            price_gbp=12.50,
            rating=3,
            in_stock=True,
            detail_url="/x",
            page_number=1,
        )


def test_negative_price_raises_validation_error():
    with pytest.raises(ValidationError):
        BookRecord(
            title="Test",
            price_gbp=-1.0,
            rating=3,
            in_stock=True,
            detail_url="/x",
            page_number=1,
        )


def test_zero_price_raises_validation_error():
    with pytest.raises(ValidationError):
        BookRecord(
            title="Test",
            price_gbp=0.0,
            rating=3,
            in_stock=True,
            detail_url="/x",
            page_number=1,
        )


def test_invalid_rating_raises_validation_error():
    with pytest.raises(ValidationError):
        BookRecord(
            title="Test",
            price_gbp=12.50,
            rating="UnknownRating",
            in_stock=True,
            detail_url="/x",
            page_number=1,
        )
    with pytest.raises(ValidationError):
        BookRecord(
            title="Test",
            price_gbp=12.50,
            rating=6,
            in_stock=True,
            detail_url="/x",
            page_number=1,
        )
    with pytest.raises(ValidationError):
        BookRecord(
            title="Test",
            price_gbp=12.50,
            rating=0,
            in_stock=True,
            detail_url="/x",
            page_number=1,
        )
