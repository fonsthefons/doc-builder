"""Checks fill_slides without an LLM: header parsing, reply cleanup, splicing, and that every layout compiles. Run: python3 test_fill_slides.py"""
import subprocess
import sys
import tempfile
from pathlib import Path

import fill_slides as fs

opts, body = fs.parse("Mode: exact\nslides: 4\n\n# Intro\ntext")
assert opts == {"mode": "exact", "slides": "4", "model": fs.DEFAULTS["model"]} and body == "# Intro\ntext", (opts, body)
assert fs.blocks("—---111---\n\nA\n---\nB *x*\n1. **—---6---**\nC") == ["A", "B *x*", "C"], fs.blocks("—---111---\nA")
assert fs.blocks("a - b\n- item") == ["a - b\n- item"]
assert fs.clean("#cols[\ncard[A][x.], \ncard[B][y.]\n]\n#takeaway[z]") == "#cols(\ncard[A][x.], \ncard[B][y.]\n)\n#takeaway[z]\n"
assert fs.clean("= T\n#kicker[29D]\n- **a** #quote[block: true][q]", "29D. notes") == "#kicker[29D]\n= T\n- *a* #quote(block: true)[q]\n"
assert fs.clean("#kicker[30E]\n= T", "29. notes") == "= T\n"
assert fs.clean("<think>hm</think>\n```typst\n= A\n- b\n```") == "= A\n- b\n"

BODY = """#section[Uno]
#kicker[29D – 30B]
= Comparación
#quote(block: true)[“Una cita breve”]
#cols(card[Bondad][Quiso que todo fuera bueno.], card[Orden][Del desorden al orden.], card[Inteligencia][En el alma.])
#takeaway[El universo es un viviente.]
= Conclusión
#enum(numbering: "A", [Uno *solo*], [4:6:9 y 4\\*3 @knuth1984])
"""
with tempfile.TemporaryDirectory() as tmp:
    for theme in ("clean", "academic", "dark"):
        r = subprocess.run([sys.executable, Path(__file__).with_name("new_doc.py")], input=f"presentation\n{theme}\n",
                           text=True, capture_output=True, cwd=tmp)
        assert r.returncode == 0, r.stderr
        src = next(p for p in Path(tmp).glob("*/main.typ") if theme in p.read_text())
        typ = src.read_text()
        out = fs.splice(typ, BODY)
        assert out.startswith(typ[:typ.index(fs.CONTENT)]) and "\n= References" in out and "lorem" not in out.split(fs.CONTENT)[1]
        src.write_text(out)
        assert fs.problems(src) == [], fs.problems(src)
        src.parent.rename(Path(tmp, f"done-{theme}"))
        print("ok", theme)
