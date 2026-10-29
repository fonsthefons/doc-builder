# doc-builder

An interactive command that creates a ready-to-edit [Typst](https://typst.app) document or presentation. It asks about the title, authors, margins, font, header and footer, page numbers, footnotes, languages, bibliography and more, then writes `<folder>/main.typ`.

## Install

```sh
git clone git@github.com:fonsthefons/doc-builder.git
cd doc-builder
./install.sh
```

The install script:
- installs Typst and aspell (the spellchecker) with Homebrew if they're missing;
- links the `newdoc` and `finishdoc` commands into `~/.local/bin`;
- adds that folder to your PATH if it isn't there already.

It only needs `python3`. The script uses the standard library alone, so there are no packages to install.

## Usage

```sh
cd ~/where/the/doc/should/live
newdoc            # answer the questions; press Enter to accept [defaults]
newdoc --help     # list document types, presentation themes and tips
```

The first question is the kind: `document` or `presentation`. The document folder is created inside the folder you run `newdoc` from. You can also type a path such as `~/uni/essay-1` when it asks for the folder name.

Preview while you edit:

```sh
typst watch essay-1/main.typ        # rebuilds main.pdf on every save
```

In Cursor or VS Code, the **Tinymist Typst** extension gives you a live preview and autocompletion.

## Finishing a document

```sh
finishdoc essay-1          # or run `finishdoc` inside the doc folder
finishdoc essay-1 --pdfa   # PDF/A-2b, the archival format many submissions require
```

It checks for:
- leftover template text (lorem ipsum, "Your Name", "Untitled", empty `#answer[]` boxes, ...);
- bibliography entries you never cite;
- Typst errors and warnings (missing fonts, broken `@references`, missing images);
- presentations: slides whose content doesn't fit and spills onto an extra page (it names the slide's line);
- spelling, in the document's language. Passages wrapped in a language helper such as `#es[...]` are checked in that language. Bibliography entries and code are skipped.

To accept names and jargon, list them one per line in `dictionary.txt` next to `main.typ`. Use `--no-spell` to skip the spellcheck.

Then it writes `essay-1/essay-1.pdf`. If anything needs fixing, it lists each problem with its line number and exits with status 1. Lines starting with `//` are skipped, so a comment never counts as leftover text.

## Document types

| Type | Defaults |
|---|---|
| `article` | Title block, abstract, numbered headings, footnotes, bibliography |
| `report` | Title page, table of contents, chapters start on a new page, bibliography |
| `letter` | Sender and recipient block, no heading numbers, no page numbers |
| `notes` | Narrow margins, two columns |
| `homework` | Course and due date, `#question[...]` and `#answer[...]` helpers, "1 / N" page numbers |
| `summary` | Key points, numbered sections, compact |

You can change every default during the questions or later in `main.typ`. All the settings are `#set` rules at the top of the file.

## Presentations

Slides are plain Typst too: no packages to download, and every setting is a `#let` or `#set` rule at the top of `main.typ`. They have no step-by-step reveals or speaker notes.

| Theme | Look |
|---|---|
| `clean` | White, one accent color, a thin line under each slide title |
| `academic` | Serif font, colored title band behind each slide title |
| `minimal` | Large text, lots of white space, no decoration |
| `dark` | Dark background, light text, for darkened lecture halls |
| `bold` | Title and section slides in full accent color, plain content slides |

You also choose 16:9 or 4:3, the font, size and accent color, and whether to include a title slide, an outline slide, slide numbers, a footer line and a references slide. The default font is the first one installed from the theme's list, such as Helvetica Neue on a Mac.

| You want | Write |
|---|---|
| New slide | `= Slide title` |
| Section divider slide (listed on the outline slide) | `#section[Results]` |
| Subheading on a slide | `== Subtitle` |
| Two columns | `#grid(columns: (1fr, 1fr), gutter: 1cm, [left], [right])` |

Citations, footnotes, images and `#es[...]` work the same as in documents (below).

## Images

Every new document and presentation has an `images/` folder: put your image files there (PNG, JPG, SVG, GIF or WebP). The last question, **Sample image**, copies a sample into that folder and shows it in the document as a numbered figure with a caption, or on the "Main finding" slide of a presentation. Change the file name to your own image when you're ready; `finishdoc` reports the sample as leftover until you do. The sample lives in `samples/sample.png` in this repo.

`width` is relative to the text width (`60%`) or absolute (`8cm`). On slides, `height: 60%` keeps an image from pushing content onto an extra page.

## Writing in the generated file

| You want | Write |
|---|---|
| Heading | `= Title`, `== Subtitle` |
| Footnote | `#footnote[text]` |
| Citation | `@key`, then add the BibTeX entry in the **References** block at the bottom of `main.typ` |
| Passage in another language | `#es[Hola]` (one helper for each extra language you listed) |
| Image | `#image("images/photo.png", width: 60%)` |
| Numbered figure with a caption | `#figure(image("images/photo.png", width: 60%), caption: [Text]) <fig-photo>`, then refer to it with `@fig-photo` |

To use a bibliography exported from Zotero instead, put `refs.bib` next to `main.typ` and replace the References block with `#bibliography("refs.bib", style: "apa")`.

## Development

```sh
python3 test_new_doc.py   # generates and compiles every document type and presentation theme, and tests finishdoc
```

The repo uses an allowlist `.gitignore`. Only the tool's files are tracked, so documents you create inside this folder are never committed. When you add a file to the tool, add a matching `!/filename` line to `.gitignore`.
