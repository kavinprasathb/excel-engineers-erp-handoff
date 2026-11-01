"""Application errors.

Every one carries a stable machine-readable `code` alongside a message written
for the person on the shop floor, because these surface directly in the UI.
Never leak SQL or a traceback into `message`.
"""


class AppError(Exception):
    code = "error"
    status = 400

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFound(AppError):
    code = "not_found"
    status = 404


class Conflict(AppError):
    code = "conflict"
    status = 409


class StockError(AppError):
    code = "stock_error"
    status = 409


class InsufficientStock(StockError):
    code = "insufficient_stock"


class InsufficientReservation(StockError):
    code = "insufficient_reservation"


class ValidationFailed(AppError):
    code = "validation_error"
    status = 422


class QuotationLocked(AppError):
    """Only a pending, latest revision may change."""

    code = "quotation_locked"
    status = 409
