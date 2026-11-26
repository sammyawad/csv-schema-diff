# CSV schema diff: check CSV headers in CI before an import

A small, offline command-line tool for **CSV header drift**: missing columns,
unexpected columns, reordered columns, and duplicate header names. Python 3.10+
with **zero dependencies**. No account, network calls, or upload of your CSVs.

Use it when a supplier export, nightly report, or spreadsheet import must keep
the same column contract. It reads only the first CSV record, including quoted
commas and multiline column names. It does not inspect data rows, infer types,
validate row widths, or guess renamed columns: a rename is missing + added.

## Try it

```sh
git clone https://github.com/sammyawad/csv-schema-diff.git
cd csv-schema-diff
python csv_schema_diff.py examples/expected.csv examples/unchanged.csv
python csv_schema_diff.py examples/expected.csv examples/changed.csv --format json
```

The second command exits **1**, reporting `email` missing and `email_address`
and `region` added. No installation is required. On Windows, `py` can replace
`python`; on systems that name Python 3 `python3`, use that instead.

```json
{"actual_columns": 4, "added": ["email_address", "region"], "compatible": false, "expected_columns": 3, "missing": ["email"], "policy": {"allow_added": false, "ignore_case": false, "ignore_order": false, "strip": false}, "reordered": false}
```

## Policies and exit codes

Default: names and order must match exactly. UTF-8 BOM is accepted. The first
record must contain nonblank, unique names in **both** files. A header-only CSV
is a valid baseline. No delimiter sniffing or silent normalization occurs.

| Option | Behavior |
| --- | --- |
| `--allow-added` | Permit new columns anywhere; missing columns still fail. |
| `--ignore-order` | Permit reordering of shared columns. |
| `--strip` | Trim names before checking; collisions become invalid input. |
| `--ignore-case` | Unicode casefold names; collisions become invalid input. |
| `--delimiter semicolon` | Also accepts `comma` (default), `tab`, or `pipe`. |
| `--encoding cp1252` | Set the encoding of both inputs explicitly. |
| `--format json` | Machine-readable stdout, including input errors. |

Exit **0** = compatible under selected policy; **1** = schema drift;
**2** = unreadable/invalid header or invalid command arguments. Argument errors
use argparse's stderr output, even in JSON mode. Reordering reports the
relative order of shared columns. Adding a column alone is not reordering.

```sh
python csv_schema_diff.py contract.csv export.csv --allow-added --ignore-order
python csv_schema_diff.py contract.tsv export.tsv --delimiter tab --format json
```

Reports include column names and input-error paths; treat CI artifacts accordingly.
The files are opened read-only. Data rows are never included in reports.

## GitHub Actions example

After copying the script into your repository, check your export against a
committed header-only baseline. Pin third-party actions according to your own
repository policy; this tool has no runtime packages to install.

```yaml
name: CSV contract
on: [push, pull_request]
permissions:
  contents: read
jobs:
  schema:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: python csv_schema_diff.py examples/expected.csv examples/unchanged.csv
```

## Development

`ci-example.yml` contains a six-job Linux/Windows and Python version matrix.
Copy it to `.github/workflows/test.yml` in a repository with workflow write
permission to enable automated CI. This repository ships it as a template;
hosted CI has not been enabled.

```sh
python -m unittest discover -s tests -v
```

Parsing follows Python's standard-library [csv.reader](https://docs.python.org/3/library/csv.html#csv.reader)
with `newline=''` and strict CSV parsing for the header record. CSV field-size
limits follow the interpreter default. Invalid content after the header is
outside this check. For row-level reconciliation, use a row-diff tool instead.

MIT licensed. Issues and pull requests are welcome in this repository.
