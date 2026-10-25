from ledgerai.engine import run_engine
r = run_engine('data/test/bank_statement_oct2026.csv','data/test/ledger_tally_export_oct2026.csv','data/test/invoices_oct2026.csv')
print('MATCHES:')
for m in r.matches:
    print(m['type'], m['bank'].line_id, [l.line_id for l in m['ledgers']], 'diff='+str(m['difference_paise']), 'needs='+str(m['needs_approval']))
print('\nUNMATCHED BANK:')
for b in r.unmatched_bank:
    print(b.line_id, b.narration, abs(b.signed_paise))
print('\nUNMATCHED LEDGER:')
for l in r.unmatched_ledger:
    print(l.line_id, l.particulars, abs(l.signed_paise))
print('\nEXCEPTIONS:')
for e in r.exceptions:
    print(e['type'], e.get('bank_ids'), e.get('ledger_ids'), e.get('difference_paise'))
print('\nINVOICE ISSUES:')
for i in r.invoice_issues:
    print(i['type'], i.get('invoice_no'))
print('\nSUGGESTIONS:')
for k,v in r.invoice_suggestions.items():
    print(k, v['status'], v.get('invoice_no'))
