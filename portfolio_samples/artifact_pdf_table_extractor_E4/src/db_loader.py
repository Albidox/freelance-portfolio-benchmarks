"""Compatibility wrapper for db_loader referencing db.py.
Strict zero em dash policy enforced.
"""
from src.db import DatabaseLoader, PostgresLoader

__all__ = ["DatabaseLoader", "PostgresLoader"]
