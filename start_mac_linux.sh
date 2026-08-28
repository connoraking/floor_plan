#!/usr/bin/env bash
set -e

FLOOR_PLAN_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$FLOOR_PLAN_DIR"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3.10 or newer is required. Install Python, then run this file again."
    exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "Floor Planner requires Python 3.10 or newer, but $(python3 --version 2>&1) was found."
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "Setting up Floor Planner for the first time..."
    if ! python3 -m venv .venv; then
        echo "The private Python environment could not be created."
        echo "On Debian or Ubuntu, install the python3-venv package and try again."
        exit 1
    fi
fi

if ! .venv/bin/python -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "The existing .venv uses an old or broken Python. Rename or remove .venv, then run this file again."
    exit 1
fi

if ! .venv/bin/python -c 'import hashlib, pathlib, sys; p=pathlib.Path("pyproject.toml"); m=pathlib.Path(".venv/.floor_planner_setup"); digest=hashlib.sha256(p.read_bytes()).hexdigest(); raise SystemExit(not (m.is_file() and m.read_text()==digest))'; then
    echo "Installing Floor Planner (the first setup requires internet and may take a few minutes)..."
    if ! .venv/bin/python -m pip install --disable-pip-version-check -e .; then
        echo "Setup did not finish. Check the internet connection, then run this file again."
        exit 1
    fi
    .venv/bin/python -c 'import hashlib, pathlib; p=pathlib.Path("pyproject.toml"); pathlib.Path(".venv/.floor_planner_setup").write_text(hashlib.sha256(p.read_bytes()).hexdigest())'
fi

if ! .venv/bin/python -m floor_planner; then
    echo "Floor Planner closed because of an error. The message above may explain what happened."
    exit 1
fi
