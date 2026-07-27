import argparse
from pathlib import Path

from app.datasets import download_coadd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/raw/coadd_complete_r03.zip"))
    args = parser.parse_args()
    print(download_coadd(args.output))


if __name__ == "__main__":
    main()
