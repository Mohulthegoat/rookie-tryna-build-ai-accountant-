### Phase 4.5 done - 2026-10-24 (resumed)
- Created missing `data/test/ANSWER_KEY.md` from the test data.
- Rewrote `src/ledgerai/normalize.py` to handle Indian CSV/Excel, DD/MM/YYYY, DD-MM-YYYY, UPI/NEFT/IMPS, opening balance skip, bank `signed = credit-debit`, ledger `signed = debit-credit`, party extraction.
- Rewrote `src/ledgerai/matcher.py`: exact (same signed amount, <=3 days, party) -> fuzzy (<=Rs 10, needs approval) -> split (2-3 ledger entries sum to bank line). Identical bank debits are duplicates and never matched twice. Added amount mismatch, uncleared cheque, unrecorded charge/interest, small-difference exceptions.
- Rewrote `src/ledgerai/invoice_check.py`: duplicate invoice numbers, CGST must equal SGST at 9% each (1-paise rounding), 18% tax/total checks, invoice suggestions for unmatched payments with `invoice_missing`.
- Rewrote `src/ledgerai/engine.py` end-to-end: reads CSV/Excel, normalises, matches, invoice checks, builds real double-entry journals (every journal balances), TB/P&L/BS, verification. Returns detailed counts/evidence.
- Wired all pages in `app.py` to the engine (Upload, Matches, Exceptions, Verification Checks, Trial Balance, P&L, Balance Sheet, Scorecard, Disagreements, Dry Run). No placeholders for the engine-driven pages.
- Added tests: `tests/test_answer_key.py`, `tests/test_edge_cases.py`, `tests/test_random_datasets.py`, `tests/dataset_gen.py`. Tests written to fail-first semantics from the answer key.
- Tests: 94 passed. data/test scores 10/10 (24/24 normal, 27/27 bank matched, 6 unmatched bank, 2 unmatched ledger, 8 planted problems, 2 invoice problems). 20 random datasets all pass with property checks.
- Ready for fresh session to continue Phase 5 (evidence graph), Phase 6 (AI layer with mock provider), etc.
