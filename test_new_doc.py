"""Generates every document preset and presentation theme (all defaults, plus extras), compiles them, and checks finishdoc. Run: python3 test_new_doc.py"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import new_doc

SCRIPT = Path(__file__).with_name("new_doc.py")
FINISH = Path(__file__).with_name("finish_doc.py")
# Answers are fed in prompt order; blank lines accept defaults and EOF accepts all the rest.
CASES = {p: f"document\n{p}\n" for p in new_doc.PRESETS}
CASES |= {f"slides-{t}": f"presentation\n{t}\n" for t in new_doc.THEMES}
CASES["report-extras"] = 'document\nreport\nMy "Quoted" Report\nSub\nAna, Bo\n\n\nen\nes,or\n' + "\n" * 20 + "y\ny\ny\nieee\n{logo}\nboth\n"
CASES["slides-extras"] = 'presentation\nacademic\nMy "Quoted" Talk\nSub\nAna, Bo\nSeminar\n\n\nen\nes,or\n4-3\n\n\n\nn\ny\nn\n\ny\nieee\n{logo}\nall\n'

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
        f = subprocess.run([sys.executable, FINISH, typ.parent], capture_output=True, text=True)
        assert f.returncode == 1 and "leftover template text" in f.stdout, f"{name}: finishdoc missed placeholders\n{f.stdout}"
        print("ok", name)

    # finishdoc on a finished doc: passes, then fails once a source goes uncited.
    clean = Path(tmp, "clean")
    clean.mkdir()
    bib = '#bibliography(bytes(```bib\n@book{k84,\n  author = {Knuth},\n  title = {T},\n  year = {1984},\n}\n```.text))'
    (clean / "main.typ").write_text(f"= Intro\nReal text, see @k84.\n{bib}\n")
    f = subprocess.run([sys.executable, FINISH, clean], capture_output=True, text=True)
    assert f.returncode == 0 and (clean / "clean.pdf").exists(), f.stdout + f.stderr
    (clean / "main.typ").write_text(f"= Intro\nReal text.\n{bib}\n")
    f = subprocess.run([sys.executable, FINISH, clean, "--pdfa"], capture_output=True, text=True)
    assert f.returncode == 1 and "never cited: k84" in f.stdout, f.stdout + f.stderr

    # Spellcheck: English typo flagged, Spanish passage checked in Spanish, dictionary.txt words accepted.
    (clean / "main.typ").write_text('#let es(body) = text(lang: "es", body)\nI recieve mail from Fonsworth. #es[Hola amigo] #es[grasias]\n')
    (clean / "dictionary.txt").write_text("Fonsworth\n")
    f = subprocess.run([sys.executable, FINISH, clean], capture_output=True, text=True)
    flagged = re.findall(r"spelling \((\w+)\): (\w+)", f.stdout)
    assert f.returncode == 1 and flagged == [("en", "recieve"), ("es", "grasias")], f.stdout + f.stderr
    print("ok finishdoc")

    # Presentations: a slide whose content doesn't fit is reported with its line; trimmed, it passes.
    talk = Path(tmp, "talk")
    talk.mkdir()
    r = subprocess.run([sys.executable, SCRIPT], input="presentation\nclean\nTalk\n\nAna\n", text=True, capture_output=True, cwd=talk)
    typ = talk / "talk" / "main.typ"
    head = typ.read_text().split("// ===== Content =====")[0]
    typ.write_text(head + "#section[Start]\n\n= Short\nFine.\n\n= Long\n#lorem(500)\n")
    f = subprocess.run([sys.executable, FINISH, typ.parent, "--no-spell"], capture_output=True, text=True)
    overflow = re.findall(r"main.typ:(\d+): slide overflows onto \d extra page\(s\), shorten it or split it: (.*)", f.stdout)
    line = typ.read_text().splitlines().index("= Long") + 1
    assert f.returncode == 1 and overflow == [(str(line), "= Long")], f.stdout + f.stderr
    typ.write_text(head + "#section[Start]\n\n= Short\nFine.\n\n= Long\nAlso fine.\n")
    f = subprocess.run([sys.executable, FINISH, typ.parent, "--no-spell"], capture_output=True, text=True)
    assert f.returncode == 0 and (talk / "talk" / "talk.pdf").exists(), f.stdout + f.stderr
    print("ok finishdoc slides")
