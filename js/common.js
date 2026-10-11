// أدوات مشتركة بين شاشة التلفزيون وريموت الحكم
(function () {
  const params = new URLSearchParams(location.search);

  // إعدادات سيرفر PeerJS: الافتراضي هو السيرفر المجاني مال PeerJS.
  // للتجربة المحلية: ?peerHost=localhost&peerPort=9000
  function peerOptions() {
    const o = { debug: 1 };
    if (params.get('peerHost')) {
      o.host = params.get('peerHost');
      o.port = Number(params.get('peerPort') || 9000);
      o.path = params.get('peerPath') || '/';
      o.secure = params.get('peerSecure') === '1';
    }
    return o;
  }

  // نمرر إعدادات السيرفر للريموت حتى يتصل بنفس السيرفر
  function peerQuery() {
    const keep = ['peerHost', 'peerPort', 'peerPath', 'peerSecure'];
    const q = new URLSearchParams();
    keep.forEach(k => params.get(k) && q.set(k, params.get(k)));
    return q;
  }

  const PREFIX = 'showtime-iq-';

  function randomCode(n = 5) {
    const chars = 'abcdefghjkmnpqrstuvwxyz23456789';
    let s = '';
    const r = crypto.getRandomValues(new Uint8Array(n));
    for (const b of r) s += chars[b % chars.length];
    return s;
  }

  function shuffle(a) {
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  // أصوات بسيطة بدون ملفات
  let ctx;
  function audio() {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      ctx = new AC();
    }
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }
  // كتم الصوت ينحفظ على الجهاز
  let muted = false;
  try { muted = localStorage.getItem('st-mute') === '1'; } catch (e) { /* ignore */ }

  function tone(freq, dur = 0.12, type = 'sine', vol = 0.15, when = 0) {
    if (muted) return;
    const a = audio();
    if (!a) return;
    const t = a.currentTime + when;
    const o = a.createOscillator(), g = a.createGain();
    o.type = type;
    o.frequency.setValueAtTime(freq, t);
    g.gain.setValueAtTime(vol, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g).connect(a.destination);
    o.start(t);
    o.stop(t + dur + 0.02);
  }
  const sfx = {
    unlock: () => audio(),
    click: () => tone(660, 0.05, 'triangle', 0.08),
    tick: () => tone(1000, 0.05, 'square', 0.05),
    wheelTick: () => tone(1400, 0.03, 'triangle', 0.05),
    correct: () => { tone(660, 0.1, 'sine', 0.2); tone(880, 0.18, 'sine', 0.2, 0.1); },
    skip: () => tone(180, 0.25, 'sawtooth', 0.12),
    join: () => { tone(520, 0.1); tone(780, 0.15, 'sine', 0.15, 0.1); },
    end: () => [523, 659, 784, 1047].forEach((f, i) => tone(f, 0.25, 'triangle', 0.18, i * 0.13)),
    buzzer: () => { tone(220, 0.5, 'sawtooth', 0.15); tone(110, 0.5, 'square', 0.08); },
    bonus: () => [784, 988, 1175, 1568].forEach((f, i) => tone(f, 0.12, 'triangle', 0.14, i * 0.07)),
    pass: () => { tone(440, 0.1, 'triangle', 0.12); tone(330, 0.16, 'triangle', 0.12, 0.1); },
    applause,
    get muted() { return muted; },
    setMuted(v) {
      muted = !!v;
      try { localStorage.setItem('st-mute', muted ? '1' : '0'); } catch (e) { /* ignore */ }
      if (muted) music.stop();
    },
  };

  // تصفيق: دفعات ضوضاء قصيرة عشوائية
  function applause(secs = 2.6) {
    if (muted) return;
    const a = audio();
    if (!a) return;
    const len = Math.floor(a.sampleRate * secs);
    const buf = a.createBuffer(1, len, a.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) {
      const t = i / len;
      const env = Math.min(1, t * 8) * (1 - t);                       // يبدي بسرعة ويخفت
      const clap = Math.random() < 0.004 ? 1 : 0.25;                  // تصفقات متفرقة
      d[i] = (Math.random() * 2 - 1) * env * clap;
    }
    const src = a.createBufferSource(), f = a.createBiquadFilter(), g = a.createGain();
    src.buffer = buf;
    f.type = 'bandpass'; f.frequency.value = 1800; f.Q.value = 0.7;
    g.gain.value = 0.5;
    src.connect(f).connect(g).connect(a.destination);
    src.start();
  }

  // موسيقى خلفية خفيفة (أربع أكوردات تتكرر)
  const CHORDS = [[220, 261.6, 329.6], [174.6, 220, 261.6], [261.6, 329.6, 392], [196, 246.9, 293.7]];
  const music = {
    timer: null, step: 0,
    start() {
      if (this.timer || muted) return;
      this.step = 0;
      this.timer = setInterval(() => {
        const chord = CHORDS[Math.floor(this.step / 8) % CHORDS.length];
        const i = this.step % 8;
        tone(chord[[0, 1, 2, 1, 0, 2, 1, 2][i]] * 2, 0.22, 'triangle', 0.03);
        if (i === 0 || i === 4) tone(chord[0] / 2, 0.45, 'sine', 0.06);
        this.step++;
      }, 240);
    },
    stop() { clearInterval(this.timer); this.timer = null; },
  };

  // ---------- بدون إنترنت ----------
  const CACHE = 'showtime-v1';
  if ('serviceWorker' in navigator && location.protocol !== 'file:') {
    window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(e => console.warn('sw', e)));
  }

  // نحفظ كل ملفات اللعبة والصور بالجهاز. onProgress(done, total)
  async function prepareOffline(onProgress) {
    if (!window.caches) throw new Error('no-cache');
    const urls = new Set(['./', 'index.html', 'remote.html', 'sw.js', 'credits.html']);
    document.querySelectorAll('script[src], link[rel="stylesheet"]').forEach(el => urls.add(el.getAttribute('src') || el.getAttribute('href')));
    // ملفات صفحة الحكم
    try {
      const html = await (await fetch('remote.html', { cache: 'no-store' })).text();
      (html.match(/(?:src|href)="([^"]+)"/g) || []).forEach(m => {
        const u = m.replace(/^(?:src|href)="|"$/g, '');
        if (!/^https?:/.test(u)) urls.add(u);
      });
    } catch (e) { /* ignore */ }
    ['cairo-arabic-400', 'cairo-arabic-700', 'cairo-arabic-800', 'cairo-latin-400', 'cairo-latin-700', 'cairo-latin-800',
      'lalezar-arabic-400', 'lalezar-latin-400'].forEach(f => urls.add('assets/fonts/' + f + '-normal.woff2'));
    if (window.COUNTRIES) COUNTRIES.flags.forEach(f => urls.add('assets/flags/' + f.c + '.svg'));
    Object.values(window.WIKI_IMAGES || {}).forEach(u => urls.add(u));

    const list = [...urls];
    const cache = await caches.open(CACHE);
    let done = 0, failed = 0;
    let i = 0;
    async function worker() {
      while (i < list.length) {
        const u = list[i++];
        try {
          const hit = await cache.match(u);
          if (!hit) {
            const res = await fetch(u, { cache: 'no-store' });
            if (res.ok) await cache.put(u, res); else failed++;
          }
        } catch (e) { failed++; }
        done++;
        if (onProgress) onProgress(done, list.length);
      }
    }
    await Promise.all([1, 2, 3, 4, 5, 6].map(worker));
    try { localStorage.setItem('st-offline', JSON.stringify({ at: Date.now(), n: list.length - failed })); } catch (e) { /* ignore */ }
    return { total: list.length, failed };
  }

  window.ST = { params, peerOptions, peerQuery, PREFIX, randomCode, shuffle, sfx, music, prepareOffline };
})();
