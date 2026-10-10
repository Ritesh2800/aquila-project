#!/usr/bin/env bash
# One-time setup: Python packages, Zero-DCE++ weights and frontend packages.
set -e
cd "$(dirname "$0")"

command -v ffmpeg >/dev/null || echo "WARNING: ffmpeg is not installed. Install it (e.g. sudo apt install ffmpeg)."

python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt

[ -d Zero-DCE_extension ] || git clone https://github.com/Li-Chongyi/Zero-DCE_extension.git

cd frontend && npm install
echo "Setup done. Start with ./run_dev.sh"
