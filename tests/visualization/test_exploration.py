"""Tables, bounded HTML, widget callbacks and explicit source-key audit."""

import contextlib
import io
import tempfile
import unittest
from dataclasses import replace
from importlib.util import find_spec
from pathlib import Path
from unittest.mock import Mock, patch

from aminor_msa import DataStore
from aminor_msa.io.parsers.dssr import NucleotideId
from aminor_msa.visualization import (
    AlignmentBrowser,
    FamilyBrowser,
    ViewStyle,
    annotations_table,
    atoms_table,
    dssr_tables,
    families_table,
    mappings_table,
    participants_table,
    residue_links_table,
    residues_table,
    sequences_table,
    structures_table,
    view_alignment,
    view_aminor_motif,
)
from tests.io.support import write_dataset


@unittest.skipUnless(
    find_spec("pandas") and find_spec("ipywidgets"), "Install the notebook extra"
)
class ExplorationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        write_dataset(self.root)
        self.store = DataStore(self.root)

    def test_catalogue_tables_are_lazy_and_keep_chain_rows(self):
        with patch(
            "aminor_msa.io.sources.structure.read_structure",
            side_effect=AssertionError("unexpected coordinates"),
        ):
            participants = participants_table(self.store)
            self.assertEqual(participants["families"].tolist(), [1, 1])
            self.assertEqual(
                families_table(self.store, participant="olejnik")["rfam_acc"].tolist(),
                ["RF00001"],
            )
            self.assertEqual(
                len(families_table(self.store, participant="absent").columns),
                len(self.store.family_records()[0]),
            )
            self.assertEqual(
                mappings_table(self.store.family("RF00001"))["chain"].tolist(),
                ["AA", "B"],
            )
            self.assertEqual(
                structures_table(self.store.family("RF00001"))[
                    "report_variants"
                ].tolist(),
                [("1", "2")],
            )
            self.assertEqual(self.store.load_state()["cached_objects"], 0)

    def test_sequence_counts_scopes_and_html_safety(self):
        alignment = self.store.family("RF00001").alignment
        summary = sequences_table(alignment)
        self.assertEqual(summary["gap_count"].tolist(), [2, 1])
        self.assertEqual(summary["ungapped_length"].tolist(), [4, 5])
        self.assertEqual(
            set(annotations_table(alignment)["scope"]), {"GF", "GS", "GR", "GC"}
        )
        alignment.sequences["<script>"] = alignment.sequences.pop(
            next(iter(alignment.sequences))
        )
        html = view_alignment(
            alignment, sequence_ids=["<script>"], start=1, stop=4
        ).data
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("[1, 4)", html)
        self.assertIn("#=GC SS_cons", html)
        for kwargs in (
            {"start": -1},
            {"start": 3, "stop": 2},
            {"stop": 7},
            {"style": ViewStyle(max_columns=2), "stop": 3},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                view_alignment(alignment, **kwargs)
        with self.assertRaises(KeyError):
            view_alignment(alignment, sequence_ids=["absent"])

    def test_structure_tables_preserve_namespaces_and_altlocs(self):
        data = self.store.structure("1abc").coordinates
        table = residues_table(data, model_number=7, chain="AA", limit=1)
        self.assertEqual(table.iloc[0]["number"], -2)
        self.assertEqual(table.iloc[0]["insertion"], "A")
        self.assertEqual(table.iloc[0]["label_chain"], "X")
        self.assertEqual(table.iloc[0]["label_number"], 1)
        record = next(data.iter_residues(model_number=7, chain="AA"))
        atoms = atoms_table(record)
        self.assertEqual(atoms["altloc"].tolist(), ["A", "B"])
        self.assertEqual(atoms["x"].tolist(), [1.0, 2.0])
        with self.assertRaises(ValueError):
            residues_table(data, limit=0)

    def test_identifier_audit_reports_misses_and_qualified_keys(self):
        data = self.store.structure("1abc").coordinates
        report = self.store.structure("1abc").report("1").read()
        original = report.nucleotides[0]
        matching = NucleotideId.parse("1..AA.GTP.-2.A")
        missing = NucleotideId.parse("1..AA.GTP.-99.A")
        qualified = NucleotideId.parse("1.op.AA.GTP.-2.A")
        report.nucleotides = tuple(
            replace(original, identifier=key) for key in (matching, missing, qualified)
        )
        with self.assertLogs(
            "aminor_msa.visualization.dssr.validation", level="WARNING"
        ):
            table = residue_links_table(data, report, model_number=7)
        self.assertEqual(table["status"].tolist(), ["matched", "missing", "unresolved"])
        self.assertEqual(table["dssr_model"].tolist(), [1, 1, 1])
        self.assertEqual(table["source_model"].tolist(), [7, 7, 7])
        self.assertEqual(table.iloc[0]["label_chain"], "X")
        with self.assertRaises(KeyError):
            residue_links_table(data, report, model_number=100)
        tables = dssr_tables(report)
        self.assertEqual(tables["nucleotides"].iloc[0]["identifier"], matching.raw)
        self.assertEqual(len(tables["aminor_motifs"]), len(report.aminor_motifs))
        report.nucleotides = ()
        self.assertIn("status", residue_links_table(data, report, model_number=7))

    def test_participant_and_type_callbacks_and_empty_subset(self):
        with contextlib.redirect_stdout(io.StringIO()):
            browser = FamilyBrowser(
                self.store, participant="olejnik_antonina", accession="RF00001"
            )
            self.assertEqual(browser.selected_family.accession, "RF00001")
            browser.participant.value = "janowiak_aleksander"
            self.assertEqual(
                browser.tables["families"]["rfam_acc"].tolist(), ["RF00002"]
            )
            self.assertEqual(browser.selected_family.accession, "RF00002")
            browser.rna_type.value = "rRNA"
            self.assertIsNone(browser.selected_family)
            self.assertEqual(list(browser.tables), ["families"])
            browser.participant.value = "olejnik_antonina"
            self.assertEqual(browser.selected_family.accession, "RF00001")
        self.assertEqual(self.store.load_state()["cached_objects"], 0)
        with self.assertRaises(ValueError):
            FamilyBrowser(self.store, participant="unknown")

    def test_alignment_controls_update_only_bounded_loaded_data(self):
        alignment = self.store.family("RF00001").alignment
        with contextlib.redirect_stdout(io.StringIO()):
            browser = AlignmentBrowser(
                alignment, style=ViewStyle(max_columns=3), start=1
            )
            browser.sequences.value = (next(iter(alignment.sequences)),)
            self.assertIn("1 / 2 sequences", browser.html.data)
            browser.window.value = (2, 4)
            self.assertIn("[2, 4)", browser.html.data)
            browser.window.value = (0, 6)
            self.assertIsNone(browser.html)
            browser.window.value = (0, 1)
            self.assertIsNotNone(browser.html)

    def test_motif_markers_use_resolved_coordinates_without_source_mutation(self):
        from aminor_msa.io.parsers.dssr import AMinorMotif

        data = self.store.structure("1abc").coordinates
        identifier = NucleotideId.parse("1..AA.GTP.-2.A")
        motif = AMinorMotif(
            identifier, identifier, identifier, "II", False, "source row"
        )
        viewer = Mock()
        before = data.structure.make_mmcif_document().as_string()
        with patch(
            "aminor_msa.visualization.structure.motifs.view_structure",
            return_value=viewer,
        ) as create:
            self.assertIs(view_aminor_motif(data, motif, model_number=7), viewer)
        create.assert_called_once_with(data, model_number=7, width=800, height=500)
        self.assertEqual(viewer.addSphere.call_count, 3)
        self.assertEqual(
            viewer.addSphere.call_args_list[0].args[0]["center"],
            {"x": 1.0, "y": 2.0, "z": 3.0},
        )
        self.assertEqual(before, data.structure.make_mmcif_document().as_string())
