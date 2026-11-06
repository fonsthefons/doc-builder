#!/usr/bin/env python3
"""Fills a presentation's slides from a notes file, using a local LLM (LM Studio server).

  fillslides <folder> [notes.txt]   notes (default <folder>/slides.txt) -> <folder>/slides.json -> main.typ
  fillslides <folder> --build       main.typ from <folder>/slides.json again, without the LLM (after editing it)

The notes file starts with optional header lines, then free text (Markdown is fine):
  mode: summarize   long, detailed notes: keep the bold ideas and quotes, drop the rest
  mode: exact       notes are the slides: reproduce them faithfully, only lay them out
  mode: expand      a few lines: build the talk; the LLM may add knowledge, marked (?) on the slide
  slides: 10        number of content slides, when the notes have no slide breaks
  model: qwen2.5-14b-instruct

Slide breaks: lines of dashes (---, —---111---). Without them the LLM first splits the ideas into slides.
The LLM answers each slide as JSON (layout, kicker, title, intro, quote, items, takeaway); this script checks it,
saves slides.json, and writes the Typst. Replaces everything between "// ===== Content =====" and "= References"
in main.typ (old file kept as main.typ.bak). A slide that still overflows after one retry is marked FIXME.
Needs LM Studio. The script starts its server and loads the model if needed, and stops only what it started.
"""
import argparse
import contextlib
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
LAYOUTS = ["bullets", "cards", "steps", "quote", "section"]
MAX_ITEMS = 6
MODES = {
    "summarize": "The notes are long and detailed. Keep only the key ideas: bold phrases are the main points, and quotes "
                 "(text in “” or \"\") stay word for word. Use the surrounding text only as context. Do not add facts "
                 "that are not in the notes.",
    "exact": "The notes already are the slide content. Reproduce their wording faithfully; only choose the layout. "
             "Do not add, drop or rephrase content.",
    "expand": "The notes are only a few lines. Build the slide using your own knowledge. End every sentence that "
              "states a fact not in the notes with (?) so the author checks it.",
}
STR = {"type": "string"}
SLIDE_SCHEMA = {"type": "object", "additionalProperties": False,
                "required": ["layout", "kicker", "title", "intro", "quote", "items", "takeaway"],
                "properties": {"layout": {"type": "string", "enum": LAYOUTS}, "kicker": STR, "title": STR, "intro": STR,
                               "quote": STR, "takeaway": STR,
                               "items": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                         "required": ["head", "text"], "properties": {"head": STR, "text": STR}}}}}
PLAN_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["slides"],
               "properties": {"slides": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                              "required": ["title", "notes"], "properties": {"title": STR, "notes": STR}}}}}
