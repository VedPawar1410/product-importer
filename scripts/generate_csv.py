"""Generate a large synthetic product CSV for load-testing the importer.

    python scripts/generate_csv.py                      # 500,000 rows -> data/products-500k.csv
    python scripts/generate_csv.py --rows 10000 --out data/products-10k.csv

Rows look like `SKU-0000042,Product 42,Synthetic description ...` (the
sku,name,description format of the original assignment). Output is
deterministic, so every run produces the identical file used for the
measurements in the README. data/ is git-ignored: regenerate, don't commit.
"""

import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=int, default=500_000, help="number of products (default 500,000)")
    parser.add_argument("--out", type=Path, default=Path("data/products-500k.csv"), help="output CSV path")
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["sku", "name", "description"])
        for i in range(args.rows):
            writer.writerow([
                f"SKU-{i:07d}",
                f"Product {i}",
                f"Synthetic description for product number {i} with some realistic length text",
            ])

    print(f"Wrote {args.rows:,} rows to {args.out} ({args.out.stat().st_size / 1_048_576:.1f} MB)")


if __name__ == "__main__":
    main()
