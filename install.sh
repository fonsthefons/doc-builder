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

if ! command -v aspell >/dev/null; then
  if command -v brew >/dev/null; then
    brew install aspell  # spellcheck for finishdoc; includes dictionaries for most languages
  else
    echo "warning: aspell not found; finishdoc will skip the spellcheck. Install it: http://aspell.net/"
  fi
fi

# ui.sh (the browser page) needs the control-panel engine next to this repo.
[ -d "$DIR/../control-panel" ] || git clone git@github.com:fonsthefons/control-panel.git "$DIR/../control-panel" \
  || echo "warning: could not clone control-panel; ./ui.sh will not work until it is in ../control-panel"

chmod +x "$DIR/ui.sh" "$DIR/new_doc.py" "$DIR/finish_doc.py" "$DIR/fill_slides.py"
mkdir -p "$BIN"
ln -sf "$DIR/new_doc.py" "$BIN/newdoc"
ln -sf "$DIR/finish_doc.py" "$BIN/finishdoc"
ln -sf "$DIR/fill_slides.py" "$BIN/fillslides"

case ":$PATH:" in
  *":$BIN:"*) ;;
  *)
    RC="$HOME/.$(basename "${SHELL:-bash}")rc"
    LINE='export PATH="$HOME/.local/bin:$PATH"'
    grep -qxF "$LINE" "$RC" 2>/dev/null || echo "$LINE" >> "$RC"
    echo "Added ~/.local/bin to PATH in $RC — open a new terminal (or run: source $RC)."
    ;;
esac

echo "Installed. Run: newdoc  /  fillslides  /  finishdoc   (add --help for details)"
cat <<'EOF'

Extra steps (by hand, only for what you use):
  • fillslides needs LM Studio (https://lmstudio.ai or brew install --cask lm-studio), opened once,
    and its model downloaded: ~/.lmstudio/bin/lms get qwen2.5-14b-instruct (or set `model:` in the notes file).
  • Live preview while editing: the "Tinymist Typst" extension in Cursor / VS Code.
  • Spellcheck in other languages: aspell includes most; check with `aspell dicts`.
EOF
