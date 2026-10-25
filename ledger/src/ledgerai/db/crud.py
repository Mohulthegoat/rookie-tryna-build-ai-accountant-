"""Database CRUD helpers for LedgerAI.

All money comes in and goes out as whole paise integers. All writes enforce
per-company isolation. Evidence is required on journal entries, journal lines
and matches.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from ledgerai.money import MoneyError

__all__ = [
    "new_id",
    "create_company",
    "get_company",
    "create_account",
    "create_journal_entry",
    "add_journal_line",
    "post_journal",
    "get_journal_balance_paise",
    "create_bank_line",
    "create_invoice",
    "create_match",
    "create_exception",
]


def new_id() -> str:
    return str(uuid.uuid4())


def _check_paise(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MoneyError(f"{name} must be a whole-number paise int")
    return value


def create_company(conn, company_id: str, name: str, **kwargs) -> dict:
    settings = json.dumps(kwargs.pop("settings", {}))
    cur = conn.execute(
        """INSERT INTO companies (id, name, gstin, pan, state_code, currency, settings_json)
           VALUES (?,?,?,?,?,?,?)""",
        (company_id, name, kwargs.get("gstin"), kwargs.get("pan"), kwargs.get("state_code"), kwargs.get("currency", "INR"), settings),
    )
    conn.commit()
    return get_company(conn, company_id)


def get_company(conn, company_id: str):
    cur = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def create_account(conn, company_id: str, code: str, name: str, account_type: str, **kwargs) -> dict:
    if account_type not in ('ASSET', 'LIABILITY', 'EQUITY', 'INCOME', 'EXPENSE'):
        raise ValueError("account_type must be ASSET/LIABILITY/EQUITY/INCOME/EXPENSE")
    account_id = kwargs.pop("account_id", new_id())
    cur = conn.execute(
        """INSERT INTO chart_of_accounts (id, company_id, code, name, account_type, parent_id, is_system, is_active)
           VALUES (?,?,?,?,?,?,?,?)""",
        (account_id, company_id, code, name, account_type, kwargs.get("parent_id"), 1 if kwargs.get("is_system") else 0, 1 if kwargs.get("is_active", True) else 0),
    )
    conn.commit()
    cur = conn.execute("SELECT * FROM chart_of_accounts WHERE id = ?", (account_id,))
    return dict(cur.fetchone())


def create_journal_entry(conn, company_id: str, entry_date: str, narration: str | None = None, **kwargs) -> dict:
    entry_id = kwargs.pop("entry_id", new_id())
    status = kwargs.pop("status", "proposed")
    assumed = 1 if kwargs.pop("assumed", True) else 0
    cur = conn.execute(
        """INSERT INTO journal_entries
           (id, company_id, entry_date, voucher_no, source_module, narration, status,
            source_file, source_row, rule_used, confidence, reason, assumed)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            entry_id,
            company_id,
            entry_date,
            kwargs.get("voucher_no"),
            kwargs.get("source_module"),
            narration,
            status,
            kwargs.get("source_file"),
            kwargs.get("source_row"),
            kwargs.get("rule_used"),
            kwargs.get("confidence"),
            kwargs.get("reason"),
            assumed,
        ),
    )
    conn.commit()
    cur = conn.execute("SELECT * FROM journal_entries WHERE id = ?", (entry_id,))
    return dict(cur.fetchone())


