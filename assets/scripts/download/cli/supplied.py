"""Supplied acquisition stage."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from aminor_msa.utils.logging import get_custom_logger
from assets.scripts.download.core.config import ROOT
from assets.scripts.download.core.records import verify_artifact

from ..sources.supplied import SUPPLIED, import_source

logger = get_custom_logger(__name__)


def main() -> None:
    """Import inputs or verify their recorded copies offline.

    :return: None.
    :rtype: None
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Directory containing supplied files to import; otherwise reuse canonical copies",
    )
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    records = []
    for filename, artifact in SUPPLIED:
        if args.verify or args.source_dir is None:
            record = verify_artifact(args.data_root, artifact)
        else:
            record = import_source(args.source_dir / filename, args.data_root, artifact)
        records.append(record)
        logger.info("%s: %s", artifact.key, record["status"])
        if record["status"] not in {"complete", "verified"}:
            logger.warning(
                "Restore %s from %s, then import with --source-dir DIRECTORY",
                filename,
                artifact.url,
            )
    if any(r["status"] not in {"complete", "verified"} for r in records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
