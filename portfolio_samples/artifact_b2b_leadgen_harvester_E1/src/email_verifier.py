"""Email verifier module alias.
Strict zero em dash policy enforced.
"""
from src.validator import EmailVerifier, SMTPValidator

__all__ = ["EmailVerifier", "SMTPValidator"]
