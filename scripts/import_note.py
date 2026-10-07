#!/usr/bin/env python3
"""Fill a post's blocks from a Chinese/English Markdown note pair (README.md + README.en.md).

    python3 scripts/import_note.py <note-dir> <slug> --sections N

Only the post's blocks, contents and references are replaced; title, dates, series and tags
stay as set in data/blog/<slug>.json. Figures are copied as SVG into assets/blog/<prefix>-<name>.svg.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CITE = re.compile(r'\[\[(\d+)((?:,[^\]]*)?)\]\]\(#ref-\1\)')


def inline(text: str) -> str:
    """Markdown citations [[n, §x]](#ref-n) become the post's linked form."""
    return CITE.sub(lambda m: f'[<a href="#ref-{m[1]}">{m[1]}</a>{m[2]}]', text.strip())


def parse(lines: list[str]) -> list[dict]:
    blocks, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith('### '):
            blocks.append({'type': 'subheading', 'text': line[4:].strip()}); i += 1
        elif line.startswith('## '):
            blocks.append({'type': 'heading', 'text': line[3:].strip()}); i += 1
        elif line.lstrip().startswith('$$'):
            tex = [line.strip()[2:]]
            while not tex[-1].rstrip().endswith('$$') or (len(tex) == 1 and tex[0].strip() == ''):
                i += 1
                tex.append(lines[i].strip())
            blocks.append({'type': 'math', 'tex': '\n'.join(tex)[:-2].strip()}); i += 1
        elif line.startswith('!['):
            alt, src = re.match(r'!\[(.*)\]\((.*)\)', line).groups()
            i += 1
            while not lines[i].strip():
                i += 1
            caption = lines[i].strip()
            caption = caption[1:-1] if caption.startswith('*') and caption.endswith('*') else caption
            blocks.append({'type': 'figure', 'src': src, 'alt': alt, 'caption': inline(caption)}); i += 1
        elif line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?', c) for c in cells):
                    rows.append([inline(c) for c in cells])
                i += 1
            blocks.append({'type': 'table', 'rows': rows})
        elif line.startswith('- '):
            items = []
            while i < len(lines) and (lines[i].startswith('- ') or lines[i].startswith('  ') or not lines[i].strip()):
                if lines[i].startswith('- '):
                    items.append([lines[i][2:]])
                elif not lines[i].strip() and not (i + 1 < len(lines) and lines[i + 1].startswith('  ')):
                    break
                else:
                    items[-1].append(lines[i][2:])
                i += 1
            blocks.append({'type': 'list', 'items': [parse(item) for item in items]})
        else:
            text = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r'(#|\$\$|!\[|- |\|)', lines[i].lstrip()):
                text.append(lines[i]); i += 1
            blocks.append({'type': 'paragraph', 'text': inline(' '.join(t.strip() for t in text))})
    return blocks


def sections(path: Path, count: int) -> tuple[list[dict], list[str]]:
    text = path.read_text()
    body, _, refs = re.split(r'^## (参考.*|References)$', text, maxsplit=1, flags=re.M)
    body = body.split('\n', 1)[1]  # drop the title line
    parts = re.split(r'(?=^## )', body, flags=re.M)
    kept = [p for p in parts if p.startswith('## ')][:count]
    references = re.findall(r'^\d+\. <a id="ref-\d+"></a>(.+)$', refs, flags=re.M)
    return parse(''.join(kept).splitlines()), references


def merge(zh: list[dict], en: list[dict], figures: dict) -> list[dict]:
    if [b['type'] for b in zh] != [b['type'] for b in en]:
        raise ValueError(f'Chinese and English structure differ:\n{[b["type"] for b in zh]}\n{[b["type"] for b in en]}')
    merged = []
    for a, b in zip(zh, en):
        kind = a['type']
        if kind in ('heading', 'subheading', 'paragraph'):
            merged.append({'type': kind, 'text': {'zh': a['text'], 'en': b['text']}})
        elif kind == 'math':
            merged.append({'type': 'math', 'tex': a['tex'] if a['tex'] == b['tex'] else {'zh': a['tex'], 'en': b['tex']}})
        elif kind == 'figure':
            if a['src'] != b['src']:
                raise ValueError(f'Figure mismatch: {a["src"]} / {b["src"]}')
            merged.append({'type': 'figure', 'src': figures[a['src']], 'alt': {'zh': a['alt'], 'en': b['alt']},
                           'caption': {'zh': a['caption'], 'en': b['caption']}})
        elif kind == 'table':
            if [len(r) for r in a['rows']] != [len(r) for r in b['rows']]:
                raise ValueError('Table shape differs')
            merged.append({'type': 'table', 'rows': [[{'zh': x, 'en': y} for x, y in zip(r, s)] for r, s in zip(a['rows'], b['rows'])]})
        else:
            if len(a['items']) != len(b['items']):
                raise ValueError('List length differs')
            merged.append({'type': 'list', 'items': [{'blocks': merge(x, y, figures)} for x, y in zip(a['items'], b['items'])]})
    return merged


def figure_sources(blocks: list[dict]) -> list[str]:
    found = []
    for block in blocks:
        if block['type'] == 'figure':
            found.append(block['src'])
        elif block['type'] == 'list':
            for item in block['items']:
                found += figure_sources(item)
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('note', type=Path)
    parser.add_argument('slug')
    parser.add_argument('--sections', type=int, required=True)
    parser.add_argument('--prefix', default=None, help='figure file prefix (default: first word of slug)')
    args = parser.parse_args()
    zh, refs_zh = sections(args.note / 'README.md', args.sections)
    en, refs_en = sections(args.note / 'README.en.md', args.sections)
    if refs_zh != refs_en:
        raise ValueError('Reference lists differ between README.md and README.en.md')
    prefix = args.prefix or args.slug.split('-')[0][:5]
    figures = {}
    for src in figure_sources(zh):
        svg = (args.note / src).with_suffix('.svg')
        target = f'{prefix}-{svg.name}'
        shutil.copyfile(svg, ROOT / 'assets/blog' / target)
        figures[src] = f'../assets/blog/{target}'
    blocks = merge(zh, en, figures)
    path = ROOT / 'data/blog' / f'{args.slug}.json'
    post = json.loads(path.read_text())
    post['contents'] = [{'target': f'block-{n}', 'label': block['text']} for n, block in enumerate(blocks) if block['type'] == 'heading']
    post['blocks'] = blocks
    post['references'] = [{'text': {'zh': ref, 'en': ref}} for ref in refs_zh]
    path.write_text(json.dumps(post, ensure_ascii=False, indent=2) + '\n')
    print(f'{path.name}: {len(blocks)} blocks, {len(figures)} figures, {len(refs_zh)} references')


if __name__ == '__main__':
    main()
