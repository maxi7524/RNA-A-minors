"""Checksums acquisition stage."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from aminor_msa.utils.logging import get_custom_logger
from assets.scripts.download.core.config import ROOT

from ..integrity.checksums import export_checksums

logger = get_custom_logger(__name__)


def main() -> None:
    """Run checksum export after acquisition completes.

    :return: None.
    :rtype: None
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    export_checksums(args.data_root)


if __name__ == "__main__":
    main()
