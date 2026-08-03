#!/usr/bin/env python3
"""Generate the structured sections of the personal homepage from JSON data."""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "site.json"
TEMPLATE_PATH = ROOT / "index.template.html"
OUTPUT_PATH = ROOT / "index.html"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def bilingual(value: dict[str, str]) -> str:
    if set(value) != {"en", "zh"} or not value["en"] or not value["zh"]:
        raise ValueError(f"Every bilingual field needs non-empty en and zh values: {value!r}")
    return (
        f'<span class="lang-en">{esc(value["en"])}</span>'
        f'<span class="lang-zh">{esc(value["zh"])}</span>'
    )


def authors(items: list[dict[str, object]]) -> str:
    rendered = []
    for item in items:
        name = esc(item["name"])
        suffix = esc(item.get("mark", ""))
        content = f"{name}{suffix}"
        if item.get("me"):
            content = f'<span class="me">{content}</span>'
        rendered.append(content)
    return ", ".join(rendered)


def links(items: list[dict[str, str]]) -> str:
    if not items:
        return ""
    rendered = []
    for item in items:
        label = esc(item["label"])
        href = esc(item["href"])
        rendered.append(f'<a class="pub-link" href="{href}" target="_blank" rel="noopener">{label}</a>')
    return '<span class="pub-links">' + " ".join(rendered) + "</span>"


def grouped(items: list[dict[str, object]]) -> str:
    by_year: dict[int, list[dict[str, object]]] = defaultdict(list)
    for item in items:
        by_year[int(item["year"])].append(item)

    blocks = []
    for year in sorted(by_year, reverse=True):
        entries = []
        for number, item in enumerate(by_year[year], start=1):
            title = bilingual(item["title"])
            type_label = bilingual(item["type"])
            title_html = f'<div class="pub-title">{title} <span class="pub-type">{type_label}</span></div>'
            venue = bilingual(item["venue"])
            link_html = links(item.get("links", []))
            venue_parts = [f'        <span class="pub-venue-text">{venue}</span>']
            if link_html:
                venue_parts.append(f"        {link_html}")
            entries.append(
                f'''    <li class="pub-item" data-num="{number}.">
      {title_html}
      <div class="pub-authors">{authors(item["authors"])}</div>
      <div class="pub-venue">
{chr(10).join(venue_parts)}
      </div>
    </li>'''
            )
        blocks.append(
            f'''  <div class="pub-year-header">{year}</div>
  <ol class="pub-list">
{chr(10).join(entries)}
  </ol>'''
        )
    return "\n\n".join(blocks)


def render_education(items: list[dict[str, object]]) -> str:
    entries = []
    for item in items:
        details = "\n".join(
            f'      <div class="detail">{bilingual(detail)}</div>' for detail in item["details"]
        )
        entries.append(
            f'''    <li class="edu-item">
      <div class="degree">{bilingual(item["degree"])}</div>
      <div class="school">{bilingual(item["school"])}</div>
{details + chr(10) if details else ""}      <div class="year">{bilingual(item["year"])}</div>
    </li>'''
        )
    return f'''<!-- DATA:EDUCATION:START -->
<section id="education">
<div class="card">
  <h2>
    <span class="lang-en">Education</span>
    <span class="lang-zh">教育背景</span>
  </h2>
  <ul class="edu-list">
{chr(10).join(entries)}
  </ul>
</div>
</section>
<!-- DATA:EDUCATION:END -->'''


def render_publications(data: dict[str, object]) -> str:
    return f'''<!-- DATA:PUBLICATIONS:START -->
<section id="publications">
<div class="card">
  <h2>
    <span class="lang-en">Publications</span>
    <span class="lang-zh">发表论文</span>
  </h2>
  <p class="section-intro">
    <span class="lang-en">See also: <a href="https://scholar.google.com/citations?user=z_r9VSwAAAAJ" target="_blank" rel="noopener">Google Scholar</a>, <a href="https://orcid.org/0000-0001-6089-9909" target="_blank" rel="noopener">ORCID</a>, and <a href="https://arxiv.org/search/?searchtype=author&amp;query=Wen+Chen" target="_blank" rel="noopener">arXiv</a>. (* Corresponding author.)</span>
    <span class="lang-zh">另见：<a href="https://scholar.google.com/citations?user=z_r9VSwAAAAJ" target="_blank" rel="noopener">Google Scholar</a>、<a href="https://orcid.org/0000-0001-6089-9909" target="_blank" rel="noopener">ORCID</a> 和 <a href="https://arxiv.org/search/?searchtype=author&amp;query=Wen+Chen" target="_blank" rel="noopener">arXiv</a>。（* 通讯作者）</span>
  </p>
{grouped(data["publications"] + data["conference_abstracts"])}
</div>
</section>
<!-- DATA:PUBLICATIONS:END -->'''


