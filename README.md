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
- links the `newdoc`, `finishdoc` and `fillslides` commands into `~/.local/bin`;
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
| Two or three columns | `#cols([left], [right])` |
| Boxed point (put 2–3 in `#cols`) | `#card[Heading][Text]` |
| Highlighted quote | `#quote(block: true)[“...”]` |
| Closing line at the bottom of the slide | `#takeaway[...]` |
| Small label above the title (e.g. a section number) | `#kicker[29D]` on the line before `= Slide title` |
| Lettered list | `#enum(numbering: "A", [one], [two])` |

### Slides from notes with a local LLM

`fillslides` writes the slides of a presentation from a notes file, using a model in [LM Studio](https://lmstudio.ai). It starts LM Studio's server and loads the model itself, and afterwards stops whatever it started (a server or model you already had running is left alone).

```sh
newdoc                         # make the presentation first (title, theme, language)
fillslides my-talk             # reads my-talk/slides.txt; or: fillslides my-talk notes.md
fillslides my-talk --build     # after editing my-talk/slides.json: rebuild the slides without the LLM
fillslides my-talk/other.json --build   # rebuild from another JSON file; a notes file works the same way
```

Header lines at the top of the notes file (all optional):

```
mode: summarize     # long, detailed notes: bold phrases and quotes become the slides (default)
mode: exact         # the notes already are the slides: keep the wording, only lay them out
mode: expand        # a few lines: the model builds the talk and marks facts it added with (?)
slides: 8           # number of content slides, when the notes have no slide breaks
model: qwen2.5-14b-instruct
```

Mark slide breaks with a line of dashes (`---`, or `—---3---`): you get exactly one slide per block. Without them, the model first splits your ideas into slides. For each slide the model answers JSON, forced by a schema, and the script writes the Typst:

```json
{"layout": "cards", "kicker": "", "title": "El constructor bueno", "intro": "", "quote": "",
 "items": [{"head": "Bondad", "text": "Quiso que todo fuera *bueno*."}, {"head": "Orden", "text": "Del desorden al orden."}],
 "takeaway": "El universo es un viviente."}
```

Layouts: `bullets`, `cards` (2–3 with headings), `steps` (numbered), `quote`, `section` (divider). The script fixes a layout that doesn't fit its items (e.g. 4 cards become bullets), drops a kicker that isn't in your notes, and escapes all text, so only `*bold*` is markup. All slides are saved in `slides.json`: edit them there and run `--build`. A slide that still overflows after one retry is marked `// FIXME`. Citations aren't generated; add `@key` by hand. The content section of `main.typ` is replaced (the old file is saved as `main.typ.bak`), and the slides are written in the presentation's language. Local models write plainer slides than you would, so review them before `finishdoc`.

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
python3 test_fill_slides.py   # fillslides without an LLM: parsing, slide checks, escaping and every layout
```

The repo uses an allowlist `.gitignore`. Only the tool's files are tracked, so documents you create inside this folder are never committed. When you add a file to the tool, add a matching `!/filename` line to `.gitignore`.
