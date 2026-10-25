from tests.test_edge_cases import one_pair
from ledgerai.engine import run_engine
import tempfile
from pathlib import Path
tmp = Path(tempfile.mkdtemp())
b,l,i = one_pair(tmp, duplicate=True)
r = run_engine(b,l,i)
print(r.counts)
for m in r.matches:
    print(m['type'], m['bank'].line_id)
for e in r.exceptions:
    print(e['type'])
print('unmatched', len(r.unmatched_bank))
