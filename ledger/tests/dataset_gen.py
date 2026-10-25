"""Deterministic synthetic datasets with known answers.

Used by the random-dataset and property tests. Everything is invented.
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

from ledgerai.money import paise_to_rupees_str

WORDS = [
    "ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT", "GOLF",
    "HOTEL", "INDIA", "JULIET", "KILO", "LIMA", "MIKE", "NOVEMBER",
    "OSCAR", "PAPA", "QUEBEC", "ROMEO", "SIERRA", "TANGO", "UNIFORM",
    "VICTOR", "WHISKEY", "XRAY", "YANKEE", "ZULU",
]
SUFFIXES = [
    "TRADERS", "TEXTILES", "ELECTRICALS", "LOGISTICS", "ENTERPRISES",
    "HARDWARE", "STEELS", "PLASTICS", "SERVICES", "DISTRIBUTORS",
    "PRINTERS", "FOODS", "CHEMICALS", "RETAIL", "CONSULTANTS",
]


def _party(i: int) -> str:
    return f"{WORDS[i % len(WORDS)]} {SUFFIXES[(i * 7) % len(SUFFIXES)]} {i:02d}"


def _rupees(paise: int) -> str:
    return paise_to_rupees_str(paise)


def _invoice(total_paise: int) -> dict:
    """Valid intra-state invoice: taxable + 9% CGST + 9% SGST = total."""
    taxable = round(total_paise * 100 / 118)
    gst = total_paise - taxable
    cgst = gst // 2
    sgst = gst - cgst
    return {
        "taxable": taxable,
        "cgst": cgst,
        "sgst": sgst,
        "igst": 0,
        "total": total_paise,
    }


def make_dataset(seed: int, out_dir: str | Path, *, indian_format: bool = False,
                 dash_dates: bool = False, shuffle: bool = False) -> dict:
    rng = random.Random(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    start = date(2026, 10, 1)
    bank_rows: list[dict] = []
    ledger_rows: list[dict] = []
    invoice_rows: list[dict] = []
    pidx = 0
    voucher = 500
    inv_seq = 0

    def dt(offset: int) -> str:
        d = start + timedelta(days=offset)
        return d.strftime("%d-%m-%Y" if dash_dates else "%d/%m/%Y")

    def pdate(offset: int) -> str:
        d = start + timedelta(days=offset)
        return d.strftime("%d-%m-%Y" if dash_dates else "%d/%m/%Y")

    def add_invoice(party: str, total: int, *, invoice_no: str | None = None,
                    override: dict | None = None) -> str:
        nonlocal inv_seq
        inv_seq += 1
        inv_no = invoice_no or f"INV/{inv_seq:04d}"
        vals = _invoice(total)
        if override:
            vals.update(override)
        invoice_rows.append({
            "Invoice No": inv_no,
            "Invoice Date": pdate(rng.randint(10, 27)),
            "Vendor": party,
            "GSTIN": f"29AAAC{inv_seq:04d}Z1Z{rng.randint(1, 9)}",
            "Taxable Value": _rupees(vals["taxable"]),
            "CGST": _rupees(vals["cgst"]),
            "SGST": _rupees(vals["sgst"]),
            "IGST": _rupees(vals["igst"]),
            "Total": _rupees(vals["total"]),
        })
        return inv_no

    def add_bank(offset: int, narration: str, *, debit: int = 0, credit: int = 0,
                 cheque: str = "") -> None:
        bank_rows.append({
            "Date": dt(offset),
            "Narration": narration,
            "Chq/Ref No": cheque,
            "Debit": _rupees(debit) if debit else "",
            "Credit": _rupees(credit) if credit else "",
            "Balance": "",
        })

    def add_ledger(offset: int, party: str, *, debit: int = 0, credit: int = 0,
                   narration: str = "", cheque: str = "") -> None:
        nonlocal voucher
        voucher += 1
        voucher_type = "Receipt" if debit else "Payment"
        note = narration or (
            f"Being receipt from {party.title()}" if debit
            else f"Being payment to {party.title()}"
        )
        ledger_rows.append({
            "Date": dt(offset),
            "Voucher No": f"{'RCT' if debit else 'PMT'}-{voucher}",
            "Voucher Type": voucher_type,
            "Particulars": party,
            "Narration": note + (f" Cheque {cheque}" if cheque else ""),
            "Debit": _rupees(debit) if debit else "",
            "Credit": _rupees(credit) if credit else "",
        })

    def new_party() -> str:
        nonlocal pidx
        p = _party(pidx)
        pidx += 1
        return p

    # Normal one-to-one pairs - target 24 total across variations
    n_normal = 24 - (seed % 6)  # varies but stays in range
    offset = 1
    for k in range(n_normal):
        party = new_party()
        amount = rng.randint(10_000, 400_000) * 100
        if k % 2 == 0:
            b_off = offset
            l_off = max(0, b_off - rng.randint(0, 2))
            add_bank(b_off, f"NEFT-HDFCN{9000000000 + seed * 137 + k}-{party}", debit=amount)
            add_ledger(l_off, party, credit=amount)
        else:
            b_off = offset
            l_off = max(0, b_off - rng.randint(0, 2))
            add_bank(b_off, f"UPI/{700000000000 + seed * 137 + k}/{party}/OKAXIS", credit=amount)
            add_ledger(l_off, party, debit=amount)
        offset += 1
        if offset > 10:
            offset = 1

    # 1. Small difference (Rs 5) - bank lower than ledger payment
    party = new_party()
    amount = rng.randint(20_000, 90_000) * 100
    add_bank(offset, f"NEFT-HDFCN{9100000000 + seed}-{party}", debit=amount)
    add_ledger(max(0, offset - 1), party, credit=amount + 500)
    offset += 1

    # 2. Split payment: one bank payment, two ledger payments
    party = new_party()
    part1 = rng.randint(10_000, 40_000) * 100
    part2 = rng.randint(10_000, 40_000) * 100
    add_bank(offset, f"NEFT-HDFCN{9200000000 + seed}-{party}", debit=part1 + part2)
    add_ledger(max(0, offset - 1), party, credit=part1)
    add_ledger(max(0, offset - 1), party, credit=part2)
    offset += 1

    # 3. Duplicate bank payment (same amount/reference twice) + one ledger entry
    party = new_party()
    amount = rng.randint(10_000, 60_000) * 100
    narr = f"UPI/{730000000000 + seed}/{party}/OKAXIS"
    add_bank(offset, narr, credit=amount)
    add_bank(offset, narr, credit=amount)
    add_ledger(max(0, offset - 1), party, debit=amount)
    add_invoice(party, amount)
    offset += 1

    # 4. Amount mismatch: bank 34,600 vs ledger 36,400
    party = new_party()
    bank_amt = rng.randint(20_000, 60_000) * 100
    diff = rng.randint(1001, 3000) * 100
    add_bank(offset, f"NEFT-HDFCN{9300000000 + seed}-{party}", debit=bank_amt)
    add_ledger(max(0, offset - 1), party, credit=bank_amt + diff)
    add_invoice(party, bank_amt)
    offset += 1

    # 5. Missing ledger entry, invoice exists
    party = new_party()
    amount = rng.randint(20_000, 90_000) * 100
    add_bank(offset, f"NEFT-HDFCN{9400000000 + seed}-{party}", debit=amount)
    add_invoice(party, amount)
    offset += 1

    # 6. Missing invoice (payment with no invoice, no ledger)
    party = new_party()
    amount = rng.randint(20_000, 90_000) * 100
    add_bank(offset, f"NEFT-HDFCN{9500000000 + seed}-{party}", debit=amount)
    offset += 1

    # 7. Uncleared cheque in ledger only
    party = new_party()
    amount = rng.randint(20_000, 90_000) * 100
    add_ledger(max(0, offset - 1), party, credit=amount, cheque=f"00{seed:04d}")

    # 8. Unrecorded bank charge and interest
    add_bank(offset, "BANK CHARGES OCT-2026 INCL GST", debit=rng.randint(100, 900) * 100)
    add_bank(offset, "INT.PD ON SB A/C TO 30-09-2026", credit=rng.randint(200, 2000) * 100)

    # Invoice problems: duplicate invoice number + GST mismatch
    dup_party = new_party()
    dup_total = rng.randint(50_000, 150_000) * 100
    add_invoice(dup_party, dup_total, invoice_no=f"DUP/{seed:04d}")
    add_invoice(dup_party, dup_total, invoice_no=f"DUP/{seed:04d}")
    gst_party = new_party()
    add_invoice(
        gst_party,
        4_660_000,
        invoice_no=f"GST/BAD{seed}",
        override={"taxable": 4_000_000, "cgst": 360_000, "sgst": 300_000, "igst": 0, "total": 4_660_000},
    )

    if shuffle:
        rng.shuffle(bank_rows)
        rng.shuffle(ledger_rows)

    # Opening balance and exact running balance
    opening = 500_000_00
    running = opening
    for row in bank_rows:
        debit = _parse(row["Debit"])
        credit = _parse(row["Credit"])
        running += credit - debit
        row["Balance"] = _rupees(running)
    bank_rows.insert(0, {
        "Date": dt(0), "Narration": "OPENING BALANCE", "Chq/Ref No": "",
        "Debit": "", "Credit": "", "Balance": _rupees(opening),
    })

    bank_csv = out / "bank.csv"
    ledger_csv = out / "ledger.csv"
    invoice_csv = out / "invoices.csv"
    _write(bank_csv, ["Date", "Narration", "Chq/Ref No", "Debit", "Credit", "Balance"], bank_rows)
    _write(ledger_csv, ["Date", "Voucher No", "Voucher Type", "Particulars", "Narration", "Debit", "Credit"], ledger_rows)
    _write(invoice_csv, ["Invoice No", "Invoice Date", "Vendor", "GSTIN", "Taxable Value", "CGST", "SGST", "IGST", "Total"], invoice_rows)

    return {
        "bank": bank_csv,
        "ledger": ledger_csv,
        "invoices": invoice_csv,
        "counts": {
            "bank_transactions": len(bank_rows) - 1,
            "ledger_entries": len(ledger_rows),
            "invoices": len(invoice_rows),
            "normal_matches": n_normal,
            "duplicate_linked": 1,
            "fuzzy_matches": 1,
            "split_matches": 1,
            "bank_matched": n_normal + 3,
            "ledger_matched": n_normal + 4,
            "unmatched_bank": 6,
            "unmatched_ledger": 2,
            "planted_problems": 8,
            "invoice_problems": 2,
        },
    }


def _parse(value: str) -> int:
    from ledgerai.money import parse_amount
    return parse_amount(value) or 0


def _write(path: Path, headers: list[str], rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
