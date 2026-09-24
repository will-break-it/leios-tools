#!/usr/bin/env python3
"""Checks for the cross-matrix comparator, against the published evidence bundle."""
import csv
import importlib.util
import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent / 'docs/vote-diffusion-followup-20260915/evidence.tar.gz'

spec = importlib.util.spec_from_file_location('compare', HERE / 'compare-vote-matrices.py')
compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)


class Comparator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.matrix = Path(cls.temp.name) / 'vd2'
        cls.matrix.mkdir()
        with tarfile.open(BUNDLE) as archive:
            archive.extractall(cls.matrix, filter='data')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_compare(self, *matrices):
        output = Path(tempfile.mkdtemp())
        compare.main([*matrices, '--output', str(output)])
        with (output / 'comparison.csv').open() as stream:
            return list(csv.DictReader(stream)), output

    def test_published_arms_reproduce_their_traffic_and_timing(self):
        rows, output = self.run_compare(f'follow-up={self.matrix}')
        self.assertEqual(len(rows), 10)
        self.assertEqual({r['matrix'] for r in rows}, {'follow-up'})
        by_arm = {(r['transport'], r['cap'], r['protect_bp'], r['announce_request_bytes']): r
                  for r in rows}
        unrestricted = by_arm[('push', 'all', 'false', '8/8')]
        self.assertEqual(unrestricted['wire_gb'], '32.684092')
        self.assertEqual(unrestricted['relay_max_peak_mbit_s'], '60.649')
        self.assertEqual(unrestricted['q95_mean_s'], '3.334')
        protected = by_arm[('push', '8', 'true', '8/8')]
        self.assertEqual(protected['wire_gb'], '7.379686')
        self.assertEqual(protected['relay_max_peak_mbit_s'], '2.659')
        self.assertEqual(protected['q95'], '20/26')
        pull = by_arm[('announce-then-request', 'all', 'false', '8/8')]
        self.assertEqual(pull['relay_max_peak_mbit_s'], '9.144')
        self.assertEqual(pull['q95_mean_s'], '3.850')
        self.assertTrue((output / 'comparison.md').is_file())

    def test_unprotected_caps_lose_the_quorum_they_were_run_to_test(self):
        rows, _ = self.run_compare(str(self.matrix))
        unprotected = [r for r in rows if r['transport'] == 'push'
                       and r['cap'] != 'all' and r['protect_bp'] == 'false']
        self.assertEqual(len(unprotected), 3)
        for row in unprotected:
            self.assertEqual(row['q95'].split('/')[0], '0')
            self.assertEqual(row['q95_mean_s'], 'n/a')

    def test_logs_without_the_q75_observer_report_it_as_absent(self):
        rows, _ = self.run_compare(str(self.matrix))
        self.assertEqual({r['q75'] for r in rows}, {'n/a'})
        self.assertEqual({r['q75_mean_s'] for r in rows}, {'n/a'})

    def test_label_defaults_to_the_directory_name(self):
        rows, _ = self.run_compare(str(self.matrix))
        self.assertEqual({r['matrix'] for r in rows}, {'vd2'})

    def test_duplicate_labels_are_rejected(self):
        output = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError):
            compare.main([f'same={self.matrix}', f'same={self.matrix}',
                          '--output', str(output)])

    def test_csv_and_markdown_share_the_column_set(self):
        rows, output = self.run_compare(str(self.matrix))
        self.assertEqual(list(rows[0]), compare.COLUMNS)
        self.assertEqual(len(compare.COLUMNS), len(compare.HEADINGS))
        header = (output / 'comparison.md').read_text().splitlines()
        columns = [line for line in header if line.startswith('| Matrix |')][0]
        self.assertEqual(columns.count('|'), len(compare.HEADINGS) + 1)

    def test_a_matrix_without_captures_reports_rounded_bytes_and_no_peaks(self):
        copy = Path(tempfile.mkdtemp()) / 'no-capture'
        shutil.copytree(self.matrix, copy)
        (copy / 'vote-traffic-sha256.json').unlink()
        rows, _ = self.run_compare(str(copy))
        for row in rows:
            self.assertIn('rounded', row['wire_gb'])
            self.assertEqual(row['relay_max_peak_mbit_s'], 'n/a')
            self.assertEqual(row['bp_max_peak_mbit_s'], 'n/a')

    def test_an_incomplete_run_is_not_reported_as_a_result(self):
        copy = Path(tempfile.mkdtemp()) / 'incomplete'
        shutil.copytree(self.matrix, copy)
        with (copy / 'runs.csv').open() as stream:
            rows = list(csv.DictReader(stream))
            fields = list(rows[0])
        rows[0]['status'] = 'failed'
        with (copy / 'runs.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
        with self.assertRaises(Exception):
            self.run_compare(str(copy))

    def test_a_corrupted_capture_fails_its_checksum(self):
        copy = Path(tempfile.mkdtemp()) / 'corrupt'
        shutil.copytree(self.matrix, copy)
        name = next(iter(json.loads((copy / 'vote-traffic-sha256.json').read_text())))
        (copy / name).write_text('{}')
        with self.assertRaises(ValueError):
            self.run_compare(str(copy))


if __name__ == '__main__':
    unittest.main(verbosity=1)
