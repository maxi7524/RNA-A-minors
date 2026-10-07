"""Bounded threaded/process workflows and selected-source deduplication."""

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from aminor_msa import DataStore
from aminor_msa.io.parallel import (
    SourceRequest,
    iter_loaded,
    iter_requests,
    read_request,
)
from aminor_msa.io.parallel.workers import _WorkerReportReader

from .support import write_dataset


def alignment_shape(store, request):
    """Prepare a small worker-local result instead of transferring an alignment.

    :param store: Worker store.
    :param request: Alignment request.
    :return: Sequence count and alignment length.
    :rtype: tuple[int,int]
    """
    alignment = read_request(store, request)
    return len(alignment.sequences), alignment.length


class ParallelTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        write_dataset(self.root)
        self.store = DataStore(self.root)

    def test_filters_kinds_and_shared_structure_deduplication(self):
        requests = list(
            iter_requests(self.store, kinds=("alignment", "coordinates", "dssr"))
        )
        self.assertEqual(sum(r.kind == "coordinates" for r in requests), 1)
        self.assertEqual(sum(r.kind == "dssr" for r in requests), 2)
        self.assertEqual(sum(r.kind == "alignment" for r in requests), 2)
        self.assertEqual(
            list(iter_requests(self.store, participant="olejnik", rna_type="rRNA")),
            [SourceRequest("alignment", "RF00001")],
        )
        self.assertEqual(
            list(iter_requests(self.store, families=["RF00002"])),
            [SourceRequest("alignment", "RF00002")],
        )

    def test_bounded_submission_and_input_order(self):
        consumed = []

        def requests():
            for number in range(8):
                consumed.append(number)
                yield SourceRequest(
                    "alignment", "RF00001" if number % 2 == 0 else "RF00002"
                )

        results = iter_loaded(self.store, requests(), workers=2, prefetch=2)
        first = next(results)
        self.assertEqual(consumed, [0, 1])
        self.assertEqual(first.request.accession, "RF00001")
        second = next(results)
        self.assertEqual(consumed, [0, 1, 2])
        self.assertEqual(second.request.accession, "RF00002")
        results.close()
        self.assertEqual(consumed, [0, 1, 2])

    def test_threaded_full_selected_workflow(self):
        requests = list(
            iter_requests(
                self.store, kinds=("alignment", "metadata", "cm", "coordinates", "dssr")
            )
        )
        results = list(iter_loaded(self.store, requests, workers=2, prefetch=2))
        self.assertEqual([r.request for r in results], requests)
        self.assertEqual(len(results), 9)
        self.assertEqual(
            next(r.data for r in results if r.request.kind == "coordinates")
            .structure[0]
            .num,
            7,
        )

    def test_worker_zip_is_reused_and_closed(self):
        created = []

        def create_reader(path):
            reader = _WorkerReportReader(path)
            created.append(reader)
            return reader

        requests = list(iter_requests(self.store, kinds=("dssr",)))
        original_open = zipfile.ZipFile
        with (
            patch(
                "aminor_msa.io.parallel.workers._WorkerReportReader",
                side_effect=create_reader,
            ),
            patch("zipfile.ZipFile", wraps=original_open) as opened,
        ):
            results = list(iter_loaded(self.store, requests, workers=1, prefetch=2))
        self.assertEqual(len(results), 2)
        # One directory index read and one reused worker-owned archive.
        self.assertEqual(opened.call_count, 2)
        self.assertEqual(len(created), 1)
        self.assertIsNone(created[0].archive)

    def test_worker_zip_closes_after_early_stop_or_failure(self):
        for fail in (False, True):
            with self.subTest(fail=fail):
                created = []

                def create_reader(path, readers=created):
                    reader = _WorkerReportReader(path)
                    readers.append(reader)
                    return reader

                requests = [
                    SourceRequest("dssr", "1abc", "1"),
                    SourceRequest("bad", "1abc"),
                ]
                with patch(
                    "aminor_msa.io.parallel.workers._WorkerReportReader",
                    side_effect=create_reader,
                ):
                    stream = iter_loaded(self.store, requests, workers=1, prefetch=1)
                    next(stream)
                    self.assertIsNotNone(created[0].archive)
                    if fail:
                        with self.assertRaises(ValueError):
                            next(stream)
                    else:
                        stream.close()
                self.assertIsNone(created[0].archive)

    def test_process_worker_transform(self):
        results = list(
            iter_loaded(
                self.store,
                iter_requests(self.store),
                workers=2,
                prefetch=2,
                backend="process",
                transform=alignment_shape,
            )
        )
        self.assertEqual([r.data for r in results], [(2, 6), (2, 6)])
        self.assertEqual([r.request.accession for r in results], ["RF00001", "RF00002"])

    def test_process_native_coordinates_transfer(self):
        results = list(
            iter_loaded(
                self.store,
                [SourceRequest("coordinates", "1abc")],
                workers=1,
                prefetch=1,
                backend="process",
            )
        )
        self.assertEqual(results[0].data.structure[0].num, 7)

    def test_process_complete_cif_transfer(self):
        requests = list(iter_requests(self.store, kinds=("cif",)))
        self.assertEqual(requests, [SourceRequest("cif", "1abc")])
        result = next(
            iter_loaded(self.store, requests, workers=1, prefetch=1, backend="process")
        )
        self.assertIn(
            "non-coordinate metadata",
            result.data.sole_block().find_value("_struct.title"),
        )

    def test_invalid_arguments_and_propagated_errors(self):
        for kwargs in ({"workers": 0}, {"prefetch": 0}, {"backend": "bad"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                list(iter_loaded(self.store, [], **kwargs))
        with self.assertRaises(ValueError):
            list(iter_requests(self.store, kinds=["bad"]))
        with self.assertRaises(ValueError):
            read_request(self.store, SourceRequest("bad", "RF00001"))
        with self.assertRaises(FileNotFoundError):
            list(iter_loaded(self.store, [SourceRequest("alignment", "RF99999")]))
