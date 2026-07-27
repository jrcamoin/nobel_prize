import argparse
from pathlib import Path

from app.datasets import download_chembl_mic


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/raw/chembl_ab_mic.csv"))
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    output = download_chembl_mic(args.output, args.limit)
    print(output)


if __name__ == "__main__":
    main()
