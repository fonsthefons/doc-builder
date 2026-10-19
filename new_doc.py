#!/usr/bin/env python3
"""Interactive Typst template generator: asks questions, then writes <folder>/main.typ in the current directory.

Press Enter to accept the [default] shown for each question.

Document types (each sets its own defaults):
  article   title block, abstract, numbered headings, footnotes, bibliography
  report    title page, table of contents, chapters on new pages, bibliography
  letter    sender/recipient block, no numbering, no page numbers
  notes     compact margins, two columns
  homework  course + due date, #question[...] / #answer[...] helpers, "1 / N" page numbers
  summary   key points, numbered sections, compact

In the generated main.typ:
  @key            cite a source (add BibTeX entries in the References block at the bottom)
  #footnote[...]  footnote
  #es[...]        passage in another language (one helper per extra language you list)

Preview: typst watch <folder>/main.typ   (or the Tinymist Typst extension in Cursor)
Test the script: python3 test_new_doc.py
"""
import argparse
import datetime
import re
import shutil
import subprocess
from pathlib import Path

PRESETS = {
    "article":  dict(numbering="1.1", title_page=False, toc=False, bib=True,  margin=2.5, size=11, columns=1, page_fmt="1",     justify=True),
    "report":   dict(numbering="1.1", title_page=True,  toc=True,  bib=True,  margin=2.5, size=11, columns=1, page_fmt="1",     justify=True),
    "letter":   dict(numbering="",    title_page=False, toc=False, bib=False, margin=2.5, size=11, columns=1, page_fmt="",      justify=False),
    "notes":    dict(numbering="",    title_page=False, toc=False, bib=False, margin=1.5, size=10, columns=2, page_fmt="1",     justify=False),
    "homework": dict(numbering="",    title_page=False, toc=False, bib=False, margin=2,   size=11, columns=1, page_fmt="1 / N", justify=False),
    "summary":  dict(numbering="1.",  title_page=False, toc=False, bib=False, margin=2,   size=10, columns=1, page_fmt="1",     justify=False),
}
BIB_STYLES = ["apa", "ieee", "mla", "chicago-author-date", "chicago-notes", "harvard-cite-them-right", "vancouver"]
TYPST_KEYWORDS = {"as", "or", "in", "if", "and", "not", "let", "set", "for", "none", "auto", "show"}


def ask(q, default=""):
    try:
        a = input(f"{q} [{default}]: " if default != "" else f"{q}: ").strip()
    except EOFError:  # piped input ran out: take defaults
        a = ""
    return a or str(default)


def yes(q, default):
    return ask(q + " (y/n)", "y" if default else "n").lower().startswith("y")


def choose(q, options, default):
    while (a := ask(f"{q} ({'/'.join(options)})", default)) not in options:
        print("  choose one of:", ", ".join(options))
    return a


def number(q, default):
    while True:
        try:
            return float(ask(q, default))
        except ValueError:
            print("  enter a number")


def s(text):  # Python str -> Typst string literal
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def n(x):
    return f"{x:g}"


def section(name):
    print(f"\n── {name} ──")


def check_font(font):
    try:
        fonts = subprocess.run(["typst", "fonts"], capture_output=True, text=True).stdout.lower().splitlines()
    except FileNotFoundError:
        return
    if font.lower() not in fonts:
        print(f"  warning: '{font}' not found by Typst (see `typst fonts`). Typst will fall back to its default.")


