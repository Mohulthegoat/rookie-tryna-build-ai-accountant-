"""20 deterministic random datasets with known answers + property checks."""
from __future__ import annotations

from pathlib import Path

import pytest

from ledgerai.engine import run_engine

from tests.dataset_gen import make_dataset


@pytest.mark.parametrize("seed", range(20))
def test_random_dataset_matches_known_answer(seed, tmp_path):
    data = make_dataset(seed, tmp_path, indian_format=seed % 2 == 0,
                        dash_dates=seed % 3 == 0, shuffle=seed % 4 == 0)
    result = run_engine(data["bank"], data["ledger"], data["invoices"])
    expected = data["counts"]
    for key, value in expected.items():
        assert result.counts[key] == value, (seed, key, result.counts[key], value)

    assert result.trial_balance.balanced
    assert result.balance_sheet.balanced
    assert result.verification.passed
    assert result.counts["planted_problems"] == 8
    assert result.counts["invoice_problems"] == 2


@pytest.mark.parametrize("seed", [0, 7, 19])
def test_properties_on_random_data(seed, tmp_path):
    data = make_dataset(seed, tmp_path, shuffle=True)
    result = run_engine(data["bank"], data["ledger"], data["invoices"])

    used_bank = [i for m in result.matches for i in m["bank_indices"]]
    used_ledger = [i for m in result.matches for i in m["ledger_indices"]]
    assert len(used_bank) == len(set(used_bank))
    assert len(used_ledger) == len(set(used_ledger))
    assert len(used_bank) == result.counts["bank_matched"]
    assert len(used_ledger) == result.counts["ledger_matched"]

    for journal in result.journals:
        debits = sum(l["debit_paise"] for l in journal["lines"])
        credits = sum(l["credit_paise"] for l in journal["lines"])
        assert debits == credits
        assert all(
            isinstance(l["debit_paise"], int) and isinstance(l["credit_paise"], int)
            for l in journal["lines"]
        )
        assert all(
            not (l["debit_paise"] and l["credit_paise"])
            for l in journal["lines"]
        )

    # every match records evidence
    for match in result.matches:
        assert match["rule_used"]
        assert match["reason"]
        assert 0 < match["confidence"] <= 1
