from ledgerai.engine import run_engine
r = run_engine('data/blind/blind_bank_statement_sep2026.csv','data/blind/blind_ledger_tally_sep2026.csv','data/blind/blind_invoices_sep2026.csv')
print(r.counts)
for m in r.matches:
    print(m['type'], m['bank'].line_id, [l.line_id for l in m['ledgers']])
print('UNB', len(r.unmatched_bank))
for b in r.unmatched_bank:
    print(b.line_id, b.narration)
print('UNL', len(r.unmatched_ledger))
for l in r.unmatched_ledger:
    print(l.line_id, l.particulars)
print('EXC')
for e in r.exceptions:
    print(e['type'])
print('INV')
for i in r.invoice_issues:
    print(i['type'])
print('SUG')
for k,v in r.invoice_suggestions.items():
    print(k,v['status'])
