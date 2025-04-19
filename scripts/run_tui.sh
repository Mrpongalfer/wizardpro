#!/bin/bash

# This script runs the WizardPro TUI application.
# It should be run from the project's root directory (e.g., ./scripts/run_tui.sh)

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"
VENV_PATH="$PROJECT_ROOT/orchestrator/venv"
TUI_MODULE="orchestrator.tui.app"

echo "[INFO] Attempting to run WizardPro TUI ($TUI_MODULE)..."
cd "$PROJECT_ROOT" || { echo "[ERROR] Failed to cd to project root: $PROJECT_ROOT"; exit 1; }

# Check venv
if [ ! -d "$VENV_PATH" ]; then
    echo "[ERROR] Virtual environment not found at $VENV_PATH."
    exit 1
fi

# Activate venv
source "$VENV_PATH/bin/activate" || { echo "[ERROR] Failed to activate venv."; exit 1; }
echo "[INFO] Virtual environment activated."

# Check TUI app file exists
if [ ! -f "$PROJECT_ROOT/orchestrator/tui/app.py" ]; then
    echo "[ERROR] TUI app script not found at $PROJECT_ROOT/orchestrator/tui/app.py."
    deactivate
    exit 1
fi

# Run the TUI module
echo "[INFO] Executing: python -m $TUI_MODULE"
echo "--- TUI Output Start (Press Ctrl+C to exit TUI) ---"
python -m "$TUI_MODULE"
RUN_STATUS=$?
echo "--- TUI Output End ---"


# Deactivate venv
deactivate
echo "[INFO] Virtual environment deactivated."

if [ $RUN_STATUS -eq 0 ]; then
  echo "[SUCCESS] TUI script finished execution successfully."
else
  echo "[ERROR] TUI script exited with status $RUN_STATUS."
fi
exit $RUN_STATUS

