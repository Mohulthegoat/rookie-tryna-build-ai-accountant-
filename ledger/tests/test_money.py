"""Tests for money.py - the foundation of every number in LedgerAI."""

from decimal import Decimal

import pytest

from ledgerai.money import (
    MoneyError,
    format_inr,
    paise_to_rupees_str,
    parse_amount,
    rupees_to_paise,
    sum_paise,
)


def test_int_is_whole_rupees():
    assert rupees_to_paise(1234) == 123400


def test_string_with_indian_commas():
    assert rupees_to_paise("1,00,000.50") == 10000050


def test_decimal_exact():
    assert rupees_to_paise(Decimal("15000.05")) == 1500005


def test_float_is_refused():
    with pytest.raises(MoneyError, match="Floats are not allowed"):
        rupees_to_paise(1234.50)


def test_parentheses_mean_negative():
    assert rupees_to_paise("(1,234.50)") == -123450


def test_currency_symbols_and_rs_prefix():
    assert rupees_to_paise("₹ 2,500") == 250000
    assert rupees_to_paise("Rs. 2,500.25") == 250025
    assert rupees_to_paise("INR 10") == 1000


def test_dr_cr_suffix_is_stripped():
    assert rupees_to_paise("500.00 Cr") == 50000


def test_five_paise_difference_is_exact():
    a = rupees_to_paise("15000.00")
    b = rupees_to_paise("15000.05")
    assert b - a == 5
    assert isinstance(b - a, int)


def test_rounding_extra_decimals_half_up():
    # 1.005 rupees = 100.5 paise -> 101 paise
    assert rupees_to_paise("1.005") == 101
    assert rupees_to_paise("1.004") == 100


def test_empty_and_garbage_are_rejected():
    with pytest.raises(MoneyError):
        rupees_to_paise("")
    with pytest.raises(MoneyError):
        rupees_to_paise("abc")
    with pytest.raises(MoneyError):
        rupees_to_paise("1.2.3")


def test_indian_grouping():
    assert paise_to_rupees_str(123450) == "1,234.50"
    assert paise_to_rupees_str(10000000) == "1,00,000.00"
    assert paise_to_rupees_str(12345678900) == "12,34,56,789.00"
    assert paise_to_rupees_str(-123450) == "-1,234.50"
    assert paise_to_rupees_str(5) == "0.05"


def test_format_inr():
    assert format_inr(10000000) == "₹1,00,000.00"
    assert format_inr(-150) == "-₹1.50"


def test_parse_amount_blank_values():
    for blank in ("", "  ", "-", "NA", "n/a", "NIL", None):
        assert parse_amount(blank) is None


def test_parse_amount_numbers():
    assert parse_amount("1,234.50") == 123450
    assert parse_amount(500) == 50000


def test_sum_paise_exact():
    assert sum_paise([1, 2, 3]) == 6
    assert sum_paise([]) == 0


def test_sum_paise_rejects_floats():
    with pytest.raises(MoneyError):
        sum_paise([1, 2.5])


def test_boolean_is_not_money():
    with pytest.raises(MoneyError):
        rupees_to_paise(True)


def test_paise_to_str_rejects_float():
    with pytest.raises(MoneyError):
        paise_to_rupees_str(1234.5)
