#!/usr/bin/env python3
"""Fills a presentation's slides from a text file, using a local LLM (LM Studio server).

Usage: fillslides <folder> [notes.txt]     (default: <folder>/slides.txt)

The notes file starts with optional header lines, then free text (Markdown is fine):
  mode: summarize   long, detailed notes: keep the bold ideas and quotes, drop the rest
  mode: exact       notes are the slides: reproduce them faithfully, only lay them out
  mode: expand      a few lines: build the talk; the LLM may add knowledge, marked // CHECK
  slides: 10        number of content slides (title/outline/section slides not counted)
  model: qwen2.5-14b-instruct

Slide breaks: lines of dashes (---, —---111---), or headings. Without them the LLM splits the ideas itself.
Replaces everything between "// ===== Content =====" and "= References" in main.typ (old file kept as main.typ.bak),
compiles, and if Typst fails or a slide overflows, sends the errors back to the LLM once to fix them.
Needs the LM Studio server: lms server start
"""
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from finish_doc import overflowing_slides

URL = "http://localhost:1234/v1/chat/completions"
DEFAULTS = {"mode": "summarize", "slides": "", "model": "qwen2.5-14b-instruct"}
CONTENT = "// ===== Content =====\n"
END = re.compile(r"^= References", re.M)
MODES = {
    "summarize": "The notes are long and detailed. Keep only the key ideas: bold phrases are the main points, and quotes "
                 "(text in “” or \"\") stay word for word. Use the surrounding text only as context. Do not add facts "
                 "that are not in the notes.",
    "exact": "The notes already are the slide content. Reproduce their wording faithfully; only choose layouts. "
             "Do not add, drop or rephrase content.",
    "expand": "The notes are only a few lines. Build a complete talk from them using your own knowledge. Put the "
              "comment `// CHECK` at the end of every line that states a fact not in the notes.",
}
SPEC = """You write ONE slide of a Typst slide deck from the notes for that slide. Output ONLY Typst markup for that
one slide, no ``` fences, no explanations. Write in this language: {lang}.

Allowed markup (nothing else, no #set, #let, #import or #show):
= Slide title                       exactly one, short (max ~8 words)
#kicker[29D]                        goes BEFORE the title: small label. ONLY if the notes start with a reference/section number; copy it. Usually omit
- point                             bullet; keep each to one line
+ point                             numbered list; #enum(numbering: "A", [..], [..]) for a lettered list
*bold*  _italic_                    emphasis (single asterisks, not **)
#quote(block: true)[“...”]          highlighted quote
#cols([...], [...])                 2 or 3 columns side by side, e.g. a comparison
#card[Heading][one or two short sentences]   boxed point; put 2-3 cards in #cols(...)
#takeaway[...]                      one closing sentence at the bottom of the slide
@key                                cite a source; only these keys exist: {keys}

The slide must fit on one 16:9 page: at most ~60 words, at most one #cols. Prefer layouts over plain bullets:
a contrast or comparison -> #cols of 2 cards; 2-3 reasons/steps -> #cols of 3 cards; a key quote -> #quote. In #cols/#card arguments, text goes inside [ ].
No LaTeX: write fractions as 2/3. Characters # $ @ < > \\ * _ that are plain text must be escaped with a backslash (e.g. 4\\*3, \\#1, \\$5).

Two example slides (each a separate answer):
#kicker[30C]
= ¿Uno o muchos mundos?
#cols(card[No: una especie][“Nada semejante a algo incompleto llegaría a ser bello”.], card[Sí: el viviente completo][Aquel del que los otros vivientes son partes.])
#takeaway[El universo es un ser viviente visible y único.]

= Tres razones
#quote(block: true)[“Los sólidos nunca son conectados por un solo término medio”]
#cols(card[Completo][Hecho de partes completas.], card[Único][Nada queda fuera.], card[Sin vejez][Nada lo ataca.])

{mode}
This is slide {i} of {n} in a talk titled "{title}".
"""
PLAN = """Split the notes into {count} for a talk. Output ONLY the slides, separated by a line containing only ---.
Each slide: first line its title, then the notes for that slide. Write in this language: {lang}.
{mode}
"""


def parse(notes):
    """Splits header lines (key: value, at the very top) from the notes body."""
    opts, lines = dict(DEFAULTS), notes.splitlines()
    while lines and (m := re.fullmatch(r"\s*(mode|slides|model)\s*:\s*(.*?)\s*", lines[0], re.I)):
        opts[m[1].lower()] = m[2]
        lines.pop(0)
    if opts["mode"] not in MODES:
        sys.exit(f"mode must be one of {', '.join(MODES)}, got {opts['mode']!r}")
    if opts["slides"] and not opts["slides"].isdigit():
        sys.exit(f"slides must be a number, got {opts['slides']!r}")
    return opts, "\n".join(lines).strip()


def blocks(notes):
    """Notes split at separator lines (only dashes, maybe with a number inside or a list number before, e.g. 1. —---111---), empty blocks dropped."""
    parts = re.split(r"^\s*(?:\d+\.)?\W*[-—–]{3,}[\d\s\-—–*]*$", notes, flags=re.M)
    return [b.strip() for b in parts if b.strip()]


