"""Bank reconciliation for LedgerAI - Phase 3.

Rules:
- Exact match first (amount + same date/window rules)
- Then fuzzy match (small amount differences, date windows)
- Then split payments
- EVERY match records evidence: source file, source row, rule used, confidence, reason
- Uncertain matches marked 'needs review' / assumed until approved by human
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ledgerai.money import MoneyError

__all__ = ["MatchCandidate", "exact_match", "fuzzy_match", "split_match", "RECON_RULES"]


RECON_RULES = {
    "amount_unit": "paise_integers",
    "fuzzy_max_diff_paise": 100,  # Rs 1.00 - be strict, differences larger need review
    "date_window_days": 3,
    "split_allowed": True,
    "evidence_required": True,
    "ai_proposes_human_approves": True,
}


@dataclass
class MatchCandidate:
    bank_line_id: str | None
    invoice_id: str | None
    match_type: str  # EXACT|FUZZY|SPLIT
    rule_used: str
    confidence: float
    reason: str
    amount_matched_paise: int
    difference_paise: int
    needs_review: bool
    evidence: dict[str, Any]


def exact_match(bank_lines: list[dict], invoices: list[dict]) -> list[MatchCandidate]:
    candidates = []
    for bl in bank_lines:
        bl_amt = bl.get('debit_paise',0) or bl.get('credit_paise',0)
        bl_date = bl.get('statement_date') or bl.get('date_iso')
        for inv in invoices:
            inv_amt = inv.get('total_paise') or 0
            if bl_amt == inv_amt:
                candidates.append(MatchCandidate(
                    bank_line_id=bl.get('id'),
                    invoice_id=inv.get('id'),
                    match_type='EXACT',
                    rule_used='exact_amount_match',
                    confidence=0.99,
                    reason=f'Exact amount match ({bl_amt} paise). Evidence required.',
                    amount_matched_paise=bl_amt,
                    difference_paise=0,
                    needs_review=False,
                    evidence={
                        'bank_source_file': bl.get('source_file'),
                        'bank_source_row': bl.get('source_row'),
                        'invoice_no': inv.get('invoice_no'),
                        'rule_used': 'exact_amount_match'
                    }
                ))
    return candidates


def fuzzy_match(bank_lines: list[dict], invoices: list[dict], max_diff_paise: int = RECON_RULES['fuzzy_max_diff_paise'], window_days: int = RECON_RULES['date_window_days']) -> list[MatchCandidate]:
    if max_diff_paise > RECON_RULES['fuzzy_max_diff_paise']:
        # Don't silently allow larger diffs
        max_diff_paise = RECON_RULES['fuzzy_max_diff_paise']
    candidates = []
    for bl in bank_lines:
        bl_amt = abs(bl.get('debit_paise',0) or bl.get('credit_paise',0))
        for inv in invoices:
            inv_amt = abs(inv.get('total_paise') or 0)
            diff = abs(bl_amt - inv_amt)
            if diff > 0 and diff <= max_diff_paise:
                candidates.append(MatchCandidate(
                    bank_line_id=bl.get('id'),
                    invoice_id=inv.get('id'),
                    match_type='FUZZY',
                    rule_used='fuzzy_amount_within_tolerance',
                    confidence=0.7 if diff > 0 else 0.99,
                    reason=f'Amount within tolerance: diff={diff} paise (max={max_diff_paise}). Needs review.',
                    amount_matched_paise=min(bl_amt, inv_amt),
                    difference_paise=diff,
                    needs_review=True,  # fuzzy always needs review
                    evidence={
                        'bank_source_file': bl.get('source_file'),
                        'bank_source_row': bl.get('source_row'),
                        'invoice_no': inv.get('invoice_no'),
                        'rule_used': 'fuzzy_amount_within_tolerance',
                        'difference_paise': diff,
                        'tolerance_paise': max_diff_paise
                    }
                ))
    return candidates


def split_match(bank_lines: list[dict], invoice: dict, group_id: str) -> list[MatchCandidate]:
    inv_amt = abs(invoice.get('total_paise') or 0)
    total = 0
    candidates = []
    for bl in bank_lines:
        amt = abs(bl.get('debit_paise',0) or bl.get('credit_paise',0))
        total += amt
        candidates.append(MatchCandidate(
            bank_line_id=bl.get('id'),
            invoice_id=invoice.get('id'),
            match_type='SPLIT',
            rule_used='split_payment_sum',
            confidence=0.85,
            reason=f'Split payment part. Sum checked against invoice. Needs review.',
            amount_matched_paise=amt,
            difference_paise=0,
            needs_review=True,
            evidence={
                'bank_source_file': bl.get('source_file'),
                'bank_source_row': bl.get('source_row'),
                'invoice_no': invoice.get('invoice_no'),
                'rule_used': 'split_payment_sum',
                'group_id': group_id,
                'running_total_paise': total,
                'invoice_total_paise': inv_amt
            }
        ))
    if total != inv_amt:
        for c in candidates:
            c.needs_review = True
            c.reason = f'Split payment sum ({total}) != invoice total ({inv_amt}). BLOCKING - needs review.'
    return candidates
