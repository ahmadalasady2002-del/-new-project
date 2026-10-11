// Service Worker: يخلي اللعبة تشتغل بدون إنترنت.
// - صفحات HTML: من الإنترنت أولاً (حتى التحديثات توصل)، وإذا ماكو إنترنت من النسخة المحفوظة.
// - باقي الملفات (صور، خطوط، سكربتات): من النسخة المحفوظة أولاً، وإذا ما موجودة نجيبها ونحفظها.
const CACHE = 'showtime-v1';

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(['./', 'index.html', 'remote.html'])).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  const sameOrigin = url.origin === self.location.origin;
  const wikiImage = url.hostname === 'upload.wikimedia.org';
  if (!sameOrigin && !wikiImage) return;          // سيرفر الحكم وويكيبيديا API: مباشرة

  if (sameOrigin && (req.mode === 'navigate' || /\.html?$/.test(url.pathname) || url.pathname.endsWith('/'))) {
    e.respondWith(fetch(req).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    }).catch(() => caches.match(req, { ignoreSearch: true }).then(r => r || caches.match('index.html'))));
    return;
  }

  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
    if (res.ok || res.type === 'opaque') { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
    return res;
  }).catch(() => caches.match(req, { ignoreSearch: true }))));
});
