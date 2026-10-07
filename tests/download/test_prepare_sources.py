"""Supplied snapshots remain usable after duplicate staging files are removed."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from assets.scripts.download.cli.supplied import main
from assets.scripts.download.sources.supplied import SUPPLIED, import_source


class SuppliedSourceTests(unittest.TestCase):
    """Validate canonical reuse and actionable errors for absent inputs."""

    def test_default_reuses_canonical_files_without_staging_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data_root = root / "data"
            source = root / "source"
            source.mkdir()
            for filename, artifact in SUPPLIED:
                path = source / filename
                if artifact.kind == "dssr_zip":
                    with zipfile.ZipFile(path, "w") as archive:
                        archive.writestr("1abc.out", "DSSR report")
                else:
                    path.write_text("Supplied table snapshot\n")
                import_source(path, data_root, artifact)
                path.unlink()
            source.rmdir()
            with (
                patch("sys.argv", ["prepare_sources", "--data-root", str(data_root)]),
                patch(
                    "assets.scripts.download.cli.supplied.import_source",
                    side_effect=AssertionError("Unexpected copy"),
                ),
                self.assertLogs(
                    "assets.scripts.download.cli.supplied", level="INFO"
                ) as logs,
            ):
                main()
            self.assertEqual(sum(": verified" in line for line in logs.output), 3)

    def test_missing_source_exits_with_restore_url(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with (
                patch("sys.argv", ["prepare_sources", "--data-root", temporary]),
                self.assertLogs(
                    "assets.scripts.download.cli.supplied", level="WARNING"
                ) as logs,
                self.assertRaises(SystemExit) as error,
            ):
                main()
            self.assertEqual(error.exception.code, 1)
            self.assertTrue(
                all("drive.google.com/file/d/" in line for line in logs.output)
            )
            self.assertEqual(len(logs.output), 3)


if __name__ == "__main__":
    unittest.main()
