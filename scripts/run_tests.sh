#!/usr/bin/env bash
# IIP Test Runner

set -e

echo "Running IIP Platform Tests..."
python -m pytest -v --cov=iip --cov-report=term-missing "$@"

echo ""
echo "Tests completed!"