def render_talks(items: list[dict[str, object]]) -> str:
    entries = []
    for number, item in enumerate(items, start=1):
        entries.append(
            f'''    <li class="talk-item" data-num="{number}.">
      <div class="talk-title">{bilingual(item["title"])} <span class="talk-type">{bilingual(item["type"])}</span></div>
      <div class="talk-event">{bilingual(item["event"])}</div>
    </li>'''
        )
    return f'''<!-- DATA:TALKS:START -->
<section id="talks">
<div class="card">
  <h2>
    <span class="lang-en">Talks &amp; Posters</span>
    <span class="lang-zh">学术报告</span>
  </h2>
  <ol class="talk-list">
{chr(10).join(entries)}
  </ol>
</div>
</section>
<!-- DATA:TALKS:END -->'''


def render_teaching(items: list[dict[str, object]]) -> str:
    entries = []
    for item in items:
        details = "\n".join(
            f'    <div class="teach-detail">{bilingual(detail)}</div>' for detail in item["details"]
        )
        entries.append(
            f'''  <div class="teach-item">
    <div class="teach-role">{bilingual(item["role"])}</div>
    <div class="teach-place">{bilingual(item["place"])}</div>
{details + chr(10) if details else ""}    <div class="teach-year">{bilingual(item["year"])}</div>
  </div>'''
        )
    return f'''<!-- DATA:TEACHING:START -->
<section id="teaching">
<div class="card">
  <h2>
    <span class="lang-en">Teaching &amp; Service</span>
    <span class="lang-zh">教学与服务</span>
  </h2>
{chr(10).join(entries)}
</div>
</section>
<!-- DATA:TEACHING:END -->'''


def render_awards(items: list[dict[str, object]]) -> str:
    entries = []
    for item in items:
        entries.append(
            f'''    <li class="award-item">
      <span class="award-name">{bilingual(item["name"])}</span>
      <span class="award-year">{esc(item["year"])}</span>
    </li>'''
        )
    return f'''<!-- DATA:AWARDS:START -->
<section id="awards">
<div class="card">
  <h2>
    <span class="lang-en">Selected Awards</span>
    <span class="lang-zh">获奖经历</span>
  </h2>
  <ul class="award-list">
{chr(10).join(entries)}
  </ul>
</div>
</section>
<!-- DATA:AWARDS:END -->'''


def validate_bilingual(value: object, path: str = "data") -> None:
    if isinstance(value, dict):
        if "en" in value or "zh" in value:
            bilingual(value)  # type: ignore[arg-type]
        for key, child in value.items():
            validate_bilingual(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            validate_bilingual(child, f"{path}[{index}]")


def replace_block(template: str, name: str, rendered: str) -> str:
    pattern = re.compile(
        rf"<!-- DATA:{name}:START -->.*?<!-- DATA:{name}:END -->",
        re.DOTALL,
    )
    updated, count = pattern.subn(rendered, template, count=1)
    if count != 1:
        raise ValueError(f"Could not find exactly one template block for {name}")
    return updated


def build() -> str:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    validate_bilingual(data)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    generated = template
    generated = replace_block(generated, "EDUCATION", render_education(data["education"]))
    generated = replace_block(generated, "PUBLICATIONS", render_publications(data))
    generated = replace_block(generated, "TALKS", render_talks(data["talks"]))
    generated = replace_block(generated, "TEACHING", render_teaching(data["teaching"]))
    generated = replace_block(generated, "AWARDS", render_awards(data["awards"]))
    return generated.rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check whether index.html is up to date")
    args = parser.parse_args()

    generated = build()
    if args.check:
        current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
        if current != generated:
            print("index.html is out of date; run scripts/build.py")
            return 1
        print("index.html is up to date")
        return 0

    OUTPUT_PATH.write_text(generated, encoding="utf-8")
    print(f"Generated {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
