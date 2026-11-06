"""Checks fill_slides without an LLM: header parsing, splitting, slide checks, escaping, and that every layout compiles. Run: python3 test_fill_slides.py"""
import subprocess
import sys
import tempfile
from pathlib import Path

import fill_slides as fs

opts, body = fs.parse("Mode: exact\nslides: 4\n\n# Intro\ntext")
assert opts == {"mode": "exact", "slides": "4", "model": fs.DEFAULTS["model"]} and body == "# Intro\ntext", (opts, body)
assert fs.blocks("—---111---\n\nA\n---\nB *x*\n1. **—---6---**\nC") == ["A", "B *x*", "C"]
assert fs.blocks("a - b\n- item") == ["a - b\n- item"]

# check(): layout must fit the items; kickers must come from the notes.
two = [{"head": "A", "text": "x"}, {"head": "B", "text": "y"}]
assert fs.check({"layout": "cards", "items": two})["layout"] == "cards"
assert fs.check({"layout": "cards", "items": two * 2})["layout"] == "bullets"          # 4 cards don't fit
assert fs.check({"layout": "cards", "items": [{"head": "", "text": "x"}] * 2})["layout"] == "bullets"
assert fs.check({"layout": "quote", "quote": ""})["layout"] == "bullets"
assert fs.check({"layout": "nonsense", "title": " T\n "}) | {"items": []} == fs.check({"layout": "bullets", "title": "T"})
assert fs.check({"kicker": "30E"}, "29. notes")["kicker"] == "" and fs.check({"kicker": "29."}, "29. notes")["kicker"] == "29."
assert len(fs.check({"items": [{"head": "", "text": "x"}] * 9})["items"]) == fs.MAX_ITEMS

assert fs.tidy("Un universo  único*") == "Un universo único" and fs.tidy("*a* 4*3") == "*a* 4*3"

# esc(): everything literal except balanced *bold*.
assert fs.esc("*a b* 4*3 #x $5 @k // [y] = - +") == r"*a b* 4\*3 \#x \$5 \@k \/\/ \[y\] \= \- \+"

NASTY = "Ratio 4:6 = 6:9 (2/3), cost $5, #1, @nobody, a_b, <tag>, [x], \\, 4*3, - dash, // not a comment"
SLIDES = [
    {"layout": "section", "title": "Primera parte", "takeaway": "dropped"},
    {"layout": "cards", "kicker": "29D", "title": "Tres *razones*", "intro": NASTY, "takeaway": "El *universo* es uno.",
     "items": [{"head": "Bondad", "text": "Quiso que todo fuera *bueno*."}, {"head": "Orden", "text": NASTY},
               {"head": "Inteligencia", "text": "En el alma."}]},
    {"layout": "quote", "title": "Cita", "quote": "“Los sólidos nunca son conectados por un solo término medio”",
     "items": [{"head": "", "text": "Hacen falta dos."}]},
    {"layout": "steps", "title": "Conclusión", "items": [{"head": "A", "text": "Uno solo."}, {"head": "", "text": NASTY}]},
]
with tempfile.TemporaryDirectory() as tmp:
    for theme in ("clean", "academic", "dark"):
        r = subprocess.run([sys.executable, Path(__file__).with_name("new_doc.py")], input=f"presentation\n{theme}\n",
                           text=True, capture_output=True, cwd=tmp)
        assert r.returncode == 0, r.stderr
        src = next(p for p in Path(tmp).glob("docs/slides/*/main.typ") if theme in p.read_text()).resolve()
        typ = src.read_text()
        assert fs.write(src, typ, [fs.check(s, "29D notes") for s in SLIDES]) == [], src.read_text()
        out = src.read_text()
        assert out.startswith(typ[:typ.index(fs.CONTENT)]) and "\n= References" in out and "lorem" not in out.split(fs.CONTENT)[1]
        assert "#kicker[29D]" in out and "#section[Primera parte]" in out and "dropped" not in out
        src.parent.rename(Path(tmp, f"done-{theme}"))
        print("ok", theme)
