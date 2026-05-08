#!/usr/bin/env bash
# Builds BiBudget into a single portable executable using PyInstaller.
# Requirements: Python 3.9+ with venv support (no Nix required).
# Output: dist/BiBudget
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.9 or newer and try again."
    exit 1
fi

echo "Python: $(python3 --version)"

# Create virtual environment on first run
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Activating virtual environment..."
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install pyinstaller -q

# Remove stale build artifacts so PyInstaller starts clean
rm -rf build dist BiBudget.spec

echo "Building BiBudget (this may take a minute)..."
pyinstaller \
    --onefile \
    --windowed \
    --name "BiBudget" \
    --icon "icons/money.png" \
    --add-data "icons:icons" \
    --add-data "themes:themes" \
    --add-data "bi_budget_desktop/migrations:bi_budget_desktop/migrations" \
    --hidden-import "dateutil.relativedelta" \
    run.py

echo ""
echo "Build complete!"
echo "  Executable : $SCRIPT_DIR/dist/BiBudget"
echo "  Database   : ~/.local/share/bi-budget/bi_budget.db  (created on first launch)"
echo ""
echo "Copy dist/BiBudget anywhere and run it — no installation needed."
