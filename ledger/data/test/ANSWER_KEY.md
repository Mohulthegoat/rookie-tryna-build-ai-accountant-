# LedgerAI test files - answer key (all data is FAKE, October 2026)

Upload: bank_statement_oct2026.csv -> Bank Statement
        ledger_tally_export_oct2026.csv -> Ledger / Tally Export
        invoices_oct2026.csv -> Invoices

Note: the bank statement uses the BANK's view (Debit = money out, Credit = money in).
The ledger uses the Tally bank-book view (Debit = money received, Credit = money paid).
This flip is realistic. If your app mis-reads it, that is a real bug to report.

## Expected totals
- Bank: 33 transactions (plus an opening balance row of 5,00,000.00, which is not a transaction)
- Ledger: 30 entries
- 27 bank lines should end up matched, 6 bank lines unmatched, 2 ledger entries unmatched

## 24 normal items: should match automatically (exact amount, date 0-2 days apart)
Sharma 42,500 / Kapoor 1,28,000 / Bharat 18,750 / Mehta 9,600 / Reddy 2,15,000 / Landlord 65,000 /
Zenith 3,250 / Iyer 76,400 / Airtel 1,499 / Nair 31,200 / Gupta 94,300 / Salary Ravi 38,000 /
Salary Anita 42,000 / Singh 12,800 / Banerjee 58,900 / BESCOM 7,420 / Joshi 26,700 / Verma 1,43,500 /
Patel 21,900 / Desai 67,800 / Chopra 8,450 / Menon 39,600 / Kulkarni 15,200 / Rao 82,100

## 8 planted problems: the app should find every one
1. SMALL DIFFERENCE  Lakshmi Steels: books 72,500.00, bank 72,495.00 (Rs 5 short).
   Expected: fuzzy match flagged "needs approval", not silently accepted.
2. SPLIT PAYMENT     Bhatt Plastics: bank one debit 1,20,000 = books 70,000 + 50,000.
   Expected: split match, both ledger entries linked to one bank line.
3. DUPLICATE         Amazon Web Services 23,400 debited TWICE in the bank, booked once.
   Expected: one match + the second bank line flagged as a possible duplicate.
4. MISSING ENTRY, INVOICE EXISTS   Sharma Traders 85,000 paid via NEFT on 27/10, not in books.
   Invoice SH/2210 (total 85,000.00) exists. Expected: suggests booking against SH/2210.
5. MISSING ENTRY, NO INVOICE       Mehra Consultants 47,500 paid on 28/10, nothing in books,
   no invoice. Expected: flagged, asks for the invoice.
6. UNCLEARED CHEQUE  Fernandes Consultants cheque 004512 for 45,000 is in books, not in bank.
   Expected: ledger-only item, "timing difference / uncleared cheque".
7. BANK CHARGES / INTEREST  Bank charges 590 (debit) and interest 1,240 (credit) are in the
   bank only. Expected: flagged to be booked.
8. TYPING MISTAKE    Kumar Hardware: books 36,400 but bank and invoice KH/3340 say 34,600
   (digits swapped). Expected: appears as one bank-only 34,600 and one ledger-only 36,400;
   an ideal system also notices they are the same payment with different amounts.

## 2 invoice problems (for the verification / GST phases)
A. DUPLICATE INVOICE NUMBER  KH/3340 from Kumar Hardware appears twice.
B. GST ERROR  ZS/0055 Zenith Stationers: taxable 40,000, CGST 3,600 but SGST 3,000
   (should be equal at 9% each = 3,600). Total 46,600 is wrong; correct total is 47,200.

## Quick scoring
Count how many of the 8 problems + 2 invoice problems the app found. 10/10 is the goal.
Anything it matched wrongly or silently accepted is a bug to report.
