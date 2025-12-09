#!/bin/bash

set -e

# Ensure venv binaries are in PATH
export PATH="/.venv/bin:${PATH}"

# Also add /usr/local/bin for system tools
export PATH="${PATH}:/usr/local/bin"

echo "RAG Container is running!!!"

# If arguments are passed, execute them instead of starting the server
if [ $# -gt 0 ]; then
  echo "Executing command: $@"
  exec "$@"
fi

# Otherwise, start the server
if [ "${DEV}" = "1" ]; then
  echo "Running in DEV mode"
  # Development: auto-reload on code changes
  python rag.py --serve
else
  echo "Running in PROD mode"
  # Production: optimized settings
  python rag.py --serve
fi

