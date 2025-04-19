#!/bin/bash

# This script installs Python dependencies for the orchestrator.
# It should be run from the project's root directory (e.g., ./scripts/install_deps.sh)

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"
VENV_PATH="$PROJECT_ROOT/orchestrator/venv"
REQ_FILE="$PROJECT_ROOT/orchestrator/requirements.txt"

echo "[INFO] Attempting to install dependencies into virtual environment: $VENV_PATH"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "[ERROR] Virtual environment not found at $VENV_PATH."
    echo "[ERROR] Please run the Step 2 setup script first to create the venv."
    exit 1
fi

# Activate virtual environment
source "$VENV_PATH/bin/activate"
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to activate virtual environment at $VENV_PATH."
    exit 1
fi
echo "[INFO] Virtual environment activated."

# Check if requirements file exists
if [ ! -f "$REQ_FILE" ]; then
    echo "[ERROR] requirements.txt not found at $REQ_FILE."
    deactivate # Deactivate venv before exiting
    exit 1
fi

# Install dependencies
echo "[INFO] Running pip install -r $REQ_FILE ..."
pip install -r "$REQ_FILE"

# Check pip install status
INSTALL_STATUS=$?

# Deactivate virtual environment
deactivate
echo "[INFO] Virtual environment deactivated."

if [ $INSTALL_STATUS -eq 0 ]; then
  echo "[SUCCESS] Dependencies installed successfully."
else
  echo "[ERROR] Failed to install dependencies. Check pip output above for errors."
  exit 1
fi

exit 0
