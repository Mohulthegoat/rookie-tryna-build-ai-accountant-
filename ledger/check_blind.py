from ledgerai.ingest import read_csv_raw
from ledgerai.money import parse_amount
r,h = read_csv_raw('data/blind/blind_bank_statement_sep2026.csv')
print(h)
print(r[0])
print(r[-1])
