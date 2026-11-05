"""Shared payment exceptions.

Kept separate from ``service.py`` so the ledger and sale routes can raise the
same error type without circular imports.
"""


class PaymentError(RuntimeError):
    """A mobile-money reference could not be accepted for a sale.

    ``paid_amount``/``paid_currency`` are populated when the carrier reported a
    successful payment for a different amount, so the POS can let the operator
    correct the sale to the amount actually paid instead of sending a second
    prompt.
    """

    def __init__(self, message, status=402, paid_amount=None, paid_currency=""):
        super().__init__(message)
        self.status = status
        self.paid_amount = paid_amount
        self.paid_currency = str(paid_currency or "")
