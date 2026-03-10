#!/usr/bin/env python3
"""Validate report.json against schema/report-v1.json. Exit 0 on success."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "report-v1.json"


def main() -> int:
    report_path = Path.cwd() / "report.json"
    if len(sys.argv) > 1:
        report_path = Path(sys.argv[1])
    if not report_path.is_file():
        print(f"Report not found: {report_path}", file=sys.stderr)
        return 1
    if not SCHEMA_PATH.is_file():
        print(f"Schema not found: {SCHEMA_PATH}", file=sys.stderr)
        return 1

    import jsonschema
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(report, schema)
    except jsonschema.ValidationError as e:
        print(f"Schema validation failed: {e}", file=sys.stderr)
        return 1
    print("Schema validation OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
