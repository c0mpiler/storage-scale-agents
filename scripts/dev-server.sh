#!/usr/bin/env bash
# Development server startup script

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Check for .env file
if [[ ! -f .env ]]; then
    echo "Warning: .env file not found. Using defaults."
    echo "Copy .env.example to .env and configure as needed."
fi

# Check for virtual environment
if [[ ! -d .venv ]]; then
    echo "Creating virtual environment..."
    uv venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
uv pip install -e ".[dev]"

# Start the server
echo "Starting Scale Agents server..."
exec python -m scale_agents.server
