"""Compatibility wrapper for data_cleaner referencing normalizer.
Strict zero em dash policy enforced.
"""
from src.normalizer import InvoiceDataCleaner, InvoiceNormalizer

__all__ = ["InvoiceDataCleaner", "InvoiceNormalizer"]
