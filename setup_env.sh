#!/bin/bash

# Exit on any error
set -e

# Ensure we're in the project directory
cd "$(dirname "$0")"

REBUILD="${1:-}"

# Check for system dependencies (macOS only)
if [[ "$OSTYPE" == "darwin"* ]]; then
  echo "Checking for system dependencies..."

  if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv is not installed"
    echo ""
    echo "Install it with Homebrew:"
    echo ""
    echo "  brew install uv"
    echo ""
    exit 1
  fi
  echo "✓ uv found: $(uv --version)"

  if ! command -v ffmpeg &> /dev/null; then
    echo "❌ Error: ffmpeg is not installed"
    echo ""
    echo "ffmpeg stitches the rendered scenes together. Install it with:"
    echo ""
    echo "  brew install ffmpeg"
    echo ""
    exit 1
  fi
  echo "✓ ffmpeg found: $(ffmpeg -version | head -1 | cut -d' ' -f1-3)"

  if ! command -v node &> /dev/null; then
    echo "❌ Error: node is not installed"
    echo ""
    echo "The scene renderer needs Node 20 or newer. Install it with:"
    echo ""
    echo "  brew install node"
    echo ""
    exit 1
  fi
  echo "✓ node found: $(node --version)"
fi

# Rebuild from scratch only when asked. A clean rebuild costs a ~1.1 GB
# reinstall, so `make setup` stays incremental and `make reset` opts in.
if [ "$REBUILD" = "--rebuild" ] && [ -d ".venv" ]; then
  echo "Removing existing virtual environment..."
  rm -rf .venv
  rm -rf uv.lock
fi

# Sync the environment based on pyproject.toml
echo "Syncing environment..."
uv sync

# Install pre-commit hooks. A fresh scaffold may not be a git repo yet,
# which is not a reason to fail the whole setup.
if git rev-parse --git-dir > /dev/null 2>&1; then
  echo "Installing pre-commit hooks..."
  uv run pre-commit install
else
  echo "⚠️  Not a git repository, skipping pre-commit hooks"
fi

echo "✓ Environment setup complete."