def add_journal_line(conn, entry_id: str, account_id: str, debit_paise: int = 0, credit_paise: int = 0, narration: str | None = None, **kwargs) -> dict:
    debit_paise = _check_paise(debit_paise, "debit_paise")
    credit_paise = _check_paise(credit_paise, "credit_paise")
    if debit_paise > 0 and credit_paise > 0:
        raise ValueError("A journal line cannot have both debit and credit")
    if debit_paise == 0 and credit_paise == 0:
        raise ValueError("A journal line must have debit or credit")
    cur = conn.execute("SELECT company_id FROM journal_entries WHERE id = ?", (entry_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError("journal entry not found")
    company_id = row["company_id"]
    line_id = kwargs.pop("line_id", new_id())
    cur = conn.execute(
        """INSERT INTO journal_lines
           (id, company_id, entry_id, account_id, debit_paise, credit_paise, narration, source_file, source_row)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (line_id, company_id, entry_id, account_id, debit_paise, credit_paise, narration, kwargs.get("source_file"), kwargs.get("source_row")),
    )
    conn.commit()
    cur = conn.execute("SELECT * FROM journal_lines WHERE id = ?", (line_id,))
    return dict(cur.fetchone())


def get_journal_balance_paise(conn, entry_id: str) -> dict:
    cur = conn.execute(
        "SELECT COALESCE(SUM(debit_paise),0) AS debits, COALESCE(SUM(credit_paise),0) AS credits FROM journal_lines WHERE entry_id = ?",
        (entry_id,),
    )
    row = dict(cur.fetchone())
    row["balanced"] = row["debits"] == row["credits"]
    row["difference_paise"] = row["debits"] - row["credits"]
    return row


def post_journal(conn, entry_id: str) -> dict:
    balance = get_journal_balance_paise(conn, entry_id)
    if not balance["balanced"]:
        raise ValueError(f"Cannot post unbalanced journal: debits={balance['debits']} credits={balance['credits']}")
    cur = conn.execute("SELECT COUNT(*) AS cnt FROM journal_lines WHERE entry_id = ?", (entry_id,))
    if cur.fetchone()["cnt"] < 2:
        raise ValueError("A journal entry must have at least two lines")
    conn.execute("UPDATE journal_entries SET status='posted' WHERE id = ?", (entry_id,))
    conn.commit()
    cur = conn.execute("SELECT * FROM journal_entries WHERE id = ?", (entry_id,))
    return dict(cur.fetchone())


def create_bank_line(conn, company_id: str, statement_date: str, source_file: str, source_row: int, **kwargs) -> dict:
    debit_paise = _check_paise(kwargs.get("debit_paise", 0), "debit_paise")
    credit_paise = _check_paise(kwargs.get("credit_paise", 0), "credit_paise")
    balance_paise = kwargs.get("balance_paise")
    if balance_paise is not None:
        _check_paise(balance_paise, "balance_paise")
    line_id = kwargs.pop("line_id", new_id())
    cur = conn.execute(
        """INSERT INTO bank_lines
           (id, company_id, statement_date, value_date, narration, cheque_no, debit_paise, credit_paise, balance_paise, source_file, source_row, raw_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            line_id,
            company_id,
            statement_date,
            kwargs.get("value_date"),
            kwargs.get("narration"),
            kwargs.get("cheque_no"),
            debit_paise,
            credit_paise,
            balance_paise,
            source_file,
            source_row,
            json.dumps(kwargs.get("raw", {})),
        ),
    )
    conn.commit()
    cur = conn.execute("SELECT * FROM bank_lines WHERE id = ?", (line_id,))
    return dict(cur.fetchone())


def create_invoice(conn, company_id: str, invoice_type: str, invoice_no: str, invoice_date: str, party_name: str, total_paise: int, **kwargs) -> dict:
    if invoice_type not in ('PURCHASE', 'SALES'):
        raise ValueError("invoice_type must be PURCHASE or SALES")
    total_paise = _check_paise(total_paise, "total_paise")
    taxable_paise = _check_paise(kwargs.get("taxable_paise", 0), "taxable_paise")
    cgst_paise = _check_paise(kwargs.get("cgst_paise", 0), "cgst_paise")
    sgst_paise = _check_paise(kwargs.get("sgst_paise", 0), "sgst_paise")
    igst_paise = _check_paise(kwargs.get("igst_paise", 0), "igst_paise")
    invoice_id = kwargs.pop("invoice_id", new_id())
    cur = conn.execute(
        """INSERT INTO invoices
           (id, company_id, invoice_type, invoice_no, invoice_date, party_name, party_gstin, party_state_code,
            taxable_paise, cgst_paise, sgst_paise, igst_paise, total_paise, source_file, source_row)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            invoice_id,
            company_id,
            invoice_type,
            invoice_no,
            invoice_date,
            party_name,
            kwargs.get("party_gstin"),
            kwargs.get("party_state_code"),
            taxable_paise,
            cgst_paise,
            sgst_paise,
            igst_paise,
            total_paise,
            kwargs.get("source_file"),
            kwargs.get("source_row"),
        ),
    )
    conn.commit()
    cur = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
    return dict(cur.fetchone())


def create_match(conn, company_id: str, match_type: str, rule_used: str, confidence: float, reason: str, **kwargs) -> dict:
    if match_type not in ('EXACT', 'FUZZY', 'SPLIT', 'MANUAL'):
        raise ValueError("match_type must be EXACT/FUZZY/SPLIT/MANUAL")
    match_id = kwargs.pop("match_id", new_id())
    assumed = 1 if kwargs.pop("assumed", True) else 0
    cur = conn.execute(
        """INSERT INTO matches
           (id, company_id, match_type, status, bank_line_id, invoice_id, journal_entry_id, match_group_id,
            rule_used, confidence, reason, source_file, source_row, assumed)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            match_id,
            company_id,
            match_type,
            kwargs.get("status", "proposed"),
            kwargs.get("bank_line_id"),
            kwargs.get("invoice_id"),
            kwargs.get("journal_entry_id"),
            kwargs.get("match_group_id"),
            rule_used,
            confidence,
            reason,
            kwargs.get("source_file"),
            kwargs.get("source_row"),
            assumed,
        ),
    )
    conn.commit()
    cur = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
    return dict(cur.fetchone())


def create_exception(conn, company_id: str, exception_type: str, severity: str, title: str, **kwargs) -> dict:
    if severity not in ('INFO', 'WARNING', 'BLOCKING'):
        raise ValueError("severity must be INFO/WARNING/BLOCKING")
    exception_id = kwargs.pop("exception_id", new_id())
    cur = conn.execute(
        """INSERT INTO exceptions
           (id, company_id, exception_type, severity, status, title, details_json,
            related_bank_line_id, related_invoice_id, related_entry_id,
            rule_used, reason, source_file, source_row)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            exception_id,
            company_id,
            exception_type,
            severity,
            kwargs.get("status", "open"),
            title,
            json.dumps(kwargs.get("details", {})),
            kwargs.get("related_bank_line_id"),
            kwargs.get("related_invoice_id"),
            kwargs.get("related_entry_id"),
            kwargs.get("rule_used"),
            kwargs.get("reason"),
            kwargs.get("source_file"),
            kwargs.get("source_row"),
        ),
    )
    conn.commit()
    cur = conn.execute("SELECT * FROM exceptions WHERE id = ?", (exception_id,))
    return dict(cur.fetchone())
