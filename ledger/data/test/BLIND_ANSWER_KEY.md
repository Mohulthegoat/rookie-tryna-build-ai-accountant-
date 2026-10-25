# LedgerAI BLIND test - answer key (all data FAKE, September 2026)

OpenCode has never seen these files or this key. Different company, different parties,
different amounts (with paise), different counts. If the engine only works on the first
test set, it is hard-coded or over-fitted, and this test will show it.

Upload: blind_bank_statement_sep2026.csv -> Bank Statement
        blind_ledger_tally_sep2026.csv   -> Ledger / Tally Export
        blind_invoices_sep2026.csv       -> Invoices

## Expected counts (they differ from the first test set on purpose)
- Bank transactions: 35 (plus an OPENING BALANCE row of 15,00,000.50, not a transaction)
- Ledger entries: 33        Invoices: 10
- Bank lines matched: 29    Bank lines unmatched: 6
- Ledger entries matched: 31  Ledger entries unmatched: 2
- 26 normal items match automatically (exact amount, date 0-3 days apart)

## 8 planted problems (same kinds as before, different details)
1. SMALL DIFFERENCE   Gowda Metals: books 58,300.00, bank 58,293.00 (Rs 7 short).
   Expected: matched as a fuzzy match, flagged "needs approval".
2. THREE-WAY SPLIT    Pillai Cement: one bank debit 2,10,000 = books 90,000 + 70,000 + 50,000.
3. DUPLICATE PAYMENT  Zoho Corporation 17,850 debited twice in the bank, booked once.
   Expected: one match + the second bank line flagged as a possible duplicate.
4. MISSING ENTRY, INVOICE EXISTS   Naidu Steel 1,12,000 paid on 25/09, not in the books.
   Invoice NS/4471 (total 1,12,000.00) exists. Expected: suggests booking against NS/4471.
5. MISSING ENTRY, NO INVOICE       Hegde Associates 33,300 paid on 26/09, no entry, no invoice.
6. UNCLEARED CHEQUE   Shetty Logistics cheque 118842 for 52,000 is in books, not in the bank.
7. BANK CHARGES / INTEREST  Bank charges 354.00 (debit) and interest 2,118.00 (credit),
   bank only. Expected: proposed entries to book them.
8. DIGITS SWAPPED     Rastogi Pumps: books 18,900 but bank and invoice RP/5518 say 19,800.
   Expected: one bank-only 19,800 and one ledger-only 18,900, ideally linked as the same
   payment with an amount mismatch.

## 2 invoice problems
A. DUPLICATE INVOICE NUMBER   RP/5518 (Rastogi Pumps) appears twice.
B. GST ERROR   TP/2209 Thakur Paints: taxable 30,000, CGST 2,700 but SGST 2,250
   (both should be 2,700). The total is wrong.

## Trial balance trap
The ledger file's Debit column totals 245,432.13 and its Credit column 922,405.89 (rupees).
A correct trial balance is built from proper double-entry journals, NOT from adding up
those two columns.

## Scoring
Matching counts above + 8 problems + 2 invoice problems = 10 findings. Also check:
amounts keep their paise (e.g. 58,293.00, no rounding), nothing silently accepted.
