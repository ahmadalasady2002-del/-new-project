// جلب الصور وعرض محتوى السؤال
(function () {
  // نجيب صور ويكيبيديا دفعة وحدة (50 عنوان بالطلب). pageimages ترجع الصور الحرة بس.
  async function resolveWiki(cat) {
    const pending = cat.items.filter(it => it.img === undefined);
    for (let i = 0; i < pending.length; i += 50) {
      const chunk = pending.slice(i, i + 50);
      const url = 'https://en.wikipedia.org/w/api.php?action=query&format=json&origin=*&redirects=1'
        + '&prop=pageimages&piprop=thumbnail&pithumbsize=800&titles='
        + encodeURIComponent(chunk.map(it => it.t).join('|'));
      try {
        const r = await fetch(url);
        const j = await r.json();
        const q = j.query || {};
        // نرجّع كل عنوان أصلي لعنوانه النهائي بعد التحويلات
        const final = t => {
          for (const n of q.normalized || []) if (n.from === t) t = n.to;
          for (const n of q.redirects || []) if (n.from === t) t = n.to;
          return t;
        };
        const byTitle = {};
        Object.values(q.pages || {}).forEach(p => { byTitle[p.title] = p.thumbnail && p.thumbnail.source; });
        chunk.forEach(it => { it.img = byTitle[final(it.t)] || null; });
      } catch (e) {
        console.warn('wiki fetch failed', e);
        chunk.forEach(it => { it.img = null; });
      }
    }
    cat.items = cat.items.filter(it => it.img);
    return cat.items.length;
  }

  function preload(src) {
    return new Promise(res => {
      const im = new Image();
      im.onload = () => res(true);
      im.onerror = () => res(false);
      im.src = src;
    });
  }

  function imageSrc(cat, item) {
    if (cat.type === 'flag' || cat.type === 'capital') return 'assets/flags/' + item.c + '.svg';
    if (cat.type === 'wiki') return item.img;
    if (cat.type === 'custom') return item.src;
    return null;
  }

  // يرجع عنصر HTML للسؤال
  function render(cat, item) {
    if (cat.type === 'logo') {
      const ns = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(ns, 'svg');
      svg.setAttribute('viewBox', '0 0 24 24');
      svg.classList.add('logo-q', 'zoomable');
      const p = document.createElementNS(ns, 'path');
      p.setAttribute('d', item.d);
      p.setAttribute('fill', '#' + item.h);
      svg.appendChild(p);
      return svg;
    }
    if (cat.type === 'capital') {
      const d = document.createElement('div');
      d.className = 'capital-q';
      const im = document.createElement('img');
      im.src = imageSrc(cat, item);
      im.alt = '';
      const n = document.createElement('div');
      n.textContent = item.q;
      d.append(im, n);
      return d;
    }
    if (cat.type === 'map') {
      const ns = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(ns, 'svg');
      svg.setAttribute('viewBox', '0 0 400 400');
      svg.classList.add('map-q', 'zoomable');
      const p = document.createElementNS(ns, 'path');
      p.setAttribute('d', item.d);
      svg.appendChild(p);
      return svg;
    }
    const im = document.createElement('img');
    im.src = imageSrc(cat, item);
    im.alt = '';
    im.className = 'zoomable' + (cat.type === 'flag' ? ' flag-q' : '');
    return im;
  }

  window.Media = { resolveWiki, preload, imageSrc, render };
})();
