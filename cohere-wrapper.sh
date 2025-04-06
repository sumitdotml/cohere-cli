#!/bin/bash

# Store the absolute path to the project directory by finding the script's real location
PROJECT_DIR=$(dirname "$(readlink -f "$0")")

# Export the project directory path so the Python script can find the .env file
export PROJECT_DIR

# Add the project directory to PYTHONPATH to ensure local modules are found
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# Path to the virtual environment
VENV_PATH="$PROJECT_DIR/.venv"

# Check if venv exists
if [ ! -d "$VENV_PATH" ]; then
  echo "Error: Virtual environment not found at $VENV_PATH" >&2
  exit 1
fi

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Run the client module directly using python -m
python -m cohere_cli.client

# Deactivate virtual environment when done
deactivate

# Unset PYTHONPATH if it was previously empty to avoid polluting the parent shell
# (This part is optional but good practice)
if [[ "$PYTHONPATH" == "$PROJECT_DIR:" ]]; then
  unset PYTHONPATH
elif [[ "$PYTHONPATH" == *":$PROJECT_DIR:"* ]]; then
  PYTHONPATH=${PYTHONPATH//:$PROJECT_DIR:/:}
elif [[ "$PYTHONPATH" == *":$PROJECT_DIR" ]]; then
  PYTHONPATH=${PYTHONPATH%:$PROJECT_DIR}
fi 