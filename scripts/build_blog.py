#!/usr/bin/env python3
"""Build local bilingual blog pages from data/blog/*.json (standard library only)."""
from __future__ import annotations

import hashlib
import html
import json
import math
import re
from pathlib import Path
from datetime import date
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
LANGS = ('en', 'zh')
# Citations may include a list of source locators after their linked references.
# Locators cover section/chapter numbers, page numbers, and equation numbers,
# including ranges whose lower endpoint carries the section prefix (e.g. §6.4.3–§6.4.6).
_NUM = r'\d+(?:\.\d+)*'
_ROMAN = r'[0-9IVXLC一二三四五六七八九十百]+'
_RANGE = r'(?:\s*[–-]\s*(?:§{1,2}\s*)?' + _NUM + r')?'
_LOC = (r'(?:§{1,2}\s*' + _NUM + _RANGE +
        r'|(?:ch\.\s*|第\s*)' + _ROMAN + r'\s*[章节]?' +
        r'|pp?\.\s*' + _NUM + r'(?:\s*[–-]\s*' + _NUM + r')?' +
        r'|(?:式|Eqs?\.)\s*\(\s*' + _NUM + r'\s*\)' + r'(?:\s*[–-]\s*\(\s*' + _NUM + r'\s*\))?' +
        r'|\(\s*' + _NUM + r'\s*\)' +
        r'|(?:引言|introduction)' +
        r'|' + _NUM + _RANGE + r')')
LOCATOR = _LOC + r'(?:[，,]?\s*' + _LOC + r')*'
# A group is one or more linked references with an optional locator; groups may be joined by semicolons.
GROUP = r'(?:<a href="#ref-\d+">\d+</a>,?)+(?:,\s*' + LOCATOR + r')?'
CITATION = re.compile(r'\[\[(\d+)\]\]\(#ref-\1\)|\[(' + GROUP + r'(?:;\s*' + GROUP + r')*)\]')
MATH = re.compile(r'\$([^$]+)\$')
TOKEN = re.compile(CITATION.pattern + r'|\*\*(.+?)\*\*|\*([^*]+)\*|' + MATH.pattern)
UNTRANSLATED = {'en': 'The following sections are currently available in Chinese only.',
                'zh': '以下部分暂无中文版。'}
MATH_HEAD = ('\n  <link rel="stylesheet" href="../assets/vendor/katex/katex.min.css">'
             '\n  <script src="../assets/vendor/katex/katex.min.js" defer></script>')


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def citation(number: str, lang: str, nrefs: int, label: str) -> str:
    if not 1 <= int(number) <= nrefs:
        raise ValueError(f'Unknown reference {number}')
    return f'<a class="citation" href="#{lang}-ref-{number}" aria-label="Reference {number}">{label}</a>'


def inline(text: str, lang: str, nrefs: int) -> str:
    """Render the small, explicit inline vocabulary used in the post data."""
    out, pos = [], 0
    for match in TOKEN.finditer(text):
        out.append(esc(text[pos:match.start()]))
        number, group, bold, italic, tex = match.groups()
        if number:
            out.append(citation(number, lang, nrefs, f'[{number}]'))
        elif group:
            parts = []
            for part in group.split(';'):
                links = []
                for target, label in re.findall(r'<a href="#ref-(\d+)">(\d+)</a>', part):
                    if target != label:
                        raise ValueError(f'Citation link {target} is labelled {label}')
                    links.append(citation(target, lang, nrefs, label))
                locator = re.search(r'</a>,\s*(' + LOCATOR + r')$', part.strip())
                parts.append(','.join(links) + (', ' + esc(locator[1]) if locator else ''))
            out.append('<span class="citation-group">[' + '; '.join(parts) + ']</span>')
        elif bold:
            out.append(f'<strong>{inline(bold, lang, nrefs)}</strong>')
        elif italic:
            out.append(f'<em>{inline(italic, lang, nrefs)}</em>')
        else:
            # TeX stays in the markup (readable without scripts); the page's local KaTeX typesets it.
            out.append(f'<span class="math" data-tex="{esc(tex)}">{esc(tex)}</span>')
        pos = match.end()
    out.append(esc(text[pos:]))
    return ''.join(out)


def available(item: dict, lang: str) -> bool:
    """Blocks and contents entries appear in every language unless `langs` narrows it."""
    return lang in item.get('langs', LANGS)


