from ledgerai.engine import run_engine
r = run_engine('data/test/bank_statement_oct2026.csv','data/test/ledger_tally_export_oct2026.csv','data/test/invoices_oct2026.csv')
print(r.counts)
for m in r.matches:
    if 'AMAZON' in m['bank'].narration.upper():
        print('MATCH', m['type'], m['bank'].line_id, [l.line_id for l in m['ledgers']])
print('UNMATCHED')
for b in r.unmatched_bank:
    print(b.line_id, 'AMAZON' in b.narration.upper())
