#!/usr/bin/env bash
# Print how to run this repo's main features.
cat <<'EOF'
doc-builder: interactive commands that create, fill and finish Typst documents and presentations.

  ./ui.sh
      The same commands in a browser page.

  ./install.sh
      Install Typst and aspell, and link newdoc, finishdoc and fillslides into ~/.local/bin.

  python3 new_doc.py
      Create a document or presentation by answering questions (same as `newdoc`; run it where the doc should live).

  python3 new_doc.py --help
      List document types, presentation themes and tips.

  typst watch mybook/main.typ
      Rebuild main.pdf on every save while you edit.

  python3 finish_doc.py mybook --pdfa
      Check for leftover text, uncited refs, Typst errors and spelling, then write mybook/mybook.pdf (PDF/A-2b).

  python3 fill_slides.py my-talk notes.md
      Write the slides of a presentation from a notes file with a local LM Studio model.

  python3 fill_slides.py my-talk --build
      Rebuild the slides from my-talk/slides.json after editing it, without the LLM.

  python3 test_new_doc.py && python3 test_fill_slides.py
      Run the tests (compile every document type and theme; fillslides without an LLM).

After ./install.sh the short names work from any folder: newdoc, finishdoc essay-1 --pdfa, fillslides my-talk.
More: README.md (how it works), to_check_in_case_of_failure.md (what to do when it breaks).
EOF