SPEC = """You design ONE slide of a talk titled "{title}" (slide {i} of {n}) from the notes for that slide.
Answer in JSON. Write all text in this language: {lang}. Empty string "" for any field you don't use.

layout: bullets  2-{max} short points (items[].text; head "")
        cards    2-3 points side by side, each with a short heading (items[].head + items[].text): for a contrast,
                 a comparison (2 cards) or 2-3 reasons/properties (3 cards)
        steps    2-{max} points in order: an argument, a process, a conclusion list (items[].text)
        quote    one key quote from the notes in "quote", optionally 1-3 bullets in items
        section  a divider slide for a new part of the talk: title only
kicker:   a reference or section number ONLY if the notes give one (e.g. "29D"); copy it exactly. Usually ""
title:    max ~8 words
intro:    optional one-line lead under the title
takeaway: optional one closing sentence
Keep it short: the whole slide must fit on one 16:9 page, about 60 words. Item text max ~15 words.
If the notes are already a list of points (A, B, C... or 1, 2, 3...), keep every point, one item each, as steps
or bullets. Mark key words with *single asterisks*. Plain text only otherwise: no Markdown, no LaTeX (write 2/3).
{mode}
"""
PLAN = """Split the notes into {count} for a talk. Answer in JSON: for each slide a title and the notes for it
(copied from the notes, or for a short brief the content you propose). Write in this language: {lang}.
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


def tidy(v):
    """Whitespace collapsed; an odd number of * means a stray one: drop the stars not between digits (4*3 stays)."""
    v = " ".join(str(v or "").split())
    loose = r"(?<!\d)\*|\*(?!\d)"
    return re.sub(loose, "", v) if len(re.findall(loose, v)) % 2 else v


def check(slide, notes=None):
    """Makes an LLM slide consistent: trims fields, fits the layout to the items, drops a kicker not found in the notes."""
    s = {k: tidy(slide.get(k)) for k in ("layout", "kicker", "title", "intro", "quote", "takeaway")}
    s["items"] = [{"head": tidy(it.get("head")), "text": tidy(it.get("text"))}
                  for it in slide.get("items") or [] if isinstance(it, dict)]
    s["items"] = [it for it in s["items"] if it["text"] or it["head"]][:MAX_ITEMS]
    if notes is not None and s["kicker"] and s["kicker"] not in notes:
        s["kicker"] = ""
    if s["layout"] not in LAYOUTS:
        s["layout"] = "bullets"
    if s["layout"] == "cards" and not (2 <= len(s["items"]) <= 3 and all(it["head"] for it in s["items"])):
        s["layout"] = "bullets"
    if s["layout"] == "quote" and not s["quote"]:
        s["layout"] = "bullets"
    if s["layout"] == "section":
        s.update(kicker="", intro="", quote="", takeaway="", items=[])
    return s


def esc(text):
    """Plain text -> Typst markup: every special character escaped, except balanced *bold*."""
    text = re.sub(r"([\\#$@<>_`~\[\]/=+\-*])", r"\\\1", text)
    return re.sub(r"\\\*(\S(?:[^*]*?\S)?)\\\*", r"*\1*", text)


def build(s):
    """Checked slide dict -> Typst for that slide."""
    if s["layout"] == "section":
        return f"#section[{esc(s['title'])}]\n"
    out = [f"#kicker[{esc(s['kicker'])}]"] if s["kicker"] else []
    out.append(f"= {esc(s['title'])}")
    if s["intro"]:
        out.append(esc(s["intro"]))
    if s["quote"] and s["layout"] == "quote":
        out.append(f"#quote(block: true)[{esc(s['quote'])}]")
    items = s["items"]
    if s["layout"] == "cards":
        out.append("#cols(" + ", ".join(f"card[{esc(it['head'])}][{esc(it['text'])}]" for it in items) + ")")
    else:
        mark = "+" if s["layout"] == "steps" else "-"
        out += [f"{mark} " + (f"*{esc(it['head'])}*: " if it["head"] else "") + esc(it["text"]) for it in items]
    if s["takeaway"]:
        out.append(f"#takeaway[{esc(s['takeaway'])}]")
    return "\n".join(out) + "\n"


def splice(typ, body):
    """Puts body in place of the content section of main.typ, keeping the preamble and the References slide."""
    start = typ.index(CONTENT) + len(CONTENT)
    end = m.start() if (m := END.search(typ, start)) else len(typ)
    return typ[:start] + body + ("\n" if end < len(typ) else "") + typ[end:]


def chat(model, messages, schema):
    """One chat call whose answer is forced to match schema; returns the parsed JSON."""
    fmt = {"type": "json_schema", "json_schema": {"name": "answer", "strict": True, "schema": schema}}
    req = urllib.request.Request(URL, json.dumps({"model": model, "messages": messages, "temperature": 0.3,
                                                  "response_format": fmt}).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            reply = json.load(r)["choices"][0]["message"]["content"]
    except OSError as e:
        sys.exit(f"cannot reach LM Studio at {URL} ({e})")
    return json.loads(re.sub(r"<think>.*?</think>", "", reply, flags=re.S))


@contextlib.contextmanager
def lm_studio(model):
    """Starts the LM Studio server and loads model if they aren't already; afterwards stops/unloads only what it started."""
    lms = shutil.which("lms") or str(Path.home() / ".lmstudio/bin/lms")
    if not Path(lms).exists():
        sys.exit("LM Studio's lms command not found: install LM Studio from https://lmstudio.ai")
    run = lambda *a: subprocess.run([lms, *a], capture_output=True, text=True)
    try:
        urllib.request.urlopen(URL.replace("chat/completions", "models"), timeout=3).close()
        started = False
    except OSError:
        started = True
    if started:
        print("starting the LM Studio server...", flush=True)
        if (r := run("server", "start")).returncode:
            sys.exit(f"could not start the LM Studio server:\n{r.stderr or r.stdout}")
    loaded = model not in {m.get("identifier") for m in json.loads(run("ps", "--json").stdout or "[]")}
    try:
        if loaded:
            print(f"loading {model}...", flush=True)
            if (r := run("load", model, "-y")).returncode:
                sys.exit(f"could not load {model} (see `lms ls` for names):\n{r.stderr or r.stdout}")
        yield
    finally:
        if loaded:
            run("unload", model)
        if started:
            run("server", "stop")
            print("stopped the LM Studio server", flush=True)


