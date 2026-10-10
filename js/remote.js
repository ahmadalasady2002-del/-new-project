// ريموت الحكم: يتصل بشاشة التلفزيون ويرسل أوامر
(function () {
  const $ = s => document.querySelector(s);
  const room = (ST.params.get('room') || '').toLowerCase();
  let peer, conn, state = null, retry;

  function status(text, ok) {
    const s = $('#r-status');
    s.textContent = text;
    s.classList.toggle('ok', !!ok);
  }

  if (!room) {
    status('ما اكو غرفة');
    $('#r-hint').textContent = 'صوّر الـQR اللي على شاشة التلفزيون.';
    render();
    return;
  }

  function start() {
    if (typeof Peer === 'undefined') { status('ما گدرنا نحمّل الاتصال'); return; }
    peer = new Peer(ST.peerOptions());
    peer.on('open', connect);
    peer.on('disconnected', () => setTimeout(() => !peer.destroyed && peer.reconnect(), 1500));
    peer.on('error', err => {
      console.warn('peer error', err.type, err);
      if (err.type === 'peer-unavailable') {
        status('الشاشة مو موجودة');
        $('#r-hint').textContent = 'تأكد إن صفحة اللعبة مفتوحة على التلفزيون، وصوّر الـQR مرة ثانية.';
      } else {
        status('مشكلة بالاتصال');
      }
      scheduleRetry();
    });
  }

  function connect() {
    if (conn && conn.open) return;
    status('جاري الاتصال…');
    if (conn) { const old = conn; conn = null; try { old.close(); } catch (e) { /* ignore */ } }
    const c = peer.connect(ST.PREFIX + room, { reliable: true });
    conn = c;
    c.on('open', () => {
      if (c !== conn) return;
      clearTimeout(retry);
      status('متصل', true);
      $('#r-hint').textContent = '';
      conn.send({ cmd: 'hello' });
    });
    c.on('data', msg => {
      if (c !== conn) return;
      if (msg && msg.type === 'state') { state = msg; render(); }
    });
    c.on('close', () => { if (c !== conn) return; status('انقطع الاتصال'); scheduleRetry(); });
    c.on('error', () => { if (c === conn) scheduleRetry(); });
  }

  function scheduleRetry() {
    clearTimeout(retry);
    retry = setTimeout(() => {
      if (!peer || peer.destroyed) return start();
      if (peer.disconnected) peer.reconnect();
      else connect();
    }, 2500);
  }

  // نبضة حتى الشاشة تعرف إننا بعدنا متصلين
  setInterval(() => { if (conn && conn.open) conn.send({ cmd: 'ping' }); }, 3000);
  // إذا الحكم سكّر الصفحة نبلغ الشاشة فوراً
  window.addEventListener('pagehide', () => {
    if (conn && conn.open) { try { conn.send({ cmd: 'bye', from: peer.id }); } catch (e) { /* ignore */ } }
  });

  // لما يرجع الموبايل من وضع السكون نتأكد من الاتصال
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && !(conn && conn.open)) scheduleRetry();
  });

  function send(cmd) {
    if (!conn || !conn.open) { status('مو متصل'); scheduleRetry(); return; }
    conn.send({ cmd });
    if (navigator.vibrate) navigator.vibrate(30);
  }

  $('#r-correct').addEventListener('click', () => send('correct'));
  $('#r-skip').addEventListener('click', () => send('skip'));
  $('#r-spin').addEventListener('click', () => send('spin'));
  $('#r-next').addEventListener('click', () => send('next'));
  $('#r-pause').addEventListener('click', () => send('pause'));
  $('#r-cancel').addEventListener('click', () => {
    if (confirm('متأكد تريد تلغي اللعبة وترجع للبداية؟')) send('cancel');
  });

  function render() {
    const p = state ? state.phase : 'none';
    document.body.dataset.phase = p;
    document.body.classList.toggle('paused', !!(state && state.paused));
    const ans = $('#r-answer'), label = $('#r-label');
    if (p === 'play') {
      label.textContent = 'الجواب الحالي';
      ans.textContent = state.answer || '…';
    } else if (p === 'wheel') {
      label.textContent = state.mixed ? 'اضغط «ابدأ الجولة» حتى تبدي' : 'دوّر العجلة حتى تبدي الجولة';
      ans.textContent = state.mixed ? '🎲' : '🎡';
    } else if (p === 'spinning') {
      label.textContent = 'العجلة دتدور…';
      ans.textContent = '🎡';
    } else if (p === 'roundEnd' || p === 'gameEnd') {
      const w = state.teams[state.winner] || state.teams[0];
      label.textContent = (p === 'gameEnd' ? 'انتهت اللعبة' : 'انتهت الجولة') + ' · آخر جواب: ' + (state.lastAnswer || '—');
      ans.textContent = (p === 'gameEnd' ? '🏆 ' : 'الفايز: ') + w.name;
    } else if (p === 'setup') {
      label.textContent = 'الشاشة دتتجهز';
      ans.textContent = '…';
    } else {
      ans.textContent = '—';
    }
    $('#r-cat').textContent = state && state.category ? 'التصنيف: ' + state.category : '';
    $('#r-next').textContent = p === 'gameEnd' ? 'لعبة جديدة' : 'الجولة الجاية';
    $('#r-spin').textContent = state && state.mixed ? 'ابدأ الجولة 🎲' : 'دوّر العجلة';
    $('#r-pause').textContent = state && state.paused ? 'كمّل' : 'إيقاف مؤقت';

    if (state) {
      state.teams.forEach((t, i) => {
        const el = $('#rt' + i);
        el.querySelector('.n').textContent = t.name;
        el.querySelector('.t').textContent = t.time + 's';
        el.querySelector('.d').textContent = '●'.repeat(t.wins) + '○'.repeat(Math.max(0, state.target - t.wins));
        el.classList.toggle('active', p === 'play' && state.turn === i);
      });
    }
  }

  start();
})();
