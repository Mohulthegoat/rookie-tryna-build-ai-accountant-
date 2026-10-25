"""One-to-one bank <-> ledger matching engine.

Order of rules, exactly as required:

1. exact signed amount, date within 3 days, party appears in narration
2. small difference up to Rs 10, same party/direction, flagged needs approval
3. split: one bank line equals the sum of 2-3 ledger entries for the same party

A bank line and a ledger entry can each be used in at most one match. Repeated
identical bank debits are reported as possible duplicates and never allow the
same ledger entry to be consumed twice.
"""
from __future__ import annotations

from itertools import combinations

from ledgerai.normalize import NormalizedLine, days_diff

__all__ = ["match_bank_ledger", "party_match"]

EXACT_DATE_WINDOW_DAYS = 3
FUZZY_MAX_PAISE = 1_000  # Rs 10
FUZZY_DATE_WINDOW_DAYS = 7
SPLIT_MAX_PARTS = 3


def party_match(a: str, b: str) -> bool:
    """Conservative party comparison on already-normalised names."""
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) >= 5 and shorter in longer:
        return True
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return False
    overlap = ta & tb
    return len(overlap) >= 2 and len(overlap) / len(ta) >= 0.75 and len(overlap) / len(tb) >= 0.75


def _match(type_, bank, ledgers, *, difference_paise=0, needs_approval=False,
           rule_used="", reason="", confidence=1.0, duplicate_linked=False) -> dict:
    return {
        "type": type_,
        "bank_indices": [bank.index],
        "ledger_indices": [l.index for l in ledgers],
        "bank": bank,
        "ledgers": ledgers,
        "amount_paise": bank.signed_paise,
        "difference_paise": difference_paise,
        "needs_approval": needs_approval,
        "duplicate_linked": duplicate_linked,
        "rule_used": rule_used,
        "reason": reason,
        "confidence": confidence,
    }


