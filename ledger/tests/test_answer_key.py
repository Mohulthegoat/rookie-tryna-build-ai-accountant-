"""Answer-key tests for the October 2026 test pack.

These assert the semantics in data/test/ANSWER_KEY.md. They intentionally do not
inspect file-specific row numbers; the engine must derive the numbers.
"""
from pathlib import Path

import pytest

from ledgerai.engine import run_engine

TEST_DIR = Path("data/test")


@pytest.fixture(scope="module")
def result():
    return run_engine(
        TEST_DIR / "bank_statement_oct2026.csv",
        TEST_DIR / "ledger_tally_export_oct2026.csv",
        TEST_DIR / "invoices_oct2026.csv",
    )


def test_source_counts(result):
    assert result.counts["bank_transactions"] == 33
    assert result.counts["ledger_entries"] == 30
    assert result.counts["invoices"] == 9


def test_match_counts(result):
    assert result.counts["normal_matches"] == 24
    assert result.counts["duplicate_linked"] == 1
    assert result.counts["fuzzy_matches"] == 1
    assert result.counts["split_matches"] == 1
    assert result.counts["bank_matched"] == 27
    assert result.counts["ledger_matched"] == 28
    assert result.counts["unmatched_bank"] == 6
    assert result.counts["unmatched_ledger"] == 2


def test_planted_problem_count_and_types(result):
    types = [e["type"] for e in result.exceptions]
    assert result.counts["planted_problems"] == 8
    for expected in (
        "duplicate_payment",
        "unrecorded_bank_charge",
        "unrecorded_bank_interest",
        "small_difference",
        "amount_mismatch",
        "uncleared_cheque",
        "missing_ledger_entry",
        "missing_invoice",
    ):
        assert expected in types, types


def test_split_is_detected_but_not_a_problem(result):
    splits = [m for m in result.matches if m["type"] == "SPLIT"]
    assert len(splits) == 1
    assert len(splits[0]["ledger_indices"]) == 2
    assert splits[0]["needs_approval"] is True
    assert "split" not in [e["type"] for e in result.exceptions]


def test_small_difference_needs_approval(result):
    fuzzy = [m for m in result.matches if m["type"] == "FUZZY"]
    assert len(fuzzy) == 1
    assert fuzzy[0]["difference_paise"] == 500
    assert fuzzy[0]["needs_approval"] is True
    diff_exc = next(e for e in result.exceptions if e["type"] == "small_difference")
    assert diff_exc["difference_paise"] == 500


def test_duplicate_bank_debit_never_matches_twice(result):
    amazon = [b for b in result.bank_lines if "AMAZON" in b.narration.upper()]
    assert len(amazon) == 2
    linked = [m for m in result.matches if "AMAZON" in m["bank"].narration.upper()]
    assert len(linked) == 1
    used = [i for m in result.matches for i in m["bank_indices"]]
    assert len(used) == len(set(used)), "a bank line was matched twice"
    led = [i for m in result.matches for i in m["ledger_indices"]]
    assert len(led) == len(set(led)), "a ledger entry was matched twice"


def test_invoice_problems(result):
    types = [i["type"] for i in result.invoice_issues]
    assert result.counts["invoice_problems"] == 2
    assert "duplicate_invoice_number" in types
    assert "gst_mismatch" in types
    gst = next(i for i in result.invoice_issues if i["type"] == "gst_mismatch")
    assert gst["invoice_no"] == "ZS/0055"


def test_invoice_suggestions_and_missing_invoice(result):
    by_bank = {}
    for line in result.unmatched_bank:
        by_bank[line.narration] = result.invoice_suggestions[line.line_id]
    sharma = next(v for k, v in by_bank.items() if "SHARMA" in k.upper())
    mehra = next(v for k, v in by_bank.items() if "MEHRA" in k.upper())
    kumar = next(v for k, v in by_bank.items() if "KUMAR" in k.upper())
    assert sharma["invoice_no"] == "SH/2210"
    assert kumar["invoice_no"] == "KH/3340"
    assert mehra["status"] == "invoice_missing"
    assert mehra["invoice_no"] is None


def test_unmatched_lists_are_the_expected_parties(result):
    bank_parties = " | ".join(b.party_norm for b in result.unmatched_bank)
    ledger_parties = " | ".join(b.party_norm for b in result.unmatched_ledger)
    for name in ("AMAZON", "SHARMA", "MEHRA", "KUMAR"):
        assert name in bank_parties
    for name in ("KUMAR", "FERNANDES"):
        assert name in ledger_parties


def test_every_journal_balances(result):
    assert result.journals
    for journal in result.journals:
        debit = sum(line["debit_paise"] for line in journal["lines"])
        credit = sum(line["credit_paise"] for line in journal["lines"])
        assert debit == credit, journal["id"]
        assert debit > 0
        for line in journal["lines"]:
            assert isinstance(line["debit_paise"], int)
            assert isinstance(line["credit_paise"], int)


def test_reports_balance(result):
    assert result.trial_balance.balanced
    assert result.trial_balance.total_debits_paise == result.trial_balance.total_credits_paise
    assert result.verification.passed
    assert result.balance_sheet.balanced
    assert result.pl.net_paise == result.pl.revenue_paise - result.pl.expenses_paise
