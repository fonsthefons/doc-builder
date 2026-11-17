# What to check when doc-builder fails

Start with the tests: `python3 test_new_doc.py` and `python3 test_fill_slides.py`. If they pass, the problem is in the document, not in the tool.

## `newdoc` / `finishdoc` / `fillslides`: "command not found"

- Is `~/.local/bin` on your PATH? Check with `echo $PATH`. `install.sh` adds it to `~/.zshrc`, so open a new terminal.
- Are the links still there? `ls -l ~/.local/bin/newdoc` should point into this repo. If you moved the repo, run `./install.sh` again.
- Without the links: `python3 /path/to/doc-builder/new_doc.py`.

## `finishdoc` reports problems (exit 1)

Each problem comes with its line number in `main.typ`.

| Problem | What to do |
|---|---|
| Leftover template text ("Your Name", lorem ipsum, empty `#answer[]`, the sample image) | Replace it, or delete it. Lines starting with `//` are ignored. |
| Uncited bibliography entries | Cite them with `@key`, or remove them from the `.bib` file. |
| Typst error: unknown font | Install the font, or change it in the `#set text(font: ...)` line. Run `typst fonts` to list the fonts Typst sees. |
| Typst error: missing image or `@reference` | Check the file name in `images/` (it is case-sensitive) and the label's spelling. |
| Slide overflows onto an extra page | Shorten that slide, or split it in two. The message names the slide's line. |
| Spelling | Fix it, or add the word (one per line) to `dictionary.txt` next to `main.typ`. Use `--no-spell` to skip the check. |
| "aspell not found" (the spellcheck is skipped) | `brew install aspell`. |
| `--pdfa` fails | PDF/A doesn't allow some things (e.g. transparent images in older Typst versions). Run `brew upgrade typst`, or leave out `--pdfa` if the submission doesn't need it. |

## `typst watch` / compile errors

- Run `typst compile main.typ` once to see the full error.
- After `brew upgrade typst`, an old document may hit a changed rule. The error names the line: compare it with a newly generated `newdoc` file of the same type.

## `fillslides`

| Message | Cause | What to do |
|---|---|---|
| `LM Studio's lms command not found` | LM Studio not installed or never opened | Install it, open it once, run `~/.lmstudio/bin/lms bootstrap`. |
| `cannot reach LM Studio at http://localhost:1234/...` | The server didn't start, or another app is using port 1234 | Run `lms server start` by hand and read the error. Check the port with `lsof -i :1234`. |
| `could not start the LM Studio server` | LM Studio problem | Open the LM Studio app. It often shows the reason there (an update waiting, a broken settings file). |
| Model not found | The model in the notes header (`model:`) or the default `qwen2.5-14b-instruct` isn't downloaded | `lms ls` to see what you have. `lms get <model>`, or set `model:` to one you have. |
| Very slow, or the Mac swaps | The model is too big for free RAM | Close apps, or choose a smaller model with `model:`. |
| A slide marked `// FIXME` | It still overflows after one retry | Edit `slides.json`, then `fillslides my-talk --build`. |
| `main.typ` content replaced by mistake | — | The previous version is in `main.typ.bak`. |

## Install

- **`brew` not found**: install Homebrew first (mac-setup). Typst and aspell are installed through it.
- **`python3` too old**: the scripts use only the standard library, but they need a recent Python 3. Homebrew's `python3` works.
