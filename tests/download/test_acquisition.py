"""Deterministic acquisition contracts with mocked external transport."""

from __future__ import annotations

import csv
import gzip
import http.client
import io
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from assets.scripts.download.core.models import Artifact
from assets.scripts.download.core.records import record_path, verify_artifact
from assets.scripts.download.core.transfer import acquire
from assets.scripts.download.core.validation import validate_artifact
from assets.scripts.download.manifests.families import build_manifest
from assets.scripts.download.manifests.planning import build_plan
from assets.scripts.download.sources.supplied import import_source


class AcquisitionTests(unittest.TestCase):
    """Verify selection and transactional acquisition using small fixtures."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifest = self.root / "families.csv"
        self.mapping = self.root / "Rfam.pdb"
        self.rows = [
            {
                "rfam_acc": "RF00001",
                "participant_id": "one",
                "download_pdb_structures": "true",
            },
            {
                "rfam_acc": "RF00002",
                "participant_id": "two",
                "download_pdb_structures": "false",
            },
        ]
        self.write_manifest()
        self.mapping.write_text(
            "RF00001\t1abc\tA\t1\t3\t10\t1e-5\t1\t3\textra\n"
            "RF00001\t1abc\tB\t1\t3\t10\t1e-5\t1\t3\textra\n"
            "RF00002\t2abc\tA\t1\t3\t10\t1e-5\t1\t3\textra\n"
        )
        self.artifact = Artifact(
            "test",
            "metadata",
            "RF00001",
            "https://example.org/test",
            "rfam/raw/test.json",
        )
        self.payload = json.dumps({"rfam": {"acc": "RF00001"}}).encode()

    def write_manifest(self) -> None:
        fields = sorted({key for row in self.rows for key in row})
        with self.manifest.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(self.rows)

    def response(self, content: bytes | None = None) -> io.BytesIO:
        result = io.BytesIO(self.payload if content is None else content)
        result.status = 200
        result.headers = {}
        result.url = self.artifact.url
        return result

    def test_pdb_deduplication_and_individual_flags(self) -> None:
        plan = build_plan(self.manifest, self.mapping)
        self.assertEqual([a.accession for a in plan if a.kind == "pdb"], ["1abc"])
        self.assertEqual(len(plan), 7)
        self.assertEqual(len({a.relative_path for a in plan}), len(plan))

    def test_catalogue_permutation_and_duplication_invariance(self) -> None:
        expected = build_plan(self.manifest, self.mapping)
        lines = self.mapping.read_text().splitlines(keepends=True)
        self.mapping.write_text("".join(reversed(lines + lines)))
        self.assertEqual(build_plan(self.manifest, self.mapping), expected)

    def test_participant_and_family_intersection(self) -> None:
        plan = build_plan(self.manifest, self.mapping, ["one"], ["RF00001"])
        self.assertEqual({a.accession for a in plan}, {"RF00001", "1abc"})
        with self.assertRaises(ValueError):
            build_plan(self.manifest, self.mapping, ["one"], ["RF00002"])

    def test_unknown_selection_is_rejected(self) -> None:
        for participants, families in [(["unknown"], None), (None, ["RF00003"])]:
            with (
                self.subTest(participants=participants, families=families),
                self.assertRaises(ValueError),
            ):
                build_plan(self.manifest, self.mapping, participants, families)

    def test_invalid_accession_and_flag_are_rejected(self) -> None:
        for key, value in [
            ("rfam_acc", "../RF00001"),
            ("download_pdb_structures", "yes"),
        ]:
            with self.subTest(key=key):
                original = self.rows[0][key]
                self.rows[0][key] = value
                self.write_manifest()
                with self.assertRaises(ValueError):
                    build_plan(self.manifest, self.mapping)
                self.rows[0][key] = original

    def test_minimal_tsv_configuration(self) -> None:
        path = self.root / "families.tsv"
        path.write_text("rfam_acc\nRF00001\n")
        self.assertEqual(len(build_plan(path, self.mapping)), 4)

    def test_dry_run_has_no_output_side_effects(self) -> None:
        output = self.root / "never_created"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "assets.scripts.download.cli.database",
                "--manifest",
                str(self.manifest),
                "--rfam-pdb",
                str(self.mapping),
                "--data-root",
                str(output),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("Planned artifacts", completed.stderr)
        self.assertFalse(output.exists())

    def test_manifest_preserves_duplicate_student_columns(self) -> None:
        source = self.root / "assignments.tsv"
        source.write_text(
            "Accession\tStudent\tStudent\tEntry type\tDescription\tName\tRNA type\tSeed sequences\tFull sequences\tSpecies\t3D structures\n"
            "RF00001\tStróżyk\tMax Bohdan\tFamily\tdescription\tname\tRNA\t2\t3\t4\t5\n",
            encoding="utf-8",
        )
        self.assertEqual(build_manifest(source, self.manifest), 1)
        with self.manifest.open() as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["participant_id"], "strozyk")
        self.assertEqual(row["student_surname"], "Stróżyk")
        self.assertEqual(row["student_given_names"], "Max Bohdan")
        with self.assertRaises(ValueError):
            build_manifest(source, self.manifest, "Unknown")

    def test_success_records_identity_and_integrity(self) -> None:
        with patch("urllib.request.urlopen", return_value=self.response()):
            result = acquire(self.root, self.artifact)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["bytes"], len(self.payload))
        self.assertEqual(
            verify_artifact(self.root, self.artifact)["status"], "verified"
        )

    def test_valid_resume_does_not_request_network(self) -> None:
        with patch("urllib.request.urlopen", return_value=self.response()):
            acquire(self.root, self.artifact)
        with patch("urllib.request.urlopen") as request:
            self.assertTrue(acquire(self.root, self.artifact)["resumed"])
            request.assert_not_called()

    def test_corrupted_file_is_detected_and_retrieved_again(self) -> None:
        with patch("urllib.request.urlopen", return_value=self.response()):
            acquire(self.root, self.artifact)
        (self.root / self.artifact.relative_path).write_bytes(b"corrupted")
        self.assertEqual(verify_artifact(self.root, self.artifact)["status"], "damaged")
        with patch("urllib.request.urlopen", return_value=self.response()) as request:
            self.assertEqual(acquire(self.root, self.artifact)["status"], "complete")
            request.assert_called_once()

    def test_missing_unrecorded_and_invalid_record(self) -> None:
        self.assertEqual(verify_artifact(self.root, self.artifact)["status"], "missing")
        destination = self.root / self.artifact.relative_path
        destination.parent.mkdir(parents=True)
        destination.write_bytes(self.payload)
        self.assertEqual(
            verify_artifact(self.root, self.artifact)["status"], "unrecorded"
        )
        provenance = record_path(self.root, self.artifact)
        provenance.parent.mkdir(parents=True)
        provenance.write_text("[]")
        self.assertEqual(verify_artifact(self.root, self.artifact)["status"], "damaged")

    def test_html_and_wrong_accession_are_not_published(self) -> None:
        for payload in [b"<html>error</html>", b'{"rfam":{"acc":"RF00002"}}', b"[]"]:
            with (
                self.subTest(payload=payload),
                patch("urllib.request.urlopen", return_value=self.response(payload)),
            ):
                with self.assertLogs(level="ERROR"):
                    self.assertEqual(
                        acquire(self.root, self.artifact, retries=0)["status"], "failed"
                    )
                self.assertFalse((self.root / self.artifact.relative_path).exists())
                self.assertFalse(list(self.root.rglob("*.part")))

    def test_transient_http_failure_is_retried(self) -> None:
        error = urllib.error.HTTPError(self.artifact.url, 503, "unavailable", {}, None)
        with patch(
            "urllib.request.urlopen", side_effect=[error, self.response()]
        ) as request:
            with patch("time.sleep"), self.assertLogs(level="WARNING"):
                self.assertEqual(
                    acquire(self.root, self.artifact, retries=1)["status"], "complete"
                )
            self.assertEqual(request.call_count, 2)

    def test_permanent_http_failure_is_not_retried(self) -> None:
        error = urllib.error.HTTPError(self.artifact.url, 404, "missing", {}, None)
        with (
            patch("urllib.request.urlopen", side_effect=error) as request,
            self.assertLogs(level="ERROR"),
        ):
            self.assertEqual(acquire(self.root, self.artifact)["status"], "failed")
            request.assert_called_once()

    def test_interrupted_transfer_removes_partial_file(self) -> None:
        response = self.response()
        response.read = unittest.mock.Mock(
            side_effect=http.client.IncompleteRead(b"partial")
        )
        with (
            patch("urllib.request.urlopen", return_value=response),
            self.assertLogs(level="ERROR"),
        ):
            self.assertEqual(
                acquire(self.root, self.artifact, retries=0)["status"], "failed"
            )
        self.assertFalse((self.root / self.artifact.relative_path).exists())
        self.assertFalse(list(self.root.rglob("*.part")))

    def test_interleaved_stockholm_and_annotation_lengths(self) -> None:
        artifact = Artifact("seed", "seed", "RF00001", "https://example.org", "test.gz")
        path = self.root / "test.gz"
        text = "# STOCKHOLM 1.0\n#=GF AC RF00001\na AC\nb A-\n#=GC SS_cons ..\na GU\nb GU\n#=GC SS_cons ..\n//\n"
        path.write_bytes(gzip.compress(text.encode()))
        self.assertEqual(validate_artifact(path, artifact)["alignment_columns"], 4)
        path.write_bytes(gzip.compress(text.replace("b GU", "b G").encode()))
        with self.assertRaises(ValueError):
            validate_artifact(path, artifact)

    def test_gzip_truncation_and_mmcif_identity(self) -> None:
        artifact = Artifact("pdb", "pdb", "1abc", "https://example.org", "test.gz")
        path = self.root / "test.gz"
        content = gzip.compress(b"data_1ABC\n_entry.id 1ABC\n")
        path.write_bytes(content)
        self.assertEqual(validate_artifact(path, artifact)["mmcif_data_block"], "1ABC")
        path.write_bytes(content[:-5])
        with self.assertRaises((EOFError, OSError)):
            validate_artifact(path, artifact)
        path.write_bytes(gzip.compress(b"data_2ABC\n"))
        with self.assertRaises(ValueError):
            validate_artifact(path, artifact)

    def test_covariance_model_identity(self) -> None:
        artifact = Artifact("cm", "cm", "RF00001", "https://example.org", "test.cm")
        path = self.root / "test.cm"
        path.write_text("INFERNAL1/a\nACC RF00001\n//\n")
        self.assertIn("model_header", validate_artifact(path, artifact))
        path.write_text("INFERNAL1/a\nACC RF00001\n//\nHMMER3/f\nACC RF00001\n//\n")
        self.assertIn("model_header", validate_artifact(path, artifact))
        path.write_text("INFERNAL1/a\nACC RF00002\n//\n")
        with self.assertRaises(ValueError):
            validate_artifact(path, artifact)

    def test_local_import_preserves_bytes_and_rejects_overwrite(self) -> None:
        source = self.root / "source.json"
        source.write_bytes(self.payload)
        import_source(source, self.root / "data", self.artifact)
        self.assertEqual(
            verify_artifact(self.root / "data", self.artifact)["status"], "verified"
        )
        source.write_bytes(b"different")
        with self.assertRaises(ValueError):
            import_source(source, self.root / "data", self.artifact)


if __name__ == "__main__":
    unittest.main()
