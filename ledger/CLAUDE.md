### Phase 4.5 - 2026-10-24 (resumed and wired)
Works:
- Engine (`ledgerai.engine`) runs end-to-end on CSV/Excel: normalise -> match bank<->ledger (exact/fuzzy/split) -> invoice checks -> suggestions -> real double-entry journals -> TB/P&L/BS -> verification.
- Matching: bank Debit = money out, ledger Debit = money in; normalised to signed integer paise; OPENING BALANCE skipped. Date within 3 days, party match for exact; up to Rs 10 flagged needs approval; splits 2-3. Repeated identical bank debits are duplicates and never matched twice.
- Invoices: duplicate numbers, CGST==SGST at 9% each with rounding tolerance, tax/total checks; suggestions for unmatched payments; "invoice missing" when none.
- Exceptions: duplicate payment, unrecorded bank charge/interest, small difference, amount mismatch, uncleared cheque, missing ledger entry, missing invoice.
- Streamlit app wired to engine on all pages: Upload (mapping UI), Matches (evidence), Exceptions (problems + suggestions), Verification Checks, Trial Balance, P&L, Balance Sheet, Scorecard, Disagreements, Dry Run.
- Answer key reconstructed at `data/test/ANSWER_KEY.md`. Tests added for answer key, edge cases, 20 random datasets.
- All amounts integer paise; every journal balances; TB/BS balanced; verification enforced.
Weak: Phase 5 (evidence graph) and Phase 6 (AI layer with mock provider) not yet implemented.
Tests: run with `.\.venv\Scripts\python.exe -m pytest -v` (see latest run).
Command to open app: `.\.venv\Scripts\python.exe -m streamlit run app.py`
