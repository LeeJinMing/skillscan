#!/bin/sh
# Zero-config local scan: install from repo and run
# Usage: ./scripts/quick-scan.sh [path]
# Or: pip install -e . && skillscan scan .
set -e
cd "$(dirname "$0")/.."
pip install -e . -q
skillscan scan "${1:-.}" -o .skillscan-out
echo "Report: .skillscan-out/report.json"
