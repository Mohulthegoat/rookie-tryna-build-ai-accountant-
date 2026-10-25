"""Financial reports and verification engine v1.

All numbers computed in deterministic Python from paise integers.
Verification does NOT trust other modules - it recomputes independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ledgerai.money import sum_paise, parse_amount

__all__ = [
    "TrialBalance",
    "PL",
    "BalanceSheet",
    "VerificationReport",
    "compute_trial_balance",
    "compute_pl",
    "compute_bs",
    "verify_all",
    "verify_independent",
]


@dataclass
class TrialBalance:
    rows: list[dict]
    total_debits_paise: int
    total_credits_paise: int
    balanced: bool


@dataclass
class PL:
    revenue_paise: int
    expenses_paise: int
    net_paise: int


@dataclass
class BalanceSheet:
    assets_paise: int
    liabilities_paise: int
    equity_paise: int
    balanced: bool


@dataclass
class VerificationReport:
    passed: bool
    status: str  # BLOCKED, NEEDS REVIEW, or READY TO CLOSE
    checks: list[dict]
    blocking_failures: list[dict]
    warnings: list[dict]


def compute_trial_balance(journal_lines: list[dict]) -> TrialBalance:
    by_acct = {}
    for line in journal_lines:
        aid = line.get("account_id") or line.get("account")
        by_acct.setdefault(aid, {"account_id": aid, "account_type": line.get("account_type", ""), "debits_paise": 0, "credits_paise": 0})
        by_acct[aid]["debits_paise"] += int(line.get("debit_paise") or 0)
        by_acct[aid]["credits_paise"] += int(line.get("credit_paise") or 0)
    rows = []
    for aid, v in by_acct.items():
        rows.append({**v, "balance_paise": v["debits_paise"] - v["credits_paise"]})
    td = sum_paise([r["debits_paise"] for r in rows])
    tc = sum_paise([r["credits_paise"] for r in rows])
    return TrialBalance(rows=rows, total_debits_paise=td, total_credits_paise=tc, balanced=(td == tc))


def compute_pl(revenue_paise: int, expenses_paise: int) -> PL:
    revenue_paise = int(revenue_paise)
    expenses_paise = int(expenses_paise)
    # Money received is income, money paid out is expense
    net = revenue_paise - expenses_paise
    return PL(revenue_paise=revenue_paise, expenses_paise=expenses_paise, net_paise=net)


def compute_bs(assets_paise: int, liabilities_paise: int, equity_paise: int) -> BalanceSheet:
    assets_paise = int(assets_paise)
    liabilities_paise = int(liabilities_paise)
    equity_paise = int(equity_paise)
    return BalanceSheet(assets_paise=assets_paise, liabilities_paise=liabilities_paise, equity_paise=equity_paise, balanced=(assets_paise == liabilities_paise + equity_paise))


def verify_independent(
    bank_lines=None,
    ledger_lines=None,
    invoices=None,
    matches=None,
    exceptions=None,
    journals=None,
) -> VerificationReport:
    """Independent verification that does not trust the matching code."""
    checks = []
    blocking = []
    warnings = []

    bank_lines = bank_lines or []
    ledger_lines = ledger_lines or []
    invoices = invoices or []
    matches = matches or []
    exceptions = exceptions or []
    journals = journals or []

    # Opening balance row excluded
    real_bank = [b for b in bank_lines if getattr(b, "signed_paise", 0) != 0 or getattr(b, "line_id", "") != ""]
    # exclude opening by narration
    real_bank = [b for b in bank_lines if not ("OPENING" in str(getattr(b, "narration", "")).upper() and "BALANCE" in str(getattr(b, "narration", "")).upper())]
    real_ledger = [l for l in ledger_lines if not ("OPENING" in str(getattr(l, "narration", "")).upper() and "BALANCE" in str(getattr(l, "narration", "")).upper()) and getattr(l, "signed_paise", 0) != 0]

    checks.append({"name": "opening_balance_excluded", "passed": True, "detail": f"Bank txn rows: {len(real_bank)}, ledger entries: {len(real_ledger)}"})

    # All dates parsed
    bad_dates = 0
    for b in real_bank:
        if not getattr(b, "date_iso", None):
            bad_dates += 1
    for l in real_ledger:
        if not getattr(l, "date_iso", None):
            bad_dates += 1
    if bad_dates:
        checks.append({"name": "all_dates_parsed", "passed": False, "detail": f"{bad_dates} lines missing dates"})
        blocking.append({"name": "all_dates_parsed", "detail": f"{bad_dates} lines have unparsed dates"})
    else:
        checks.append({"name": "all_dates_parsed", "passed": True})

    # No bank line or ledger entry matched twice
    used_bank = []
    used_ledger = []
    for m in matches:
        for i in m.get("bank_indices", []):
            used_bank.append(i)
        for i in m.get("ledger_indices", []):
            used_ledger.append(i)
    if len(used_bank) != len(set(used_bank)):
        checks.append({"name": "no_double_match_bank", "passed": False})
        blocking.append({"name": "no_double_match_bank", "detail": "A bank line was matched more than once"})
    else:
        checks.append({"name": "no_double_match_bank", "passed": True})
    if len(used_ledger) != len(set(used_ledger)):
        checks.append({"name": "no_double_match_ledger", "passed": False})
        blocking.append({"name": "no_double_match_ledger", "detail": "A ledger entry was matched more than once"})
    else:
        checks.append({"name": "no_double_match_ledger", "passed": True})

    # Matched + unmatched = total (for bank/ledger movements)
    bank_matched = len(set(used_bank))
    ledger_matched = len(set(used_ledger))
    bank_unmatched = len([b for b in real_bank if getattr(b, "index", id(b)) not in set(used_bank)])
    ledger_unmatched = len([l for l in real_ledger if getattr(l, "index", id(l)) not in set(used_ledger)])
    # Differences tracked via exceptions/mismatches
    if bank_matched + bank_unmatched == len(real_bank):
        checks.append({"name": "bank_totals_match", "passed": True, "detail": f"{bank_matched}+{bank_unmatched}={len(real_bank)}"})
    else:
        checks.append({"name": "bank_totals_match", "passed": False, "detail": f"{bank_matched}+{bank_unmatched}!={len(real_bank)}"})
        blocking.append({"name": "bank_totals_match", "detail": "Bank matched + unmatched != total"})
    if ledger_matched + ledger_unmatched == len(real_ledger):
        checks.append({"name": "ledger_totals_match", "passed": True, "detail": f"{ledger_matched}+{ledger_unmatched}={len(real_ledger)}"})
    else:
        checks.append({"name": "ledger_totals_match", "passed": False, "detail": f"{ledger_matched}+{ledger_unmatched}!={len(real_ledger)}"})
        blocking.append({"name": "ledger_totals_match", "detail": "Ledger matched + unmatched != total"})

    # Every journal balances
    journals_ok = True
    for journal in journals:
        lines = journal.get("lines", [])
        d = sum(int(l.get("debit_paise", 0) or 0) for l in lines)
        c = sum(int(l.get("credit_paise", 0) or 0) for l in lines)
        if d != c:
            journals_ok = False
            break
    if journals_ok and journals:
        checks.append({"name": "journals_balance", "passed": True})
    elif not journals:
        checks.append({"name": "journals_balance", "passed": False})
        blocking.append({"name": "journals_balance", "detail": "No journals"})
    else:
        checks.append({"name": "journals_balance", "passed": False})
        blocking.append({"name": "journals_balance", "detail": "Unbalanced journal found"})

    # No duplicate invoice numbers
    inv_nums = []
    for inv in invoices:
        inv_nums.append(str(inv.get("invoice_no") or (inv.get("raw") or {}).get("Invoice No") or ""))
    if len([x for x in inv_nums if x]) != len(set([x for x in inv_nums if x])):
        checks.append({"name": "no_duplicate_invoice_numbers", "passed": False})
        blocking.append({"name": "no_duplicate_invoice_numbers", "detail": "Duplicate invoice numbers present"})
    else:
        checks.append({"name": "no_duplicate_invoice_numbers", "passed": True})

    # GST consistent
    gst_ok = True
    for inv in invoices:
        raw = inv.get("raw") or {}
        taxable = parse_amount(raw.get("Taxable Value") or raw.get("taxable") or inv.get("taxable_paise")) or inv.get("taxable_paise") or 0
        cgst = parse_amount(raw.get("CGST") or inv.get("cgst_paise")) or inv.get("cgst_paise") or 0
        sgst = parse_amount(raw.get("SGST") or inv.get("sgst_paise")) or inv.get("sgst_paise") or 0
        igst = parse_amount(raw.get("IGST") or inv.get("igst_paise")) or inv.get("igst_paise") or 0
        total = parse_amount(raw.get("Total") or inv.get("total_paise")) or inv.get("total_paise") or 0
        if igst == 0 and (cgst or sgst):
            if abs(cgst - sgst) > 1:
                gst_ok = False
            expected = int(round(taxable * 0.18))
            if abs((cgst + sgst) - expected) > 2:
                gst_ok = False
        if taxable and (cgst + sgst + igst) != total:
            gst_ok = False
    if gst_ok:
        checks.append({"name": "gst_consistent", "passed": True})
    else:
        checks.append({"name": "gst_consistent", "passed": False})
        blocking.append({"name": "gst_consistent", "detail": "GST inconsistent"})

    # Open blocking exceptions
    open_blocking = []
    for exc in exceptions:
        if exc.get("severity") == "BLOCKING" or exc.get("type") in ("duplicate_payment", "amount_mismatch", "uncleared_cheque", "missing_ledger_entry", "missing_invoice", "unrecorded_bank_charge", "unrecorded_bank_interest"):
            open_blocking.append(exc)
    if open_blocking:
        warnings.append({"name": "open_exceptions", "count": len(open_blocking)})

    if blocking:
        status = "BLOCKED"
        passed = False
    elif open_blocking or warnings:
        status = "NEEDS REVIEW"
        passed = True  # not blocked by integrity, but needs review
    else:
        status = "READY TO CLOSE"
        passed = True

    return VerificationReport(passed=passed, status=status, checks=checks, blocking_failures=blocking, warnings=warnings)


def verify_all(tb: TrialBalance, entries: list[dict], matches: list[dict]) -> VerificationReport:
    checks = []
    blocking = []
    warnings = []
    if not tb.balanced:
        checks.append({"name": "trial_balance_balanced", "passed": False, "detail": f"{tb.total_debits_paise} != {tb.total_credits_paise}"})
        blocking.append({"name": "trial_balance_balanced", "detail": "BLOCKED - debits != credits"})
    else:
        checks.append({"name": "trial_balance_balanced", "passed": True})
    for e in entries:
        if not e.get("rule_used") and e.get("status") == "posted":
            warnings.append({"name": "entry_missing_rule", "entry_id": e.get("id"), "detail": "needs review"})
            break
    else:
        checks.append({"name": "posted_entries_have_evidence", "passed": True})

    if blocking:
        status = "BLOCKED"
        passed = False
    elif warnings:
        status = "NEEDS REVIEW"
        passed = True
    else:
        status = "READY TO CLOSE"
        passed = True
    return VerificationReport(passed=passed, status=status, checks=checks, blocking_failures=blocking, warnings=warnings)

