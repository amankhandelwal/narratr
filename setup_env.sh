#!/bin/bash

# Exit on any error
set -e

# Ensure we're in the project directory
cd "$(dirname "$0")"

REBUILD="${1:-}"

# macOS on Apple Silicon is the only supported host: narration runs on MPS and
# the doctor checks are written against Homebrew. Fail here rather than let a
# Linux box report a green setup it cannot render with.
if [[ "$OSTYPE" != "darwin"* ]]; then
  echo "❌ Error: narratr only runs on macOS (Apple Silicon)"
  echo ""
  echo "Narration needs Metal (MPS); this host reports OSTYPE=$OSTYPE."
  echo "Run setup on a Mac."
  echo ""
  exit 1
fi

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

if ! command -v npm &> /dev/null; then
  echo "❌ Error: npm is not installed"
  echo ""
  echo "npm installs the scene renderer's dependencies. It ships with Node:"
  echo ""
  echo "  brew install node"
  echo ""
  exit 1
fi
echo "✓ npm found: $(npm --version)"

# Rebuild from scratch only when asked. A clean rebuild costs a ~1.1 GB
# reinstall, so `make setup` stays incremental and `make reset` opts in.
if [ "$REBUILD" = "--rebuild" ] && [ -d ".venv" ]; then
  echo "Removing existing virtual environment..."
  rm -rf .venv
  # uv.lock is deliberately kept. Deleting it would re-resolve every
  # dependency, so a "rebuild" would quietly install a different set of
  # versions than the one this project was verified against.
fi

# Sync the environment based on pyproject.toml
echo "Syncing environment..."
uv sync

# Install the renderer's Node dependencies. Without this the pipeline gets all
# the way through narration — around 100 minutes on a long video — before dying
# with "renderer not installed".
echo "Installing renderer dependencies..."
if [ -f "render/remotion/package-lock.json" ]; then
  (cd render/remotion && npm ci)
else
  (cd render/remotion && npm install)
fi
echo "✓ Renderer dependencies installed"

# Install pre-commit hooks. A fresh scaffold may not be a git repo yet,
# which is not a reason to fail the whole setup.
if git rev-parse --git-dir > /dev/null 2>&1; then
  echo "Installing pre-commit hooks..."
  uv run pre-commit install
else
  echo "⚠️  Not a git repository, skipping pre-commit hooks"
fi

echo "✓ Environment setup complete."
