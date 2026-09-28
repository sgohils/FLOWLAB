"""One way to raise an API error.

Every error the client receives has the same shape - ``{"message", "hint"}`` -
so the frontend never has to guess.  ``hint`` is the sentence that tells the
user what to *do* about it, which is different from explaining what went wrong.
"""

from __future__ import annotations

from fastapi import HTTPException


class ApiError(HTTPException):
    """An HTTP error with an optional actionable hint."""

    def __init__(self, status_code: int, message: str, hint: str | None = None) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.hint = hint


def api_error(status_code: int, message: str, hint: str | None = None) -> ApiError:
    return ApiError(status_code, message, hint)
