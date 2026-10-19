#!/usr/bin/env bash
# Installs Typst (if missing) and the `newdoc` and `finishdoc` commands. Safe to re-run.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/.local/bin"

command -v python3 >/dev/null || { echo "python3 is required: https://www.python.org/downloads/"; exit 1; }

if ! command -v typst >/dev/null; then
  if command -v brew >/dev/null; then
    brew install typst
  else
    echo "warning: Typst not found and Homebrew unavailable. Install it: https://github.com/typst/typst#installation"
  fi
fi

chmod +x "$DIR/new_doc.py" "$DIR/finish_doc.py"
mkdir -p "$BIN"
ln -sf "$DIR/new_doc.py" "$BIN/newdoc"
ln -sf "$DIR/finish_doc.py" "$BIN/finishdoc"

case ":$PATH:" in
  *":$BIN:"*) ;;
  *)
    RC="$HOME/.$(basename "${SHELL:-bash}")rc"
    LINE='export PATH="$HOME/.local/bin:$PATH"'
    grep -qxF "$LINE" "$RC" 2>/dev/null || echo "$LINE" >> "$RC"
    echo "Added ~/.local/bin to PATH in $RC — open a new terminal (or run: source $RC)."
    ;;
esac

echo "Installed. Run: newdoc  /  finishdoc   (add --help for details)"