def texts(post: dict, lang: str, headings: bool = False) -> list[str]:
    result = []

    def visit(blocks: list[dict]) -> None:
        for block in blocks:
            if not available(block, lang):
                continue
            kind = block['type']
            if kind == 'paragraph':
                result.append(block['text'][lang])
            elif kind in ('heading', 'subheading'):
                if headings:
                    result.append(block['text'][lang])
            elif kind == 'list':
                for item in block['items']:
                    if isinstance(item, str):
                        result.append(item)
                    elif 'blocks' in item:
                        visit(item['blocks'])
                    else:
                        if available(item, lang):
                            result.append(item[lang])
            elif kind == 'figure':
                result.append(block['caption'][lang])
            elif kind != 'math':
                raise ValueError(f'Unknown block type: {kind}')

    visit(post['blocks'])
    return result


def plain(text: str) -> str:
    """The words a reader sees: no citation, emphasis or formula markup (used for search and excerpts)."""
    text = CITATION.sub('', text)
    text = MATH.sub(lambda m: m[1].replace("'", '′') if re.fullmatch(r"[A-Za-z]'?", m[1]) else '', text)
    text = re.sub(r'\*\*(.+?)\*\*|\*([^*]+)\*', lambda m: m[1] or m[2], text)
    return re.sub(r'\s+', ' ', text).strip()


def stats(post: dict, lang: str) -> tuple[int, int]:
    text = '\n'.join(texts(post, lang))
    text = CITATION.sub('', text)
    # An inline formula counts as one unit; display equations are not counted.
    text = MATH.sub('x', text)
    words = re.findall(r"[A-Za-z0-9]+(?:[’'\-][A-Za-z0-9]+)*", text)
    count = len(words)
    if lang == 'zh':
        count += len(re.findall(r'[\u3400-\u4dbf\u4e00-\u9fff]', text))
    return count, max(1, math.ceil(count / (300 if lang == 'zh' else 200)))


def metadata(post: dict, lang: str) -> str:
    count, minutes = stats(post, lang)
    label = f'{count:,} 字 · 预计阅读 {minutes} 分钟' if lang == 'zh' else f'{count:,} words · {minutes} min read'
    explanation = ('统计正文与图注，不含标题和参考文献；汉字逐字计数，英文和数字按词计。按每分钟300字估算。'
                   if lang == 'zh' else 'Body and captions, excluding the title and references. Estimated at 200 words per minute.')
    return f'<p class="post-meta" title="{esc(explanation)}">{label}</p>'


def figure_size(path: Path) -> tuple[int, int]:
    """Width/height attributes (width 2000) from an SVG's viewBox, so the layout reserves the right space."""
    with path.open(errors='ignore') as handle:
        match = re.search(r'viewBox="[\d.]+ [\d.]+ ([\d.]+) ([\d.]+)"', handle.read(2000))
    return (2000, round(2000 * float(match[2]) / float(match[1]))) if match else (2000, 1517)