def clean(reply, notes=None):
    """LLM reply -> Typst: drop ``` fences and <think>, fix the slips small models make often.
    With notes (one slide): keep a #kicker only if its text is in the notes, and put it before the title."""
    reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.S)
    reply = re.sub(r"^```\w*\n|\n?```\s*$", "", reply.strip())
    reply = re.sub(r"\*\*(.+?)\*\*", r"*\1*", reply)  # Markdown bold
    reply = re.sub(r"#quote\[block:\s*true\]", "#quote(block: true)", reply)
    reply = re.sub(r"#cols\[(\s*card\[[\s\S]*?\]\s*)\](?=[ \t]*$)", r"#cols(\1)", reply, flags=re.M)  # else cards print as text
    if notes is not None:
        kickers = re.findall(r"^#kicker\[(.*?)\]\s*$", reply, re.M)
        reply = re.sub(r"^#kicker\[.*\n?", "", reply, flags=re.M).strip()
        if kickers and kickers[0] and kickers[0] in notes:
            reply = f"#kicker[{kickers[0]}]\n{reply}"
    return reply.strip() + "\n"


def splice(typ, body):
    """Puts body in place of the content section of main.typ, keeping the preamble and the References slide."""
    start = typ.index(CONTENT) + len(CONTENT)
    end = m.start() if (m := END.search(typ, start)) else len(typ)
    return typ[:start] + body + ("\n" if end < len(typ) else "") + typ[end:]


def chat(model, messages):
    req = urllib.request.Request(URL, json.dumps({"model": model, "messages": messages, "temperature": 0.3}).encode(),
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            return json.load(r)["choices"][0]["message"]["content"]
    except OSError as e:
        sys.exit(f"cannot reach LM Studio at {URL} ({e}). Start it with: lms server start")


def problems(src):
    r = subprocess.run(["typst", "compile", str(src)], capture_output=True, text=True)
    if r.returncode:
        return [r.stderr.strip()]
    return overflowing_slides(src, src.read_text())


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    folder = Path(sys.argv[1])
    src = (folder / "main.typ").resolve()  # typst eval --in needs an absolute path
    notes_file = Path(sys.argv[2]) if len(sys.argv) == 3 else folder / "slides.txt"
    typ = src.read_text()
    if CONTENT not in typ or "<slide>" not in typ:
        sys.exit(f"{src} is not a presentation made by newdoc")
    opts, notes = parse(notes_file.read_text())
    keys = ", ".join(re.findall(r"^@\w+\{([^,\s]+),", typ, re.M)) or "(none: do not cite)"
    lang = m[1] if (m := re.search(r'#set text\(.*lang: "(\w+)"', typ)) else "same as the notes"
    title = m[1] if (m := re.search(r'^#let title = "(.*)"', typ, re.M)) else ""
    mode, model = MODES[opts["mode"]], opts["model"]
    shutil.copy(src, src.with_name("main.typ.bak"))

    if len(parts := blocks(notes)) > 1:  # the notes mark slide breaks: one slide per block
        if opts["slides"] and int(opts["slides"]) != len(parts):
            print(f"note: the notes have {len(parts)} blocks separated by dashes; making {len(parts)} slides, not {opts['slides']}")
    else:  # a list of ideas: let the LLM split it into slides first
        count = f"exactly {opts['slides']} slides" if opts["slides"] else "a sensible number of slides"
        print(f"asking {model} to plan {count}...", flush=True)
        parts = blocks(clean(chat(model, [{"role": "system", "content": PLAN.format(count=count, lang=lang, mode=mode)},
                                          {"role": "user", "content": notes}])))

    done, failed = [], []
    for i, part in enumerate(parts, 1):
        print(f"slide {i}/{len(parts)} ({model}, {opts['mode']})...", flush=True)
        messages = [{"role": "system", "content": SPEC.format(keys=keys, lang=lang, mode=mode, i=i, n=len(parts), title=title)},
                    {"role": "user", "content": part}]
        for attempt in (1, 2):
            reply = chat(model, messages)
            slide = clean(reply, part)
            heads = len(re.findall(r"^= ", slide, re.M))
            src.write_text(splice(typ, slide))
            issues = ([f"the answer must have exactly one '= Title' line, it has {heads}"] if heads != 1 else []) + problems(src)
            if not issues:
                break
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": "Fix these problems and output the whole slide again:\n" + "\n".join(issues)}]
        else:
            failed.append(i)
            slide = f"// FIXME: fill_slides could not make a clean slide {i}: {'; '.join(issues)}\n" + slide
        done.append(slide)

    src.write_text(splice(typ, "\n".join(done)))
    issues = problems(src)
    print("\n".join(issues) if issues else f"done: {src}")
    if failed:
        sys.exit(f"slides {failed} have problems (marked FIXME in main.typ); fix them by hand. The old file is main.typ.bak")
    if issues:
        sys.exit("the deck has the problems listed above; fix them by hand. The old file is main.typ.bak")
    print(f"now review it, then run: finishdoc {folder}")


if __name__ == "__main__":
    main()
