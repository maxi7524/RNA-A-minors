"""Unit tests for the library's supplied Rfam catalogue parser."""

import tempfile
import unittest
from pathlib import Path

from aminor_msa.rfam_mapping import read_rfam_pdb


class RfamMappingTests(unittest.TestCase):
    def test_parse_mapping_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "Rfam.pdb"
            path.write_text(
                "RF00001\t1ABC\tAA\t-2\t121\t81.2\t1.1e-18\t1\t120\t00bac0\n"
            )
            records = read_rfam_pdb(path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].pdb_id, "1abc")
        self.assertEqual(records[0].chain, "AA")
        self.assertEqual(records[0].pdb_start, -2)
        self.assertEqual(records[0].cm_end, 120)
        self.assertEqual(records[0].extra, "00bac0")


if __name__ == "__main__":
    unittest.main()