def problems(src):
    r = subprocess.run(["typst", "compile", str(src)], capture_output=True, text=True)
    if r.returncode:
        return [r.stderr.strip()]
    return overflowing_slides(src, src.read_text())


def write(src, typ, slides):
    """Builds every slide into main.typ; returns the deck's problems."""
    src.write_text(splice(typ, "\n".join(("// FIXME: too long, shorten or split it\n" if s.get("fixme") else "") + build(s)
                                         for s in slides)))
    return problems(src)


def generate(src, typ, notes, opts):
    """Notes -> list of checked slide dicts, one LLM call per slide (plus a planning call for notes without breaks)."""
    keys = re.findall(r"^@\w+\{([^,\s]+),", typ, re.M)
    lang = m[1] if (m := re.search(r'#set text\(.*lang: "(\w+)"', typ)) else "same as the notes"
    title = m[1] if (m := re.search(r'^#let title = "(.*)"', typ, re.M)) else ""
    mode, model = MODES[opts["mode"]], opts["model"]

    if len(parts := blocks(notes)) > 1:  # the notes mark slide breaks: one slide per block
        if opts["slides"] and int(opts["slides"]) != len(parts):
            print(f"note: the notes have {len(parts)} blocks separated by dashes; making {len(parts)} slides, not {opts['slides']}")
    else:  # a list of ideas: let the LLM split it into slides first
        count = f"exactly {opts['slides']} slides" if opts["slides"] else "a sensible number of slides"
        print(f"asking {model} to plan {count}...", flush=True)
        plan = chat(model, [{"role": "system", "content": PLAN.format(count=count, lang=lang, mode=mode)},
                            {"role": "user", "content": notes}], PLAN_SCHEMA)
        parts = [f"{p['title']}\n{p['notes']}" for p in plan["slides"]]

    slides = []
    for i, part in enumerate(parts, 1):
        print(f"slide {i}/{len(parts)} ({model}, {opts['mode']})...", flush=True)
        messages = [{"role": "system", "content": SPEC.format(title=title, i=i, n=len(parts), lang=lang, max=MAX_ITEMS, mode=mode)},
                    {"role": "user", "content": part}]
        for attempt in (1, 2):
            raw = chat(model, messages, SLIDE_SCHEMA)
            slide = check(raw, part)
            src.write_text(splice(typ, build(slide)))
            if not (issues := problems(src)):
                break
            messages += [{"role": "assistant", "content": json.dumps(raw, ensure_ascii=False)},
                         {"role": "user", "content": "The slide is too long for one page. Answer again with fewer and "
                                                     "shorter items (about half the words).\n" + "\n".join(issues)}]
        else:
            slide["fixme"] = True
        slides.append(slide)
    if keys:
        print(f"note: citations aren't generated; add @{keys[0]} etc. by hand")
    return slides


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("notes", type=Path, nargs="?", help="notes file (default: <folder>/slides.txt)")
    ap.add_argument("--build", action="store_true", help="rebuild main.typ from slides.json, without the LLM")
    args = ap.parse_args()
    src = (args.folder / "main.typ").resolve()  # typst eval --in needs an absolute path
    jsn = args.folder / "slides.json"
    typ = src.read_text()
    if CONTENT not in typ or "<slide>" not in typ:
        sys.exit(f"{src} is not a presentation made by newdoc")
    shutil.copy(src, src.with_name("main.typ.bak"))

    if args.build:
        slides = [check(s) for s in json.loads(jsn.read_text())]
    else:
        opts, notes = parse((args.notes or args.folder / "slides.txt").read_text())
        with lm_studio(opts["model"]):
            slides = generate(src, typ, notes, opts)
        jsn.write_text(json.dumps([{k: v for k, v in s.items() if k != "fixme"} for s in slides], ensure_ascii=False, indent=2))
        print(f"saved {jsn} (edit it, then: fillslides {args.folder} --build)")

    issues = write(src, typ, slides)
    print("\n".join(issues) if issues else f"done: {src}")
    if fixme := [i for i, s in enumerate(slides, 1) if s.get("fixme")]:
        print(f"slides {fixme} were too long (marked FIXME in main.typ): shorten them in slides.json and run --build")
    if issues:
        sys.exit("the deck has the problems listed above. The old file is main.typ.bak")
    print(f"now review it, then run: finishdoc {args.folder}")


if __name__ == "__main__":
    main()
