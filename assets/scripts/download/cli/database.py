"""Database acquisition stage."""

from __future__ import annotations

import argparse
import logging
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

from aminor_msa.utils.files import write_json
from aminor_msa.utils.logging import get_custom_logger
from assets.scripts.download.core.config import ROOT
from assets.scripts.download.core.records import verify_artifact
from assets.scripts.download.core.transfer import acquire

from ..manifests.planning import build_plan

logger = get_custom_logger(__name__)


def main() -> None:
    """Run acquisition, read-only planning or offline verification.

    :return: None.
    :rtype: None
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "data/config/families.csv"
    )
    parser.add_argument(
        "--rfam-pdb", type=Path, default=ROOT / "data/rfam/raw/Rfam.pdb"
    )
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--participant", action="append")
    parser.add_argument("--family", action="append")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--verbose", action="store_true")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.workers < 1 or args.timeout <= 0 or args.retries < 0:
        parser.error(
            "workers and timeout must be positive; retries must be nonnegative"
        )
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    plan = build_plan(args.manifest, args.rfam_pdb, args.participant, args.family)
    logger.info("Planned artifacts: %s", dict(Counter(a.kind for a in plan)))
    if args.dry_run:
        return
    records = []
    last_progress = time.monotonic()
    if not args.verify:
        write_json(args.data_root / "downloads/plan.json", [asdict(a) for a in plan])
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        if args.verify:
            pending = {pool.submit(verify_artifact, args.data_root, a): a for a in plan}
        else:
            pending = {
                pool.submit(acquire, args.data_root, a, args.timeout, args.retries): a
                for a in plan
            }
        for future in as_completed(pending):
            records.append(future.result())
            if len(records) % 100 == 0 or time.monotonic() - last_progress >= 20:
                logger.info(
                    "Progress %s/%s: %s",
                    len(records),
                    len(plan),
                    dict(Counter(r["status"] for r in records)),
                )
                last_progress = time.monotonic()
    records.sort(key=lambda r: r["key"])
    counts = dict(Counter(r["status"] for r in records))
    logger.info("Final artifact statuses: %s", counts)
    if not args.verify:
        write_json(
            args.data_root / "downloads/last_run.json",
            {"counts": counts, "records": records},
        )
    for record in records:
        if record["status"] not in {"complete", "verified"}:
            logger.warning("%s: %s", record["key"], record["status"])
    if any(r["status"] not in {"complete", "verified"} for r in records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