def content(post: dict, lang: str) -> str:
    nrefs = len(post['references'])

    def render_blocks(block_list: list[dict], prefix: str, top: bool = False) -> str:
        rendered = []
        for index, block in enumerate(block_list):
            if not available(block, lang):
                continue
            kind = block['type']
            block_id = f'{lang}-block-{prefix}' if top else f'{prefix}-block-{index}'
            if kind in ('paragraph', 'heading', 'subheading'):
                tag = {'heading': 'h2', 'subheading': 'h3'}.get(kind, 'p')
                rendered.append(f'<{tag} id="{block_id}">{inline(block["text"][lang], lang, nrefs)}</{tag}>')
            elif kind == 'math':
                # `tex` is a string, or a {zh, en} pair when the equation carries words (labels, units).
                tex = block['tex'][lang] if isinstance(block['tex'], dict) else block['tex']
                rendered.append(f'<div class="math-display" id="{block_id}" data-tex="{esc(tex)}">{esc(tex)}</div>')
            elif kind == 'list':
                items = []
                for number, item in enumerate(block['items']):
                    item_id = f'{lang}-item-{prefix}-{number}' if top else f'{prefix}-item-{index}-{number}'
                    if isinstance(item, str):
                        value = inline(item, lang, nrefs)
                    elif 'blocks' in item:
                        value = render_blocks(item['blocks'], item_id)
                    else:
                        value = inline(item[lang], lang, nrefs) if available(item, lang) else ''
                    items.append(f'<li id="{item_id}">{value}</li>')
                rendered.append('<ul class="post-list">' + ''.join(items) + '</ul>')
            elif kind == 'figure':
                src = block['src']
                if not src.startswith('../assets/blog/') or not (ROOT / 'blog' / src).resolve().is_file():
                    raise ValueError(f'Missing or invalid figure: {src}')
                width, height = figure_size((ROOT / 'blog' / src).resolve())
                rendered.append(f'<figure id="{block_id}"><a href="{esc(src)}" target="_blank" rel="noopener" class="figure-link"><img src="{esc(src)}" alt="{esc(block["alt"][lang])}" width="{width}" height="{height}"></a><figcaption>{inline(block["caption"][lang], lang, nrefs)}</figcaption></figure>')
            else:
                raise ValueError(f'Unknown block type: {kind}')
        return ''.join(rendered)

    blocks, noted = [], False
    for index, block in enumerate(post['blocks']):
        if not available(block, lang):
            if not noted:
                blocks.append(f'<p class="translation-note" id="{lang}-translation-note">{UNTRANSLATED[lang]}</p>')
                noted = True
        else:
            blocks.append(render_blocks([block], str(index), top=True))
    references = []
    for number, ref in enumerate(post['references'], 1):
        url = ref.get('url', '')
        parsed_url = urlsplit(url) if url else None
        if url and (parsed_url.scheme != 'https' or not parsed_url.hostname or parsed_url.username or parsed_url.password
                    or parsed_url.hostname.lower() in ('localhost', '127.0.0.1', '::1')
                    or re.search(r'/(?:Users|home|Volumes)(?:/|$)', parsed_url.path)):
            raise ValueError('References must use public HTTPS URLs, not local library paths')
        label = inline(ref['text'][lang], lang, nrefs)
        entry = f'<a href="{esc(url)}">{label}</a>' if url else label
        references.append(f'<li id="{lang}-ref-{number}">{entry}</li>')
    heading = '参考文献' if lang == 'zh' else 'References'
    return '\n'.join(blocks) + f'<section class="references" aria-labelledby="{lang}-references"><h2 id="{lang}-references">{heading}</h2><ol>{"".join(references)}</ol></section>'


def validate_contents_targets(post: dict, lang: str, article_content: str) -> None:
    targets = set(re.findall(r'\bid="([^"]+)"', article_content))
    for entry in post.get('contents', []):
        if available(entry, lang) and f'{lang}-{entry["target"]}' not in targets:
            raise ValueError(f'Invalid contents target for {lang}: {entry["target"]}')


def contents(post: dict, lang: str) -> str:
    label = '目录' if lang == 'zh' else 'Contents'
    entries = ''.join(f'<li><a href="#{lang}-{esc(item["target"])}">{esc(item["label"][lang])}</a></li>' for item in post.get('contents', []) if available(item, lang))
    progress = '阅读进度' if lang == 'zh' else 'Reading progress'
    # The slider stays hidden until blog.js enables it, so the contents work without scripts.
    slider = (f'<div class="read-progress" role="slider" tabindex="0" hidden aria-orientation="vertical" aria-label="{progress}" '
              'aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><span class="read-thumb"></span></div>')
    return (f'<aside class="post-toc" aria-label="{label}"><details open><summary>{label}</summary>'
            f'<div class="toc-body">{slider}<ol>{entries}</ol><p class="read-percent" aria-hidden="true"></p></div></details></aside>')


def bilingual(value: dict) -> str:
    return ''.join(f'<span class="lang-{lang}" lang="{"zh-CN" if lang == "zh" else "en"}">{esc(value[lang])}</span>' for lang in LANGS)


def versioned(markup: str) -> str:
    """Tag local css/js with a content hash, so a browser never pairs a new page with a cached old script."""
    def tag(match: re.Match) -> str:
        digest = hashlib.sha1((ROOT / 'blog' / match['url']).resolve().read_bytes()).hexdigest()[:8]
        return f'{match["attr"]}="{match["url"]}?v={digest}"'
    return re.sub(r'(?P<attr>href|src)="(?P<url>\.\./assets/[^"?]+\.(?:css|js))"', tag, markup)


