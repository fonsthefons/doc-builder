#!/usr/bin/env python3
"""Final check + PDF build for a document made with newdoc.

Checks:
  - leftover template text (lorem ipsum, "Your Name", empty #answer[] boxes, ...)
  - bibliography entries you never cite
  - Typst errors and warnings (missing fonts, broken references, ...)
Then writes <folder>/<folder-name>.pdf. Exits with status 1 if anything needs fixing.

Usage: finishdoc [path]   (path = doc folder or .typ file; default: current folder)
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

PLACEHOLDERS = [
    r"#lorem\(", r"Your Name", r"\bUntitled\b", r"Recipient Name", r"Dear Recipient", r"Street 1",
    r"Course name", r"#answer\[\s*\]", r'"\w+" text here', r"A footnote\.", r"#footnote\[Source\.\]",
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", default=".", help="doc folder or .typ file (default: current folder)")
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

    for issue in issues:
        print("✗", issue)
    if r.returncode != 0:
        sys.exit("\nTypst failed: no PDF written.")
    if issues:
        sys.exit(f"\nPDF written to {out}, but fix the {len(issues)} issue(s) above before handing it in.")
    print(f"✓ All checks passed. PDF{'/A' if args.pdfa else ''}: {out}")


if __name__ == "__main__":
    main()
