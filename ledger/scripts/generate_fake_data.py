#!/usr/bin/env python3
"""Create the fake Indian company dataset used for all LedgerAI development.

Usage (from the project folder, with the virtual environment active):

    python scripts/generate_fake_data.py

Optional:

    python scripts/generate_fake_data.py --outdir data/fake --seed 42

Everything it writes is invented. Never put real client data in data/fake.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running this file directly without installing the package first.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from ledgerai.fake_data import generate_all  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate fake Indian accounting data")
    parser.add_argument("--outdir", default=str(REPO_ROOT / "data" / "fake"), help="Output folder")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (reproducible output)")
    args = parser.parse_args()

    truth = generate_all(args.outdir, seed=args.seed)

    print("=" * 64)
    print("LedgerAI fake data generated - ALL DATA IS FAKE")
    print("=" * 64)
    print(f"Company : {truth['company']['name']}")
    print(f"Period  : {truth['company']['period']}")
    print(f"Folder  : {Path(args.outdir).resolve()}")
    print()
    print(f"Bank transactions : {truth['counts']['bank_transactions']}")
    print(f"Ledger lines      : {truth['counts']['ledger_lines']}")
    print(f"Purchase invoices : {truth['counts']['purchase_invoices']}")
    print(f"Sales invoices    : {truth['counts']['sales_invoices']}")
    print()
    print("Deliberate messy cases:")
    for case in truth["cases"]:
        print(f"  - {case['type']}: {case['description']}")
    print()
    print("Open data/fake/ground_truth.json to see the expected answers.")
    print("=" * 64)


if __name__ == "__main__":
    main()
