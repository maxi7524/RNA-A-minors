"""Independent checksum export checks on a complete miniature input tree."""

import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from assets.scripts.download.core.records import record_path
from assets.scripts.download.integrity.checksums import export_checksums
from assets.scripts.download.sources.supplied import SUPPLIED, import_source


class ChecksumTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "data"
        sources = Path(temporary.name) / "sources"
        sources.mkdir()
        for filename, artifact in SUPPLIED:
            source = sources / filename
            if artifact.kind == "dssr_zip":
                with zipfile.ZipFile(source, "w") as archive:
                    archive.writestr("1ABC.out1", "test report")
            elif filename == "Rfam.pdb":
                source.write_text("RF00001\t1abc\tA\t1\t2\t10\t1e-4\t1\t2\n")
            else:
                source.write_text("supplied assignment snapshot\n")
            import_source(source, self.root, artifact)
        (self.root / "config/families.csv").write_text(
            "rfam_acc,download_seed_alignment,download_covariance_model,download_family_metadata,download_pdb_structures\n"
            "RF00001,false,false,false,false\n"
        )

    @unittest.skipUnless(shutil.which("sha256sum"), "GNU sha256sum is unavailable")
    def test_export_and_independent_corruption_detection(self) -> None:
        self.assertEqual(export_checksums(self.root), 4)
        command = ["sha256sum", "--check", "--quiet", "downloads/checksums.sha256"]
        result = subprocess.run(
            command, cwd=self.root, capture_output=True, check=False
        )
        self.assertEqual(result.returncode, 0)
        (self.root / "rfam/raw/Rfam.pdb").write_text("corrupted")
        result = subprocess.run(
            command, cwd=self.root, capture_output=True, check=False
        )
        self.assertNotEqual(result.returncode, 0)

    def test_missing_expected_provenance_prevents_export(self) -> None:
        record_path(self.root, SUPPLIED[-1][1]).unlink()
        with self.assertRaises(ValueError):
            export_checksums(self.root)
        self.assertFalse((self.root / "downloads/checksums.sha256").exists())
