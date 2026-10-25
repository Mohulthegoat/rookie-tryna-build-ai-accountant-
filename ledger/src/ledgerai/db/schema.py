"""SQLite schema and connection helpers for LedgerAI.

Non-negotiables enforced here:
- Money is stored as INTEGER paise. No TEXT that looks like currency floats.
- Double-entry: every posted journal has balanced debits/credits (enforced by
  triggers and by code).
- Evidence is stored on journal_entries, journal_lines and matches (rule used,
  confidence, reason, source file/row). AI items are marked assumed until
  approved.
- Data is separated per company (company_id everywhere).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

__all__ = ["DEFAULT_DB", "get_connection", "init_db", "SCHEMA_SQL"]

DEFAULT_DB = Path("ledgerai.db")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  gstin TEXT,
  pan TEXT,
  state_code TEXT,
  currency TEXT NOT NULL DEFAULT 'INR',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  settings_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS chart_of_accounts (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  account_type TEXT NOT NULL CHECK(account_type IN ('ASSET','LIABILITY','EQUITY','INCOME','EXPENSE')),
  parent_id TEXT REFERENCES chart_of_accounts(id),
  is_system INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  UNIQUE(company_id, code)
);

CREATE TABLE IF NOT EXISTS journal_entries (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  entry_date TEXT NOT NULL,  -- ISO8601 date
  voucher_no TEXT,
  source_module TEXT,        -- e.g. ingestion, reconciliation, agent
  narration TEXT,
  status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed','approved','posted','rejected','void')),
  -- Evidence (rule 2)
  source_file TEXT,
  source_row INTEGER,
  rule_used TEXT,
  confidence REAL,
  reason TEXT,
  -- Approval tracking (rule 4)
  assumed INTEGER NOT NULL DEFAULT 1,
  approved_by TEXT,
  approved_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS journal_lines (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  entry_id TEXT NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
  account_id TEXT NOT NULL REFERENCES chart_of_accounts(id),
  debit_paise INTEGER NOT NULL DEFAULT 0 CHECK(debit_paise >= 0),
  credit_paise INTEGER NOT NULL DEFAULT 0 CHECK(credit_paise >= 0),
  narration TEXT,
  -- Evidence per line
  source_file TEXT,
  source_row INTEGER,
  CHECK (NOT (debit_paise > 0 AND credit_paise > 0)),
  CHECK (debit_paise > 0 OR credit_paise > 0)
);

CREATE TABLE IF NOT EXISTS bank_lines (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  statement_date TEXT NOT NULL,
  value_date TEXT,
  narration TEXT,
  cheque_no TEXT,
  debit_paise INTEGER NOT NULL DEFAULT 0,
  credit_paise INTEGER NOT NULL DEFAULT 0,
  balance_paise INTEGER,
  source_file TEXT NOT NULL,
  source_row INTEGER NOT NULL,
  raw_json TEXT,
  UNIQUE(company_id, source_file, source_row)
);

CREATE TABLE IF NOT EXISTS invoices (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  invoice_type TEXT NOT NULL CHECK(invoice_type IN ('PURCHASE','SALES')),
  invoice_no TEXT NOT NULL,
  invoice_date TEXT NOT NULL,
  party_name TEXT NOT NULL,
  party_gstin TEXT,
  party_state_code TEXT,
  taxable_paise INTEGER NOT NULL DEFAULT 0,
  cgst_paise INTEGER NOT NULL DEFAULT 0,
  sgst_paise INTEGER NOT NULL DEFAULT 0,
  igst_paise INTEGER NOT NULL DEFAULT 0,
  total_paise INTEGER NOT NULL,
  source_file TEXT,
  source_row INTEGER,
  UNIQUE(company_id, invoice_type, invoice_no)
);

CREATE TABLE IF NOT EXISTS matches (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  match_type TEXT NOT NULL CHECK(match_type IN ('EXACT','FUZZY','SPLIT','MANUAL')),
  status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed','approved','rejected')),
  bank_line_id TEXT REFERENCES bank_lines(id),
  invoice_id TEXT REFERENCES invoices(id),
  journal_entry_id TEXT REFERENCES journal_entries(id),
  -- Split payments link multiple bank lines to one invoice
  match_group_id TEXT,
  -- Evidence (rule 2)
  rule_used TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0,
  reason TEXT NOT NULL,
  source_file TEXT,
  source_row INTEGER,
  assumed INTEGER NOT NULL DEFAULT 1,
  approved_by TEXT,
  approved_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS exceptions (
  id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  exception_type TEXT NOT NULL,
  severity TEXT NOT NULL CHECK(severity IN ('INFO','WARNING','BLOCKING')),
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','in_progress','resolved','dismissed')),
  title TEXT NOT NULL,
  details_json TEXT NOT NULL DEFAULT '{}',
  related_bank_line_id TEXT REFERENCES bank_lines(id),
  related_invoice_id TEXT REFERENCES invoices(id),
  related_entry_id TEXT REFERENCES journal_entries(id),
  -- Evidence
  rule_used TEXT,
  reason TEXT,
  source_file TEXT,
  source_row INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  resolved_at TEXT,
  resolved_by TEXT,
  resolution_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_journal_entries_company_date ON journal_entries(company_id, entry_date);
CREATE INDEX IF NOT EXISTS idx_journal_lines_entry ON journal_lines(entry_id);
CREATE INDEX IF NOT EXISTS idx_bank_lines_company_date ON bank_lines(company_id, statement_date);
CREATE INDEX IF NOT EXISTS idx_invoices_company_type ON invoices(company_id, invoice_type);
CREATE INDEX IF NOT EXISTS idx_matches_group ON matches(match_group_id);
CREATE INDEX IF NOT EXISTS idx_exceptions_company_status ON exceptions(company_id, status);

-- Keep updated_at fresh on journal entries
CREATE TRIGGER IF NOT EXISTS trg_journal_entries_updated_at
AFTER UPDATE ON journal_entries
BEGIN
  UPDATE journal_entries SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- Prevent posting an unbalanced journal entry (double-entry enforcement)
CREATE TRIGGER IF NOT EXISTS trg_journal_balance_on_insert
BEFORE INSERT ON journal_lines
BEGIN
  SELECT CASE
    WHEN NEW.entry_id IS NOT NULL AND (
      (SELECT COALESCE(SUM(debit_paise),0) - COALESCE(SUM(credit_paise),0)
         FROM journal_lines WHERE entry_id = NEW.entry_id) + NEW.debit_paise - NEW.credit_paise != 0
    ) AND (SELECT status FROM journal_entries WHERE id = NEW.entry_id) = 'posted'
    THEN RAISE(ABORT, 'Cannot post an unbalanced journal entry (debits != credits)')
  END;
END;

CREATE TRIGGER IF NOT EXISTS trg_journal_balance_on_update
BEFORE UPDATE ON journal_lines
BEGIN
  SELECT CASE
    WHEN (
      (SELECT COALESCE(SUM(debit_paise),0) - COALESCE(SUM(credit_paise),0)
         FROM journal_lines WHERE entry_id = NEW.entry_id AND id != NEW.id) + NEW.debit_paise - NEW.credit_paise != 0
    ) AND (SELECT status FROM journal_entries WHERE id = NEW.entry_id) = 'posted'
    THEN RAISE(ABORT, 'Cannot post an unbalanced journal entry (debits != credits)')
  END;
END;
"""


def get_connection(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def get_schema_version(conn: sqlite3.Connection) -> str:
    cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='journal_entries'")
    row = cur.fetchone()
    return "v1_phase0_schema" if row else "unknown"
