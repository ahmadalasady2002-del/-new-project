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
  function tone(freq, dur = 0.12, type = 'sine', vol = 0.15, when = 0) {
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
  };

  window.ST = { params, peerOptions, peerQuery, PREFIX, randomCode, shuffle, sfx };
})();
