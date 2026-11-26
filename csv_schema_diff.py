#!/usr/bin/env python3
"""Compare CSV headers before an import. Python 3.10+, standard library only."""
import argparse
from collections import Counter
import csv
import json
import sys

__version__ = "1.0.0"


def read_header(path, delimiter=",", encoding="utf-8-sig", strip=False, ignore_case=False):
    with open(path, encoding=encoding, newline="") as stream:
        try:
            header = next(csv.reader(stream, delimiter=delimiter, strict=True))
        except StopIteration:
            raise ValueError("empty file: expected a header record") from None
    if not header:
        raise ValueError("blank header record")
    if strip:
        header = [value.strip() for value in header]
    if ignore_case:
        header = [value.casefold() for value in header]
    if any(not value.strip() for value in header):
        raise ValueError("empty or whitespace-only column name")
    duplicates = [name for name, count in Counter(header).items() if count > 1]
    if duplicates:
        raise ValueError("duplicate column names: " + json.dumps(duplicates, ensure_ascii=True))
    return header


def compare(expected, actual, allow_added=False, ignore_order=False):
    expected_set, actual_set = set(expected), set(actual)
    missing = [name for name in expected if name not in actual_set]
    added = [name for name in actual if name not in expected_set]
    # Compare relative order of shared columns; a permitted new column may be anywhere.
    reordered = ([name for name in expected if name in actual_set] !=
                 [name for name in actual if name in expected_set])
    compatible = not missing and (allow_added or not added) and (ignore_order or not reordered)
    return {"compatible": compatible, "missing": missing, "added": added,
            "reordered": reordered, "expected_columns": len(expected), "actual_columns": len(actual)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("expected", help="baseline CSV (its first record is the contract)")
    parser.add_argument("actual", help="incoming CSV to check")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--delimiter", choices=["comma", "semicolon", "tab", "pipe"], default="comma")
    parser.add_argument("--encoding", default="utf-8-sig", help="input encoding (default: UTF-8 with optional BOM)")
    parser.add_argument("--allow-added", action="store_true", help="permit extra columns; missing columns still fail")
    parser.add_argument("--ignore-order", action="store_true")
    parser.add_argument("--strip", action="store_true", help="strip leading/trailing header whitespace")
    parser.add_argument("--ignore-case", action="store_true", help="Unicode casefold names before comparison")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    delimiter = {"comma": ",", "semicolon": ";", "tab": "\t", "pipe": "|"}[args.delimiter]
    try:
        headers = [read_header(path, delimiter, args.encoding, args.strip, args.ignore_case)
                   for path in (args.expected, args.actual)]
        result = compare(*headers, args.allow_added, args.ignore_order)
        result["policy"] = {"allow_added": args.allow_added, "ignore_order": args.ignore_order,
                            "strip": args.strip, "ignore_case": args.ignore_case}
        code = 0 if result["compatible"] else 1
    except (OSError, UnicodeError, LookupError, csv.Error, ValueError) as error:
        result = {"compatible": False, "error": str(error)}
        code = 2
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    elif code == 2:
        print("ERROR: " + ascii(result["error"]), file=sys.stderr)
    else:
        print("PASS: CSV header contract satisfied" if code == 0 else "FAIL: CSV header contract changed")
        print("Missing: " + json.dumps(result["missing"], ensure_ascii=True))
        print("Added: " + json.dumps(result["added"], ensure_ascii=True))
        print("Shared columns reordered: " + str(result["reordered"]).lower())
    return code


if __name__ == "__main__":
    sys.exit(main())
