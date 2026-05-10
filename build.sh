#!/usr/bin/env bash
# Builds BiBudget into platform-specific portable executables.
#
#   Linux   — native build via venv + PyInstaller
#   Windows — cross-compile via Wine + PyInstaller
#
# Requirements:
#   Linux build : Python 3.9+
#   Windows build : Wine (wine64 or wine) + Windows Python installed under Wine
#
# Output:
#   dist/BiBudget-linux/BiBudget
#   dist/BiBudget-windows/BiBudget.exe
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  BiBudget - Multi-Platform Build"
echo "============================================"
echo ""

# ──────────────────────────────────────────────
# Clean stale artifacts before any build
# ──────────────────────────────────────────────
rm -rf build BiBudget.spec

# ══════════════════════════════════════════════
#  Linux Build  (native)
# ══════════════════════════════════════════════
echo "═══ [1/2] Building for Linux ═══"

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Cannot build Linux target."
    exit 1
fi

echo "Python: $(python3 --version)"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install pyinstaller -q

echo "Running PyInstaller for Linux..."
rm -rf dist/BiBudget-linux
pyinstaller \
    --onefile \
    --windowed \
    --name "BiBudget" \
    --icon "icons/money.png" \
    --add-data "icons:icons" \
    --add-data "themes:themes" \
    --add-data "bi_budget_desktop/migrations:bi_budget_desktop/migrations" \
    --hidden-import "dateutil.relativedelta" \
    --distpath "dist/BiBudget-linux" \
    run.py

deactivate
rm -rf build BiBudget.spec
echo "  \u2713 Linux executable: dist/BiBudget-linux/BiBudget"
echo ""

# ══════════════════════════════════════════════
#  Windows Build  (cross-compile via Wine)
# ══════════════════════════════════════════════
echo "═══ [2/2] Building for Windows ═══"

# Detect available wine command
WINE=""
for candidate in wine64 wine; do
    if command -v "$candidate" &>/dev/null; then
        WINE="$candidate"
        break
    fi
done

if [ -z "$WINE" ]; then
    echo "  SKIP: neither wine64 nor wine found."
    echo "  Install Wine (e.g. 'sudo pacman -S wine' on Arch/CachyOS)"
    echo ""
    echo "============================================"
    echo "  Build Complete (Linux only)"
    echo "============================================"
    echo "  Linux   : dist/BiBudget-linux/BiBudget"
    echo ""
    echo "  To build for Windows, install Wine and re-run."
    echo "============================================"
    exit 0
fi

echo "Wine: $WINE ($($WINE --version 2>/dev/null || echo 'unknown'))"

# Ensure Python for Windows is installed under Wine
PYTHON_WINE="$WINE python"
if ! $PYTHON_WINE --version &>/dev/null; then
    echo ""
    echo "  Python for Windows not found under Wine."
    echo "  Downloading and installing Python 3.11.9..."
    echo "  (This is a one-time setup, ~30MB download)"

    # xvfb-run helps with GUI installers on headless systems
    XVFB=""
    if command -v xvfb-run &>/dev/null; then
        XVFB="xvfb-run"
    fi

    PYTHON_URL="https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    INSTALLER="/tmp/python-3.11.9-amd64.exe"

    if [ ! -f "$INSTALLER" ]; then
        echo "  Downloading..."
        wget -q "$PYTHON_URL" -O "$INSTALLER"
    fi

    echo "  Installing (this may take a moment)..."
    $XVFB $WINE "$INSTALLER" /quiet \
        InstallAllUsers=1 PrependPath=1 TargetDir=C:\\Python311 || {
        echo "  ERROR: Python installation under Wine failed."
        echo "  Try running manually: $WINE $INSTALLER"
        exit 1
    }

    if ! $PYTHON_WINE --version &>/dev/null; then
        echo "  ERROR: Python installed but not found. Try adding to WINEPATH."
        exit 1
    fi
fi

echo "Python (Windows): $($PYTHON_WINE --version 2>/dev/null)"
echo ""

echo "Installing Windows dependencies..."
WINEDEBUG=-all $PYTHON_WINE -m pip install --upgrade pip -q
WINEDEBUG=-all $PYTHON_WINE -m pip install -r requirements.txt -q
WINEDEBUG=-all $PYTHON_WINE -m pip install pyinstaller -q

echo "Building Windows executable..."
rm -rf build BiBudget.spec dist/BiBudget-windows
WINEDEBUG=-all $WINE pyinstaller \
    --onefile \
    --windowed \
    --name "BiBudget" \
    --add-data "icons;icons" \
    --add-data "themes;themes" \
    --add-data "bi_budget_desktop/migrations;bi_budget_desktop/migrations" \
    --hidden-import "dateutil.relativedelta" \
    --distpath "dist/BiBudget-windows" \
    run.py

rm -rf build BiBudget.spec

echo "  \u2713 Windows executable: dist/BiBudget-windows/BiBudget.exe"
echo ""

# ──────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────
echo "============================================"
echo "  Build Complete"
echo "============================================"
echo "  Linux   : dist/BiBudget-linux/BiBudget"
echo "  Windows : dist/BiBudget-windows/BiBudget.exe"
echo ""
echo "  Copy either executable anywhere and run it."
echo "============================================"
