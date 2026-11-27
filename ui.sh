#!/usr/bin/env bash
# The same commands as help.sh, as task cards in a browser page (control-panel).
cd "$(dirname "$0")"
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
PYTHONPATH="$PWD/../control-panel/src${PYTHONPATH:+:$PYTHONPATH}" exec $PY -m control_panel --tasks ui.json "$@"
