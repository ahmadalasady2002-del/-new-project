// شاشة التلفزيون: كل منطق اللعبة هنا، وريموت الحكم يرسل أوامر بس
(function () {
  const { sfx, shuffle } = ST;
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];

  const SKIP_PENALTY = 3;
  const REVEAL_MS = 900;      // مدة عرض ✓ والجواب بعد الإجابة الصحيحة
  const EFFECT_MS = 12000;    // مدة التضبيب/الزوم لحد ما تتوضح الصورة
  const WHEEL_MS = 4200;

  const S = {
    selected: new Set(['flags', 'apps', 'cars', 'players']),
    settings: { time: 45, target: 3, mode: 'normal', play: 'wheel' },
    teams: [{ name: '', time: 45, wins: 0 }, { name: '', time: 45, wins: 0 }],
    cats: [], cat: null, item: null,
    phase: 'setup', turn: 0, roundStarter: 0,
    paused: false, busy: false, lastAnswer: '',
    wheelRot: 0, effect: null,
    refs: new Set(), peer: null, code: null,
    custom: [],
  };

  // ---------- التنقل بين الشاشات ----------
  function show(id) {
    $$('.screen').forEach(s => s.classList.toggle('active', s.id === id));
    if (id === 's-cats') renderCats();
    if (id === 's-custom') renderCustomList();
  }
  $$('[data-go]').forEach(b => b.addEventListener('click', () => { sfx.click(); show(b.dataset.go); }));

  $('#btn-start').addEventListener('click', () => { sfx.unlock(); sfx.click(); show('s-cats'); });
  $('#btn-howto').addEventListener('click', () => show('s-howto'));
  $('#btn-custom').addEventListener('click', () => { sfx.unlock(); show('s-custom'); });
  $('#btn-fullscreen').addEventListener('click', () => {
    const el = document.documentElement;
    (el.requestFullscreen || el.webkitRequestFullscreen || (() => {})).call(el);
  });

  // ---------- التصنيفات ----------
  function allCategories() {
    return [...CATEGORIES, ...S.custom];
  }

  function renderCats() {
    const grid = $('#cat-grid');
    grid.innerHTML = '';
    for (const c of allCategories()) {
      const b = document.createElement('button');
      b.className = 'cat-tile' + (S.selected.has(c.id) ? ' on' : '');
      b.innerHTML = `<span class="ic"></span><span class="nm"></span><span class="ct"></span>`;
      b.querySelector('.ic').textContent = c.icon;
      b.querySelector('.nm').textContent = c.name;
      b.querySelector('.ct').textContent = c.items.length + ' سؤال' + (c.type === 'wiki' ? ' · يحتاج إنترنت' : '');
      if (!c.items.length) b.disabled = true;
      b.addEventListener('click', () => {
        sfx.click();
        S.selected.has(c.id) ? S.selected.delete(c.id) : S.selected.add(c.id);
        b.classList.toggle('on');
        updateCatsNext();
      });
      grid.appendChild(b);
    }
    // نشيل أي اختيار لتصنيف انحذف
    const ids = new Set(allCategories().map(c => c.id));
    [...S.selected].forEach(id => ids.has(id) || S.selected.delete(id));
    updateCatsNext();
  }
  function updateCatsNext() { $('#btn-cats-next').disabled = S.selected.size === 0; }

  $('#btn-cats-next').addEventListener('click', () => {
    sfx.click();
    S.prep = prepareCategories();
    show('s-teams');
  });

  // نسخة من كل تصنيف مختار مع "رزمة" أسئلة مخلوطة
  async function prepareCategories() {
    const chosen = allCategories().filter(c => S.selected.has(c.id))
      .map(c => ({ ...c, items: c.items.map(it => ({ ...it })) }));
    const failed = [];
    for (const c of chosen) {
      if (c.type === 'wiki') {
        const n = await Media.resolveWiki(c);
        if (!n) failed.push(c.name);
      }
      c.deck = [];
    }
    return { cats: chosen.filter(c => c.items.length), failed };
  }

  // ---------- الفرق والإعدادات ----------
  $$('.seg').forEach(seg => {
    const key = seg.dataset.key;
    const sync = () => seg.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.v === String(S.settings[key])));
    seg.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
      sfx.click();
      S.settings[key] = (key === 'mode' || key === 'play') ? b.dataset.v : Number(b.dataset.v);
      sync();
    }));
    sync();
  });

  $('#btn-teams-next').addEventListener('click', () => {
    sfx.click();
    S.teams[0].name = $('#team1').value.trim() || 'الفريق 1';
    S.teams[1].name = $('#team2').value.trim() || 'الفريق 2';
    show('s-join');
    if (S.refs.size) { startGame(); return; }  // الحكم داخل من قبل
    initPeer();
  });

  $('#btn-no-ref').addEventListener('click', () => { sfx.click(); startGame(); });

  // ---------- الاتصال بالحكم (PeerJS) ----------
  function remoteUrl() {
    const u = new URL('remote.html', location.href);
    const q = ST.peerQuery();
    q.set('room', S.code);
    u.search = q.toString();
    return u.toString();
  }

  function qrSvg(text, cell) {
    const qr = qrcode(0, 'M');
    qr.addData(text);
    qr.make();
    return qr.createSvgTag({ cellSize: cell, margin: 2, scalable: true });
  }

  function renderQr() {
    const url = remoteUrl();
    $('#qr').innerHTML = qrSvg(url, 8);
    $('#qr').title = url;
    $('#join-status').textContent = 'رمز الغرفة: ' + S.code.toUpperCase();
  }

  function initPeer() {
    if (S.peer && !S.peer.destroyed) { if (S.code) renderQr(); return; }
    if (typeof Peer === 'undefined') { $('#join-status').textContent = 'ما گدرنا نحمّل الاتصال. تگدرون تلعبون بدون حكم.'; return; }
    S.code = sessionStorage.getItem('st-room') || ST.randomCode();
    const peer = new Peer(ST.PREFIX + S.code, ST.peerOptions());
    S.peer = peer;
    peer.on('open', () => { sessionStorage.setItem('st-room', S.code); renderQr(); });
    peer.on('connection', conn => {
      conn.on('open', () => {
        S.refs.add(conn);
        sfx.join();
        toast('تم دخول الحكم ✓');
        broadcast();
        updateRefUi();
        if ($('#s-join').classList.contains('active')) setTimeout(startGame, 900);
      });
      conn.on('data', onCommand);
      const drop = () => {
        if (!S.refs.delete(conn)) return;
        updateRefUi();
        if (!S.refs.size && S.phase !== 'setup') toast('الحكم انقطع — يگدر يرجع يصوّر الـQR');
      };
      conn.on('close', drop);
      conn.on('error', drop);
    });
    peer.on('disconnected', () => setTimeout(() => !peer.destroyed && peer.reconnect(), 2000));
    peer.on('error', err => {
      console.warn('peer error', err.type, err);
      if (err.type === 'unavailable-id') {
        // الرمز مستخدم (مثلاً بعد تحديث الصفحة) — نسوي رمز جديد
        sessionStorage.removeItem('st-room');
        peer.destroy();
        S.peer = null;
        initPeer();
      } else if (err.type === 'network' || err.type === 'server-error' || err.type === 'socket-error') {
        $('#join-status').textContent = 'مشكلة بالاتصال، دنعيد المحاولة…';
      }
    });
  }

  function updateRefUi() {
    document.body.classList.toggle('has-ref', S.refs.size > 0);
  }

  function broadcast() {
    if (!S.refs.size) return;
    const st = {
      type: 'state',
      phase: S.phase, paused: S.paused,
      answer: S.phase === 'play' && S.item ? S.item.a : '',
      lastAnswer: S.lastAnswer, winner: S.lastWinner,
      category: S.cat ? S.cat.name : '',
      turn: S.turn, target: S.settings.target, mixed: S.settings.play === 'mixed',
      teams: S.teams.map(t => ({ name: t.name, time: Math.max(0, Math.ceil(t.time)), wins: t.wins })),
    };
    S.refs.forEach(c => { try { c.open && c.send(st); } catch (e) { console.warn(e); } });
  }

  function onCommand(msg) {
    if (!msg || typeof msg !== 'object') return;
    switch (msg.cmd) {
      case 'hello': broadcast(); break;
      case 'spin': spin(); break;
      case 'correct': correct(); break;
      case 'skip': skip(); break;
      case 'pause': togglePause(); break;
      case 'next': next(); break;
      case 'cancel': cancelGame(); break;
    }
  }

  // ---------- اللعبة ----------
  async function startGame() {
    if (S.starting || (S.phase !== 'setup' && $('#s-game').classList.contains('active'))) return;
    S.starting = true;
    $('#join-status').textContent = 'جاري تحميل الصور…';
    const { cats, failed } = await S.prep;
    S.starting = false;
    if (failed.length) toast('ما گدرنا نجيب صور: ' + failed.join('، '));
    if (!cats.length) {
      show('s-cats');
      toast('ما بقى ولا تصنيف. تأكدوا من الإنترنت أو اختاروا تصنيفات ثانية.');
      return;
    }
    S.cats = cats;
    S.teams.forEach(t => { t.wins = 0; });
    S.roundStarter = 1;      // nextRound يقلبها، فالجولة الأولى يبدي الفريق 1
    show('s-game');
    $('#s-game').classList.toggle('mixed', S.settings.play === 'mixed');
    drawWheel();
    nextRound();
  }

  function nextRound() {
    S.roundStarter = 1 - S.roundStarter;
    S.turn = S.roundStarter;
    S.teams.forEach(t => { t.time = S.settings.time; });
    S.cat = null; S.item = null; S.paused = false;
    setPhase('wheel');
  }

  function setPhase(p) {
    S.phase = p;
    const g = $('#s-game');
    g.dataset.phase = p;
    if (p !== 'roundEnd' && p !== 'gameEnd') $('#overlay').classList.remove('show');
    renderHud();
    broadcast();
  }

  function renderHud() {
    S.teams.forEach((t, i) => {
      const box = $('#tb' + i);
      box.querySelector('.t-name').textContent = t.name;
      const sec = Math.max(0, Math.ceil(t.time));
      box.querySelector('.t-time').innerHTML = sec + '<small>s</small>';
      box.querySelector('.t-dots').innerHTML = Array.from({ length: S.settings.target },
        (_, k) => `<i class="${k < t.wins ? 'on' : ''}"></i>`).join('');
      box.classList.toggle('active', S.phase === 'play' && S.turn === i);
      box.classList.toggle('low', S.phase === 'play' && S.turn === i && sec <= 5);
    });
    $('#cat-chip').textContent = S.cat ? 'التصنيف: ' + S.cat.name : '';
    $('#cat-chip').style.visibility = S.cat ? 'visible' : 'hidden';
    $('#s-game').classList.toggle('paused', S.paused);
    $('#lc-pause').textContent = S.paused ? 'كمّل' : 'إيقاف';
  }

  // ---------- العجلة ----------
  // القطع مرسومة SVG، والكتابة HTML فوقها. الكتابة تلف ويا العجلة بس تبقى دايماً عدلة
  // (تنلف بعكس العجلة)، وحجمها ينحسب حتى تبقى داخل الدائرة اللي تنرسم جوه كل قطعة.
  const WHEEL_COLORS = ['#c9b8f5', '#7fd3df', '#a98be8', '#5fbfd0'];
  const WR = 190;           // نصف قطر العجلة بوحدات الـviewBox (العرض الكلي 400)
  const HUB = 52;           // نصف قطر الدائرة اللي بالنص + هامش
  const SPIN_EASE = 'cubic-bezier(.17,.67,.12,1)';
  const measureCtx = document.createElement('canvas').getContext('2d');

  function textWidth(t, px) {
    measureCtx.font = `800 ${px}px Cairo, system-ui, sans-serif`;
    return measureCtx.measureText(t).width;
  }

  // أكبر خط (بوحدات العجلة) يخلي السطور داخل دائرة نصف قطرها rho
  function fitLabel(icon, name, rho) {
    const words = name.split(/\s+/);
    const layouts = [[name]];
    if (words.length > 1) {
      // نقسم الاسم سطرين من أقرب مسافة للنص
      let best = 1, diff = Infinity;
      for (let k = 1; k < words.length; k++) {
        const d = Math.abs(words.slice(0, k).join(' ').length - words.slice(k).join(' ').length);
        if (d < diff) { diff = d; best = k; }
      }
      layouts.push([words.slice(0, best).join(' '), words.slice(best).join(' ')]);
    }
    let pick = null;
    for (const lines of layouts) {
      // بخط 10: عرض أعرض سطر، والارتفاع = أيقونة (1.25) + كل سطر 1.25
      const w = Math.max(14, ...lines.map(l => textWidth(l, 10)));
      const h = 10 * 1.25 * (lines.length + 1);
      const k = (rho * 2 * 0.86) / Math.hypot(w, h);   // نسبة التكبير حتى القطر يدخل بالدائرة
      const fs = Math.min(30, 10 * k);
      if (!pick || fs > pick.fs) pick = { lines, fs };
    }
    return pick;
  }

  function drawWheel() {
    const n = S.cats.length;
    const pt = (a, r) => [r * Math.sin(a * Math.PI / 180), -r * Math.cos(a * Math.PI / 180)];
    // الدائرة الأكبر اللي تدخل جوه القطعة (بين المركز والحافة)
    const half = Math.PI / n;
    let d = n === 1 ? 0 : WR / (1 + Math.sin(half));
    let rho = n === 1 ? WR * 0.6 : d * Math.sin(half);
    if (n > 1 && d - rho < HUB) { d = (WR + HUB) / 2; rho = Math.min(d * Math.sin(half), (WR - HUB) / 2); }
    if (n === 1) { d = (WR + HUB) / 2; rho = (WR - HUB) / 2; }

    // كل الكتابات بنفس الحجم (حجم أصغر وحدة) حتى تبين مرتبة
    const fits = S.cats.map(c => fitLabel(c.icon, c.short || c.name, rho));
    const fsAll = Math.min(...fits.map(f => f.fs));
    let svg = '';
    let labels = '';
    S.cats.forEach((c, i) => {
      const a0 = i * 360 / n, a1 = (i + 1) * 360 / n, mid = (a0 + a1) / 2;
      // عدد فردي: آخر قطعة لون ثالث حتى ما تتلاصق قطعتين بنفس اللون
      const col = WHEEL_COLORS[(n % 2 && n > 1 && i === n - 1) ? 2 : i % 2];
      if (n === 1) {
        svg += `<circle r="${WR}" fill="${col}"/>`;
      } else {
        const [x0, y0] = pt(a0, WR), [x1, y1] = pt(a1, WR);
        svg += `<path d="M0 0L${x0.toFixed(2)} ${y0.toFixed(2)}A${WR} ${WR} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}Z" fill="${col}" stroke="#0a0e1c" stroke-opacity=".25" stroke-width="1.5"/>`;
      }
      const [x, y] = pt(n === 1 ? 180 : mid, d);
      const { lines } = fits[i];
      const fs = fsAll;
      labels += `<div class="wl" style="left:${(50 + x / 4).toFixed(3)}%;top:${(50 + y / 4).toFixed(3)}%">`
        + `<div class="wl-in" style="font-size:calc(var(--wu) * ${fs.toFixed(2)})">`
        + `<span class="wl-ic">${escapeXml(c.icon)}</span>`
        + lines.map(l => `<span>${escapeXml(l)}</span>`).join('')
        + '</div></div>';
    });
    $('#wheel').innerHTML = svg;
    $('#wheel-labels').innerHTML = labels;
    setWheelRotation(false);
  }

  function setWheelRotation(animate) {
    const spinEl = $('#wheel-spin');
    const tr = animate ? `transform ${WHEEL_MS}ms ${SPIN_EASE}` : 'none';
    spinEl.style.transition = tr;
    spinEl.style.transform = `rotate(${S.wheelRot}deg)`;
    $$('#wheel-labels .wl-in').forEach(el => {
      el.style.transition = tr;
      el.style.transform = `translate(-50%, -50%) rotate(${-S.wheelRot}deg)`;
    });
  }

  // وحدة العجلة بالبكسل حتى الخط يكبر ويصغر ويا حجم العجلة
  function syncWheelUnit() {
    const w = $('#wheel-wrap').getBoundingClientRect().width;
    if (w) $('#wheel-wrap').style.setProperty('--wu', (w / 400) + 'px');
  }
  window.addEventListener('resize', syncWheelUnit);
  if (window.ResizeObserver) new ResizeObserver(syncWheelUnit).observe($('#wheel-wrap'));
  // إذا الخط وصل متأخر نعيد الحساب
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => S.cats.length && S.phase !== 'spinning' && drawWheel());

  function escapeXml(s) {
    return s.replace(/[<>&"]/g, ch => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[ch]));
  }

  function spin() {
    if (S.phase !== 'wheel') return;
    sfx.unlock();
    // مختلط: بدون عجلة، كل سؤال من تصنيف عشوائي
    if (S.settings.play === 'mixed') {
      sfx.click();
      setPhase('play');
      nextQuestion();
      return;
    }
    const n = S.cats.length;
    const idx = Math.floor(Math.random() * n);
    const center = (idx + 0.5) * 360 / n;
    const jitter = (Math.random() - 0.5) * (360 / n) * 0.6;
    const cur = S.wheelRot;
    const want = ((-center - jitter - cur) % 360 + 720) % 360;
    S.wheelRot = cur + 360 * 5 + want;
    setWheelRotation(true);
    setPhase('spinning');
    // تكات العجلة تبطئ تدريجياً
    let t = 0;
    (function tick() {
      const p = t / WHEEL_MS;
      if (p >= 0.95) return;
      sfx.wheelTick();
      const gap = 40 + 400 * p * p;
      t += gap;
      setTimeout(tick, gap);
    })();
    setTimeout(() => {
      $('#wheel-wrap').classList.add('picked');
      setTimeout(() => {
        $('#wheel-wrap').classList.remove('picked');
        if (S.phase !== 'spinning') return;   // انلغت اللعبة وهي دتدور
        S.cat = S.cats[idx];
        setPhase('play');
        nextQuestion();
      }, 900);
    }, WHEEL_MS + 100);
  }

  // ---------- الأسئلة ----------
  // بالمختلط ناخذ تصنيف عشوائي، ونتجنب نفس التصنيف مرتين ورا بعض
  function pickMixed() {
    const pool = S.cats.length > 1 ? S.cats.filter(c => c !== S.cat) : S.cats;
    return pool[Math.floor(Math.random() * pool.length)];
  }

  function drawItem(cat) {
    if (!cat.deck.length) cat.deck = shuffle(cat.items.slice());
    return cat.deck.pop();
  }

  let qToken = 0;
  async function nextQuestion() {
    const token = ++qToken;
    S.busy = true;
    if (S.settings.play === 'mixed') S.cat = pickMixed();
    const cat = S.cat;
    renderHud();
    let item = null;
    // نجرب لحد 6 مرات إذا صورة ما تحملت
    for (let tries = 0; tries < 6; tries++) {
      const cand = drawItem(cat);
      const src = Media.imageSrc(cat, cand);
      if (!src || await Promise.race([Media.preload(src), wait(6000).then(() => false)])) { item = cand; break; }
    }
    if (token !== qToken || S.phase !== 'play') return;
    if (!item) { toast('مشكلة بتحميل الصور'); item = drawItem(cat); }
    S.item = item;
    const card = $('#card');
    card.classList.remove('correct');
    $('#q-prompt').textContent = cat.prompt;
    $('#q-answer').textContent = '';
    const media = $('#q-media');
    media.innerHTML = '';
    const el = Media.render(cat, item);
    media.appendChild(el);
    card.classList.remove('pop'); void card.offsetWidth; card.classList.add('pop');
    applyEffect(el);
    // نحضّر صورة السؤال الجاي بالخلفية
    if (!cat.deck.length) cat.deck = shuffle(cat.items.slice());
    const nxt = cat.deck[cat.deck.length - 1];
    const ns = nxt && Media.imageSrc(cat, nxt);
    if (ns) Media.preload(ns);
    S.busy = false;
    lastTick = performance.now();
    broadcast();
  }

  function applyEffect(el) {
    S.effect = null;
    if (!el.classList.contains('zoomable') || S.settings.mode === 'normal') return;
    let frames;
    if (S.settings.mode === 'blur') {
      frames = [{ filter: 'blur(26px)' }, { filter: 'blur(14px)', offset: 0.35 }, { filter: 'blur(0px)' }];
    } else {
      const ox = 25 + Math.random() * 50, oy = 25 + Math.random() * 50;
      el.style.transformOrigin = `${ox}% ${oy}%`;
      frames = [{ transform: 'scale(5)' }, { transform: 'scale(2.2)', offset: 0.4 }, { transform: 'scale(1)' }];
    }
    S.effect = el.animate(frames, { duration: EFFECT_MS, fill: 'forwards', easing: 'linear' });
    if (S.paused) S.effect.pause();
  }

  function correct() {
    if (S.phase !== 'play' || S.busy || S.paused || !S.item) return;
    S.busy = true;
    sfx.correct();
    S.lastAnswer = S.item.a;
    if (S.effect) S.effect.finish();
    $('#q-answer').textContent = S.item.a;
    $('#card').classList.add('correct');
    broadcast();
    setTimeout(() => {
      if (S.phase !== 'play') return;
      S.turn = 1 - S.turn;
      renderHud();
      nextQuestion();
    }, REVEAL_MS);
  }

  function skip() {
    if (S.phase !== 'play' || S.busy || S.paused || !S.item) return;
    sfx.skip();
    S.lastAnswer = S.item.a;
    const t = S.teams[S.turn];
    t.time -= SKIP_PENALTY;
    flashPenalty(S.turn);
    toast('الجواب كان: ' + S.item.a, 1600);
    renderHud();
    if (t.time <= 0) { endRound(); return; }
    nextQuestion();
  }

  function flashPenalty(i) {
    const box = $('#tb' + i);
    const f = document.createElement('span');
    f.className = 'penalty';
    f.textContent = '−' + SKIP_PENALTY + 's';
    box.appendChild(f);
    setTimeout(() => f.remove(), 1200);
  }

  function togglePause() {
    if (!['play', 'wheel'].includes(S.phase)) return;
    S.paused = !S.paused;
    if (S.effect) S.paused ? S.effect.pause() : S.effect.play();
    lastTick = performance.now();
    renderHud();
    broadcast();
  }

  function endRound() {
    if (S.phase !== 'play') return;
    S.teams[S.turn].time = 0;
    if (S.item) S.lastAnswer = S.item.a;
    const winner = 1 - S.turn;
    S.lastWinner = winner;
    S.teams[winner].wins++;
    const gameOver = S.teams[winner].wins >= S.settings.target;
    S.busy = false;
    qToken++;
    if (S.effect) S.effect.finish();
    sfx.buzzer();
    setTimeout(sfx.end, 450);
    setPhase(gameOver ? 'gameEnd' : 'roundEnd');
    const w = S.teams[winner];
    $('#ov-title').textContent = gameOver ? '🏆 مبروك!' : 'انتهت الجولة!';
    $('#ov-winner').textContent = gameOver ? w.name + ' فاز باللعبة' : 'الفايز: ' + w.name;
    const score = `${S.teams[0].name} ${S.teams[0].wins} — ${S.teams[1].wins} ${S.teams[1].name}`;
    $('#ov-sub').textContent = (gameOver ? 'النتيجة النهائية: ' : `${S.settings.target} جولات = الفوز باللعبة · `) + score;
    const acts = $('#ov-actions');
    acts.innerHTML = '';
    const btn = (label, cls, fn) => {
      const b = document.createElement('button');
      b.className = 'btn ' + cls;
      b.textContent = label;
      b.addEventListener('click', () => { sfx.click(); fn(); });
      acts.appendChild(b);
    };
    if (gameOver) {
      btn('لعبة جديدة', 'primary', newGame);
      btn('القائمة الرئيسية', 'ghost', toMenu);
      confetti();
    } else {
      btn('الجولة الجاية', 'primary', next);
    }
    $('#overlay').classList.add('show');
  }

  function next() {
    if (S.phase === 'roundEnd') nextRound();
    else if (S.phase === 'gameEnd') newGame();
  }

  function newGame() {
    S.teams.forEach(t => { t.wins = 0; });
    S.roundStarter = 1;
    nextRound();
  }

  // الحكم (أو الشاشة) يلغي اللعبة ونرجع للبداية
  function cancelGame() {
    if (S.phase === 'setup') return;
    qToken++;
    S.busy = false;
    S.paused = false;
    S.item = null;
    if (S.effect) { S.effect.cancel(); S.effect = null; }
    S.teams.forEach(t => { t.wins = 0; });
    toast('انلغت اللعبة');
    toMenu();
  }

  function toMenu() {
    S.phase = 'setup';
    S.cat = null;
    $('#overlay').classList.remove('show');
    broadcast();
    show('s-title');
  }

  // ---------- المؤقت ----------
  let lastTick = performance.now();
  setInterval(() => {
    const now = performance.now();
    const dt = (now - lastTick) / 1000;
    lastTick = now;
    if (S.phase !== 'play' || S.paused || S.busy) return;
    const t = S.teams[S.turn];
    const before = Math.ceil(t.time);
    t.time -= dt;
    const after = Math.ceil(t.time);
    if (after !== before) {
      if (after <= 5 && after > 0) sfx.tick();
      renderHud();
      broadcast();
    }
    if (t.time <= 0) endRound();
  }, 100);

  // ---------- أدوات واجهة ----------
  let toastTimer;
  function toast(msg, ms = 2600) {
    const t = $('#toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), ms);
  }
  // التوست موجود بشاشة اللعب، فنخليه يطلع فوق كل الشاشات
  document.body.appendChild($('#toast'));

  function wait(ms) { return new Promise(r => setTimeout(r, ms)); }

  function confetti() {
    const box = document.createElement('div');
    box.className = 'confetti';
    const cols = ['#a78bfa', '#67d3e0', '#4ade80', '#f5c76b', '#f472b6'];
    for (let i = 0; i < 80; i++) {
      const p = document.createElement('i');
      p.style.left = Math.random() * 100 + '%';
      p.style.background = cols[i % cols.length];
      p.style.animationDelay = Math.random() * 0.8 + 's';
      p.style.animationDuration = 2 + Math.random() * 1.5 + 's';
      box.appendChild(p);
    }
    document.body.appendChild(box);
    setTimeout(() => box.remove(), 4500);
  }

  // التحكم من نفس الجهاز (بدون حكم)
  $('#lc-spin').addEventListener('click', spin);
  $('#wheel-hub').addEventListener('click', spin);
  $('#lc-correct').addEventListener('click', correct);
  $('#lc-skip').addEventListener('click', skip);
  $('#lc-pause').addEventListener('click', togglePause);
  $('#lc-cancel').addEventListener('click', () => { if (confirm('تريدون تلغون اللعبة وترجعون للبداية؟')) cancelGame(); });
  $('#mixed-start').addEventListener('click', spin);
  $('#ref-mini').addEventListener('click', () => {
    initPeer();
    const pop = document.createElement('div');
    pop.className = 'qr-pop';
    pop.innerHTML = '<div class="qr"></div><p>الحكم يصوّره من جواله · اضغط للإغلاق</p>';
    if (S.code) pop.querySelector('.qr').innerHTML = qrSvg(remoteUrl(), 6);
    else pop.querySelector('p').textContent = 'جاري تجهيز الاتصال… جرّب بعد ثواني';
    pop.addEventListener('click', () => pop.remove());
    document.body.appendChild(pop);
  });

  document.addEventListener('keydown', e => {
    if (e.target.matches('input')) return;
    if (!$('#s-game').classList.contains('active')) return;
    const k = e.key.toLowerCase();
    if (k === 'enter') { e.preventDefault(); S.phase === 'play' ? correct() : next(); }
    else if (k === 's' || k === 'س') skip();
    else if (k === 'w' || k === 'ص' || k === ' ') { e.preventDefault(); spin(); }
    else if (k === 'p' || k === 'ح') togglePause();
  });

  // ---------- التصنيفات الخاصة ----------
  let objectUrls = [];
  async function loadCustom() {
    objectUrls.forEach(u => URL.revokeObjectURL(u));
    objectUrls = [];
    const raw = await CustomStore.all();
    S.raw = raw;
    S.custom = raw.map(c => ({
      id: 'custom-' + c.id, name: c.name, icon: '⭐', type: 'custom',
      prompt: c.prompt || 'شنو هاي الصورة؟',
      items: c.items.map(it => {
        let src = it.url;
        if (it.blob) { src = URL.createObjectURL(it.blob); objectUrls.push(src); }
        return { a: it.a, src };
      }),
    }));
  }

  let editing = null;
  function renderCustomList() {
    const list = $('#custom-list');
    list.innerHTML = '';
    if (!S.raw || !S.raw.length) list.innerHTML = '<p class="muted">ما عندكم تصنيفات خاصة لحد الآن.</p>';
    (S.raw || []).forEach(c => {
      const b = document.createElement('button');
      b.className = 'cat-tile' + (editing && editing.id === c.id ? ' on' : '');
      b.innerHTML = '<span class="ic">⭐</span><span class="nm"></span><span class="ct"></span>';
      b.querySelector('.nm').textContent = c.name;
      b.querySelector('.ct').textContent = c.items.length + ' صورة';
      b.addEventListener('click', () => { editing = c; renderCustomList(); });
      list.appendChild(b);
    });
    renderEditor();
  }

  function renderEditor() {
    const ed = $('#custom-editor');
    ed.classList.toggle('hidden', !editing);
    if (!editing) return;
    $('#ce-title').textContent = editing.name + ' — ' + (editing.prompt || '');
    const box = $('#ce-items');
    box.innerHTML = '';
    editing.items.forEach((it, i) => {
      const row = document.createElement('div');
      row.className = 'ce-item';
      const img = document.createElement('img');
      img.src = it.blob ? URL.createObjectURL(it.blob) : it.url;
      img.onload = () => it.blob && URL.revokeObjectURL(img.src);
      const inp = document.createElement('input');
      inp.value = it.a;
      inp.placeholder = 'الجواب';
      inp.addEventListener('change', async () => { it.a = inp.value.trim(); await persist(); });
      const del = document.createElement('button');
      del.className = 'btn ghost';
      del.textContent = '✕';
      del.addEventListener('click', async () => { editing.items.splice(i, 1); await persist(); renderEditor(); });
      row.append(img, inp, del);
      box.appendChild(row);
    });
  }

  async function persist() {
    await CustomStore.save(editing);
    const id = editing.id;
    await loadCustom();
    editing = S.raw.find(c => c.id === id) || null;
    renderCustomList();
  }

  $('#btn-new-cat').addEventListener('click', async () => {
    const name = $('#new-cat-name').value.trim();
    if (!name) { toast('اكتبوا اسم التصنيف'); return; }
    editing = { id: Date.now().toString(36), name, prompt: $('#new-cat-prompt').value.trim() || 'شنو هاي الصورة؟', items: [] };
    $('#new-cat-name').value = $('#new-cat-prompt').value = '';
    await persist();
  });

  $('#ce-files').addEventListener('change', async e => {
    if (!editing) return;
    for (const f of e.target.files) {
      const blob = await shrink(f);
      editing.items.push({ id: Math.random().toString(36).slice(2), a: f.name.replace(/\.[^.]+$/, ''), blob });
    }
    e.target.value = '';
    await persist();
    toast('انضافت الصور — تأكدوا من الأجوبة');
  });

  $('#ce-url-add').addEventListener('click', async () => {
    const url = $('#ce-url').value.trim(), a = $('#ce-url-answer').value.trim();
    if (!editing || !/^https?:\/\//.test(url) || !a) { toast('حطوا رابط صورة وجوابها'); return; }
    editing.items.push({ id: Math.random().toString(36).slice(2), a, url });
    $('#ce-url').value = $('#ce-url-answer').value = '';
    await persist();
  });

  $('#ce-delete').addEventListener('click', async () => {
    if (!editing || !confirm('متأكدين تحذفون "' + editing.name + '"؟')) return;
    await CustomStore.remove(editing.id);
    S.selected.delete('custom-' + editing.id);
    editing = null;
    await loadCustom();
    renderCustomList();
  });

  // نصغّر الصور الكبيرة حتى ما تاخذ مساحة
  async function shrink(file, max = 1000) {
    try {
      const bmp = await createImageBitmap(file);
      const k = Math.min(1, max / Math.max(bmp.width, bmp.height));
      if (k === 1 && file.size < 400000) return file;
      const c = document.createElement('canvas');
      c.width = Math.round(bmp.width * k);
      c.height = Math.round(bmp.height * k);
      c.getContext('2d').drawImage(bmp, 0, 0, c.width, c.height);
      return await new Promise(r => c.toBlob(r, 'image/jpeg', 0.85));
    } catch (e) {
      return file;
    }
  }

  loadCustom();
  window.__ST_STATE = S; // للتجربة والتصحيح
})();
