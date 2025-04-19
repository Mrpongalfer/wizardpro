#!/bin/bash

# This script runs the main WizardPro orchestrator using 'python -m'.
# It should be run from the project's root directory (e.g., ./scripts/run_wizardpro.sh)
# Optional: Pass initial request as arguments: ./scripts/run_wizardpro.sh "My project idea"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"
VENV_PATH="$PROJECT_ROOT/orchestrator/venv"
# Note: We run FROM the project root, so python finds the 'orchestrator' package
PYTHON_MODULE="orchestrator.main"

echo "[INFO] Attempting to run WizardPro Orchestrator as module ($PYTHON_MODULE)..."
cd "$PROJECT_ROOT" || { echo "[ERROR] Failed to cd to project root: $PROJECT_ROOT"; exit 1; }


# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "[ERROR] Virtual environment not found at $VENV_PATH."
    echo "[ERROR] Please run setup steps first (Step 2 and install_deps.sh)."
    exit 1
fi

# Activate virtual environment
source "$VENV_PATH/bin/activate"
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to activate virtual environment at $VENV_PATH."
    exit 1
fi
echo "[INFO] Virtual environment activated."

# Check if main python module can be conceptually found (basic check)
# A more robust check might try 'python -m $PYTHON_MODULE --help' if applicable
if [ ! -f "$PROJECT_ROOT/orchestrator/main.py" ]; then
    echo "[ERROR] Main script not found at $PROJECT_ROOT/orchestrator/main.py."
    deactivate
    exit 1
fi

# Run the main python module
# Pass any arguments passed to this bash script along to the python script
echo "[INFO] Executing: python -m $PYTHON_MODULE \"\$@\""
echo "--- Orchestrator Output Start ---"
python -m "$PYTHON_MODULE" "$@" # Use -m flag
RUN_STATUS=$? # Capture Python's exit status
echo "--- Orchestrator Output End ---"


# Deactivate virtual environment
deactivate
echo "[INFO] Virtual environment deactivated."

# Check the captured exit status from the python script
if [ $RUN_STATUS -eq 0 ]; then
  echo "[SUCCESS] Orchestrator script finished execution successfully (Python Exit Code 0)."
  exit 0 # Exit bash script with success code
else
  echo "[ERROR] Orchestrator script execution failed (Python Exit Code $RUN_STATUS). Check output above for errors."
  exit $RUN_STATUS # Exit bash script with Python's non-zero exit code
fi
