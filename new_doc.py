#!/usr/bin/env python3
"""Interactive Typst template generator: asks questions, then writes <folder>/main.typ in the current directory.

Press Enter to accept the [default] shown for each question. The first question is the kind: document or presentation.

Document types (each sets its own defaults):
  article   title block, abstract, numbered headings, footnotes, bibliography
  report    title page, table of contents, chapters on new pages, bibliography
  letter    sender/recipient block, no numbering, no page numbers
  notes     compact margins, two columns
  homework  course + due date, #question[...] / #answer[...] helpers, "1 / N" page numbers
  summary   key points, numbered sections, compact

Presentation themes (16:9 or 4:3 slides; title slide, outline, slide numbers, references slide):
  clean     white, one accent color, thin line under each slide title
  academic  serif font, colored title band behind each slide title
  minimal   large text, lots of white space, no decoration
  dark      dark background, light text, for darkened lecture halls
  bold      title and section slides in full accent color, plain content slides

In the generated main.typ:
  @key            cite a source (add BibTeX entries in the References block at the bottom)
  #footnote[...]  footnote
  #es[...]        passage in another language (one helper per extra language you list)
  = Title         (presentations) starts a new slide
  #section[...]   (presentations) section divider slide, listed on the outline slide

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
SANS = ["Helvetica Neue", "Inter", "Arial", "Liberation Sans", "DejaVu Sans"]
# Slide themes. heading: Typst code drawing a slide title from `body`; filled: title/section slides in full accent color;
# weight: font weight of slide, section and title-slide titles.
THEMES = {
    "clean":    dict(fonts=SANS, size=20, accent="#1f4e79", bg="#ffffff", fg="#222222", filled=False, weight="bold",
                     heading='block(width: 100%, inset: (bottom: 0.3em), stroke: (bottom: 1.5pt + accent), below: 0.9em, text(1.4em, fill: accent, body))'),
    "academic": dict(fonts=["Libertinus Serif"], size=21, accent="#7a1f2b", bg="#ffffff", fg="#222222", filled=False, weight="bold",
                     heading='block(width: 100%, fill: accent, outset: (x: margin-x, top: margin-top), inset: (top: 0.2em, bottom: 0.45em), below: 1em, text(1.4em, fill: white, body))'),
    "minimal":  dict(fonts=["Avenir Next", *SANS], size=22, accent="#333333", bg="#ffffff", fg="#333333", filled=False, weight="regular",
                     heading='block(below: 1.2em, text(1.6em, fill: accent, body))'),
    "dark":     dict(fonts=SANS, size=20, accent="#8ab4f8", bg="#1e1f26", fg="#e8e8e8", filled=False, weight="bold",
                     heading='block(inset: (left: 0.6em), stroke: (left: 4pt + accent), below: 0.9em, text(1.4em, body))'),
    "bold":     dict(fonts=SANS, size=20, accent="#d1495b", bg="#ffffff", fg="#222222", filled=True, weight="bold",
                     heading='block(below: 0.9em, text(1.5em, fill: accent, body))'),
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


def typst_fonts():
    try:
        return set(subprocess.run(["typst", "fonts"], capture_output=True, text=True).stdout.lower().splitlines())
    except FileNotFoundError:
        return None


def check_font(font):
    fonts = typst_fonts()
    if fonts is not None and font.lower() not in fonts:
        print(f"  warning: '{font}' not found by Typst (see `typst fonts`). Typst will fall back to its default.")


def first_font(candidates):  # first one installed, so the default never triggers a missing-font warning
    fonts = typst_fonts() or set()
    return next((f for f in candidates if f.lower() in fonts), candidates[0])


def folder_for(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "doc"


def ask_languages(c):
    section("Language")
    c["lang"] = ask("Main language code (en, es, fr, de, ...)", "en")
    c["langs"] = [l.strip() for l in ask("Other languages used inside the doc, comma-separated (empty = none)").split(",") if l.strip()]
    bad = [l for l in [c["lang"], *c["langs"]] if not re.fullmatch(r"[a-z]{2,3}", l)]
    if bad:
        raise SystemExit(f"Invalid language code(s): {bad}. Use ISO codes like en, es, pt.")


def ask_accent(c, default):
    c["accent"] = ask("Accent color for headings/links (hex like #1f4e79, empty = black)", default)
    if c["accent"] and not re.fullmatch(r"#?[0-9a-fA-F]{6}", c["accent"]):
        raise SystemExit("Accent color must be a 6-digit hex like #1f4e79.")


def ask_logo(c, places, default):
    c["logo"] = ""
    while logo := ask("Logo image path (empty = none)"):
        if Path(logo).expanduser().is_file():
            c["logo"] = str(Path(logo).expanduser())
            c["logo_pos"] = choose("Logo on", places, default)
            break
        print("  file not found")


def collect():
    section("Kind")
    if choose("Kind", ["document", "presentation"], "document") == "presentation":
        return collect_presentation()
    return collect_document()


def collect_presentation():
    section("Presentation")
    theme = choose("Theme", list(THEMES), "clean")
    t = THEMES[theme]
    c = dict(kind="presentation", theme=theme)
    c["title"] = ask("Title", "Untitled")
    c["subtitle"] = ask("Subtitle (empty = none)")
    c["authors"] = [a.strip() for a in ask("Author(s), comma-separated", "Your Name").split(",") if a.strip()]
    c["institution"] = ask("Institution or course (empty = none)")
    c["date"] = ask("Date of the talk (empty = none)", datetime.date.today().strftime("%d %B %Y"))
    c["folder"] = ask("Folder name", folder_for(c["title"]))

    ask_languages(c)

    section("Slides")
    c["aspect"] = choose("Aspect ratio", ["16-9", "4-3"], "16-9")
    c["font"] = ask("Font", first_font(t["fonts"]))
    check_font(c["font"])
    c["size"] = number("Font size (pt)", t["size"])
    ask_accent(c, t["accent"])

    section("Extras")
    c["title_slide"] = yes("Title slide", True)
    c["outline"] = yes("Outline slide", True)
    c["slide_numbers"] = yes("Slide numbers", True)
    c["footer_text"] = ask("Footer text (empty = none)", " · ".join(x for x in [", ".join(c["authors"]), c["institution"]] if x))
    c["bib"] = yes("References slide", True)
    c["bib_style"] = choose("Citation style", BIB_STYLES, "apa") if c["bib"] else ""
    ask_logo(c, ["title", "all"], "title")
    return c


def collect_document():
    section("Document")
    preset = choose("Type", list(PRESETS), "article")
    p = PRESETS[preset]
    c = dict(kind="document", preset=preset)
    c["title"] = ask("Title", "Untitled")
    c["subtitle"] = ask("Subtitle (empty = none)") if preset != "letter" else ""
    c["authors"] = [a.strip() for a in ask("Author(s), comma-separated", "Your Name").split(",") if a.strip()]
    c["date"] = ask("Date (empty = none)", datetime.date.today().strftime("%d %B %Y"))
    if preset == "homework":
        c["course"] = ask("Course", "Course name")
        c["due"] = ask("Due date (empty = none)")
    c["folder"] = ask("Folder name", folder_for(c["title"]))

    ask_languages(c)

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
    ask_accent(c, "#1f4e79")

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
    ask_logo(c, ["header", "title", "both"], "title")
    return c


def lang_helpers(langs):
    if not langs:
        return []
    out = ["\n// ===== Other languages: wrap passages so hyphenation and quotes follow that language ====="]
    for l in langs:
        out.append(f'#let {helper(l)}(body) = text(lang: "{l}", body)')
    return out


def helper(lang):
    return "lang-" + lang if lang in TYPST_KEYWORDS else lang


def bibliography(style, title=""):
    return f"""
