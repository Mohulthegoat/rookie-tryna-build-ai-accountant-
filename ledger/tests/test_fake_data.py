"""Tests for the fake data generator.

These tests protect the fixture itself. If the fake data stops containing the
messy cases, later phases would silently lose their test material.
"""

import csv
import json
from decimal import Decimal

import pytest

from ledgerai.fake_data import generate_all
from ledgerai.money import parse_amount, rupees_to_paise


@pytest.fixture()
def data_dir(tmp_path):
    generate_all(tmp_path, seed=42)
    return tmp_path


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_all_files_created(data_dir):
    for name in (
        "bank_statement_oct2025.csv",
        "bank_statement_oct2025.xlsx",
        "ledger_oct2025.csv",
        "purchase_invoices_oct2025.csv",
        "sales_invoices_oct2025.csv",
        "vendors_and_customers_oct2025.csv",
        "ground_truth.json",
    ):
        assert (data_dir / name).exists(), name


def test_bank_running_balance_is_exact(data_dir):
    rows = read_csv(data_dir / "bank_statement_oct2025.csv")
    opening = parse_amount(rows[0]["Balance"])
    balance = opening
    for row in rows[1:]:
        debit = parse_amount(row["Debit"]) or 0
        credit = parse_amount(row["Credit"]) or 0
        balance += credit - debit
        assert parse_amount(row["Balance"]) == balance


def test_bank_opening_and_closing_match_ground_truth(data_dir):
    truth = json.loads((data_dir / "ground_truth.json").read_text(encoding="utf-8"))
    rows = read_csv(data_dir / "bank_statement_oct2025.csv")
    assert parse_amount(rows[0]["Balance"]) == truth["opening_balance_paise"]
    assert parse_amount(rows[-1]["Balance"]) == truth["closing_balance_paise"]


def test_ledger_debits_equal_credits(data_dir):
    rows = read_csv(data_dir / "ledger_oct2025.csv")
    debits = sum(parse_amount(r["Debit"]) or 0 for r in rows)
    credits = sum(parse_amount(r["Credit"]) or 0 for r in rows)
    assert debits == credits
    assert debits > 0


def test_every_ledger_voucher_has_two_sides(data_dir):
    rows = read_csv(data_dir / "ledger_oct2025.csv")
    vouchers = {}
    for row in rows:
        vouchers.setdefault(row["VoucherNo"], []).append(row)
    for voucher_no, lines in vouchers.items():
        assert len(lines) == 2, voucher_no
        debit = sum(parse_amount(l["Debit"]) or 0 for l in lines)
        credit = sum(parse_amount(l["Credit"]) or 0 for l in lines)
        assert debit == credit, voucher_no


@pytest.mark.parametrize("filename", ["purchase_invoices_oct2025.csv", "sales_invoices_oct2025.csv"])
def test_invoice_totals_add_up(data_dir, filename):
    rows = read_csv(data_dir / filename)
    assert rows
    for row in rows:
        taxable = rupees_to_paise(row["TaxableValue"])
        cgst = rupees_to_paise(row["CGST"])
        sgst = rupees_to_paise(row["SGST"])
        igst = rupees_to_paise(row["IGST"])
        total = rupees_to_paise(row["InvoiceTotal"])
        assert taxable + cgst + sgst + igst == total, row["InvoiceNo"]
        # Intra-state means CGST+SGST only; inter-state means IGST only.
        assert (igst == 0) != (cgst + sgst == 0), row["InvoiceNo"]


def test_missing_invoice_case(data_dir):
    truth = json.loads((data_dir / "ground_truth.json").read_text(encoding="utf-8"))
    case = next(c for c in truth["cases"] if c["type"] == "missing_invoice")
    purchases = read_csv(data_dir / "purchase_invoices_oct2025.csv")
    assert all(inv["VendorName"] != case["vendor"] for inv in purchases)
    bank = read_csv(data_dir / "bank_statement_oct2025.csv")
    row = bank[case["bank_row"]]  # +1 because index 0 is the opening row
    assert parse_amount(row["Debit"]) == case["amount_paise"]
    assert case["vendor"] in row["Narration"]


