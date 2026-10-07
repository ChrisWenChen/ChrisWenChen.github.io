# Wen Chen personal homepage

The homepage is generated from `data/site.json` and `index.template.html`.
The standalone blog index and bilingual articles are generated from `data/blog/*.json`
and `blog.template.html`. Generated HTML is kept in the repository for static hosting.

## Update content

1. For homepage content, edit `data/site.json`. For articles, edit `data/blog/*.json`.
   Keep both `en` and `zh` values for bilingual fields; change templates for layout/navigation.
2. Generate the public page:

   ```bash
   python3 scripts/build.py
   ```

3. Check that the generated page is up to date:

   ```bash
   python3 scripts/build.py --check
   ```

The build fails when a bilingual field is missing either language. Preview locally with:

```bash
python3 -m http.server 8765
```

Then open <http://localhost:8765/index.html>.

## Blog

- The index opens with **Recent** (newest creation date first), followed by **Series**
  (all posts in manually curated topic/order). Edit `data/blog-index.json` to set
  `recent_limit` and arrange `directories`: each has a bilingual `title` and ordered
  `posts` list. Entries may be slug strings, objects with `slug` and a bilingual
  display `title`, or title-only objects for planned articles (no link or dates).
  Empty directories remain visible. Planned articles do not enter Recent or search.
  Every published post must appear exactly once in the archive.
- Tags: `data/blog-index.json` holds the tag vocabulary (`tags`: key → bilingual label);
  each post lists 1–4 of those keys in `tags`. Tags appear as filter chips beside the
  search box, on Recent cards, and in the article header (linking to `index.html?tag=key`).
  A tag only narrows the list; result order stays newest-created first.
- Notes kept as a Chinese/English Markdown pair (`README.md` + `README.en.md` in one folder)
  can refill a post's body: `python3 scripts/import_note.py <note-dir> <slug> --sections N`
  imports the first N `##` sections (both files must have the same block structure), copies
  their figures as SVG into `assets/blog/`, and keeps the post's title, dates, series and tags.
- Each article requires `created` and `updated` dates (`YYYY-MM-DD`). Maintain these
  explicitly; layout rebuilds do not change article dates. The first post dates reflect
  its original local creation/edit session on 2026-10-03.
- Recent entries use the first article figure as their thumbnail, when available.
  Search replaces both sections with a deduplicated result list across Chinese/English
  titles, summaries, series and article body/captions, without a server. Results show
  highlighted matching excerpts, preferring the interface language where possible.
  Space-separated terms must all match; matching ignores case and normalizes full-width
  characters. Results retain newest-created order. Clear search to restore the directory.

- Index: <http://localhost:8765/blog/index.html>
- First article: <http://localhost:8765/blog/early-theories-of-light.html?lang=zh>
- English: <http://localhost:8765/blog/early-theories-of-light.html?lang=en>
- The language controls update the visible article, document language/title, metadata,
  and reference anchors. Preferences are shared with the homepage through
  `site-language` in local storage; `?lang=en|zh` overrides the saved preference.
- Counts are generated from the selected language's body and figure captions,
  excluding titles, section headings, reference markers, and the bibliography. Chinese
  counts one unit per Han character plus one per English/numeric token; English counts
  words. An inline formula counts as one unit; display equations are not counted.
  Reading time is rounded up at 300 Chinese units/minute or 200 English words/minute.
  The metadata tooltip explains this convention. Figures may take longer to study.
- The article is a bilingual snapshot of **sections 1-3** (the whole of "光的早期理论")
  from the `klm-graviton-scattering` project's
  `notes/optics/01-early-theories/README.md`, not a live dependency on that repository.
  It contains twelve figures; only the referenced SVGs are copied to `assets/blog/`.
  No planning notes or local book PDFs are copied. Image attribution and licensing are
  preserved in references 2, 10, and 11.
- The bibliography has 11 entries. Section citations include their chapter/section
  locators and link to the matching language's bibliography entry.
- Where the note explains Chinese labels inside a display equation (the fringe
  conditions in section 3), the English page gets English labels and the note's
  explanatory aside is left out; everything else is the note's text verbatim.

### Post data

- Block types: `paragraph`, `heading` (a section title), `list`, `figure`, and `math`
  (`{"type": "math", "tex": "..."}`, a display equation; give `tex` as `{"zh": ..., "en": ...}`
  when the equation contains words that differ by language). List items may be bilingual
  strings or structured `blocks` containing bilingual paragraphs and display-math blocks.
  Inline markup supports
  `**bold**`, `*italic*`, `$TeX$`, and numbered references written either as
  `[[5]](#ref-5)` or as a group copied from the notes,
  `[<a href="#ref-5">5</a>,<a href="#ref-10">10</a>]`, which renders as `[5,10]`. A group
  may carry locators and join several sources with semicolons, e.g.
  `[<a href="#ref-5">5</a>, §5.3; <a href="#ref-6">6</a>, §8.4]`. Formulas may sit inside
  bold or italic text.
- Formulas are TeX, typeset in the browser by the bundled KaTeX 0.16.47
  (`assets/vendor/katex/`, MIT license, woff2 fonts only). Pages without formulas do
  not load it, no network service is involved, and the TeX stays readable if scripts
  are off. The test suite checks every formula with KaTeX when `node` is available.
- A block or contents entry with `"langs": ["zh"]` exists in Chinese only and needs
  only its `zh` text. The English page shows a short note where such a part starts,
  and leaves it out of the English contents, counts and search. To translate it, add
  the `en` text and delete `langs`. Every other bilingual value still needs both
  languages.
- Search and the card excerpts use plain text: citation markers, emphasis marks and
  formulas are dropped (single-letter symbols such as `$B'$` stay).
- The generated pages tag `blog.css`, `blog.js` and the KaTeX files with a content hash
  (`?v=...`) so a browser never pairs a new page with a cached old script. Re-run
  `python3 scripts/build.py` after editing any of them.

Checks:

```bash
python3 scripts/build.py --check
python3 -m unittest discover -s tests
node --check assets/blog.js
```

These commands only build/check local files. They do not commit, push, or deploy.