def collect():
    section("Document")
    preset = choose("Type", list(PRESETS), "article")
    p = PRESETS[preset]
    c = dict(preset=preset)
    c["title"] = ask("Title", "Untitled")
    c["subtitle"] = ask("Subtitle (empty = none)") if preset != "letter" else ""
    c["authors"] = [a.strip() for a in ask("Author(s), comma-separated", "Your Name").split(",") if a.strip()]
    c["date"] = ask("Date (empty = none)", datetime.date.today().strftime("%d %B %Y"))
    if preset == "homework":
        c["course"] = ask("Course", "Course name")
        c["due"] = ask("Due date (empty = none)")
    c["folder"] = ask("Folder name", re.sub(r"[^a-z0-9]+", "-", c["title"].lower()).strip("-") or "doc")

    section("Language")
    c["lang"] = ask("Main language code (en, es, fr, de, ...)", "en")
    c["langs"] = [l.strip() for l in ask("Other languages used inside the doc, comma-separated (empty = none)").split(",") if l.strip()]
    bad = [l for l in [c["lang"], *c["langs"]] if not re.fullmatch(r"[a-z]{2,3}", l)]
    if bad:
        raise SystemExit(f"Invalid language code(s): {bad}. Use ISO codes like en, es, pt.")

    section("Page")
    c["paper"] = ask("Paper (a4, us-letter, a5, ...)", "a4")
    c["landscape"] = yes("Landscape", False)
    m = p["margin"]
    c["margins"] = {side: number(f"{side.capitalize()} margin (cm)", m) for side in ("top", "bottom", "left", "right")}
    c["columns"] = int(number("Columns", p["columns"]))

    section("Typography")
    c["font"] = ask("Font", "Libertinus Serif")
    check_font(c["font"])
    c["size"] = number("Font size (pt)", p["size"])
    c["leading"] = number("Line spacing (em, 0.65 = normal, 1 = loose)", 0.65)
    c["justify"] = yes("Justify paragraphs", p["justify"])
    c["indent"] = number("First-line paragraph indent (em, 0 = none)", 0)
    c["numbering"] = ask("Heading numbering (1.1 / I.1 / a) / 1. / empty = none)", p["numbering"])
    c["accent"] = ask("Accent color for headings/links (hex like #1f4e79, empty = black)", "#1f4e79")
    if c["accent"] and not re.fullmatch(r"#?[0-9a-fA-F]{6}", c["accent"]):
        raise SystemExit("Accent color must be a 6-digit hex like #1f4e79.")

    section("Header / footer")
    dh = c["title"] if preset in ("report", "notes", "summary") else c.get("course", "")
    c["header_left"] = ask("Header left text (empty = none)", dh)
    c["header_right"] = ask("Header right text (empty = none)", ", ".join(c["authors"]) if preset == "homework" else "")
    c["footer_text"] = ask("Footer left text (empty = none)")
    c["page_fmt"] = choose("Page number format (none = no numbers)", ["1", "1 / N", "i", "none"], p["page_fmt"] or "none")
    c["page_pos"] = choose("Page number position", ["center", "right"], "center") if c["page_fmt"] != "none" else ""
    c["footnote_fmt"] = choose("Footnote numbering", ["1", "a", "i", "*"], "1")

    section("Extras")
    c["title_page"] = yes("Separate title page", p["title_page"]) if preset != "letter" else False
    c["toc"] = yes("Table of contents", p["toc"]) if preset != "letter" else False
    c["abstract"] = yes("Abstract", True) if preset == "article" else False
    c["bib"] = yes("Bibliography", p["bib"])
    c["bib_style"] = choose("Citation style", BIB_STYLES, "apa") if c["bib"] else ""
    c["logo"] = ""
    while logo := ask("Logo image path (empty = none)"):
        if Path(logo).expanduser().is_file():
            c["logo"] = str(Path(logo).expanduser())
            c["logo_pos"] = choose("Logo in", ["header", "title", "both"], "title")
            break
        print("  file not found")
    return c


