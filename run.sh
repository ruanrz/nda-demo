#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment in .venv ..."
  python3 -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate

echo "Installing dependencies ..."
python -m pip install -r requirements.txt

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo ""
  echo "OPENAI_API_KEY is not set in your shell."
  echo "You can still input it in the app sidebar after startup."
  echo ""
fi

echo "Starting Streamlit ..."
exec streamlit run demo_app.py
