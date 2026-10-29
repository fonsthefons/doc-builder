#!/usr/bin/env python3
"""Final check + PDF build for a document or presentation made with newdoc.

Checks:
  - leftover template text (lorem ipsum, "Your Name", empty #answer[] boxes, ...)
  - bibliography entries you never cite
  - Typst errors and warnings (missing fonts, broken references, ...)
  - spelling (aspell), in the doc's language; #es[...]-style passages are checked in their own language.
    Words to accept (names, jargon): one per line in dictionary.txt next to main.typ.
  - presentations: slides whose content doesn't fit and spills onto an extra page
Then writes <folder>/<folder-name>.pdf. Exits with status 1 if anything needs fixing.

Usage: finishdoc [path]   (path = doc folder or .typ file; default: current folder)
"""
import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

PLACEHOLDERS = [
    r"#lorem\(", r"Your Name", r"\bUntitled\b", r"Recipient Name", r"Dear Recipient", r"Street 1",
    r"Course name", r"#answer\[\s*\]", r'"\w+" text here', r"A footnote\.", r"#footnote\[Source\.\]",
    r"Image goes here",
]
# Source lines that start a slide, in the same order as the <slide> marks the presentation template records.
SLIDE_START = re.compile(r"\s*(= |#title-slide\(|#outline-slide\(|#section\[)")

MAX_SPELLING = 30


def aspell(lang, text):
    r = subprocess.run(["aspell", "list", f"--lang={lang}", "--encoding=utf-8"], input=text, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip())
    return r.stdout.split()


def spelling(src, text):
    """Misspelled words as 'file:line: spelling (lang): word' issues."""
    # HTML export gives the rendered text without Typst code; drop bibliography and code.
    out = subprocess.run(["typst", "compile", "--features", "html", "--format", "html", str(src), "-"],
                         capture_output=True, text=True, cwd=src.parent).stdout
    lang = m.group(1) if (m := re.search(r'#set text\([^)]*lang: "([\w-]+)"', text)) else "en"  # Typst's default
    out = re.sub(r'<section role="doc-bibliography".*?</section>|<(pre|code)\b.*?</\1>', " ", out, flags=re.S)
    words = aspell(lang, html.unescape(re.sub(r"<[^>]+>", " ", out)))

    # HTML export loses text(lang: ...), so re-check passages in other languages from the source.
    helpers = dict(re.findall(r'#let ([\w-]+)\(body\) = text\(lang: "([\w-]+)"', text))
    passages = [(helpers[h], seg) for h, seg in re.findall(r"#([\w-]+)\[([^\]]*)\]", text) if h in helpers]
    passages += re.findall(r'#text\(lang: "([\w-]+)"\)\[([^\]]*)\]', text)
    lang_of = {}  # misspelled word -> language of the passage it's in
    for plang, seg in passages:
        wrong = aspell(plang, seg)
        lang_of.update(dict.fromkeys(wrong, plang))
        fine = set(re.findall(r"\w+", seg)) - set(wrong)
        words = [w for w in words if w not in fine]

    dic = src.with_name("dictionary.txt")
    accepted = {w.strip().lower() for w in dic.read_text().splitlines()} if dic.exists() else set()
    lines = text.splitlines()
    issues = []
    for w in dict.fromkeys(words):  # unique, in reading order
        if w.lower() in accepted:
            continue
        n = next((i for i, l in enumerate(lines, 1) if re.search(rf"\b{re.escape(w)}\b", l)), None)
        if n is None:  # generated text (lorem, Typst labels): nothing to fix in the source
            continue
        count = words.count(w)
        issues.append(f"{src.name}:{n}: spelling ({lang_of.get(w, lang)}): {w}" + (f" (×{count})" if count > 1 else ""))
    if len(issues) > MAX_SPELLING:
        issues = issues[:MAX_SPELLING] + [f"... and {len(issues) - MAX_SPELLING} more misspelled words"]
    return issues


def overflowing_slides(src, text):
    """Slides whose content spills onto extra pages, as 'file:line: ...' issues."""
    for cmd in (["typst", "eval", "query(<slide>).map(it => it.value)", "--in", str(src)],
                ["typst", "query", str(src), "<slide>", "--field", "value"]):  # Typst before 0.15
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=src.parent)
        if r.returncode == 0:
            break
    else:
        return [f"{src.name}: could not check slides for overflow: {r.stderr.strip()}"]
    marks = json.loads(r.stdout)
    starts = [(i, l.strip()) for i, l in enumerate(text.splitlines(), 1) if SLIDE_START.match(l)]
    issues = []
    for k, m in enumerate(marks):
        end = marks[k + 1]["page"] if k + 1 < len(marks) else m["pages"] + 1
        if (extra := end - m["page"] - 1) > 0:
            # If the source was restructured (e.g. slides added by a custom helper), fall back to the slide number.
            where, what = (f"{src.name}:{starts[k][0]}", starts[k][1]) if len(starts) == len(marks) else (src.name, f"slide {m['page']}")
            issues.append(f"{where}: slide overflows onto {extra} extra page(s), shorten it or split it: {what}")
    return issues


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", default=".", help="doc folder or .typ file (default: current folder)")
    ap.add_argument("--no-spell", action="store_true", help="skip the spellcheck")
    ap.add_argument("--pdfa", action="store_true", help="produce PDF/A-2b (archival; often required for submissions)")
    args = ap.parse_args()

    src = Path(args.path).expanduser().resolve()
    if src.is_dir():
        src = src / "main.typ"
    if not src.is_file():
        sys.exit(f"Not found: {src}")
    text = src.read_text()
    issues = []

    # Placeholders, ignoring // comment lines.
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("//"):
            continue
        for pat in PLACEHOLDERS:
            if m := re.search(pat, line):
                issues.append(f"{src.name}:{i}: leftover template text: {m.group()}")

    # Uncited entries in the inline ```bib block.
    if bib := re.search(r"```bib(.*?)```", text, re.S):
        body = text.replace(bib.group(), "")
        for key in re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", bib.group(1)):
            if not re.search(rf"@{re.escape(key)}\b|<{re.escape(key)}>", body):
                issues.append(f"{src.name}: bibliography entry never cited: {key}")

    out = src.with_name(src.parent.name + ".pdf")
    cmd = ["typst", "compile", "--diagnostic-format", "short", str(src), str(out)]
    if args.pdfa:
        cmd[2:2] = ["--pdf-standard", "a-2b"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=src.parent)
    except FileNotFoundError:
        sys.exit("Typst not installed: run ./install.sh in doc-builder")
    issues += [l for l in r.stderr.splitlines() if ": error:" in l or ": warning:" in l]
    if r.returncode == 0 and "<slide>" in text:
        issues += overflowing_slides(src, text)

    if not args.no_spell and r.returncode == 0:
        try:
            issues += spelling(src, text)
        except FileNotFoundError:
            print("⚠ aspell not installed, spellcheck skipped (brew install aspell)")
        except RuntimeError as e:
            print(f"⚠ spellcheck skipped: {e}")

    for issue in issues:
        print("✗", issue)
    if r.returncode != 0:
        sys.exit("\nTypst failed: no PDF written.")
    if issues:
        sys.exit(f"\nPDF written to {out}, but fix the {len(issues)} issue(s) above before handing it in.")
    print(f"✓ All checks passed. PDF{'/A' if args.pdfa else ''}: {out}")


if __name__ == "__main__":
    main()
