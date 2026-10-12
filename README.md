# Wen Chen personal homepage

The homepage is generated from `data/site.json` and `index.template.html`.
Generated HTML is kept in the repository for static hosting.

## Update content

1. For homepage content, edit `data/site.json`.
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

The blog was removed on 2026-10-11 and archived at git tag `blog-archive-2026-10-11`.
