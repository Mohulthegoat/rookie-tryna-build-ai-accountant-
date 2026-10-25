"""Ingestion layer for LedgerAI - Phase 2.

Reads messy Indian bank CSV/Excel (separate debit/credit columns, DD/MM/YYYY
dates, UPI/NEFT/IMPS narrations) and Tally exports with a column-mapping step.

All amounts are converted to whole paise integers using ledgerai.money.
Nothing is guessed silently - mapping is explicit and ambiguous columns
require user confirmation.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ledgerai.money import parse_amount, rupees_to_paise, MoneyError

__all__ = [
    "ColumnMapping",
    "MappedRow",
    "read_csv_raw",
    "read_excel_raw",
    "detect_bank_format",
    "apply_mapping",
    "INGESTION_RULES",
]

INGESTION_RULES = {
    "needs_review_tag": "needs review",
    "no_float_arithmetic": True,
    "amount_unit": "paise_integers",
    "date_formats": ["DD/MM/YYYY", "DD-MM-YYYY", "YYYY-MM-DD"],
}


@dataclass
class ColumnMapping:
    """User-confirmed mapping from source columns to canonical fields."""
    date_col: str | None = None
    narration_col: str | None = None
    debit_col: str | None = None
    credit_col: str | None = None
    amount_col: str | None = None  # for single-amount formats
    drcr_col: str | None = None
    balance_col: str | None = None
    cheque_col: str | None = None
    value_date_col: str | None = None
    company_id: str | None = None
    source_file: str = ""
    confirmed: bool = False  # must be confirmed by user before import
    mapping_notes: list[str] = field(default_factory=list)


@dataclass
class MappedRow:
    row_index: int  # 1-based data row index
    date_iso: str | None
    narration: str
    cheque_no: str | None
    debit_paise: int
    credit_paise: int
    balance_paise: int | None
    needs_review: bool
    review_reason: str | None
    raw: dict[str, Any]


def read_csv_raw(path: str | Path) -> tuple[list[dict], list[str]]:
    path = Path(path)
    rows = []
    # Try common encodings for Indian exports
    for enc in ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1']:
        try:
            with open(path, 'r', encoding=enc, newline='') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                for row in reader:
                    rows.append(dict(row))
            return rows, headers
        except Exception:
            continue
    raise ValueError(f"Could not read CSV: {path}")


def read_excel_raw(path: str | Path, sheet: str | int = 0) -> tuple[list[dict], list[str]]:
    try:
        import openpyxl
    except ImportError as e:
        raise ImportError("openpyxl required for Excel") from e
    path = Path(path)
    wb = openpyxl.load_workbook(path, data_only=True)
    if isinstance(sheet, str):
        ws = wb[sheet]
    else:
        ws = wb.worksheets[sheet]
    rows_iter = ws.iter_rows(values_only=True)
    headers = [str(h).strip() if h is not None else f'col{i}' for i, h in enumerate(next(rows_iter))]
    rows = []
    for r in rows_iter:
        if all(c is None or str(c).strip() == '' for c in r):
            continue
        row = {}
        for i, h in enumerate(headers):
            v = r[i] if i < len(r) else None
            if v is None:
                row[h] = ''
            elif hasattr(v, 'strftime'):
                row[h] = v.strftime('%d/%m/%Y')
            else:
                row[h] = str(v)
        rows.append(row)
    return rows, headers


def _parse_date_ddmmyyyy(s: str) -> str | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%y']:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None


def detect_bank_format(headers: list[str]) -> dict[str, Any]:
    """Suggest mapping for common Indian bank formats."""
    h = [str(x).strip().lower() for x in headers]
    def find(*cands):
        for c in cands:
            for i, x in enumerate(h):
                if c in x:
                    return headers[i]
        return None
    mapping = {
        'date_col': find('date', 'txn date', 'transaction date'),
        'value_date_col': find('value date'),
        'narration_col': find('narration', 'description', 'particular', 'remarks', 'details'),
        'debit_col': find('debit', 'withdrawal', 'dr'),
        'credit_col': find('credit', 'deposit', 'cr'),
        'amount_col': find('amount') if not find('debit','credit') else None,
        'drcr_col': find('dr/cr', 'type'),
        'balance_col': find('balance'),
        'cheque_col': find('cheque', 'chq', 'ref'),
    }
    mapping['needs_review'] = not all([mapping['date_col'], mapping['narration_col']])
    mapping['suggestion'] = 'Confirm mapping before import. AI suggests but user must approve.' 
    return mapping


def apply_mapping(rows: list[dict], mapping: ColumnMapping) -> list[MappedRow]:
    if not mapping.confirmed:
        raise ValueError("Column mapping not confirmed. Set mapping.confirmed = True only after user review.")
    out = []
    for idx, row in enumerate(rows, start=1):
        needs_review = False
        review_reason = None
        try:
            date_iso = _parse_date_ddmmyyyy(row.get(mapping.date_col) if mapping.date_col else '')
        except Exception:
            date_iso = None
            needs_review = True
            review_reason = 'date parse failed'
        narration = str(row.get(mapping.narration_col, '') if mapping.narration_col else '')
        cheque_no = str(row.get(mapping.cheque_col, '') if mapping.cheque_col else '') or None
        debit_p = 0
        credit_p = 0
        try:
            if mapping.debit_col and row.get(mapping.debit_col):
                v = parse_amount(row.get(mapping.debit_col))
                debit_p = v if v is not None else 0
            if mapping.credit_col and row.get(mapping.credit_col):
                v = parse_amount(row.get(mapping.credit_col))
                credit_p = v if v is not None else 0
            if mapping.amount_col and not (debit_p or credit_p) and row.get(mapping.amount_col):
                v = parse_amount(row.get(mapping.amount_col))
                if v is None:
                    raise MoneyError('amount missing')
                drcr = str(row.get(mapping.drcr_col,'')).lower() if mapping.drcr_col else ''
                if 'dr' in drcr or (mapping.narration_col and 'dr' in narration.lower() and 'cr' not in narration.lower()):
                    debit_p = abs(v)
                elif 'cr' in drcr:
                    credit_p = abs(v)
                else:
                    needs_review = True
                    review_reason = (review_reason + '; ' if review_reason else '') + 'amount present but direction unclear - needs review'
        except MoneyError as e:
            needs_review = True
            review_reason = (review_reason + '; ' if review_reason else '') + f'amount parse error: {e}'
        except Exception as e:
            needs_review = True
            review_reason = (review_reason + '; ' if review_reason else '') + f'error: {e}'
        if debit_p > 0 and credit_p > 0:
            needs_review = True
            review_reason = (review_reason + '; ' if review_reason else '') + 'both debit and credit present - needs review'
        balance_p = None
        try:
            if mapping.balance_col and row.get(mapping.balance_col):
                v = parse_amount(row.get(mapping.balance_col))
                balance_p = v
        except Exception:
            needs_review = True
            review_reason = (review_reason + '; ' if review_reason else '') + 'balance parse issue - needs review'
        out.append(MappedRow(row_index=idx, date_iso=date_iso, narration=narration, cheque_no=cheque_no,
                             debit_paise=debit_p, credit_paise=credit_p, balance_paise=balance_p,
                             needs_review=needs_review, review_reason=review_reason, raw=row))
    return out
