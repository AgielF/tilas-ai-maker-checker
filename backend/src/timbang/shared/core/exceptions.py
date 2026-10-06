"""Domain exceptions for Tilas.

These are raised in the service layer and mapped to HTTP status codes
in the router layer — never let stack traces leak to production responses
(docs/SECURITY.md).
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain exceptions."""


class NotFoundError(DomainError):
    """Raised when a requested resource does not exist."""


class ValidationError(DomainError):
    """Raised when business validation rules are violated."""


class UpstreamError(DomainError):
    """Raised when an upstream service (9Router, LLM) returns an error or times out."""
