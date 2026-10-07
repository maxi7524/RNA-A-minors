"""Restore source materials, prepare the manifest and acquire the configured data."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from aminor_msa.utils.logging import get_custom_logger

from ..core.config import ROOT
from ..manifests.families import build_manifest
from ..sources.drive import SOURCE_FOLDER, download_materials

logger = get_custom_logger(__name__)


def main() -> None:
    """Run the full acquisition workflow; preserve an existing edited manifest.

    :return: None.
    :rtype: None
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument(
        "--reference-root", type=Path, default=ROOT / "assets/references"
    )
    parser.add_argument("--source-folder", default=SOURCE_FOLDER)
    parser.add_argument("--drive-cookies", type=Path)
    parser.add_argument("--refresh-sources", action="store_true")
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--rfam-pdb", type=Path)
    parser.add_argument("--participant", action="append")
    parser.add_argument("--family", action="append")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--refresh-manifest", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--stage",
        choices=("all", "sources", "manifest", "database", "supplied", "checksums"),
        default="all",
    )
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if args.workers < 1 or args.timeout <= 0 or args.retries < 0:
        parser.error(
            "workers and timeout must be positive; retries must be nonnegative"
        )
    if args.dry_run and args.verify:
        parser.error("--dry-run and --verify are mutually exclusive")
    if args.dry_run and args.stage not in {"all", "database"}:
        parser.error("--dry-run applies to all or database")
    if args.verify and args.stage not in {"all", "database", "supplied"}:
        parser.error("--verify applies to all, database or supplied")
    manifest = args.manifest or args.data_root / "config/families.csv"
    if args.stage in {"supplied", "checksums"}:
        stage_args = [
            sys.executable,
            "-B",
            "-m",
            "assets.scripts.download.cli." + args.stage,
            "--data-root",
            str(args.data_root),
        ]
        if args.stage == "supplied":
            if args.source_dir is not None:
                stage_args.extend(["--source-dir", str(args.source_dir)])
            if args.verify:
                stage_args.append("--verify")
        raise SystemExit(subprocess.run(stage_args, cwd=ROOT, check=False).returncode)
    if not args.dry_run and not args.verify and args.stage in {"all", "sources"}:
        logger.info("Stage 1/3: supplied source materials")
        download_materials(
            args.data_root,
            args.reference_root,
            args.source_folder,
            args.source_dir,
            args.timeout,
            args.drive_cookies,
            args.refresh_sources,
        )
    if not args.dry_run and not args.verify and args.stage in {"all", "manifest"}:
        logger.info("Stage 2/3: family manifest")
        if not manifest.exists() or args.refresh_manifest:
            build_manifest(args.data_root / "config/rfam-family-student.tsv", manifest)
        else:
            logger.info("Keeping existing manifest: %s", manifest)
    if args.stage not in {"sources", "manifest"} and not manifest.exists():
        parser.error("An existing manifest is required; run --stage manifest first")

    if args.stage in {"sources", "manifest"}:
        return
    logger.info("Stage 3/3: Rfam and PDB database files")
    command = [
        sys.executable,
        "-B",
        "-m",
        "assets.scripts.download.cli.database",
        "--manifest",
        str(manifest),
        "--rfam-pdb",
        str(args.rfam_pdb or args.data_root / "rfam/raw/Rfam.pdb"),
        "--data-root",
        str(args.data_root),
        "--workers",
        str(args.workers),
        "--timeout",
        str(args.timeout),
        "--retries",
        str(args.retries),
    ]
    for option, values in [
        ("--participant", args.participant),
        ("--family", args.family),
    ]:
        for value in values or []:
            command.extend([option, value])
    if args.dry_run:
        command.append("--dry-run")
    if args.verify:
        command.append("--verify")
    if args.verbose:
        command.append("--verbose")
    database_result = subprocess.run(command, cwd=ROOT, check=False).returncode
    logger.info("Workflow finished: database_exit=%s", database_result)
    if database_result:
        raise SystemExit(database_result)


if __name__ == "__main__":
    main()
