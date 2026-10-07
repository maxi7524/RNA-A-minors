"""Full acquisition ordering and manifest preservation without external services."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from assets.scripts.download.cli.workflow import main
from assets.scripts.download.manifests.planning import build_plan
from assets.scripts.download.sources.drive import download_materials
from tests.download.support import write_supplied_sources


class _WorkflowFixture(unittest.TestCase):
    """Validate the default entry point across source and database stages."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "originals"
        self.data = self.root / "data"
        self.references = self.root / "references"
        write_supplied_sources(self.source)
        self.argv = [
            "download",
            "--data-root",
            str(self.data),
            "--reference-root",
            str(self.references),
            "--source-dir",
            str(self.source),
        ]


class WorkflowTests(_WorkflowFixture):
    """Validate the default entry point across source and database stages."""

    def test_default_builds_manifest_before_database_stage(
        self,
    ) -> None:
        stages = []

        def materials(*args):
            stages.append("sources")
            return download_materials(*args)

        def database(command, **kwargs):
            manifest = Path(command[command.index("--manifest") + 1])
            mapping = Path(command[command.index("--rfam-pdb") + 1])
            plan = build_plan(manifest, mapping)
            self.assertEqual({a.kind for a in plan}, {"seed", "cm", "metadata", "pdb"})
            stages.append("database")
            return SimpleNamespace(returncode=0)

        with (
            patch("sys.argv", self.argv),
            patch(
                "assets.scripts.download.cli.workflow.download_materials",
                side_effect=materials,
            ),
            patch(
                "assets.scripts.download.cli.workflow.subprocess.run",
                side_effect=database,
            ),
        ):
            main()
        self.assertEqual(stages, ["sources", "database"])
        with (self.data / "config/families.csv").open() as handle:
            self.assertEqual(next(csv.DictReader(handle))["rfam_acc"], "RF00001")

    def test_existing_user_manifest_is_preserved(self) -> None:
        download_materials(self.data, self.references, source_dir=self.source)
        manifest = self.data / "config/families.csv"
        content = "rfam_acc,download_pdb_structures\nRF00001,false\n"
        manifest.write_text(content)
        with (
            patch("sys.argv", self.argv),
            patch(
                "assets.scripts.download.cli.workflow.subprocess.run",
                return_value=SimpleNamespace(returncode=0),
            ),
            patch(
                "assets.scripts.download.cli.workflow.build_manifest",
                side_effect=AssertionError("Unexpected overwrite"),
            ),
        ):
            main()
        self.assertEqual(manifest.read_text(), content)

    def test_dry_run_has_no_source_side_effects(self) -> None:
        self.data.mkdir()
        manifest = self.data / "custom.csv"
        manifest.write_text("rfam_acc\nRF00001\n")
        with (
            patch("sys.argv", self.argv + ["--manifest", str(manifest), "--dry-run"]),
            patch(
                "assets.scripts.download.cli.workflow.subprocess.run",
                return_value=SimpleNamespace(returncode=0),
            ) as database,
            patch(
                "assets.scripts.download.cli.workflow.download_materials",
                side_effect=AssertionError("Unexpected sources"),
            ),
        ):
            main()
        self.assertIn("--dry-run", database.call_args.args[0])
        self.assertFalse(self.references.exists())
        self.assertEqual(list(self.data.iterdir()), [manifest])


class StageSelectionTests(_WorkflowFixture):
    """Exercise the single entry point's offline and explicitly selected stages."""

    def test_sources_stage_does_not_require_or_create_family_manifest(self):
        with (
            patch("sys.argv", self.argv + ["--stage", "sources"]),
            patch(
                "assets.scripts.download.cli.workflow.subprocess.run",
                side_effect=AssertionError("Unexpected database stage"),
            ),
        ):
            main()
        self.assertTrue((self.data / "config/sources.csv").is_file())
        self.assertFalse((self.data / "config/families.csv").exists())

    def test_manifest_stage_does_not_access_drive(self):
        download_materials(self.data, self.references, source_dir=self.source)
        with (
            patch("sys.argv", self.argv + ["--stage", "manifest"]),
            patch(
                "assets.scripts.download.cli.workflow.download_materials",
                side_effect=AssertionError("Unexpected Drive access"),
            ),
            patch(
                "assets.scripts.download.cli.workflow.subprocess.run",
                side_effect=AssertionError("Unexpected database stage"),
            ),
        ):
            main()
        self.assertTrue((self.data / "config/families.csv").is_file())

    def test_verify_skips_sources_and_manifest_updates(self):
        self.data.mkdir()
        manifest = self.data / "custom.csv"
        manifest.write_text("rfam_acc\nRF00001\n")
        with (
            patch("sys.argv", self.argv + ["--manifest", str(manifest), "--verify"]),
            patch(
                "assets.scripts.download.cli.workflow.download_materials",
                side_effect=AssertionError("Unexpected Drive access"),
            ),
            patch(
                "assets.scripts.download.cli.workflow.build_manifest",
                side_effect=AssertionError("Unexpected manifest edit"),
            ),
            patch(
                "assets.scripts.download.cli.workflow.subprocess.run",
                return_value=SimpleNamespace(returncode=0),
            ) as database,
        ):
            main()
        self.assertIn("--verify", database.call_args.args[0])
        self.assertEqual(list(self.data.iterdir()), [manifest])

    def test_auxiliary_stages_forward_arguments_and_exit_code(self):
        for stage in ("supplied", "checksums"):
            with (
                self.subTest(stage=stage),
                patch("sys.argv", self.argv + ["--stage", stage]),
                patch(
                    "assets.scripts.download.cli.workflow.subprocess.run",
                    return_value=SimpleNamespace(returncode=4),
                ) as command,
                self.assertRaises(SystemExit) as error,
            ):
                main()
            self.assertEqual(error.exception.code, 4)
            self.assertIn(
                "assets.scripts.download.cli." + stage, command.call_args.args[0]
            )

    def test_invalid_mode_combinations_fail_before_any_transfer(self):
        for args in (
            ["--dry-run", "--verify"],
            ["--stage", "sources", "--dry-run"],
            ["--stage", "manifest", "--verify"],
        ):
            with (
                self.subTest(args=args),
                patch("sys.argv", self.argv + args),
                patch(
                    "assets.scripts.download.cli.workflow.download_materials",
                    side_effect=AssertionError("Unexpected transfer"),
                ),
                self.assertRaises(SystemExit) as error,
            ):
                main()
            self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
