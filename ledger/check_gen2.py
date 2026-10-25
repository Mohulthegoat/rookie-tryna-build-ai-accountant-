from tests.dataset_gen import make_dataset
from ledgerai.engine import run_engine
for seed in [0,18,19]:
    d = make_dataset(seed, 'D:/t'+str(seed), shuffle=seed%4==0)
    r = run_engine(d['bank'], d['ledger'], d['invoices'])
    print(seed, d['counts']['normal_matches'], r.counts['normal_matches'], d['counts'])
