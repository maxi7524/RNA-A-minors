"""Drive source routing, local restoration and resumable manifests."""

from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from assets.scripts.download.cli.workflow import main
from assets.scripts.download.core.records import record_path
from assets.scripts.download.sources.drive import (
    SOURCE_FOLDER,
    download_materials,
    route_material,
)
from assets.scripts.download.sources.supplied import SUPPLIED
from tests.download.support import write_supplied_sources


class SourceTests(unittest.TestCase):
    """Exercise source acquisition with verified small fixtures and mocked Drive."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "originals"
        self.data = self.root / "data"
        self.references = self.root / "assets/references"
        write_supplied_sources(self.source)

    def test_local_import_and_cached_reuse_need_no_drive_or_staging(self) -> None:
        result = download_materials(self.data, self.references, source_dir=self.source)
        self.assertEqual(result, {"downloaded": 0, "imported": 4, "reused": 0})
        shutil.rmtree(self.source)
        with patch(
            "assets.scripts.download.sources.drive._gdown",
            side_effect=AssertionError("Unexpected Drive"),
        ):
            reused = download_materials(
                self.data, self.references, folder_url=SOURCE_FOLDER
            )
        self.assertEqual(reused["reused"], 4)
        with (self.data / "config/sources.csv").open() as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(len(row["sha256"]) == 64 for row in rows))

    def test_pinned_canonical_snapshots_restore_missing_provenance_without_drive(
        self,
    ) -> None:
        download_materials(self.data, self.references, source_dir=self.source)
        for _, artifact in SUPPLIED:
            record_path(self.data, artifact).unlink()
        with patch(
            "assets.scripts.download.sources.drive._gdown",
            side_effect=AssertionError("Unexpected Drive"),
        ):
            result = download_materials(
                self.data, self.references, folder_url=SOURCE_FOLDER
            )
        self.assertEqual(result, {"downloaded": 0, "imported": 3, "reused": 1})

    def test_sources_cli_imports_materials_without_article_downloads(self) -> None:
        with (
            patch(
                "sys.argv",
                [
                    "download",
                    "--stage",
                    "sources",
                    "--data-root",
                    str(self.data),
                    "--reference-root",
                    str(self.references),
                    "--source-dir",
                    str(self.source),
                ],
            ),
            patch(
                "assets.scripts.download.sources.drive._gdown",
                side_effect=AssertionError("Unexpected HTTP"),
            ),
        ):
            main()
        self.assertTrue((self.data / "config/sources.csv").is_file())
        self.assertTrue((self.references / "AminorsMSA_Main.docx").is_file())

    def test_missing_drive_inputs_are_routed_and_imported_atomically(self) -> None:
        by_id = {
            artifact.url.split("/d/")[1].split("/")[0]: name
            for name, artifact in SUPPLIED
        }
        by_id["1ldhO9f8A3VH1H6uC1TY05Ez32zh7_08NauZ7ZgYYHHg"] = "AminorsMSA_Main.docx"

        def download(**kwargs):
            shutil.copyfile(self.source / by_id[kwargs["id"]], kwargs["output"])
            return kwargs["output"]

        transport = Mock()
        transport.download.side_effect = download
        with patch(
            "assets.scripts.download.sources.drive._gdown", return_value=transport
        ):
            result = download_materials(
                self.data, self.references, cookies_file=self.root / "cookies.txt"
            )
        self.assertEqual(result["downloaded"], 4)
        self.assertEqual(transport.download.call_count, 4)
        self.assertTrue(
            all(
                call.kwargs["use_cookies"] for call in transport.download.call_args_list
            )
        )
        self.assertFalse(list(self.root.rglob(".download-*")))
        self.assertTrue((self.references / "AminorsMSA_Main.docx").is_file())

    def test_folder_discovery_routes_other_materials_without_dropping_them(
        self,
    ) -> None:
        download_materials(self.data, self.references, source_dir=self.source)
        transport = Mock()
        transport.download_folder.return_value = [
            SimpleNamespace(id="notes", path="course/notes.txt")
        ]
        transport.download.side_effect = lambda **kwargs: Path(
            kwargs["output"]
        ).write_text("Course notes\n")
        with patch(
            "assets.scripts.download.sources.drive._gdown", return_value=transport
        ):
            result = download_materials(
                self.data,
                self.references,
                folder_url=SOURCE_FOLDER,
                refresh_sources=True,
            )
        self.assertEqual(result["downloaded"], 1)
        self.assertEqual(
            (self.references.parent / "materials/course/notes.txt").read_text(),
            "Course notes\n",
        )
        self.assertTrue(transport.download_folder.call_args.kwargs["skip_download"])

    def test_failed_drive_transfer_preserves_manifest_and_cleans_temporary_files(
        self,
    ) -> None:
        download_materials(self.data, self.references, source_dir=self.source)
        manifest = self.data / "config/sources.csv"
        before = manifest.read_bytes()
        (self.data / SUPPLIED[0][1].relative_path).unlink()
        transport = Mock()
        transport.download.side_effect = OSError("Interrupted")
        with (
            patch(
                "assets.scripts.download.sources.drive._gdown",
                return_value=transport,
            ),
            self.assertRaises(OSError),
        ):
            download_materials(self.data, self.references, folder_url=SOURCE_FOLDER)
        self.assertEqual(manifest.read_bytes(), before)
        self.assertFalse(list(self.root.rglob(".download-*")))

    def test_folder_paths_and_ambiguous_destinations_are_rejected(self) -> None:
        for name in ["../bad.txt", "/bad.txt", "a\\bad.txt"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                route_material(name, self.data, self.references)
        transport = Mock()
        transport.download_folder.return_value = [
            SimpleNamespace(id="a", path="one/paper.pdf"),
            SimpleNamespace(id="b", path="two/paper.pdf"),
        ]
        with (
            patch(
                "assets.scripts.download.sources.drive._gdown",
                return_value=transport,
            ),
            self.assertRaises(ValueError),
        ):
            download_materials(self.data, self.references, folder_url=SOURCE_FOLDER)
        transport.download.assert_not_called()


if __name__ == "__main__":
    unittest.main()