// ===== References =====
// Add BibTeX entries inside the block below as you write; cite them in the text with @key.
// (Prefer a separate file, e.g. a Zotero export? Use: #bibliography("refs.bib", {title}style: "{style}"))
#bibliography({title}style: "{style}", bytes(```bib
@book{{knuth1984,
  author    = {{Donald E. Knuth}},
  title     = {{The TeXbook}},
  publisher = {{Addison-Wesley}},
  year      = {{1984}},
}}
```.text))"""


def build(c):
    return build_presentation(c) if c["kind"] == "presentation" else build_document(c)


def build_presentation(c):
    t = THEMES[c["theme"]]
    logo = "logo" + Path(c["logo"]).suffix if c["logo"] else ""
    accent = f'rgb("#{c["accent"].lstrip("#")}")' if c["accent"] else "black"
    on_fill = "white" if t["filled"] else "fg"
    number = 'counter(page).display("1 / 1", both: true)' if c["slide_numbers"] else "none"
    out = [f"""// {c['title']} — created {datetime.date.today()} with new_doc.py (presentation, theme: {c['theme']})
// Live preview in Cursor: install the "Tinymist Typst" extension, or run `typst watch main.typ`.
// Each `= Heading` starts a new slide; #section[...] adds a divider slide.

// ===== Metadata =====
#let title = {s(c['title'])}
#let subtitle = {s(c['subtitle'])}
#let authors = ({''.join(s(a) + ', ' for a in c['authors'])})
#let institution = {s(c['institution'])}
#let date = {s(c['date'])}
#let footer-text = {s(c['footer_text'])}
#set document(title: title, author: authors)

// ===== Theme: {c['theme']} =====
#let accent = {accent}
#let fg = rgb("{t['fg']}")  // text color
#let bg = rgb("{t['bg']}")  // background color
#let filled = {str(t['filled']).lower()}  // true = title and section slides in full accent color
#let title-weight = "{t['weight']}"
#let margin-x = 1.8cm
#let margin-top = 1.4cm
#let font-size = {n(c['size'])}pt

#set page(
  paper: "presentation-{c['aspect']}",
  fill: bg,
  margin: (x: margin-x, top: margin-top, bottom: 1.6cm),"""]
    if logo and c["logo_pos"] == "all":
        out.append(f'  foreground: place(top + right, dx: -0.4cm, dy: 0.35cm, image("{logo}", height: 0.8cm)),')
    if c["footer_text"] or c["slide_numbers"]:
        out.append(f"""  footer: context {{
    set text(size: 0.6em, fill: fg.transparentize(40%))
    grid(columns: (1fr, auto), align: (left, right), footer-text, {number})
  }},""")
    else:
        out.append("  footer: none,")
    out.append(f""")
#set text(font: {s(c['font'])}, size: font-size, fill: fg, lang: {s(c['lang'])})
#set par(leading: 0.7em)
#set list(spacing: 0.9em)
#set enum(spacing: 0.9em)
#show link: set text(fill: accent)
#show heading.where(level: 2): set text(size: font-size, fill: accent)
#show bibliography: set text(size: 0.7em)
#set footnote.entry(separator: line(length: 30%, stroke: 0.5pt + fg))

// Every slide records its page, so finishdoc can spot a slide whose content spills onto an extra page.
#let slide-mark = context [#metadata((page: here().page(), pages: counter(page).final().first())) <slide>]
#let slide-title(body) = {{
  set text(size: font-size, weight: title-weight)
  {t['heading']}
}}
#show heading.where(level: 1): it => {{
  pagebreak(weak: true)
  slide-mark
  slide-title(it.body)
}}

// #section[...]: divider slide, listed on the outline slide.
#let section(body) = {{
  [#metadata(body) <section>]
  page(fill: if filled {{ accent }} else {{ bg }}, footer: none, foreground: none)[
    #slide-mark
    #align(center + horizon, text(2em, weight: title-weight, fill: if filled {{ white }} else {{ accent }}, body))
  ]
}}

#let outline-slide(title: "Outline") = {{
  pagebreak(weak: true)
  slide-mark
  slide-title(title)
  context {{
    let sections = query(<section>).map(m => m.value)
    enum(..if sections.len() > 0 {{ sections }} else {{ query(heading.where(level: 1)).map(h => h.body) }})
  }}
}}

#let title-slide() = page(fill: if filled {{ accent }} else {{ bg }}, footer: none, foreground: none)[
  #slide-mark
  #set text(fill: {on_fill})
  #align(center + horizon)[""")
    if logo and c["logo_pos"] in ("title", "all"):
        out.append(f'    #image("{logo}", height: 2cm)\n    #v(0.6cm)')
    out.append(f"""    #text(2em, weight: title-weight, fill: if filled {{ white }} else {{ accent }}, title)
    #if subtitle != "" [ \\ #text(1.2em, subtitle)]
    #v(1.2cm)
    #authors.join(", ")
    #if institution != "" [ \\ #institution]
    #if date != "" [ \\ #text(0.8em, date)]
  ]
]""")
    out += lang_helpers(c["langs"])

    out.append("\n// ===== Title =====")
    if c["title_slide"]:
        out.append("#title-slide()")
    if c["outline"]:
        out.append("#outline-slide()")

    cite = " @knuth1984" if c["bib"] else ""
    lang_demo = f'\n- In another language: #{helper(c["langs"][0])}["{c["langs"][0]}" text here]' if c["langs"] else ""
    out.append(f"""
// ===== Content =====
#section[Introduction]

= Motivation
- #lorem(8)
- #lorem(10){cite}
- #lorem(6)#footnote[A footnote.]{lang_demo}

= Research question
#lorem(25)

#section[Results]

= Main finding
#grid(columns: (1fr, 1fr), gutter: 1cm,
  [
    - #lorem(6)
    - #lorem(8)
  ],
  // Replace with: image("figure.png", width: 100%)
  rect(width: 100%, height: 5cm, stroke: accent)[#align(center + horizon)[Image goes here]],
)

= Conclusion
+ #lorem(8)
+ #lorem(8)""")
    if c["bib"]:
        out.append("\n= References" + bibliography(c["bib_style"], "title: none, "))
    return "\n".join(out) + "\n"


def build_document(c):
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

    out += lang_helpers(c["langs"])

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
        lang_demo = f'\n\nA passage in another language: #{helper(l)}["{l}" text here]. '
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
        out.append(bibliography(c["bib_style"]))
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
