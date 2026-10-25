"""Edge-case tests for ingestion and the reconciliation engine."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest
from openpyxl import Workbook

from ledgerai.engine import run_engine
from ledgerai.money import parse_amount


BANK_HEADERS = ["Date", "Narration", "Chq/Ref No", "Debit", "Credit", "Balance"]
LEDGER_HEADERS = ["Date", "Voucher No", "Voucher Type", "Particulars", "Narration", "Debit", "Credit"]
INVOICE_HEADERS = ["Invoice No", "Invoice Date", "Vendor", "GSTIN", "Taxable Value", "CGST", "SGST", "IGST", "Total"]


def write_csv(path: Path, headers, rows) -> Path:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    return path


def one_pair(tmp_path: Path, *, bank_date="02/10/2026", ledger_date="01/10/2026",
             bank_debit="1,23,456.78", ledger_credit="1,23,456.78",
             bank_narration="NEFT-HDFCN123-ALPHA TRADERS",
             duplicate=False) -> tuple[Path, Path, Path]:
    bank = [{
        "Date": "01/10/2026", "Narration": "OPENING BALANCE", "Chq/Ref No": "",
        "Debit": "", "Credit": "", "Balance": "5,00,000.00",
    }, {
        "Date": bank_date, "Narration": bank_narration, "Chq/Ref No": "",
        "Debit": bank_debit, "Credit": "", "Balance": "",
    }]
    if duplicate:
        bank.append(dict(bank[-1]))
    ledger = [{
        "Date": ledger_date, "Voucher No": "PMT-1", "Voucher Type": "Payment",
        "Particulars": "Alpha Traders", "Narration": "Being payment to Alpha Traders",
        "Debit": "", "Credit": ledger_credit,
    }]
    return (
        write_csv(tmp_path / "bank.csv", BANK_HEADERS, bank),
        write_csv(tmp_path / "ledger.csv", LEDGER_HEADERS, ledger),
        write_csv(tmp_path / "invoices.csv", INVOICE_HEADERS, []),
    )


def test_empty_files_do_not_crash(tmp_path):
    bank = tmp_path / "bank.csv"
    bank.write_text("", encoding="utf-8")
    ledger = tmp_path / "ledger.csv"
    ledger.write_text("", encoding="utf-8")
    invoices = tmp_path / "invoices.csv"
    invoices.write_text("", encoding="utf-8")
    result = run_engine(bank, ledger, invoices)
    assert result.counts["bank_transactions"] == 0
    assert result.counts["ledger_entries"] == 0
    assert result.counts["unmatched_bank"] == 0
    assert result.trial_balance.balanced
    assert result.verification.passed


def test_indian_number_format_and_dd_mm_yyyy(tmp_path):
    bank, ledger, invoices = one_pair(tmp_path)
    result = run_engine(bank, ledger, invoices)
    assert result.bank_lines[0].debit_paise == 12_345_678
    assert result.ledger_lines[0].signed_paise == -12_345_678
    assert result.bank_lines[0].date_iso == "2026-10-02"
    assert result.counts["normal_matches"] == 1


def test_dd_mm_yyyy_with_dashes(tmp_path):
    bank, ledger, invoices = one_pair(
        tmp_path, bank_date="02-10-2026", ledger_date="01-10-2026"
    )
    result = run_engine(bank, ledger, invoices)
    assert result.bank_lines[0].date_iso == "2026-10-02"
    assert result.counts["normal_matches"] == 1


def test_xlsx_bank_statement(tmp_path):
    _, ledger, invoices = one_pair(tmp_path)
    wb = Workbook()
    ws = wb.active
    ws.append(BANK_HEADERS)
    ws.append(["01/10/2026", "OPENING BALANCE", "", "", "", 500000])
    ws.append(["02/10/2026", "NEFT-HDFCN123-ALPHA TRADERS", "", 123456.78, "", 376543.22])
    bank = tmp_path / "bank.xlsx"
    wb.save(bank)
    result = run_engine(bank, ledger, invoices)
    assert result.counts["bank_transactions"] == 1
    assert result.bank_lines[0].debit_paise == 12_345_678
    assert result.counts["normal_matches"] == 1


def test_duplicate_bank_rows_match_once(tmp_path):
    bank, ledger, invoices = one_pair(tmp_path, duplicate=True)
    result = run_engine(bank, ledger, invoices)
    # Duplicate identical bank debits - only one matched, duplicate detected
    assert result.counts["bank_matched"] == 1
    assert len(result.unmatched_bank) == 1
    assert any(e["type"] == "duplicate_payment" for e in result.exceptions)
    assert result.counts["ledger_matched"] == 1


def test_amounts_are_integer_paise_everywhere(tmp_path):
    bank, ledger, invoices = one_pair(tmp_path)
    result = run_engine(bank, ledger, invoices)
    for line in result.bank_lines:
        assert isinstance(line.signed_paise, int)
        assert isinstance(line.debit_paise, int)
        assert isinstance(line.credit_paise, int)
    for journal in result.journals:
        for line in journal["lines"]:
            assert isinstance(line["debit_paise"], int)
            assert isinstance(line["credit_paise"], int)


def test_negative_parentheses_amount(tmp_path):
    assert parse_amount("(1,000.50)") == -100050