def page(body: str, titles: dict[str, str], descriptions: dict[str, str], listing: bool = False) -> str:
    template = (ROOT / 'blog.template.html').read_text()
    replacements = {'TITLE': esc(titles['en']), 'TITLE_EN': esc(titles['en']), 'TITLE_ZH': esc(titles['zh']),
                    'DESCRIPTION': esc(descriptions['en']), 'BODY': body, 'HEAD': MATH_HEAD if 'data-tex="' in body else '',
                    'BLOG_CURRENT': ' aria-current="page"' if listing else ''}
    for key, value in replacements.items():
        template = template.replace('{{' + key + '}}', value)
    if re.search(r'\{\{[A-Z_]+\}\}', template):
        raise ValueError('Unfilled blog template slot')
    return versioned(template).rstrip() + '\n'


def validate_languages(value: object, langs: tuple[str, ...] = LANGS) -> None:
    """Bilingual values need nonempty text in each language; a `langs` list narrows that for what it contains."""
    if isinstance(value, dict):
        if 'langs' in value:
            langs = tuple(value['langs'])
            if not langs or not set(langs) <= set(LANGS) or len(set(langs)) != len(langs):
                raise ValueError('langs must list en and/or zh')
        if 'en' in value or 'zh' in value:
            if set(value) != set(langs) or any(not isinstance(value[x], str) or not value[x].strip() for x in langs):
                raise ValueError('Bilingual values require nonempty ' + ' and '.join(langs) + ' strings')
        for key, child in value.items():
            if key != 'langs':
                validate_languages(child, langs)
    elif isinstance(value, list):
        for child in value:
            validate_languages(child, langs)


def dates(post: dict) -> str:
    return '<p class="post-dates">' + ''.join(
        f'<span>{bilingual(labels)} <time datetime="{post[key]}">{post[key]}</time></span>'
        for key, labels in [('created', {'en': 'Created', 'zh': '创建'}),
                            ('updated', {'en': 'Updated', 'zh': '最后更新'})]) + '</p>'


def tag_links(post: dict, vocabulary: dict, lang: str | None = None) -> str:
    """Each tag links to the index filtered by that tag; `lang` picks one label, otherwise both are emitted."""
    items = ''.join(f'<li><a href="index.html?tag={tag}">{esc(vocabulary[tag][lang]) if lang else bilingual(vocabulary[tag])}</a></li>'
                    for tag in post['tags'])
    return f'<ul class="post-tags">{items}</ul>'


def validate_tags(posts: list[dict], vocabulary: dict) -> None:
    for key in vocabulary:
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', key):
            raise ValueError(f'Invalid tag key: {key}')
    for post in posts:
        tags = post.get('tags')
        if not isinstance(tags, list) or not 1 <= len(tags) <= 4 or len(set(tags)) != len(tags):
            raise ValueError(f'{post["slug"]}: tags must list 1–4 distinct keys')
        unknown = [tag for tag in tags if tag not in vocabulary]
        if unknown:
            raise ValueError(f'{post["slug"]}: tags not in data/blog-index.json: {unknown}')


def search_text(post: dict) -> str:
    return esc(' '.join(post[field][lang] for field in ('title', 'description', 'series') for lang in LANGS)
               + ' ' + ' '.join(plain(text) for lang in LANGS for text in texts(post, lang, headings=True)))


SUBSCRIPT = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')
SUPERSCRIPT = str.maketrans('0123456789T', '⁰¹²³⁴⁵⁶⁷⁸⁹ᵀ')
GREEK = {'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ', 'epsilon': 'ε', 'theta': 'θ', 'lambda': 'λ',
         'mu': 'μ', 'nu': 'ν', 'pi': 'π', 'sigma': 'σ', 'tau': 'τ', 'phi': 'φ', 'omega': 'ω', 'circ': '°'}


def tex_text(tex: str) -> str:
    """Simple inline TeX as plain characters for card excerpts (the index loads no KaTeX)."""
    tex = re.sub(r'\\math(?:sf|rm|bf)\s*\{?\s*([A-Za-z])\s*\}?', r'\1', tex)
    tex = re.sub(r'\\([A-Za-z]+)', lambda m: GREEK.get(m[1], ''), tex)
    tex = re.sub(r'_\{?(\d+)\}?', lambda m: m[1].translate(SUBSCRIPT), tex)
    tex = re.sub(r'\^\{?([\dT]+|°)\}?', lambda m: m[1].translate(SUPERSCRIPT), tex)
    return re.sub(r'[{}]', '', tex)


