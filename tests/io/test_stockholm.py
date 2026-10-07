"""Stockholm contracts and invariance under block partition and row order."""

import io
import itertools
import unittest

from aminor_msa.io import parse_stockholm

from .support import STOCKHOLM_SAMPLE


class StockholmTests(unittest.TestCase):
    def test_annotations_and_interleaving(self):
        alignment = parse_stockholm(io.StringIO(STOCKHOLM_SAMPLE))
        self.assertEqual(alignment.sequences, {"seq1": "A-cU.G", "seq2": "AUCU-G"})
        self.assertEqual(alignment.length, 6)
        self.assertEqual(alignment.file_annotations["RN"], ("[1]", "[2]"))
        self.assertEqual(
            alignment.sequence_annotations["seq1"]["DE"],
            ("source description", "second description"),
        )
        self.assertEqual(alignment.residue_annotations["seq1"]["PP"], "9.87.6")
        self.assertEqual(alignment.column_annotations["SS_cons"], "(.<>.)")

    def test_partition_and_order_invariance(self):
        rows = {"seq1": "A-cU.G", "seq2": "AUCU-G"}
        annotation = "(.<>.)"
        for split in range(1, 6):
            for order in itertools.permutations(rows):
                with self.subTest(split=split, order=order):
                    chunks = ["# STOCKHOLM 1.0"]
                    for start, stop in ((0, split), (split, 6)):
                        chunks.extend(
                            f"{name} {rows[name][start:stop]}" for name in order
                        )
                        chunks.append(f"#=GC SS_cons {annotation[start:stop]}")
                    result = parse_stockholm(io.StringIO("\n".join(chunks + ["//"])))
                    self.assertEqual(result.sequences, rows)
                    self.assertEqual(result.column_annotations["SS_cons"], annotation)

    def test_invalid_inputs_rejected(self):
        cases = [
            STOCKHOLM_SAMPLE.replace("//", ""),
            STOCKHOLM_SAMPLE.replace("seq2 U-G", "seq2 UG"),
            STOCKHOLM_SAMPLE.replace("#=GC SS_cons >.)", "#=GC SS_cons >)"),
            STOCKHOLM_SAMPLE.replace("#=GR seq1 PP 7.6", "#=GR seq1 PP 76"),
            STOCKHOLM_SAMPLE.replace("#=GS seq1", "#=GS missing"),
            STOCKHOLM_SAMPLE + STOCKHOLM_SAMPLE,
            "# STOCKHOLM 1.0\n//\n",
        ]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(ValueError):
                parse_stockholm(io.StringIO(source))