def build(c):
    logo = "logo" + Path(c["logo"]).suffix if c["logo"] else ""
    accent = f'rgb("#{c["accent"].lstrip("#")}")' if c["accent"] else "black"
    mg = c["margins"]
    out = [f"""// {c['title']} — created {datetime.date.today()} with new_doc.py (preset: {c['preset']})
// Live preview in Cursor: install the "Tinymist Typst" extension, or run `typst watch main.typ`.

// ===== Metadata =====
#let title = {s(c['title'])}
#let subtitle = {s(c['subtitle'])}
#let authors = ({''.join(s(a) + ', ' for a in c['authors'])})
#let date = {s(c['date'])}
#let accent = {accent}
#set document(title: title, author: authors)

// ===== Page =====
#set page(
  paper: {s(c['paper'])},
  flipped: {str(c['landscape']).lower()},  // true = landscape
  margin: (top: {n(mg['top'])}cm, bottom: {n(mg['bottom'])}cm, left: {n(mg['left'])}cm, right: {n(mg['right'])}cm),
  columns: {c['columns']},"""]

    head_left = s(c["header_left"])
    if logo and c["logo_pos"] in ("header", "both"):
        head_left = f'stack(dir: ltr, spacing: 0.5em, image("{logo}", height: 0.8cm), align(horizon, {head_left}))'
    if c["header_left"] or c["header_right"] or head_left != s(c["header_left"]):
        out.append(f"""  header: {{
    set text(size: 0.85em, fill: luma(90))
    grid(columns: (1fr, 1fr), align: (left + horizon, right + horizon), {head_left}, {s(c['header_right'])})
  }},""")
    else:
        out.append("  header: none,")

    if c["page_fmt"] != "none" or c["footer_text"]:
        fmt = {"1": '"1"', "1 / N": '"1 / 1", both: true', "i": '"i"'}.get(c["page_fmt"])
        num = f"counter(page).display({fmt})" if fmt else "none"
        center, right = (num, "none") if c["page_pos"] == "center" else ("none", num)
        out.append(f"""  footer: context {{
    set text(size: 0.85em, fill: luma(90))
    grid(columns: (1fr, auto, 1fr), align: (left, center, right), {s(c['footer_text'])}, {center}, {right})
  }},""")
    else:
        out.append("  footer: none,")
    out.append(")")

    out.append(f"""
// ===== Typography =====
#set text(font: {s(c['font'])}, size: {n(c['size'])}pt, lang: {s(c['lang'])})
#set par(justify: {str(c['justify']).lower()}, leading: {n(c['leading'])}em, first-line-indent: {n(c['indent'])}em)
#set heading(numbering: {s(c['numbering']) if c['numbering'] else 'none'})
#show heading: set text(fill: accent)
#show link: set text(fill: accent)
#set footnote(numbering: {s(c['footnote_fmt'])})""")
    if c["preset"] == "report":
        out.append("#show heading.where(level: 1): it => pagebreak(weak: true) + it  // chapters start on a new page")

    if c["langs"]:
        out.append("\n// ===== Other languages: wrap passages so hyphenation and quotes follow that language =====")
        for l in c["langs"]:
            out.append(f'#let {"lang-" + l if l in TYPST_KEYWORDS else l}(body) = text(lang: "{l}", body)')

    if c["preset"] == "homework":
        out.append("""
// ===== Q&A helpers: #question[...] and #answer[...] =====
#let qn = counter("question")
#let question(body) = block(above: 1.6em, below: 0.8em, {
  qn.step()
  strong([Question ] + context qn.display() + [. ])
  body
})
#let answer(body) = block(width: 100%, inset: 0.8em, stroke: (left: 2pt + accent), fill: accent.lighten(92%), body)""")

    out.append("\n// ===== Title =====")
    if c["preset"] == "letter":
        out.append("""#grid(columns: (1fr, 1fr),
  [*#authors.join(", ")* \\ Street 1 \\ City],
  align(right, date),
)
#v(1cm)
Recipient Name \\
Street 1 \\
City
#v(1cm)
*#title*

Dear Recipient,""")
    elif c["title_page"]:
        logo_img = f'#image("{logo}", width: 4cm)\n    #v(1cm)\n    ' if logo and c["logo_pos"] in ("title", "both") else ""
        out.append(f"""#page(header: none, footer: none, columns: 1)[
  #align(center + horizon)[
    {logo_img}#text(2.2em, weight: "bold", fill: accent, title)
    #if subtitle != "" [ \\ #text(1.3em, subtitle)]
    #v(2cm)
    #text(1.2em, authors.join(", ")) \\
    #date
  ]
]
#counter(page).update(1)""")
    else:
        logo_img = f'#image("{logo}", height: 1.5cm)\n    ' if logo and c["logo_pos"] in ("title", "both") else ""
        extra = ""
        if c["preset"] == "homework":
            extra = f'\n    #{s(c["course"])}' + (f' #h(1em) Due: #{s(c["due"])}' if c["due"] else "") + " \\"
        abstract = "\n  #block(inset: (x: 2em), above: 1.5em)[*Abstract.* #lorem(60)]" if c["abstract"] else ""
        out.append(f"""#place(top + center, scope: "parent", float: true)[
  #align(center)[
    {logo_img}#text(1.8em, weight: "bold", fill: accent, title)
    #if subtitle != "" [ \\ #text(1.2em, subtitle)]
    #v(0.3em){extra}
    #authors.join(", ") #if date != "" [ #h(1em) #date]
  ]{abstract}
  #v(1em)
]""")

    if c["toc"]:
        out.append("\n#outline()" + ("\n#pagebreak()" if c["preset"] == "report" else ""))

    out.append("\n// ===== Content =====")
    cite = " See @knuth1984" if c["bib"] else ""
    lang_demo = ""
    if c["langs"]:
        l = c["langs"][0]
        lang_demo = f'\n\nA passage in another language: #{"lang-" + l if l in TYPST_KEYWORDS else l}["{l}" text here]. '
    body = {
        "article": f"= Introduction\n#lorem(80){cite}.#footnote[A footnote.]{lang_demo}\n\n= Method\n#lorem(100)\n\n== Details\n#lorem(60)",
        "report": f"= Introduction\n#lorem(120){cite}.#footnote[A footnote.]{lang_demo}\n\n== Background\n#lorem(80)\n\n= Results\n#lorem(150)",
        "letter": f"\n#lorem(80){lang_demo}\n\n#lorem(40)\n\nSincerely,\n#v(1cm)\n#authors.join(\", \")",
        "notes": f"= Topic\n- Key idea: #lorem(12)\n- Another idea#footnote[Source.]{cite}{lang_demo}\n\n= Next topic\n#lorem(60)",
        "homework": f"#question[#lorem(20)]\n#answer[#lorem(40){cite}]{lang_demo}\n\n#question[#lorem(15)]\n#answer[]",
        "summary": f"= Key points\n+ #lorem(10)\n+ #lorem(12)\n\n= Summary\n#lorem(80){cite}{lang_demo}\n\n= Open questions\n- #lorem(8)",
    }[c["preset"]]
    out.append(body)

    if c["bib"]:
        out.append(f"""
// ===== References =====
// Add BibTeX entries inside the block below as you write; cite them in the text with @key.
// (Prefer a separate file, e.g. a Zotero export? Use: #bibliography("refs.bib", style: "{c['bib_style']}"))
#bibliography(style: "{c['bib_style']}", bytes(```bib
@book{{knuth1984,
  author    = {{Donald E. Knuth}},
  title     = {{The TeXbook}},
  publisher = {{Addison-Wesley}},
  year      = {{1984}},
}}
```.text))""")
    return "\n".join(out) + "\n"


def main():
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    c = collect()
    folder = Path(c["folder"]).expanduser()
    target = folder / "main.typ"
    if target.exists():
        raise SystemExit(f"{target} already exists; not overwriting.")
    folder.mkdir(parents=True, exist_ok=True)
    if c["logo"]:
        shutil.copy(c["logo"], folder / ("logo" + Path(c["logo"]).suffix))
    target.write_text(build(c))
    print(f"\nCreated {target}\nOpen it in Cursor:  cursor {folder}\nPreview:  typst watch {target}")


if __name__ == "__main__":
    main()
