#!/usr/bin/env bash
# Run tests with coverage

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Activate virtual environment if exists
if [[ -d .venv ]]; then
    source .venv/bin/activate
fi

# Run pytest with coverage
exec pytest \
    --cov=scale_agents \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    -v \
    "$@"
