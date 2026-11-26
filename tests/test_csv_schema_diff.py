import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from csv_schema_diff import compare, main, read_header

ROOT = Path(__file__).resolve().parents[1]


class HeaderTests(unittest.TestCase):
    def header(self, content, **kwargs):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.csv'
            path.write_bytes(content.encode('utf-8'))
            return read_header(path, **kwargs)

    def test_bom_crlf(self):
        self.assertEqual(self.header('\ufeffid,email\r\n1,x\r\n'), ['id', 'email'])

    def test_quoted_comma(self):
        self.assertEqual(self.header('id,"last, first"\n'), ['id', 'last, first'])

    def test_multiline_name(self):
        self.assertEqual(self.header('id,"long\nname"\n'), ['id', 'long\nname'])

    def test_semicolon(self):
        self.assertEqual(self.header('id;name\n', delimiter=';'), ['id', 'name'])

    def test_tab(self):
        self.assertEqual(self.header('id\tname\n', delimiter='\t'), ['id', 'name'])

    def test_pipe(self):
        self.assertEqual(self.header('id|name\n', delimiter='|'), ['id', 'name'])

    def test_empty_file(self):
        with self.assertRaisesRegex(ValueError, 'empty file'):
            self.header('')

    def test_blank_record(self):
        with self.assertRaisesRegex(ValueError, 'blank header'):
            self.header('\n')

    def test_empty_name(self):
        with self.assertRaisesRegex(ValueError, 'column name'):
            self.header('id,,name\n')

    def test_whitespace_name(self):
        with self.assertRaisesRegex(ValueError, 'column name'):
            self.header('id,   \n')

    def test_duplicate(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.header('id,id\n')

    def test_strip_collision(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.header('id, id \n', strip=True)

    def test_casefold_collision(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.header('Straße,STRASSE\n', ignore_case=True)

    def test_normalization_opt_in(self):
        self.assertEqual(self.header(' ID ,Name\n'), [' ID ', 'Name'])
        self.assertEqual(self.header(' ID ,Name\n', strip=True, ignore_case=True), ['id', 'name'])

    def test_malformed_quote(self):
        import csv
        with self.assertRaises(csv.Error):
            self.header('id,"unterminated\n')

    def test_header_only_not_rows(self):
        self.assertEqual(self.header('id,name\n"unterminated'), ['id', 'name'])


class ComparisonTests(unittest.TestCase):
    def test_identical(self):
        self.assertTrue(compare(['id', 'name'], ['id', 'name'])['compatible'])

    def test_added_default_fails(self):
        result = compare(['id'], ['id', 'name'])
        self.assertFalse(result['compatible'])
        self.assertEqual(result['added'], ['name'])

    def test_allow_added_anywhere(self):
        for actual in (['extra', 'id', 'name'], ['id', 'name', 'extra']):
            self.assertTrue(compare(['id', 'name'], actual, allow_added=True)['compatible'])

    def test_allow_added_still_rejects_missing(self):
        for actual in (['name'], ['name', 'extra']):
            self.assertFalse(compare(['id', 'name'], actual, allow_added=True)['compatible'])

    def test_order_policy_edges(self):
        for actual in (['name', 'id'], ['extra', 'name', 'id']):
            self.assertFalse(compare(['id', 'name'], actual, allow_added=True)['compatible'])
            self.assertTrue(compare(['id', 'name'], actual, allow_added=True, ignore_order=True)['compatible'])

    def test_rename_not_guessed(self):
        result = compare(['id', 'email'], ['id', 'email_address'])
        self.assertEqual(result['missing'], ['email'])
        self.assertEqual(result['added'], ['email_address'])
        self.assertFalse(result['reordered'])

    def test_report_order_deterministic(self):
        result = compare(['z', 'a', 'b'], ['c', 'd'])
        self.assertEqual(result['missing'], ['z', 'a', 'b'])
        self.assertEqual(result['added'], ['c', 'd'])


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'csv_schema_diff.py'), *map(str, args)],
                              capture_output=True, text=True, check=False)

    def test_pass_code_zero(self):
        result = self.run_cli(ROOT / 'examples/expected.csv', ROOT / 'examples/unchanged.csv')
        self.assertEqual(result.returncode, 0)
        self.assertIn('PASS:', result.stdout)

    def test_drift_json_code_one(self):
        result = self.run_cli(ROOT / 'examples/expected.csv', ROOT / 'examples/changed.csv', '--format', 'json')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['added'], ['email_address', 'region'])

    def test_missing_file_json_code_two(self):
        result = self.run_cli(ROOT / 'examples/expected.csv', ROOT / 'examples/absent.csv', '--format', 'json')
        self.assertEqual(result.returncode, 2)
        self.assertIn('error', json.loads(result.stdout))
        self.assertEqual(result.stderr, '')

    def test_unknown_encoding_json_code_two(self):
        result = self.run_cli(ROOT / 'examples/expected.csv', ROOT / 'examples/unchanged.csv',
                              '--encoding', 'not-a-real-codec', '--format', 'json')
        self.assertEqual(result.returncode, 2)
        self.assertIn('error', json.loads(result.stdout))

    def test_invalid_baseline_and_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            invalid = Path(folder) / 'duplicate.csv'
            invalid.write_text('id,id\n', encoding='utf-8')
            valid = ROOT / 'examples/expected.csv'
            for pair in ((invalid, valid), (valid, invalid)):
                result = self.run_cli(*pair, '--format', 'json')
                self.assertEqual(result.returncode, 2)
                self.assertIn('duplicate', json.loads(result.stdout)['error'])

    def test_bad_argument(self):
        result = self.run_cli('a', 'b', '--delimiter', 'guess')
        self.assertEqual(result.returncode, 2)
        self.assertIn('invalid choice', result.stderr)

    def test_non_utf8_error(self):
        with tempfile.TemporaryDirectory() as folder:
            invalid = Path(folder) / 'latin.csv'
            invalid.write_bytes(b'id,caf\xe9\n')
            result = self.run_cli(invalid, invalid, '--format', 'json')
            self.assertEqual(result.returncode, 2)
            self.assertIn('error', json.loads(result.stdout))
            result = self.run_cli(invalid, invalid, '--encoding', 'cp1252')
            self.assertEqual(result.returncode, 0)

    def test_control_characters_escaped_in_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'control.csv'
            path.write_text('"bad\x1b[31m",id\n', encoding='utf-8')
            result = self.run_cli(ROOT / 'examples/expected.csv', path)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn('\x1b', result.stdout)


if __name__ == '__main__':
    unittest.main()
