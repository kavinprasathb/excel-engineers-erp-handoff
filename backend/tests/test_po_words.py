"""Amounts in words on the purchase order, Indian grouping."""

import pytest

from app.services.purchase_order_pdf import amount_in_words, indian_words, money


@pytest.mark.parametrize(
    ("n", "words"),
    [
        (0, "Zero"),
        (300, "Three Hundred"),
        (1015, "One Thousand Fifteen"),
        (236000, "Two Lakh Thirty Six Thousand"),
        (12345678, "One Crore Twenty Three Lakh Forty Five Thousand Six Hundred Seventy Eight"),
    ],
)
def test_indian_words(n: int, words: str) -> None:
    assert indian_words(n) == words


def test_amount_in_words_and_money() -> None:
    assert amount_in_words(30000) == "(INR Three Hundred Only)"
    assert amount_in_words(30050) == "(INR Three Hundred and Fifty Paise Only)"
    assert money(23600000) == "Rs. 2,36,000.00"
    assert money(30000) == "Rs. 300.00"