def excerpt(post: dict, lang: str) -> str:
    """The opening text of the article: leading paragraphs joined across short lead-ins to display equations,
    ending before the first equation once there is enough text to fill the card."""
    parts = []
    for block in post['blocks']:
        if parts and (block['type'] == 'heading' or (block['type'] == 'math' and sum(map(len, parts)) >= 60)):
            break
        if block['type'] != 'paragraph' or not available(block, lang):
            continue
        text = CITATION.sub('', block['text'][lang])
        text = MATH.sub(lambda m: tex_text(m[1]), text)
        parts.append(re.sub(r'\*\*(.+?)\*\*|\*([^*]+)\*', lambda m: m[1] or m[2], text).strip())
        if sum(map(len, parts)) >= 160:
            break
    joined = re.sub(r'\s+', ' ', ('' if lang == 'zh' else ' ').join(parts)).strip()
    joined = re.sub(r'\s+([.,;:])', r'\1', joined)  # space left where a citation was removed
    # A sentence cut off before its equation ends in an ellipsis rather than a dangling colon.
    if joined and not re.search(r'[。.!?！？]$', joined):
        joined = re.sub(r'[：:，,]$', '', joined) + '…'
    return joined or post['description'][lang]


def listing_page(posts: list[dict], config: dict) -> str:
    vocabulary = config['tags']
    limit = config['recent_limit']
    if type(limit) is not int or limit < 1:
        raise ValueError('recent_limit must be a positive integer')
    by_slug = {post['slug']: post for post in posts}
    cards = []
    for post in sorted(posts, key=lambda p: (p['created'], p['slug']), reverse=True)[:limit]:
        slug = post['slug']
        figure = next((b for b in post['blocks'] if b['type'] == 'figure'), None)
        thumbnail = (f'<a class="post-thumbnail" href="{slug}.html" tabindex="-1" aria-hidden="true">'
                     f'<img src="{esc(figure["src"])}" alt="" loading="lazy" width="320" height="240"></a>') if figure else ''
        cards.append(f'''<li class="blog-card" data-search="{search_text(post)}">
<div class="card-copy"><p class="eyebrow">{bilingual(post['series'])}</p>
<h3><a href="{slug}.html">{bilingual(post['title'])}</a></h3>
<p class="card-excerpt">{bilingual({lang: excerpt(post, lang) for lang in LANGS})}</p>
<div class="card-metadata">{dates(post)}{''.join(f'<div class="lang-{lang}">{metadata(post, lang)}</div>' for lang in LANGS)}</div>{tag_links(post, vocabulary)}</div>{thumbnail}</li>''')
    results = []
    for post in sorted(posts, key=lambda p: (p['created'], p['slug']), reverse=True):
        search_fields = ' '.join(
            f'data-text-{lang}="{esc(" ".join([post["title"][lang], post["description"][lang], post["series"][lang], *map(plain, texts(post, lang, headings=True))]))}"'
            for lang in LANGS)
        descriptions = ' '.join(f'data-desc-{lang}="{esc(post["description"][lang])}"' for lang in LANGS)
        results.append(f'<li class="search-result" data-tags="{" ".join(post["tags"])}" {descriptions} {search_fields}>'
                       f'<h3><a href="{post["slug"]}.html">{bilingual(post["title"])}</a></h3>'
                       f'{dates(post)}<p class="search-snippet"></p></li>')
    groups, assigned = [], []
    for directory in config['directories']:
        entries = []
        for number, entry in enumerate(directory['posts'], 1):
            number_label = f'<span class="archive-number">{number:02d}</span>'
            if isinstance(entry, dict) and 'slug' not in entry:
                entries.append(f'<li class="archive-planned"><span class="archive-title">{number_label}<span>{bilingual(entry["title"])}</span></span></li>')
                continue
            slug = entry if isinstance(entry, str) else entry['slug']
            if slug not in by_slug or slug in assigned:
                raise ValueError(f'Unknown or duplicate archived post: {slug}')
            assigned.append(slug)
            post = by_slug[slug]
            label = entry.get('title', post['title']) if isinstance(entry, dict) else post['title']
            entries.append(f'<li data-search="{search_text(post)}"><a class="archive-title" href="{slug}.html">{number_label}<span>{bilingual(label)}</span></a>{dates(post)}</li>')
        groups.append(f'<section class="archive-group"><h3>{bilingual(directory["title"])}</h3><ul>{"".join(entries)}</ul></section>')
    if set(assigned) != set(by_slug):
        raise ValueError('Every post must be placed in data/blog-index.json directories')
    used = {tag for post in posts for tag in post['tags']}
    chips = ''.join(f'<button type="button" class="tag-chip" data-tag="{tag}" aria-pressed="false">{bilingual(label)}</button>'
                    for tag, label in vocabulary.items() if tag in used)
    return f'''<div class="blog-index">
<div class="index-toolbar">
<div class="tag-filter" role="group" aria-label="Filter by tag / 按标签筛选">{chips}</div>
<label class="blog-search"><span>{bilingual({'en': 'Search', 'zh': '搜索'})}</span><input id="blog-search" type="search" aria-label="Search posts / 搜索博文" autocomplete="off"></label></div>
<section id="recent" aria-labelledby="recent-title"><h2 id="recent-title" class="index-heading">{bilingual({'en': 'Recent', 'zh': '最近'})}</h2>
<ul class="blog-posts">{''.join(cards)}</ul></section>
<section id="archived" aria-labelledby="archived-title"><h2 id="archived-title" class="index-heading">{bilingual({'en': 'Series', 'zh': '系列'})}</h2>{''.join(groups)}</section>
<section id="search-results" aria-labelledby="results-title" hidden>
<h2 id="results-title" class="index-heading">{bilingual({'en': 'Search results', 'zh': '搜索结果'})}<span id="results-count"></span></h2>
<ul class="search-results-list">{''.join(results)}</ul></section>
<p class="search-empty" hidden>{bilingual({'en': 'No matching posts.', 'zh': '没有找到匹配的文章。'})}</p>
<p id="search-status" class="sr-only" role="status" aria-live="polite"></p>
</div>'''