def match_bank_ledger(
    bank_lines: list[NormalizedLine],
    ledger_lines: list[NormalizedLine],
    *,
    exact_window_days: int = EXACT_DATE_WINDOW_DAYS,
    fuzzy_max_paise: int = FUZZY_MAX_PAISE,
    fuzzy_window_days: int = FUZZY_DATE_WINDOW_DAYS,
) -> dict:
    # Give every line an index used by the result sets and matches.
    for i, line in enumerate(bank_lines):
        line.index = i  # type: ignore[attr-defined]
    for i, line in enumerate(ledger_lines):
        line.index = i  # type: ignore[attr-defined]

    used_bank: set[int] = set()
    used_ledger: set[int] = set()
    matches: list[dict] = []

    # ---------------------------------------------------------------- exact
    for bank in bank_lines:
        if bank.index in used_bank or bank.signed_paise == 0:
            continue
        candidates = []
        for ledger in ledger_lines:
            if ledger.index in used_ledger or ledger.signed_paise != bank.signed_paise:
                continue
            distance = days_diff(bank.date_iso, ledger.date_iso)
            if distance > exact_window_days:
                continue
            if not party_match(bank.party_norm, ledger.party_norm):
                continue
            candidates.append((distance, ledger.index, ledger))
        if not candidates:
            continue
        candidates.sort(key=lambda item: (item[0], item[1]))
        distance, _, ledger = candidates[0]
        matches.append(_match(
            "EXACT", bank, [ledger],
            rule_used="exact_signed_amount_date_within_3_party_match",
            reason=(
                f"Same signed amount {bank.signed_paise} paise and party "
                f"'{ledger.party}' within {distance} day(s)."
            ),
            confidence=0.99,
        ))
        used_bank.add(bank.index)
        used_ledger.add(ledger.index)

    # ---------------------------------------------------------------- fuzzy
    for bank in bank_lines:
        if bank.index in used_bank or bank.signed_paise == 0:
            continue
        candidates = []
        for ledger in ledger_lines:
            if ledger.index in used_ledger or ledger.signed_paise == 0:
                continue
            if (bank.signed_paise < 0) != (ledger.signed_paise < 0):
                continue
            difference = abs(bank.signed_paise - ledger.signed_paise)
            if not (0 < difference <= fuzzy_max_paise):
                continue
            distance = days_diff(bank.date_iso, ledger.date_iso)
            if distance > fuzzy_window_days:
                continue
            if not party_match(bank.party_norm, ledger.party_norm):
                continue
            candidates.append((difference, distance, ledger.index, ledger))
        if not candidates:
            continue
        difference, distance, _, ledger = min(candidates, key=lambda item: (item[0], item[1], item[2]))
        matches.append(_match(
            "FUZZY", bank, [ledger],
            difference_paise=difference,
            needs_approval=True,
            rule_used="small_difference_within_10_rupees_party_match",
            reason=(
                f"Difference of {difference} paise (Rs {difference / 100:.2f}) is within the "
                f"Rs 10 tolerance; needs approval."
            ),
            confidence=0.75,
        ))
        used_bank.add(bank.index)
        used_ledger.add(ledger.index)

    # ---------------------------------------------------------------- split
    for bank in bank_lines:
        if bank.index in used_bank or bank.signed_paise == 0:
            continue
        pool = [
            ledger for ledger in ledger_lines
            if ledger.index not in used_ledger
            and ledger.signed_paise != 0
            and (bank.signed_paise < 0) == (ledger.signed_paise < 0)
            and party_match(bank.party_norm, ledger.party_norm)
        ]
        target = abs(bank.signed_paise)
        found = None
        for size in range(2, SPLIT_MAX_PARTS + 1):
            for combo in combinations(pool, size):
                if sum(abs(item.signed_paise) for item in combo) == target:
                    found = combo
                    break
            if found:
                break
        if not found:
            continue
        matches.append(_match(
            "SPLIT", bank, list(found),
            needs_approval=True,
            rule_used="split_sum_match_same_party",
            reason=(
                f"One bank line of {target} paise equals {len(found)} ledger entries "
                f"for '{bank.party}'. Needs approval."
            ),
            confidence=0.82,
        ))
        used_bank.add(bank.index)
        used_ledger.update(item.index for item in found)

    # ---------------------------------------------------- duplicate detection
    # Group identical signed amounts for the same party. Only one member of a
    # group may be matched; every extra member is a possible duplicate.
    groups: dict[tuple[int, str], list[NormalizedLine]] = {}
    for bank in bank_lines:
        if bank.signed_paise == 0:
            continue
        groups.setdefault((bank.signed_paise, bank.party_norm), []).append(bank)

    duplicate_bank_indices: set[int] = set()
    exceptions: list[dict] = []
    for (signed, party), group in groups.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda line: line.index)
        duplicate_bank_indices.update(line.index for line in group[1:])
        exceptions.append({
            "type": "duplicate_payment",
            "severity": "BLOCKING",
            "title": "Possible duplicate bank payment",
            "reason": (
                f"{len(group)} identical bank debits/credits of {abs(signed)} paise "
                f"for '{party}'. Only one can be matched."
            ),
            "bank_indices": [line.index for line in group],
            "bank_ids": [line.line_id for line in group],
            "amount_paise": abs(signed),
            "party": party,
            "rule_used": "identical_signed_amount_and_party",
        })

    for match in matches:
        if any(i in duplicate_bank_indices for i in match["bank_indices"]):
            match["duplicate_linked"] = True

    # -------------------------------------------------------- amount mismatch
    unmatched_bank = [b for b in bank_lines if b.index not in used_bank]
    unmatched_ledger = [l for l in ledger_lines if l.index not in used_ledger]
    already_paired: set[tuple[int, int]] = set()

    for bank in unmatched_bank:
        if bank.index in duplicate_bank_indices:
            continue
        best = None
        for ledger in unmatched_ledger:
            if (bank.signed_paise < 0) != (ledger.signed_paise < 0):
                continue
            if not party_match(bank.party_norm, ledger.party_norm):
                continue
            distance = days_diff(bank.date_iso, ledger.date_iso)
            if distance > fuzzy_window_days:
                continue
            difference = abs(bank.signed_paise - ledger.signed_paise)
            if difference <= fuzzy_max_paise:
                continue
            # A mismatch should be plausible, not two unrelated invoices.
            if difference / max(abs(bank.signed_paise), abs(ledger.signed_paise)) > 0.5:
                continue
            key = (bank.index, ledger.index)
            if key in already_paired:
                continue
            candidate = (distance, difference, ledger.index, ledger)
            if best is None or candidate[:3] < best[:3]:
                best = candidate
        if best is None:
            continue
        _, difference, _, ledger = best
        already_paired.add((bank.index, ledger.index))
        exceptions.append({
            "type": "amount_mismatch",
            "severity": "BLOCKING",
            "title": "Bank and ledger amounts differ",
            "reason": (
                f"Bank amount {abs(bank.signed_paise)} paise vs ledger "
                f"{abs(ledger.signed_paise)} paise for '{bank.party}' "
                f"(difference {difference} paise). Not matched."
            ),
            "bank_indices": [bank.index],
            "bank_ids": [bank.line_id],
            "ledger_indices": [ledger.index],
            "ledger_ids": [ledger.line_id],
            "difference_paise": difference,
            "bank_amount_paise": abs(bank.signed_paise),
            "ledger_amount_paise": abs(ledger.signed_paise),
            "party": bank.party,
            "rule_used": "same_party_same_direction_amount_differs",
        })

    # ------------------------------------------------------ uncleared cheque
    for ledger in unmatched_ledger:
        cheque_hint = bool(ledger.cheque_no) or "CHEQUE" in f"{ledger.narration} {ledger.particulars}".upper()
        if not cheque_hint:
            continue
        exceptions.append({
            "type": "uncleared_cheque",
            "severity": "BLOCKING",
            "title": "Cheque recorded in ledger but not cleared in bank",
            "reason": (
                f"Ledger entry {ledger.line_id} for '{ledger.party}' "
                f"({abs(ledger.signed_paise)} paise) has no bank counterpart."
            ),
            "ledger_indices": [ledger.index],
            "ledger_ids": [ledger.line_id],
            "cheque_no": ledger.cheque_no,
            "amount_paise": abs(ledger.signed_paise),
            "party": ledger.party,
            "rule_used": "ledger_cheque_not_found_in_bank",
        })

    # ------------------------------------- unrecorded charge / interest hints
    for bank in unmatched_bank:
        if bank.index in duplicate_bank_indices:
            continue
        upper = bank.narration.upper()
        if "BANK CHARGE" in upper or ("CHARGE" in upper and "BANK" in upper):
            exceptions.append({
                "type": "unrecorded_bank_charge",
                "severity": "WARNING",
                "title": "Bank charges not recorded in ledger",
                "reason": f"Bank narration '{bank.narration}' has no ledger entry.",
                "bank_indices": [bank.index],
                "bank_ids": [bank.line_id],
                "amount_paise": abs(bank.signed_paise),
                "rule_used": "unmatched_bank_narration_bank_charge",
            })
        elif "INT.PD" in upper or "INTEREST" in upper:
            exceptions.append({
                "type": "unrecorded_bank_interest",
                "severity": "WARNING",
                "title": "Bank interest not recorded in ledger",
                "reason": f"Bank narration '{bank.narration}' has no ledger entry.",
                "bank_indices": [bank.index],
                "bank_ids": [bank.line_id],
                "amount_paise": abs(bank.signed_paise),
                "rule_used": "unmatched_bank_narration_interest",
            })

    # Small-difference exceptions mirror the fuzzy match for the scorecard.
    for match in matches:
        if match["type"] == "FUZZY":
            exceptions.append({
                "type": "small_difference",
                "severity": "WARNING",
                "title": "Small amount difference needs approval",
                "reason": match["reason"],
                "bank_indices": match["bank_indices"],
                "bank_ids": [match["bank"].line_id],
                "ledger_indices": match["ledger_indices"],
                "ledger_ids": [line.line_id for line in match["ledgers"]],
                "difference_paise": match["difference_paise"],
                "amount_paise": abs(match["amount_paise"]),
                "party": match["bank"].party,
                "rule_used": match["rule_used"],
            })

    return {
        "matches": matches,
        "unmatched_bank": [(line.index, line) for line in unmatched_bank],
        "unmatched_ledger": [(line.index, line) for line in unmatched_ledger],
        "exceptions": exceptions,
        "bank_matched": used_bank,
        "ledger_matched": used_ledger,
        "duplicate_bank_indices": duplicate_bank_indices,
    }
