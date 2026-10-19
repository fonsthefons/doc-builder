"""Generates every preset (all defaults, plus one with extras) and compiles it with Typst. Run: python3 test_new_doc.py"""
import subprocess
import sys
import tempfile
from pathlib import Path

import new_doc

SCRIPT = Path(__file__).with_name("new_doc.py")
# Answers are fed in prompt order; blank lines accept defaults and EOF accepts all the rest.
CASES = {p: f"{p}\n" for p in new_doc.PRESETS}
CASES["report-extras"] = 'report\nMy "Quoted" Report\nSub\nAna, Bo\n\n\nen\nes,or\n' + "\n" * 20 + "y\ny\ny\nieee\n{logo}\nboth\n"

with tempfile.TemporaryDirectory() as tmp:
    logo = Path(tmp, "l.svg")
    logo.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>')
    for name, answers in CASES.items():
        cwd = Path(tmp, name)
        cwd.mkdir()
        r = subprocess.run([sys.executable, SCRIPT], input=answers.format(logo=logo), text=True, capture_output=True, cwd=cwd)
        assert r.returncode == 0, f"{name}: {r.stderr}"
        typ = next(cwd.glob("*/main.typ"))
        c = subprocess.run(["typst", "compile", typ], capture_output=True, text=True)
        assert c.returncode == 0, f"{name}: typst failed\n{c.stderr}\n--- {typ}\n{typ.read_text()}"
        print("ok", name)
