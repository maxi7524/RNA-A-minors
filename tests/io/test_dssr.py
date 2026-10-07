"""DSSR real-row fixtures, completeness and source identifier preservation."""

import io
import unittest

from aminor_msa.io import NucleotideId, parse_dssr

from .support import DSSR_SAMPLE


class DssrTests(unittest.TestCase):
    def test_verified_rows(self):
        report = parse_dssr(io.StringIO(DSSR_SAMPLE), source="6WLU.out1 excerpt")
        self.assertTrue(report.complete)
        self.assertEqual(len(report.base_pairs), 2)
        self.assertEqual(report.base_pairs[0].first.number, -4)
        self.assertEqual(report.base_pairs[0].leontis_westhof, "cWH")
        self.assertEqual(report.base_pairs[0].dssr, "cW+M")
        self.assertEqual([m.kind for m in report.aminor_motifs], ["I", "I", "X"])
        self.assertTrue(report.aminor_motifs[0].starred)
        self.assertEqual(report.aminor_motifs[0].donor.name, "G")
        self.assertEqual(report.aminor_motifs[1].first.number, 61)
        self.assertEqual(report.aminor_motifs[1].second.number, 82)
        self.assertEqual(report.raw_text, DSSR_SAMPLE)
        self.assertIn("k-turn", report.nucleotides[2].features)

    def test_short_long_and_insertion_identifiers(self):
        for token, expected in (
            ("1..AA.GTP.-2.A", (1, "AA", "GTP", -2, "A")),
            ("AA.GTP-2^A", (None, "AA", "GTP", -2, "A")),
            ("B.5MC12", (None, "B", "5MC", 12, "")),
        ):
            with self.subTest(token=token):
                identifier = NucleotideId.parse(token)
                self.assertEqual(
                    (
                        identifier.model,
                        identifier.chain,
                        identifier.name,
                        identifier.number,
                        identifier.insertion,
                    ),
                    expected,
                )
                self.assertEqual(identifier.raw, token)

    def test_invalid_identifiers(self):
        for token in ("bad", "1..A.A.foo.", "A.12"):
            with self.subTest(token=token), self.assertRaises(ValueError):
                NucleotideId.parse(token)

    def test_declared_counts_are_checked(self):
        for old, new in (
            ("List of 2 base pairs", "List of 3 base pairs"),
            ("List of 3 A-minor", "List of 4 A-minor"),
            ("features of 3 nucleotides", "features of 4 nucleotides"),
        ):
            with self.subTest(old=old), self.assertRaises(ValueError):
                parse_dssr(io.StringIO(DSSR_SAMPLE.replace(old, new)))

    def test_incomplete_output_is_not_a_negative_label(self):
        with self.assertLogs("aminor_msa.io.parsers.dssr", "WARNING"):
            report = parse_dssr(io.StringIO("no nucleotides found"))
        self.assertFalse(report.complete)
        self.assertEqual(report.aminor_motifs, ())

    def test_dot_bracket_and_chain_breaks(self):
        source = "Secondary structures in dot-bracket notation (dbn) as a whole and per chain\n>x [whole]\nAC&GU\n((&))\n"
        with self.assertLogs("aminor_msa.io.parsers.dssr", "WARNING"):
            report = parse_dssr(io.StringIO(source))
        self.assertEqual(report.dot_brackets[0].sequence, "AC&GU")
        for invalid in (
            source.replace("((&))", "((.))"),
            source.replace("((&))", "(.)"),
            source.replace("((&))", ""),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_dssr(io.StringIO(invalid))
