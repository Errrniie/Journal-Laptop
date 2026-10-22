#!/bin/bash

# Always launch relative to this script so moving the project does not break it.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || exit 1
cd "$SCRIPT_DIR" || exit 1

exec -a ernesto-journal "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/main.py"
