# Wen Chen personal homepage

The homepage is generated from `data/site.json` and `index.template.html`.

## Update content

1. Edit `data/site.json` only. Keep both `en` and `zh` values for bilingual fields.
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
