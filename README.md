# doc-builder

An interactive command that creates a ready-to-edit [Typst](https://typst.app) document. It asks about the title, authors, margins, font, header and footer, page numbers, footnotes, languages, bibliography and more, then writes `<folder>/main.typ`.

## Install

```sh
git clone git@github.com:fonsthefons/doc-builder.git
cd doc-builder
./install.sh
```

The install script:
- installs Typst with Homebrew if it's missing;
- links the `newdoc` and `finishdoc` commands into `~/.local/bin`;
- adds that folder to your PATH if it isn't there already.

It only needs `python3`. The script uses the standard library alone, so there are no packages to install.

## Usage

```sh
cd ~/where/the/doc/should/live
newdoc            # answer the questions; press Enter to accept [defaults]
newdoc --help     # list document types and tips
```

The document folder is created inside the folder you run `newdoc` from. You can also type a path such as `~/uni/essay-1` when it asks for the folder name.

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
- Typst errors and warnings (missing fonts, broken `@references`, missing images).

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

## Writing in the generated file

| You want | Write |
|---|---|
| Heading | `= Title`, `== Subtitle` |
| Footnote | `#footnote[text]` |
| Citation | `@key`, then add the BibTeX entry in the **References** block at the bottom of `main.typ` |
| Passage in another language | `#es[Hola]` (one helper for each extra language you listed) |
| Image | `#image("photo.png", width: 60%)` |

To use a bibliography exported from Zotero instead, put `refs.bib` next to `main.typ` and replace the References block with `#bibliography("refs.bib", style: "apa")`.

## Development

```sh
python3 test_new_doc.py   # generates and compiles every document type, and tests finishdoc
```

The repo uses an allowlist `.gitignore`. Only the tool's files are tracked, so documents you create inside this folder are never committed. When you add a file to the tool, add a matching `!/filename` line to `.gitignore`.
