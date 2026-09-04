.PHONY: help setup reset weights doctor validate test fix clean

# Default target
help:
	@echo "Available commands:"
	@echo "  make setup      - Set up development environment (incremental)"
	@echo "  make reset      - Rebuild the environment from scratch (~1.1 GB reinstall)"
	@echo "  make weights    - Pre-download the Chatterbox model (~3.8 GB, once)"
	@echo "  make doctor     - Check this machine can actually render"
	@echo ""
	@echo "Development commands:"
	@echo "  make validate   - Validate examples/scenes.json against the schema"
	@echo "  make test       - Run linting, type checks, and tests"
	@echo "  make fix        - Auto-fix linting and formatting issues"
	@echo "  make clean      - Clean up cache files and test artifacts"
	@echo ""
	@echo "  make help       - Show this help message"

# Set up development environment
setup:
	@echo "Setting up development environment..."
	@bash setup_env.sh
	@$(MAKE) --no-print-directory weights
	@$(MAKE) --no-print-directory doctor

# Rebuild the environment from scratch
reset:
	@echo "Rebuilding environment from scratch..."
	@bash setup_env.sh --rebuild
	@echo "✓ Environment rebuilt (model weights kept in the shared HuggingFace cache)"

# Pull the checkpoints now rather than on the first render, so a 75-second
# model load two hours into a run does not look like a hang.
weights:
	@echo "Fetching Chatterbox Turbo weights (~3.8 GB on first run)..."
	@uv run python -c "from chatterbox.tts_turbo import ChatterboxTurboTTS as T; T.from_pretrained(device='cpu')" \
		> /dev/null 2>&1 && echo "✓ Weights ready" \
		|| { echo "❌ Weight download failed. Re-run 'make weights'"; exit 1; }

# Check this machine can actually render
doctor:
	@uv run narratr doctor

# Validate the example spec
validate:
	@uv run narratr validate examples/scenes.json

# Run linting, type checks, and tests
test:
	@echo "Formatting code with ruff..."
	@uv run ruff format .
	@echo "✓ Code formatted"
	@echo "\nRunning ruff linter..."
	@uv run ruff check .
	@echo "✓ Linting passed"
	@echo "\nRunning ruff formatter check..."
	@uv run ruff format --check .
	@echo "✓ Format check passed"
	@echo "\nRunning mypy type checks..."
	@uv run mypy narratr/
	@echo "✓ Type checks passed"
	@echo "\nRunning all tests..."
	@uv run pytest tests/ -v
	@echo "\n✓ All checks passed!"

# Auto-fix linting and formatting issues
fix:
	@echo "Auto-fixing code with ruff..."
	@echo "\n1. Formatting code..."
	@uv run ruff format .
	@echo "✓ Code formatted"
	@echo "\n2. Fixing linting issues..."
	@uv run ruff check --fix .
	@echo "✓ Auto-fixable linting issues resolved"
	@echo "\n✓ Fix complete! Run 'make test' to verify."

# Clean up cache files and test artifacts
clean:
	@echo "Cleaning up cache files and test artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleanup complete"
