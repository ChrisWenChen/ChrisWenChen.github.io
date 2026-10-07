(() => {
  'use strict';
  // Typeset TeX with the local KaTeX (loaded only on pages that have formulas); the TeX text stays as the fallback.
  if (window.katex) {
    document.querySelectorAll('[data-tex]').forEach(element => {
      try {
        window.katex.render(element.dataset.tex, element, {displayMode: element.classList.contains('math-display'), throwOnError: false});
      } catch (_) {}
    });
  }
  const toggle = document.querySelector('.lang-toggle');
  const compact = window.matchMedia('(max-width: 950px)');
  const updateContents = () => document.querySelectorAll('.post-toc details').forEach(details => { details.open = !compact.matches; });
  updateContents();
  compact.addEventListener('change', updateContents);
  const search = document.getElementById('blog-search');
  const normalize = text => text.normalize('NFKC').toLowerCase();
  function matchingRanges(text, terms) {
    let normalized = '';
    const positions = [];
    let offset = 0;
    for (const character of text) {
      const value = normalize(character);
      for (let i = 0; i < value.length; i++) positions.push([offset, offset + character.length]);
      normalized += value;
      offset += character.length;
    }
    const ranges = [];
    for (const term of terms) {
      let start = normalized.indexOf(term);
      while (start !== -1) {
        ranges.push([positions[start][0], positions[start + term.length - 1][1]]);
        start = normalized.indexOf(term, start + term.length);
      }
    }
    return ranges.sort((a, b) => a[0] - b[0]);
  }
  function snippet(text, terms, lang) {
    const paragraph = document.createElement('span');
    paragraph.lang = lang === 'zh' ? 'zh-CN' : 'en';
    const ranges = matchingRanges(text, terms);
    const start = Math.max(0, (ranges[0]?.[0] || 0) - 45);
    const end = Math.min(text.length, Math.max(start + 190, ranges[0]?.[1] || 0));
    let cursor = start;
    if (start) paragraph.append('…');
    for (const [left, right] of ranges) {
      if (left >= end || right <= cursor) continue;
      const from = Math.max(cursor, left);
      paragraph.append(text.slice(cursor, from));
      const mark = document.createElement('mark');
      mark.textContent = text.slice(from, Math.min(right, end));
      paragraph.append(mark);
      cursor = Math.min(right, end);
    }
    paragraph.append(text.slice(cursor, end));
    if (end < text.length) paragraph.append('…');
    return paragraph;
  }
  // A tag narrows the result list like a search term; it never reorders it. `?tag=` lets article pages link here.
  const chips = [...document.querySelectorAll('.tag-chip')];
  let activeTag = new URL(location.href).searchParams.get('tag') || '';
  if (!chips.some(chip => chip.dataset.tag === activeTag)) activeTag = '';
  chips.forEach(chip => chip.addEventListener('click', () => {
    activeTag = activeTag === chip.dataset.tag ? '' : chip.dataset.tag;
    const url = new URL(location.href);
    if (activeTag) url.searchParams.set('tag', activeTag); else url.searchParams.delete('tag');
    try { history.replaceState(null, '', url); } catch (_) {}
    filterPosts();
  }));
  function filterPosts() {
    if (!search) return;
    const terms = [...new Set(normalize(search.value).trim().split(/\s+/).filter(Boolean))];
    const active = terms.length > 0 || activeTag !== '';
    chips.forEach(chip => chip.setAttribute('aria-pressed', String(chip.dataset.tag === activeTag)));
    const lang = document.body.classList.contains('zh') ? 'zh' : 'en';
    document.getElementById('recent').hidden = active;
    document.getElementById('archived').hidden = active;
    document.getElementById('search-results').hidden = !active;
    let count = 0;
    document.querySelectorAll('.search-result').forEach(entry => {
      const texts = {en: entry.dataset.textEn, zh: entry.dataset.textZh};
      const combined = normalize(texts.en + ' ' + texts.zh);
      const tagged = !activeTag || entry.dataset.tags.split(' ').includes(activeTag);
      entry.hidden = !active || !tagged || !terms.every(term => combined.includes(term));
      if (entry.hidden) return;
      count++;
      const target = entry.querySelector('.search-snippet');
      target.replaceChildren();
      if (!terms.length) {
        target.append(entry.dataset[lang === 'zh' ? 'descZh' : 'descEn']);
        return;
      }
      // Prefer the interface language, but show the other language when it
      // contains matches that would otherwise be invisible.
      const other = lang === 'zh' ? 'en' : 'zh';
      const primaryTerms = terms.filter(term => normalize(texts[lang]).includes(term));
      if (primaryTerms.length) target.append(snippet(texts[lang], primaryTerms, lang));
      const remaining = terms.filter(term => !primaryTerms.includes(term));
      if (remaining.length) target.append(snippet(texts[other], remaining, other));
    });
    document.querySelector('.search-empty').hidden = !active || count !== 0;
    const label = lang === 'zh' ? `找到 ${count} 篇文章` : `${count} post${count === 1 ? '' : 's'} found`;
    document.getElementById('results-count').textContent = active ? label : '';
    document.getElementById('search-status').textContent = active ? label : '';
  }
  search?.addEventListener('input', filterPosts);
  function setLanguage(language, updateURL = false) {
    const lang = language === 'zh' ? 'zh' : 'en';
    const previous = document.body.classList.contains('zh') ? 'zh' : 'en';
    document.body.classList.toggle('zh', lang === 'zh');
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    document.title = document.body.dataset[lang === 'zh' ? 'titleZh' : 'titleEn'];
    filterPosts();
    toggle.textContent = lang === 'zh' ? 'EN' : '中文';
    toggle.setAttribute('aria-label', lang === 'zh' ? 'Switch to English' : '切换到中文');
    try { localStorage.setItem('site-language', lang); } catch (_) {}
    // Keep reference destinations usable when the article language changes.
    const url = new URL(location.href);
    const ref = url.hash.match(/^#(?:en|zh)-(.+)$/);
    if (ref) url.hash = `${lang}-${ref[1]}`;
    if (updateURL) url.searchParams.set('lang', lang);
    try { history.replaceState(null, '', url); } catch (_) {}
    if (ref && previous !== lang) document.getElementById(`${lang}-${ref[1]}`)?.scrollIntoView();
    // Carry the active language across pages even if storage is unavailable.
    document.querySelectorAll('a[href]').forEach(link => {
      if (link.getAttribute('href').startsWith('#')) return;
      const target = new URL(link.getAttribute('href'), location.href);
      if (target.origin === location.origin && target.pathname.endsWith('.html')) {
        target.searchParams.set('lang', lang);
        link.href = target.href;
      }
    });
  }
  let saved = 'en';
  try { saved = localStorage.getItem('site-language') || 'en'; } catch (_) {}
  const url = new URL(location.href);
  const requested = url.searchParams.get('lang');
  const hashLanguage = url.hash.match(/^#(en|zh)-/)?.[1];
  setLanguage(['en', 'zh'].includes(requested) ? requested : (hashLanguage || saved));
  toggle.addEventListener('click', () => setLanguage(document.body.classList.contains('zh') ? 'en' : 'zh', true));

  // Reading progress: a slider beside the contents that shows where you are and can be dragged or clicked to scroll.
  const readers = [];
  document.querySelectorAll('.post-layout').forEach(layout => {
    const article = layout.querySelector('.post');
    const slider = layout.querySelector('.read-progress');
    if (!article || !slider) return;
    slider.hidden = false;
    const thumb = slider.querySelector('.read-thumb');
    const label = layout.querySelector('.read-percent');
    const links = [...layout.querySelectorAll('.post-toc ol a')].map(link => ({link, target: document.getElementById(link.getAttribute('href').slice(1))}));
    // Progress 0 is the top of the page and 1 is the point where the end of the article reaches the bottom of the window.
    const span = () => Math.max(0, article.getBoundingClientRect().bottom + scrollY - innerHeight);
    const update = () => {
      if (layout.offsetParent === null) return;
      const total = span();
      const progress = total > 0 ? Math.min(1, Math.max(0, scrollY / total)) : 0;
      const percent = Math.round(progress * 100);
      slider.style.setProperty('--p', progress);
      slider.setAttribute('aria-valuenow', percent);
      label.textContent = percent + '%';
      let current = null;
      for (const entry of links) if (entry.target && entry.target.getBoundingClientRect().top <= innerHeight * 0.3) current = entry.link;
      links.forEach(entry => entry.link === current ? entry.link.setAttribute('aria-current', 'true') : entry.link.removeAttribute('aria-current'));
    };
    const seek = event => {
      const box = slider.getBoundingClientRect();
      const room = Math.max(1, box.height - thumb.offsetHeight);
      const progress = Math.min(1, Math.max(0, (event.clientY - box.top - thumb.offsetHeight / 2) / room));
      scrollTo({top: progress * span(), behavior: 'instant'});
    };
    slider.addEventListener('pointerdown', event => {
      try { slider.setPointerCapture(event.pointerId); } catch (_) {}
      slider.classList.add('dragging');
      seek(event);
      event.preventDefault();
    });
    slider.addEventListener('pointermove', event => { if (slider.classList.contains('dragging')) seek(event); });
    const release = event => { slider.classList.remove('dragging'); try { slider.releasePointerCapture(event.pointerId); } catch (_) {} };
    slider.addEventListener('pointerup', release);
    slider.addEventListener('pointercancel', release);
    slider.addEventListener('keydown', event => {
      const moves = {ArrowUp: -60, ArrowDown: 60, PageUp: -innerHeight * 0.9, PageDown: innerHeight * 0.9};
      if (event.key in moves) scrollBy({top: moves[event.key], behavior: 'instant'});
      else if (event.key === 'Home') scrollTo({top: 0, behavior: 'instant'});
      else if (event.key === 'End') scrollTo({top: span(), behavior: 'instant'});
      else return;
      event.preventDefault();
    });
    if (window.ResizeObserver) new ResizeObserver(update).observe(article);
    readers.push(update);
  });
  if (readers.length) {
    let queued = false;
    const updateAll = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; readers.forEach(update => update()); });
    };
    addEventListener('scroll', updateAll, {passive: true});
    addEventListener('resize', updateAll);
    addEventListener('load', updateAll);
    toggle.addEventListener('click', updateAll);
    updateAll();
  }
})();