def test_duplicate_payment_case(data_dir):
    truth = json.loads((data_dir / "ground_truth.json").read_text(encoding="utf-8"))
    case = next(c for c in truth["cases"] if c["type"] == "duplicate_payment")
    bank = read_csv(data_dir / "bank_statement_oct2025.csv")
    rows = [bank[i] for i in case["bank_rows"]]
    assert rows[0]["Date"] == rows[1]["Date"]
    assert parse_amount(rows[0]["Debit"]) == parse_amount(rows[1]["Debit"]) == case["amount_paise"]
    assert rows[0]["Narration"] != rows[1]["Narration"]  # different references


def test_split_payment_case(data_dir):
    truth = json.loads((data_dir / "ground_truth.json").read_text(encoding="utf-8"))
    case = next(c for c in truth["cases"] if c["type"] == "split_payment")
    bank = read_csv(data_dir / "bank_statement_oct2025.csv")
    parts = [parse_amount(bank[i]["Debit"]) for i in case["bank_rows"]]
    assert parts == case["parts_paise"]
    assert sum(parts) == case["invoice_total_paise"]
    purchases = read_csv(data_dir / "purchase_invoices_oct2025.csv")
    invoice = next(inv for inv in purchases if inv["InvoiceNo"] == case["invoice_no"])
    assert rupees_to_paise(invoice["InvoiceTotal"]) == case["invoice_total_paise"]


def test_small_difference_case(data_dir):
    truth = json.loads((data_dir / "ground_truth.json").read_text(encoding="utf-8"))
    case = next(c for c in truth["cases"] if c["type"] == "small_difference")
    bank = read_csv(data_dir / "bank_statement_oct2025.csv")
    assert parse_amount(bank[case["bank_row"]]["Credit"]) == case["bank_amount_paise"]

    ledger = read_csv(data_dir / "ledger_oct2025.csv")
    receipts = [
        r
        for r in ledger
        if r["VoucherNo"] == "RV-003" and parse_amount(r["Debit"])
    ]
    assert len(receipts) == 1
    assert parse_amount(receipts[0]["Debit"]) == case["ledger_amount_paise"]
    assert case["bank_amount_paise"] - case["ledger_amount_paise"] == 5


def test_uncleared_cheque_case(data_dir):
    truth = json.loads((data_dir / "ground_truth.json").read_text(encoding="utf-8"))
    case = next(c for c in truth["cases"] if c["type"] == "uncleared_cheque")
    ledger = read_csv(data_dir / "ledger_oct2025.csv")
    cheque_lines = [r for r in ledger if r["ChequeNo"] == case["cheque_no"]]
    assert cheque_lines
    assert sum(parse_amount(r["Credit"]) or 0 for r in cheque_lines) == case["amount_paise"]
    bank = read_csv(data_dir / "bank_statement_oct2025.csv")
    assert all(case["cheque_no"] not in r["ChequeNo"] for r in bank)


def test_unrecorded_bank_charge_case(data_dir):
    truth = json.loads((data_dir / "ground_truth.json").read_text(encoding="utf-8"))
    case = next(c for c in truth["cases"] if c["type"] == "unrecorded_bank_charge")
    bank = read_csv(data_dir / "bank_statement_oct2025.csv")
    row = bank[case["bank_row"]]
    assert parse_amount(row["Debit"]) == case["amount_paise"]
    assert "BANK CHARGES" in row["Narration"]
    ledger = read_csv(data_dir / "ledger_oct2025.csv")
    assert all("BANK CHARGES" not in r["Narration"].upper() for r in ledger)


def test_generator_is_reproducible(data_dir, tmp_path):
    second = tmp_path / "second"
    generate_all(second, seed=42)
    first_bank = (data_dir / "bank_statement_oct2025.csv").read_text(encoding="utf-8-sig")
    second_bank = (second / "bank_statement_oct2025.csv").read_text(encoding="utf-8-sig")
    assert first_bank == second_bank
