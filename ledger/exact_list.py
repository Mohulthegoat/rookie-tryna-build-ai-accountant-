from ledgerai.engine import run_engine
r = run_engine('data/test/bank_statement_oct2026.csv','data/test/ledger_tally_export_oct2026.csv','data/test/invoices_oct2026.csv')
print([m['bank'].line_id for m in r.matches if m['type']=='EXACT'])
print([m['bank'].line_id for m in r.matches if m['type']=='FUZZY'])
print([m['bank'].line_id for m in r.matches if m['type']=='SPLIT'])
print(r.counts)