def build_pages() -> dict[Path, str]:
    posts = [json.loads(path.read_text()) for path in sorted((ROOT / 'data/blog').glob('*.json'))]
    config = json.loads((ROOT / 'data/blog-index.json').read_text())
    validate_languages(config)
    validate_tags(posts, config['tags'])
    pages = {}
    for post in posts:
        validate_languages(post)
        for field in ('created', 'updated'):
            if date.fromisoformat(post[field]).isoformat() != post[field]:
                raise ValueError(f'Use YYYY-MM-DD for {field}')
        if post['updated'] < post['created']:
            raise ValueError('Updated date cannot precede created date')
        slug = post['slug']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or slug == 'index':
            raise ValueError(f'Invalid post slug: {slug}')
        path = ROOT / 'blog' / f'{slug}.html'
        if path in pages:
            raise ValueError(f'Duplicate post: {slug}')
        versions = []
        for lang in LANGS:
            back = '← 所有博文' if lang == 'zh' else '← All posts'
            article_content = content(post, lang)
            validate_contents_targets(post, lang, article_content)
            versions.append(f'''<div class="post-layout lang-{lang}">{contents(post, lang)}<article class="post lang-{lang}" lang="{'zh-CN' if lang == 'zh' else 'en'}">
<a class="back-link" href="index.html?lang={lang}">{back}</a>
<header>{dates(post)}<p class="eyebrow">{esc(post['series'][lang])}</p><h1>{esc(post['title'][lang])}</h1>{metadata(post, lang)}{tag_links(post, config['tags'], lang)}</header>
{article_content}
</article></div>''')
        pages[path] = page('\n'.join(versions), {lang: post['title'][lang] + ' | Wen Chen' for lang in LANGS}, post['description'])
    title = {'en': 'Blog | Wen Chen', 'zh': '博客 | 陈文'}
    description = {'en': 'Notes on physics, its history, and the questions behind it.', 'zh': '关于物理、物理史，以及它们背后的问题。'}
    listing = listing_page(posts, config)
    pages[ROOT / 'blog/index.html'] = page(listing, title, description, listing=True)
    return pages
