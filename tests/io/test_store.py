"""Lazy loading, catalogue relationships, LRU behavior and worker serialization."""

import pickle
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from aminor_msa import DataStore

from .support import write_dataset


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        write_dataset(self.root)
        self.store = DataStore(self.root)

    def test_construction_and_handle_lookup_do_not_open_files(self):
        with (
            patch("pathlib.Path.open", side_effect=AssertionError("unexpected read")),
            patch("zipfile.ZipFile", side_effect=AssertionError("unexpected ZIP open")),
        ):
            store = DataStore(self.root)
            family = store.family("rf00001")
            source = store.structure("1ABC")
            self.assertEqual(family.accession, "RF00001")
            self.assertEqual(source.pdb_id, "1abc")

    def test_links_deduplicate_pdb_but_preserve_chains(self):
        family = self.store.family("RF00001")
        with patch(
            "aminor_msa.io.sources.structure.read_structure",
            side_effect=AssertionError("coordinates loaded"),
        ):
            self.assertEqual([r.chain for r in family.mappings], ["AA", "B"])
            self.assertEqual([s.pdb_id for s in family.structures], ["1abc"])
            self.assertEqual(self.store.family("RF00002").structures[0].pdb_id, "1abc")

    def test_manifest_filters_and_row_copies(self):
        self.assertEqual(self.store.family_ids(participant="OLEJNIK"), ("RF00001",))
        self.assertEqual(self.store.family_ids(rna_type="rRNA"), ("RF00001",))
        self.assertEqual(self.store.family_ids(rna_type="Gene; rRNA"), ("RF00001",))
        self.assertEqual(
            self.store.family_ids(rna_type="riboswitch", participant="olejnik"), ()
        )
        self.assertEqual(
            self.store.family_ids(entry_type="family"), ("RF00001", "RF00002")
        )
        record = self.store.family_records()[0]
        record["rfam_acc"] = "bad"
        self.assertEqual(self.store.family_ids()[0], "RF00001")

    def test_archive_inventory_does_not_decompress_reports(self):
        with patch.object(
            zipfile.ZipFile,
            "open",
            side_effect=AssertionError("unexpected decompression"),
        ):
            reports = self.store.structure("1abc").reports
            self.assertEqual([r.variant for r in reports], ["1", "2"])

    def test_complete_cif_document_is_a_separate_lazy_read(self):
        source = self.store.structure("1abc")
        with patch(
            "aminor_msa.io.sources.structure.read_mmcif_document",
            side_effect=AssertionError("unexpected second representation"),
        ):
            self.assertEqual(source.coordinates.structure[0].num, 7)
        document = source.cif_document
        self.assertIn(
            "non-coordinate metadata", document.sole_block().find_value("_struct.title")
        )

    def test_selected_member_only_and_ambiguous_variant(self):
        source = self.store.structure("1abc")
        with self.assertRaises(ValueError):
            source.report()
        with self.assertRaises(KeyError):
            source.report(99)
        original = zipfile.ZipFile.open
        opened = []

        def tracked(archive, name, *args, **kwargs):
            opened.append(name)
            return original(archive, name, *args, **kwargs)

        with patch.object(zipfile.ZipFile, "open", tracked):
            report = source.report(2).read()
        self.assertEqual(opened, ["reports/1ABC.out2"])
        self.assertEqual(report.nucleotides[0].identifier.model, 1)
        self.assertEqual(source.report(2).variant, "2")

    def test_no_cache_by_default_and_lru_limit(self):
        first = self.store.family("RF00001").alignment
        second = self.store.family("RF00001").alignment
        self.assertIsNot(first, second)
        self.assertEqual(len(self.store._cache), 0)
        store = DataStore(self.root, cache_entries=2)
        first = store.family("RF00001").alignment
        _ = store.family("RF00001").metadata
        self.assertIs(store.family("RF00001").alignment, first)
        _ = store.family("RF00002").alignment
        self.assertEqual(
            list(store._cache), [("alignment", "RF00001"), ("alignment", "RF00002")]
        )
        store.clear_cache()
        self.assertEqual(len(store._cache), 0)

    def test_serialization_drops_parsed_state(self):
        store = DataStore(self.root, cache_entries=2)
        _ = store.family("RF00001").alignment
        _ = store.family("RF00001").structures
        _ = store.structure("1abc").reports
        store._dssr_reader = lambda member: None
        restored = pickle.loads(pickle.dumps(store))
        self.assertEqual(len(restored._cache), 0)
        self.assertFalse(restored.load_state()["pdb_catalogue_indexed"])
        self.assertFalse(restored.load_state()["zip_names_indexed"])
        self.assertIsNone(restored._dssr_reader)
        self.assertEqual(restored.family("RF00001").alignment.length, 6)

    def test_accession_mismatch_rejected(self):
        path = self.root / "rfam/raw/RF00001/family.json"
        path.write_text(path.read_text().replace("RF00001", "RF00002"))
        with self.assertRaises(ValueError):
            _ = self.store.family("RF00001").metadata

    def test_missing_and_invalid_sources(self):
        with self.assertRaises(FileNotFoundError):
            _ = self.store.family("RF99999").alignment
        for identifier in ("../../x", "rf1"):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                self.store.family(identifier)
        with self.assertRaises(ValueError):
            self.store.structure("../x")
        with self.assertRaises(ValueError):
            DataStore(self.root, cache_entries=-1)
