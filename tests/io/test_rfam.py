"""Rfam family metadata and first-model Infernal header parsing."""

import tempfile
import unittest
from pathlib import Path

from aminor_msa.io import read_covariance_model, read_family_metadata

from .support import write_dataset


class RfamTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        write_dataset(self.root)

    def test_metadata_retains_unknown_fields(self):
        metadata = read_family_metadata(self.root / "rfam/raw/RF00001/family.json")
        self.assertEqual(metadata.accession, "RF00001")
        self.assertEqual(metadata.payload["rfam"]["release"], {"number": 15})

    def test_first_cm_header_excludes_embedded_hmm(self):
        model = read_covariance_model(self.root / "rfam/raw/RF00001/model.cm")
        self.assertEqual(model.accession, "RF00001")
        self.assertEqual(model.consensus_length, 4)
        self.assertEqual(model.fields["COM"], ("first", "second"))
        self.assertTrue(model.path.exists())

    def test_invalid_metadata(self):
        path = self.root / "bad.json"
        for value in ("[]", '{"rfam":{"acc":"RF00001"}}'):
            path.write_text(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                read_family_metadata(path)

    def test_invalid_cm(self):
        path = self.root / "bad.cm"
        for value in (
            "HMMER3/f\n",
            "INFERNAL1/a\nACC RF00001\n",
            "INFERNAL1/a\nACC RF00001\nNAME x\nCLEN 0\nCM\n",
        ):
            path.write_text(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                read_covariance_model(path)
