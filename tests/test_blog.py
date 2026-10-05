"""Run with python3 -m unittest discover -s tests. No external dependencies (the KaTeX check needs node and is skipped without it)."""
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_blog import (build_pages, content, inline, plain, stats, texts,
                        validate_contents_targets, validate_languages)


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids, self.links = [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        for key in ('href', 'src'):
            if key in attrs:
                self.links.append(attrs[key])


class BlogTests(unittest.TestCase):
    def setUp(self):
        self.post = json.loads((ROOT / 'data/blog/early-theories-of-light.json').read_text())

    def test_bilingual_content(self):
        validate_languages(self.post)
        with self.assertRaises(ValueError):
            validate_languages({'en': 'Missing Chinese'})
        # A block may exist in one language only, but it has to say so.
        validate_languages({'langs': ['zh'], 'text': {'zh': '仅中文'}})
        with self.assertRaises(ValueError):
            validate_languages({'text': {'zh': '仅中文'}})
        with self.assertRaises(ValueError):
            validate_languages({'langs': ['zh'], 'text': {'zh': '中文', 'en': 'English'}})
        with self.assertRaises(ValueError):
            validate_languages({'langs': ['fr'], 'text': {'fr': 'Bonjour'}})
        self.assertGreater(len(self.post['blocks']), 0)
        self.assertNotIn('character *jing*', json.dumps(self.post))

    def test_counts(self):
        original = {lang: stats(self.post, lang) for lang in ('en', 'zh')}
        self.assertGreater(original['en'][0], 0)
        self.assertGreater(original['zh'][0], 0)
        # Bibliography changes do not alter reading statistics.
        self.post['references'].append({'text': {'en': 'Extra source', 'zh': '额外来源'}, 'url': 'https://example.org'})
        self.assertEqual(stats(self.post, 'en'), original['en'])
        # An inline formula counts as one unit; display equations and the TeX inside are not counted.
        sample = {'blocks': [{'type': 'paragraph', 'text': {'en': 'a', 'zh': '设 $\\theta_1$ 为长度[[1]](#ref-1)'}},
                             {'type': 'math', 'tex': 'a b c d'}]}
        self.assertEqual(stats(sample, 'zh'), (5, 1))

    def test_inline(self):
        self.assertEqual(inline('[[2]](#ref-2)', 'zh', 9), '<a class="citation" href="#zh-ref-2" aria-label="Reference 2">[2]</a>')
        self.assertEqual(
            inline('[<a href="#ref-5">5</a>,<a href="#ref-10">10</a>]', 'zh', 12),
            '<span class="citation-group">[<a class="citation" href="#zh-ref-5" aria-label="Reference 5">5</a>,'
            '<a class="citation" href="#zh-ref-10" aria-label="Reference 10">10</a>]</span>')
        for locator in ('§§1.1, 2.1', '§§2.2–2.3, 3.5', 'ch.9'):
            rendered = inline(f'[<a href="#ref-5">5</a>, {locator}]', 'en', 12)
            self.assertIn(locator, rendered)
            self.assertNotIn('&lt;a href=', rendered)
        self.assertEqual(inline("$B'$", 'en', 9), '<span class="math" data-tex="B&#x27;">B&#x27;</span>')
        self.assertIn('data-tex="\\theta_2&lt;\\theta_1"', inline(r'$\theta_2<\theta_1$', 'zh', 9))
        self.assertEqual(inline('<script>', 'en', 9), '&lt;script&gt;')
        with self.assertRaises(ValueError):
            inline('[[10]](#ref-10)', 'en', 9)
        with self.assertRaises(ValueError):
            inline('[<a href="#ref-5">6</a>]', 'en', 9)

    def test_semicolon_groups_and_nested_markup(self):
        rendered = inline('[<a href="#ref-5">5</a>, §§2.3, 5.3; <a href="#ref-6">6</a>, §8.4]', 'en', 12)
        self.assertEqual(rendered.count('class="citation"'), 2)
        self.assertIn('[<a class="citation" href="#en-ref-5" aria-label="Reference 5">5</a>, §§2.3, 5.3; '
                      '<a class="citation" href="#en-ref-6" aria-label="Reference 6">6</a>, §8.4]', rendered)
        self.assertNotIn('&lt;a', rendered)
        # A formula inside bold or italic text is typeset like any other.
        self.assertEqual(inline('**$\\alpha=0$：沿轴**', 'zh', 9),
                         '<strong><span class="math" data-tex="\\alpha=0">\\alpha=0</span>：沿轴</strong>')
        self.assertEqual(plain('**$\\alpha=0$：沿轴** 与 [<a href="#ref-5">5</a>, §5.3; <a href="#ref-6">6</a>, §8.4]'), '：沿轴 与')

    def test_equation_labels_follow_the_language(self):
        sample = {'references': [], 'blocks': [
            {'type': 'math', 'tex': {'zh': '\\text{亮纹：}m=0', 'en': '\\text{bright fringes: }m=0'}},
            {'type': 'math', 'tex': 'x=1'}]}
        validate_languages(sample)
        self.assertIn('data-tex="\\text{亮纹：}m=0"', content(sample, 'zh'))
        self.assertIn('data-tex="\\text{bright fringes: }m=0"', content(sample, 'en'))
        self.assertNotIn('亮纹', content(sample, 'en'))
        self.assertEqual(content(sample, 'zh').count('data-tex="x=1"'), 1)
        with self.assertRaises(ValueError):
            validate_languages({'type': 'math', 'tex': {'zh': '\\text{亮}'}})

    def test_plain_text_for_search(self):
        text = '映照面容[[1]](#ref-1)。**粗** *斜* $B\'$ 与 $\\theta_1$ [<a href="#ref-5">5</a>,<a href="#ref-10">10</a>]'
        self.assertEqual(plain(text), '映照面容。粗 斜 B′ 与')

    def test_generated_pages_and_links(self):
        pages = build_pages()
        self.assertEqual(len(pages), 2)
        for path, text in pages.items():
            self.assertEqual(path.read_text(), text)
            doc = Document(text)
            self.assertEqual(len(doc.ids), len(set(doc.ids)), path)
            self.assertNotIn('file://', text)
            self.assertNotIn('/Users/', text)
            self.assertNotIn('../../refs/', text)
            for href in doc.links:
                url = urlsplit(href)
                if url.scheme or url.netloc:
                    continue
                target = (path.parent / unquote(url.path)).resolve() if url.path else path
                self.assertTrue(target.is_file(), f'{path}: {href}')
                if url.fragment and target.suffix == '.html':
                    ids = doc.ids if target == path else Document(target.read_text()).ids
                    self.assertIn(unquote(url.fragment), ids, href)

    def test_scripts_and_styles_are_versioned(self):
        for path, text in build_pages().items():
            for name in ('blog.css', 'blog.js'):
                digest = hashlib.sha1((ROOT / 'assets' / name).read_bytes()).hexdigest()[:8]
                self.assertIn(f'../assets/{name}?v={digest}"', text, path)

    def test_index_layout(self):
        listing = build_pages()[ROOT / 'blog/index.html']
        self.assertLess(listing.index('id="recent"'), listing.index('id="archived"'))
        self.assertIn('type="search"', listing)
        self.assertIn('class="post-thumbnail"', listing)
        self.assertIn('最后更新', listing)
        self.assertEqual(listing.count('data-search='), 2)
        config = json.loads((ROOT / 'data/blog-index.json').read_text())
        self.assertEqual(config['directories'][0]['posts'][0]['slug'], self.post['slug'])
        self.assertEqual([d['title']['zh'] for d in config['directories']], ['光学', '量子计算', '量子动力学'])
        planned = re.findall(r'<li class="archive-planned">(.*?)</li>', listing)
        self.assertEqual(len(planned), 3)
        for entry in planned:
            self.assertNotIn('<a ', entry)
            self.assertNotIn('<time', entry)
        self.assertIn(html.escape(self.post['title']['zh']), listing)
        # No script is needed on the index page.
        self.assertNotIn('katex', listing)

    def test_search_text_is_plain(self):
        listing = build_pages()[ROOT / 'blog/index.html']
        fields = dict(re.findall(r'data-(search|text-en|text-zh)="([^"]*)"', listing)[-3:])
        for name, text in fields.items():
            for markup in ('[[', '](#ref-', '**', '$', '&lt;a'):
                self.assertNotIn(markup, text, name)
        for lang in ('en', 'zh'):
            for phrase in texts(self.post, lang):
                cleaned = plain(phrase)
                if cleaned:
                    self.assertIn(cleaned, html.unescape(fields[f'text-{lang}']))

    def test_invalid_contents_target_is_rejected(self):
        post = {'contents': [{'target': 'block-9', 'label': {'en': 'Missing', 'zh': '缺失'}}]}
        with self.assertRaisesRegex(ValueError, 'Invalid contents target'):
            validate_contents_targets(post, 'en', '<p id="en-block-0">Present</p>')

    def test_legacy_language_restrictions_remain_supported(self):
        legacy = {'references': [], 'blocks': [
            {'type': 'paragraph', 'langs': ['zh'], 'text': {'zh': '仅中文段落'}},
            {'type': 'paragraph', 'text': {'en': 'English paragraph', 'zh': '双语段落'}},
        ]}
        validate_languages(legacy)
        self.assertEqual(texts(legacy, 'en'), ['English paragraph'])
        self.assertEqual(texts(legacy, 'zh'), ['仅中文段落', '双语段落'])
        self.assertIn('translation-note', content(legacy, 'en'))
        self.assertNotIn('translation-note', content(legacy, 'zh'))

    def test_nested_blocks_counts_search_and_citations(self):
        sample = {'references': [{'url': '', 'text': {'en': 'Book', 'zh': '书'}}], 'blocks': [
            {'type': 'list', 'items': [{'blocks': [
                {'type': 'paragraph', 'text': {'en': 'Nested words [<a href="#ref-1">1</a>, §§2.2–2.3, 3.5]', 'zh': '嵌套文字[[1]](#ref-1)'}},
                {'type': 'math', 'tex': 'x = 1'},
                {'type': 'paragraph', 'text': {'en': 'More words [<a href="#ref-1">1</a>, ch.9]', 'zh': '更多文字'}},
                {'type': 'list', 'items': [{'blocks': [
                    {'type': 'paragraph', 'text': {'en': 'Deep paragraph', 'zh': '深层段落'}},
                    {'type': 'math', 'tex': 'y = 2'}]}]},
            ]}]},
        ]}
        validate_languages(sample)
        for lang in ('en', 'zh'):
            markup = content(sample, lang)
            doc = Document(markup)
            self.assertEqual(len(doc.ids), len(set(doc.ids)))
            self.assertIn(f'<li id="{lang}-ref-1">Book' if lang == 'en' else f'<li id="{lang}-ref-1">书', markup)
            self.assertEqual(markup.count('class="math-display"'), 2)
            self.assertEqual(stats(sample, lang), (6, 1) if lang == 'en' else (12, 1))
            gathered = ' '.join(plain(text) for text in texts(sample, lang))
            self.assertIn('Deep paragraph' if lang == 'en' else '深层段落', gathered)
            self.assertNotIn('§§2.2', gathered)
            self.assertNotIn('ch.9', gathered)
        english = content(sample, 'en')
        self.assertIn('§§2.2–2.3, 3.5', english)
        self.assertIn('ch.9', english)
        self.assertIn('href="#en-ref-1"', english)
        self.assertNotIn('<a href="">', english)
        for url in ('/Users/wenchen/refs/book.pdf', 'file:///Users/name/book.pdf', 'http://example.org/book'):
            invalid = {'references': [{'url': url, 'text': {'en': 'Book', 'zh': '书'}}], 'blocks': []}
            with self.assertRaisesRegex(ValueError, 'public HTTPS'):
                content(invalid, 'en')

    @unittest.skipUnless(shutil.which('node'), 'node is needed to run KaTeX')
    def test_every_formula_typesets(self):
        page = build_pages()[ROOT / 'blog/early-theories-of-light.html']
        formulas = [{'tex': html.unescape(tex), 'display': kind == 'math-display'}
                    for kind, tex in re.findall(r'<(?:span|div) class="(math|math-display)"[^>]*? data-tex="([^"]*)"', page)]
        self.assertGreater(len(formulas), 60)
        script = ("const katex = require(process.argv[1]); const items = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
                  "for (const f of items) katex.renderToString(f.tex, {throwOnError: true, displayMode: f.display});")
        result = subprocess.run(['node', '-e', script, str(ROOT / 'assets/vendor/katex/katex.min.js')],
                                input=json.dumps(formulas), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr[-600:])


if __name__ == '__main__':
    unittest.main()
