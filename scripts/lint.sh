#!/usr/bin/env bash
# Lint and format code

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Activate virtual environment if exists
if [[ -d .venv ]]; then
    source .venv/bin/activate
fi

echo "Running ruff check..."
ruff check src/ tests/

echo "Running ruff format check..."
ruff format --check src/ tests/

echo "Running mypy..."
mypy src/

echo "All checks passed!"
