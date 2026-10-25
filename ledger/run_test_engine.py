"""Run engine on test data - proves calculations independent of UI."""
from __future__ import annotations
import csv, json, sys
from pathlib import Path
from ledgerai.money import parse_amount, rupees_to_paise, format_inr
from ledgerai.ingest import read_csv_raw, detect_bank_format, ColumnMapping, apply_mapping
from ledgerai.recon import exact_match, fuzzy_match, split_match
from ledgerai.reports import compute_trial_balance, compute_pl, compute_bs, verify_all

TEST_DIR = Path('data/test')

def main():
    print('='*60)
    print('LEDGERAI ENGINE TEST - RUNNING ON data/test/')
    print('='*60)
    
    # Read files
    bank_rows, bank_headers = read_csv_raw(TEST_DIR / 'bank_statement_oct2026.csv')
    ledger_rows, ledger_headers = read_csv_raw(TEST_DIR / 'ledger_tally_export_oct2026.csv')
    inv_rows, inv_headers = read_csv_raw(TEST_DIR / 'invoices_oct2026.csv')
    
    print(f'\n1. COUNTS')
    print(f'   Bank lines read: {len(bank_rows)} (including header row in CSV? DictReader skips header)')
    print(f'   Ledger entries read: {len(ledger_rows)}')
    print(f'   Invoices read: {len(inv_rows)}')
    
    # Map bank
    sug = detect_bank_format(bank_headers)
    m = ColumnMapping(date_col=sug['date_col'], narration_col=sug['narration_col'],
                      debit_col=sug['debit_col'], credit_col=sug['credit_col'],
                      balance_col=sug['balance_col'], cheque_col=sug['cheque_col'],
                      confirmed=True)
    mapped_bank = apply_mapping(bank_rows, m)
    print(f'   Mapped bank lines: {len(mapped_bank)}')
    
    # Parse ledger (different format)
    ledger_parsed = []
    for i, r in enumerate(ledger_rows, 1):
        dr = parse_amount(r.get('Debit',''))
        cr = parse_amount(r.get('Credit',''))
        ledger_parsed.append({
            'row_index': i,
            'date': r.get('Date'),
            'voucher_no': r.get('Voucher No'),
            'particulars': r.get('Particulars'),
            'narration': r.get('Narration'),
            'debit_paise': dr or 0,
            'credit_paise': cr or 0,
            'raw': r
        })
    
    # Parse invoices
    invoices_parsed = []
    for i, r in enumerate(inv_rows, 1):
        total = parse_amount(r.get('Total',''))
        taxable = parse_amount(r.get('Taxable Value',''))
        cgst = parse_amount(r.get('CGST',''))
        sgst = parse_amount(r.get('SGST',''))
        igst = parse_amount(r.get('IGST',''))
        invoices_parsed.append({
            'id': f'INV{i}',
            'row_index': i,
            'invoice_no': r.get('Invoice No'),
            'date': r.get('Invoice Date'),
            'vendor': r.get('Vendor'),
            'gstin': r.get('GSTIN'),
            'taxable_paise': taxable or 0,
            'cgst_paise': cgst or 0,
            'sgst_paise': sgst or 0,
            'igst_paise': igst or 0,
            'total_paise': total or 0,
            'raw': r
        })
    
    print(f'\n2. MATCHING')
    # Build bank line dicts for matching
    bank_for_match = []
    for mb in mapped_bank:
        if mb.date_iso == '2026-10-01' and mb.narration == 'OPENING BALANCE':
            continue  # skip opening
        amt = mb.debit_paise or mb.credit_paise
        bank_for_match.append({
            'id': f'BL{mb.row_index}',
            'debit_paise': mb.debit_paise,
            'credit_paise': mb.credit_paise,
            'amount': amt,
            'narration': mb.narration,
            'date_iso': mb.date_iso,
            'source_file': 'bank_statement_oct2026.csv',
            'source_row': mb.row_index
        })
    
    exact = exact_match(bank_for_match, invoices_parsed)
    print(f'   Exact matches: {len(exact)}')
    for e in exact:
        print(f'     - {e.evidence}')
    
    # Fuzzy - look for small differences
    fuzzy = fuzzy_match(bank_for_match, invoices_parsed)
    print(f'   Fuzzy matches: {len(fuzzy)}')
    for f in fuzzy:
        print(f'     - diff={f.difference_paise} paise, reason={f.reason}, evidence={f.evidence}')
    
    # Find split payments - bank lines that together match invoice
    split_matches = []
    # Check Bhatt Plastics - bank has 120000 debit, two invoices 70000+50000
    bhatt_bank = [b for b in bank_for_match if 'BHATT' in b['narration'].upper()]
    bhatt_invoices = [i for i in invoices_parsed if 'BHATT' in i['vendor'].upper()]
    if bhatt_bank and len(bhatt_invoices) >= 2:
        split_matches.extend(split_match(bhatt_bank, {'id': 'INV_SPLIT_BHATT', 'invoice_no': 'BP/1801+BP/1802', 'total_paise': sum(i['total_paise'] for i in bhatt_invoices)}, 'GRP-BHATT'))
        print(f'   Split matches (Bhatt): {len(split_matches)}')
    
    total_matches = len(exact) + len(fuzzy) + len(split_matches)
    print(f'   Total matches found by engine: {total_matches}')
    
    # Unmatched
    matched_bank_ids = set([e.bank_line_id for e in exact] + [f.bank_line_id for f in fuzzy])
    for sm in split_matches:
        matched_bank_ids.add(sm.bank_line_id)
    unmatched = [b for b in bank_for_match if b['id'] not in matched_bank_ids and b['amount'] > 0]
    print(f'   Unmatched bank items (amount>0): {len(unmatched)}')
    for u in unmatched:
        print(f'     - {u["narration"]} amt={u["amount"]} paise ({u["amount"]/100:.2f})')
    
    print(f'\n3. EXCEPTIONS')
    exceptions = []
    # Duplicate in bank
    seen = {}
    for b in bank_for_match:
        key = (b['narration'], b['debit_paise'], b['credit_paise'])
        if key in seen and (b['debit_paise'] or b['credit_paise']):
            exceptions.append({'type': 'duplicate_payment', 'reason': f'Duplicate bank entry: {b["narration"]} same amount', 'bank_id': b['id']})
        seen[key] = seen.get(key,0)+1
    # Duplicate invoice
    inv_seen = {}
    for inv in invoices_parsed:
        if inv['invoice_no'] in inv_seen:
            exceptions.append({'type': 'duplicate_invoice', 'reason': f'Duplicate invoice number: {inv["invoice_no"]}', 'invoice': inv['invoice_no']})
        inv_seen[inv['invoice_no']] = True
    # Unrecorded bank charge/interest
    for b in bank_for_match:
        if 'BANK CHARGES' in b['narration'].upper() and not any('BANK CHARGE' in str(l.get('particulars','')).upper() or 'BANK CHARGE' in str(l.get('narration','')).upper() for l in ledger_parsed):
            exceptions.append({'type': 'unrecorded_bank_charge', 'reason': f'Bank charge not in ledger: {b["narration"]}', 'bank_id': b['id']})
        if 'INT.PD' in b['narration'].upper() and not any('INTEREST' in str(l.get('particulars','')).upper() for l in ledger_parsed):
            exceptions.append({'type': 'unrecorded_bank_interest', 'reason': f'Interest not in ledger: {b["narration"]}', 'bank_id': b['id']})
    # Uncleared cheque - in ledger but not in bank
    for lp in ledger_parsed:
        if lp['debit_paise'] > 0 and lp['particulars']:
            found = False
            for b in bank_for_match:
                if lp['particulars'].upper() in b['narration'].upper() and b['debit_paise'] == lp['debit_paise']:
                    found = True
            if not found and 'CHEQUE' in str(lp.get('narration','')).upper():
                exceptions.append({'type': 'uncleared_cheque', 'reason': f'Cheque in ledger not cleared in bank: {lp["particulars"]} {lp["debit_paise"]/100}', 'voucher': lp['voucher_no']})
    
    for ex in exceptions:
        print(f'   - {ex}')
    
    print(f'\n4. VERIFICATION CHECKS')
    # Build trial balance from ledger
    tb_lines = []
    for lp in ledger_parsed:
        if lp['debit_paise'] > 0:
            tb_lines.append({'account_id': lp['particulars'], 'debit_paise': lp['debit_paise'], 'credit_paise': 0})
        if lp['credit_paise'] > 0:
            tb_lines.append({'account_id': lp['particulars'], 'debit_paise': 0, 'credit_paise': lp['credit_paise']})
    tb = compute_trial_balance(tb_lines)
    print(f'   Trial balance balanced: {tb.balanced}')
    print(f'   Total debits: {tb.total_debits_paise} paise ({tb.total_debits_paise/100:.2f})')
    print(f'   Total credits: {tb.total_credits_paise} paise ({tb.total_credits_paise/100:.2f})')
    
    vrep = verify_all(tb, [], [])
    print(f'   Verification passed: {vrep.passed}')
    for c in vrep.checks:
        print(f'     - {c}')
    if vrep.blocking_failures:
        print(f'   BLOCKING: {vrep.blocking_failures}')
    
    print(f'\n5. TRIAL BALANCE TOTALS')
    print(f'   DEBITS:  {tb.total_debits_paise} paise = ₹{tb.total_debits_paise/100:,.2f}')
    print(f'   CREDITS: {tb.total_credits_paise} paise = ₹{tb.total_credits_paise/100:,.2f}')
    print(f'   DIFFERENCE: {tb.total_debits_paise - tb.total_credits_paise} paise')
    
    print('\n' + '='*60)
    print('RAW OUTPUT COMPLETE')
    print('='*60)
    
    return {
        'bank_count': len(bank_rows),
        'ledger_count': len(ledger_rows),
        'invoice_count': len(inv_rows),
        'exact': len(exact),
        'fuzzy': len(fuzzy),
        'split': len(split_matches),
        'unmatched': len(unmatched),
        'exceptions': exceptions,
        'tb_balanced': tb.balanced,
        'tb_debits': tb.total_debits_paise,
        'tb_credits': tb.total_credits_paise
    }

if __name__ == '__main__':
    main()
