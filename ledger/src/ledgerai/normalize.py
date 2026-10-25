"""Normalisation of bank statements, Tally bank-book exports and invoices.

Every amount becomes a signed integer in paise.

Sign convention (one convention for both sources):

    bank  : signed = credit - debit     (credit = money in, debit = money out)
    ledger: signed = debit  - credit    (Tally debit = money in, credit = out)

That makes a bank payment and the matching Tally payment both negative, so
matching is a simple signed-amount comparison. The OPENING BALANCE row is not
a transaction and is never normalised.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from ledgerai.money import parse_amount

__all__ = [
    "NormalizedLine",
    "normalize_bank",
    "normalize_ledger",
    "normalize_invoices",
    "extract_opening_balance",
    "days_diff",
]


@dataclass
class NormalizedLine:
    source: str
    row_index: int
    date_iso: str | None
    narration: str
    particulars: str
    cheque_no: str | None
    signed_paise: int
    party: str
    party_norm: str
    raw: dict
    line_id: str = ""
    debit_paise: int = 0
    credit_paise: int = 0
    voucher_type: str = ""

    @property
    def amount_paise(self) -> int:
        return abs(self.signed_paise)

    @property
    def is_money_out(self) -> bool:
        return self.signed_paise < 0


_NOISE = {
    "UPI", "NEFT", "IMPS", "RTGS", "ATM", "POS", "OKAXIS", "OKICICI",
    "HDFC", "ICICI", "AXIS", "SBIN", "SBI", "KOTAK", "YESB", "IDFB",
    "BANK", "TRANSFER", "PAYMENT", "RECEIPT", "REF", "REFNO", "TXN",
    "TRANSACTION", "BY", "TO", "FROM", "DR", "CR",
}

_SUFFIX_WORDS = {"PVT", "LTD", "LIMITED", "CO", "COMPANY", "AND", "THE", "LLP", "INC"}


def _parse_date(value) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text:
        return None
    # ISO datetime from Excel
    text = text.split("T")[0]
    for fmt in (
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%y",
        "%d-%m-%y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y",
        "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
    ):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _norm_party(value) -> str:
    if not value:
        return ""
    text = str(value).upper()
    # keep letters and digits only; punctuation and reference separators vanish
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    words = [w for w in text.split(" ") if w and w not in _SUFFIX_WORDS]
    return " ".join(words)


def _clean_candidate(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip(" -/")
    return text.strip()


def _looks_like_party(segment: str) -> bool:
    letters = re.sub(r"[^A-Za-z]", "", segment)
    if len(letters) < 3:
        return False
    cleaned = re.sub(r"[^A-Z ]", " ", segment.upper()).strip()
    if not cleaned:
        return False
    tokens = [t for t in cleaned.split() if t]
    if not tokens:
        return False
    if all(t in _NOISE for t in tokens):
        return False
    return True


def _extract_party(narration) -> str:
    """Best-effort party name from a bank narration or ledger particular.

    Handles the common Indian bank shapes generically:
        UPI/<ref>/<PARTY>/OKAXIS
        IMPS/<ref>/<PARTY>
        NEFT-<ref>-<PARTY>
    without a hard-coded list of company names.
    """
    if not narration:
        return ""
    text = str(narration).strip()
    upper = text.upper()

    party = ""
    if upper.startswith("UPI/") or upper.startswith("UPI-"):
        parts = re.split(r"[/]", upper)
        candidates = [p for p in parts[1:] if _looks_like_party(p) and p.strip() not in _NOISE]
        if candidates:
            party = candidates[-1]
    elif upper.startswith("IMPS/") or upper.startswith("IMPS-"):
        parts = re.split(r"[/]", upper, maxsplit=2)
        if len(parts) >= 3:
            party = parts[2]
    elif upper.startswith("NEFT-") or upper.startswith("NEFT/") or upper.startswith("RTGS-") or upper.startswith("RTGS/"):
        match = re.match(r"^(?:NEFT|RTGS)[-/][A-Z0-9]+[-/](.+)$", upper)
        if match:
            party = match.group(1)
    elif upper.startswith("ATM/") or upper.startswith("POS/"):
        party = upper

    if not party:
        party = upper

    # Drop the trailing bank label that some UPI narrations carry.
    party = re.sub(r"\b(?:OKAXIS|OKICICI|OKHDFCBANK|OKSBI)\b", " ", party)
    return _clean_candidate(party)


def _find_header(headers: list[str], *names: str) -> str | None:
    lowered = {str(h).strip().lower(): h for h in headers}
    for name in names:
        if name in lowered:
            return lowered[name]
    for name in names:
        for low, original in lowered.items():
            if name in low:
                return original
    return None


def extract_opening_balance(rows: list[dict], headers: list[str]) -> int | None:
    """Return the opening balance in paise, if the statement has one."""
    balance_col = _find_header(headers, "balance")
    if not balance_col:
        return None
    for row in rows:
        narration = str(row.get(_find_header(headers, "narration", "description") or "", "") or "")
        if "OPENING" in narration.upper() and "BALANCE" in narration.upper():
            try:
                return parse_amount(row.get(balance_col))
            except Exception:
                return None
    return None


def normalize_bank(rows: list[dict], headers: list[str]) -> list[NormalizedLine]:
    date_col = _find_header(headers, "date", "txn date", "transaction date", "value date")
    narr_col = _find_header(headers, "narration", "description", "particulars", "remarks", "details")
    chq_col = _find_header(headers, "chq/ref no", "cheque no", "cheque", "chq", "ref no", "reference")
    debit_col = _find_header(headers, "debit", "withdrawal", "dr")
    credit_col = _find_header(headers, "credit", "deposit", "cr")
    amount_col = _find_header(headers, "amount")
    drcr_col = _find_header(headers, "dr/cr", "dr cr", "type")

    out: list[NormalizedLine] = []
    for index, row in enumerate(rows, start=1):
        narration = str(row.get(narr_col, "") if narr_col else "" or "")
        if "OPENING" in narration.upper() and "BALANCE" in narration.upper():
            continue

        debit = parse_amount(row.get(debit_col)) if debit_col else None
        credit = parse_amount(row.get(credit_col)) if credit_col else None
        debit = debit or 0
        credit = credit or 0

        if amount_col and not (debit or credit):
            amount = parse_amount(row.get(amount_col)) or 0
            direction = str(row.get(drcr_col, "") if drcr_col else "").upper()
            if "DR" in direction:
                debit = abs(amount)
            elif "CR" in direction:
                credit = abs(amount)
            elif amount < 0:
                debit = abs(amount)
            else:
                credit = abs(amount)

        signed = credit - debit
        if signed == 0 and not (debit or credit):
            # Opening/blank rows have no transaction amount; ignore them.
            continue

        party = _extract_party(narration)
        cheque = str(row.get(chq_col, "") if chq_col else "").strip() or None
        out.append(NormalizedLine(
            source="bank",
            row_index=index,
            date_iso=_parse_date(row.get(date_col) if date_col else None),
            narration=narration,
            particulars="",
            cheque_no=cheque,
            signed_paise=signed,
            party=party,
            party_norm=_norm_party(party),
            raw=row,
            line_id=f"BL{index}",
            debit_paise=debit,
            credit_paise=credit,
        ))
    return out


def normalize_ledger(rows: list[dict], headers: list[str]) -> list[NormalizedLine]:
    date_col = _find_header(headers, "date")
    narr_col = _find_header(headers, "narration", "description")
    part_col = _find_header(headers, "particulars", "party", "ledger", "account")
    vno_col = _find_header(headers, "voucher no", "voucher", "vch no")
    vtype_col = _find_header(headers, "voucher type", "vch type", "type")
    debit_col = _find_header(headers, "debit", "dr")
    credit_col = _find_header(headers, "credit", "cr")
    chq_col = _find_header(headers, "cheque no", "cheque", "chq")

    out: list[NormalizedLine] = []
    for index, row in enumerate(rows, start=1):
        narration = str(row.get(narr_col, "") if narr_col else "" or "")
        particulars = str(row.get(part_col, "") if part_col else "" or "")
        debit = parse_amount(row.get(debit_col)) if debit_col else None
        credit = parse_amount(row.get(credit_col)) if credit_col else None
        debit = debit or 0
        credit = credit or 0
        if not (debit or credit):
            continue

        signed = debit - credit
        party = _extract_party(particulars) or _extract_party(narration)
        voucher_type = str(row.get(vtype_col, "") if vtype_col else "").strip()
        cheque = str(row.get(chq_col, "") if chq_col else "").strip() or None
        if not cheque:
            match = re.search(r"Cheque\s*([0-9]{3,})", narration, re.IGNORECASE)
            if match:
                cheque = match.group(1)

        out.append(NormalizedLine(
            source="ledger",
            row_index=index,
            date_iso=_parse_date(row.get(date_col) if date_col else None),
            narration=narration,
            particulars=particulars,
            cheque_no=cheque,
            signed_paise=signed,
            party=party,
            party_norm=_norm_party(party),
            raw=row,
            line_id=f"LE{index}",
            debit_paise=debit,
            credit_paise=credit,
            voucher_type=voucher_type,
        ))
    return out


def normalize_invoices(rows: list[dict], headers: list[str]) -> list[dict]:
    no_col = _find_header(headers, "invoice no", "invoice number", "bill no", "voucher no")
    date_col = _find_header(headers, "invoice date", "date")
    party_col = _find_header(headers, "vendor", "party", "supplier", "customer", "name")
    gstin_col = _find_header(headers, "gstin", "gst no")
    taxable_col = _find_header(headers, "taxable value", "taxable", "net amount")
    cgst_col = _find_header(headers, "cgst")
    sgst_col = _find_header(headers, "sgst")
    igst_col = _find_header(headers, "igst")
    total_col = _find_header(headers, "total", "invoice total", "gross")

    def amount(col, row):
        if not col:
            return 0
        try:
            return parse_amount(row.get(col)) or 0
        except Exception:
            return 0

    out = []
    for index, row in enumerate(rows, start=1):
        invoice_no = str(row.get(no_col, "") if no_col else "" or "").strip()
        if not invoice_no:
            continue
        party = str(row.get(party_col, "") if party_col else "" or "").strip()
        out.append({
            "id": f"INV{index}",
            "row_index": index,
            "invoice_no": invoice_no,
            "date_iso": _parse_date(row.get(date_col) if date_col else None),
            "party": party,
            "party_norm": _norm_party(party),
            "gstin": str(row.get(gstin_col, "") if gstin_col else "" or "").strip(),
            "taxable_paise": amount(taxable_col, row),
            "cgst_paise": amount(cgst_col, row),
            "sgst_paise": amount(sgst_col, row),
            "igst_paise": amount(igst_col, row),
            "total_paise": amount(total_col, row),
            "raw": row,
        })
    return out


def days_diff(date_a: str | None, date_b: str | None) -> int:
    if not date_a or not date_b:
        return 999
    try:
        a = datetime.strptime(date_a, "%Y-%m-%d")
        b = datetime.strptime(date_b, "%Y-%m-%d")
        return abs((a - b).days)
    except Exception:
        return 999
