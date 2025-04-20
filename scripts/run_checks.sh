#!/bin/bash
echo "--- Running Code Checks ---"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"
VENV_PATH="$PROJECT_ROOT/orchestrator/venv/bin/activate"
SOURCE_DIR="$PROJECT_ROOT/orchestrator"

# Activate venv
source "$VENV_PATH" || { echo "[ERROR] Failed to activate venv"; exit 1; }
echo "[INFO] Venv activated."

# Run Ruff (Linter + Formatter Check) - very fast!
echo "[INFO] Running Ruff check..."
ruff check "$SOURCE_DIR"
RUFF_STATUS=$?
echo "[INFO] Running Ruff format check..."
ruff format --check "$SOURCE_DIR"
RUFF_FORMAT_STATUS=$?

# Run MyPy (Type Checker)
echo "[INFO] Running MyPy check..."
mypy "$SOURCE_DIR"
MYPY_STATUS=$?

# Optional: Run Pytest later when we have tests
# echo "[INFO] Running Pytest..."
# pytest "$PROJECT_ROOT/tests" # Assuming tests are in /tests
# PYTEST_STATUS=$?

deactivate
echo "[INFO] Venv deactivated."

# Exit with non-zero code if any check failed
if [ $RUFF_STATUS -ne 0 ] || [ $RUFF_FORMAT_STATUS -ne 0 ] || [ $MYPY_STATUS -ne 0 ]; then
    echo "[ERROR] Code checks failed!"
    exit 1
else
    echo "[SUCCESS] All code checks passed!"
    exit 0
fi
