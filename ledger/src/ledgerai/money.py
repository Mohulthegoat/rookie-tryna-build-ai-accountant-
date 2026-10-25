"""Money handling for LedgerAI.

THE MOST IMPORTANT RULE IN THIS PROJECT
---------------------------------------
All money is stored and calculated as whole paise, using Python integers.

    1 rupee = 100 paise
    Rs 1,234.50 = 123450 paise

Why: floating point numbers (like 0.1 + 0.2 = 0.30000000000000004) silently
create accounting errors. Integers cannot do that. An LLM is never allowed to
do arithmetic here either.

This module is used by every other module. Keep it small and boring.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

__all__ = [
    "MoneyError",
    "rupees_to_paise",
    "paise_to_rupees_str",
    "format_inr",
    "parse_amount",
    "sum_paise",
]

# Characters people put in Indian money strings: currency signs, spaces,
# and the words "Rs", "INR". Commas are handled separately.
_CURRENCY_NOISE = re.compile(r"(?i)(?:₹|rs\.?|inr|rupees?)")
_PARENS = re.compile(r"^\s*\((.*)\)\s*$")
_DR_CR = re.compile(r"(?i)\s*(dr|cr)\.?\s*$")


class MoneyError(ValueError):
    """Raised when a value cannot be safely converted to paise."""


def rupees_to_paise(value: int | str | Decimal) -> int:
    """Convert a rupee amount to whole paise.

    Accepts:
      * int            -> treated as whole rupees (1234 -> 123400)
      * str/Decimal    -> parsed exactly, commas and currency symbols allowed
                          ("1,234.50", "₹ 1,234.5", "(50.25)" for negative)

    Refuses:
      * float          -> because floats are the bug we are avoiding
      * anything else  -> MoneyError with a clear message

    Rounding: if more than 2 decimal places are supplied, we round half-up to
    the nearest paise. Bank files sometimes contain extra decimals. The
    original value is preserved in the evidence trail by the ingestion layer.
    """
    if isinstance(value, bool):
        raise MoneyError("Boolean is not a money value")
    if isinstance(value, float):
        raise MoneyError(
            "Floats are not allowed for money. Pass int paise, int rupees, "
            "a string like '1234.50', or Decimal."
        )
    if isinstance(value, int):
        return value * 100

    if not isinstance(value, (str, Decimal)):
        raise MoneyError(f"Unsupported money type: {type(value).__name__}")

    text = str(value).strip()
    if not text:
        raise MoneyError("Empty money value")

    negative = False
    match = _PARENS.match(text)
    if match:
        negative = True
        text = match.group(1)

    text = _CURRENCY_NOISE.sub("", text)
    text = _DR_CR.sub("", text)
    text = text.replace(",", "").replace("\u00a0", "").replace(" ", "").strip()

    if text.startswith("-"):
        negative = not negative
        text = text[1:]
    elif text.startswith("+"):
        text = text[1:]

    if not text:
        raise MoneyError(f"No digits found in money value: {value!r}")

    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise MoneyError(f"Not a valid money value: {value!r}") from exc

    paise = (amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    result = int(paise)
    return -result if negative else result


def paise_to_rupees_str(paise: int) -> str:
    """Format paise as a plain rupee string using Indian digit grouping.

    123450      -> "1,234.50"
    10000000    -> "1,00,000.00"
    -123450     -> "-1,234.50"

    Indian grouping: the last 3 digits, then groups of 2
    (e.g. 12,34,56,789.00).
    """
    if isinstance(paise, bool) or not isinstance(paise, int):
        raise MoneyError("paise must be a whole-number int")

    sign = "-" if paise < 0 else ""
    paise = abs(paise)
    rupees, fraction = divmod(paise, 100)
    digits = str(rupees)

    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups) + "," + tail

    return f"{sign}{digits}.{fraction:02d}"


def format_inr(paise: int) -> str:
    """Format paise for display, with the rupee sign: '₹1,00,000.00'."""
    if isinstance(paise, bool) or not isinstance(paise, int):
        raise MoneyError("paise must be a whole-number paise int")
    if paise < 0:
        return "-₹" + paise_to_rupees_str(-paise)
    return "₹" + paise_to_rupees_str(paise)


def parse_amount(value: str) -> int | None:
    """Parse a messy spreadsheet cell into paise, or None for a blank cell.

    Handles blanks, '-', 'NA', 'NIL' (common in Tally and bank exports).
    Any other non-numeric text raises MoneyError so it is never silently
    treated as zero.
    """
    if value is None:
        return None
    if isinstance(value, (int, Decimal)):
        return rupees_to_paise(value)
    if not isinstance(value, str):
        raise MoneyError(f"Unsupported money type: {type(value).__name__}")

    text = value.strip()
    if text == "" or text in {"-", "--"} or text.upper() in {"NA", "N/A", "NIL"}:
        return None
    return rupees_to_paise(text)


def sum_paise(values) -> int:
    """Sum an iterable of paise integers, rejecting floats and bools."""
    total = 0
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise MoneyError("sum_paise only accepts whole-number paise ints")
        total += value
    return total
