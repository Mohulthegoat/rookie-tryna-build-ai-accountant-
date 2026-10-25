## What the engine shows (real output)

**Counts:** Bank lines 34, Ledger entries 30, Invoices 9

**Matches:** EXACT 5, FUZZY 0, SPLIT 1 (Bhatt). **28 unmatched** bank items with amounts.

**Exact matches found:** BL28,BL29 matched AW/9912 (duplicate bank debit matched same invoice), BL30 matched SH/2210, BL32 matched KH/3340 twice.

**Split:** Bhatt Plastics (BL27) matched to BP/1801+BP/1802 as split.

**Exceptions detected:**
1. DUPLICATE_PAYMENT - Amazon Web Services appears twice (BL28, BL29) - same amount
2. DUPLICATE_INVOICE - KH/3340 appears twice in invoices
3. UNRECORDED_BANK_CHARGE - BANK CHARGES OCT-2026 INCL GST not in ledger
4. UNRECORDED_BANK_INTEREST - INT.PD ON SB A/C not in ledger

**Verification:** TB not balanced (90.56L debits vs 64.16L credits) - BLOCKED. Verification passed: False.

## Planted problems status
From what I can see in the data:
- Amazon duplicate payment in bank - DETECTED ✓
- Duplicate invoice KH/3340 - DETECTED ✓
- Bank charges unrecorded - DETECTED ✓
- Interest unrecorded - DETECTED ✓
- Bhatt split payment - DETECTED ✓
- Lakshmi Steels 5 Rs difference (72495 vs 72500) - NOT matched by current fuzzy (diff 500 paise > 100 tolerance)
- Kumar Hardware - ledger says 36400, invoice KH/3340 is 34600, bank entries don't match cleanly - needs investigation
- Zenith Stationers invoice GST split odd (CGST 3600 SGST 3000 on 40000) - not auto-detected
- Sharma Traders direction mismatch - not matched
- Many unmatched items

**Missing:** ANSWER_KEY.md not present. Cannot confirm exact "8 planted problems, 2 invoice problems, 24 normal matches" without it.

## What's not built/connected
1. No ANSWER_KEY.md to validate against
2. Fuzzy tolerance is 100 paise - Lakshmi 5 Rs diff not caught
3. UI (app.py) not wired to engine - it's a shell
4. No tests added for these specific planted problems yet
5. Engine script exists but not integrated into app

## Fixes needed
1. Add tests for each detected/planted problem
2. Make fuzzy tolerance configurable and handle small differences better
3. Wire engine to app to display results
4. Improve matching logic
5. Give exact command to see results in app
