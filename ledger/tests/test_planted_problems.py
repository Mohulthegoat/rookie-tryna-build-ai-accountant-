"""Tests for planted problems in test data."""
import csv
from pathlib import Path
from ledgerai.money import parse_amount
from ledgerai.ingest import read_csv_raw, detect_bank_format, ColumnMapping, apply_mapping

TEST_DIR = Path('data/test')

def test_bank_has_duplicate_amazon():
    rows, _ = read_csv_raw(TEST_DIR / 'bank_statement_oct2026.csv')
    narrations = [r['Narration'] for r in rows]
    amazon = [n for n in narrations if 'AMAZON' in n.upper()]
    assert len(amazon) == 2

def test_invoice_has_duplicate_kh3340():
    rows, _ = read_csv_raw(TEST_DIR / 'invoices_oct2026.csv')
    invs = [r['Invoice No'] for r in rows]
    kh = [i for i in invs if i == 'KH/3340']
    assert len(kh) == 2

def test_bank_has_charges():
    rows, _ = read_csv_raw(TEST_DIR / 'bank_statement_oct2026.csv')
    charges = [r for r in rows if 'BANK CHARGES' in r['Narration'].upper()]
    assert len(charges) >= 1

def test_bank_has_interest():
    rows, _ = read_csv_raw(TEST_DIR / 'bank_statement_oct2026.csv')
    interest = [r for r in rows if 'INT.PD' in r['Narration'].upper()]
    assert len(interest) >= 1

def test_bhatt_split_invoices():
    rows, _ = read_csv_raw(TEST_DIR / 'invoices_oct2026.csv')
    bhatt = [r for r in rows if 'BHATT' in r['Vendor'].upper()]
    assert len(bhatt) == 2
    totals = [parse_amount(r['Total']) for r in bhatt]
    assert sum(totals) == 12000000  # 120000

def test_lakshmi_small_difference():
    bank_rows, _ = read_csv_raw(TEST_DIR / 'bank_statement_oct2026.csv')
    ledger_rows, _ = read_csv_raw(TEST_DIR / 'ledger_tally_export_oct2026.csv')
    # Bank shows 72495, ledger shows 72500
    bank_lakshmi = [r for r in bank_rows if 'LAKSHMI' in r['Narration'].upper()]
    ledger_lakshmi = [r for r in ledger_rows if 'LAKSHMI' in r['Particulars'].upper()]
    assert bank_lakshmi
    assert ledger_lakshmi
    assert parse_amount(bank_lakshmi[0]['Debit']) == 7249500
    assert parse_amount(ledger_lakshmi[0]['Credit']) == 7250000
    assert abs(parse_amount(bank_lakshmi[0]['Debit']) - parse_amount(ledger_lakshmi[0]['Credit'])) == 500
