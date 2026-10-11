// ينزّل صور ويكيبيديا لكل تصنيفات الصور ويحفظها جوه اللعبة، حتى تشتغل بدون إنترنت.
// يشتغل على GitHub Actions (.github/workflows/fetch-images.yml) لأن يحتاج إنترنت.
//   node tools/fetch-wiki-images.mjs
// يكتب:
//   assets/wiki/*.jpg|png        الصور (بعرض 480 بكسل)
//   js/data/wiki-images.js       خريطة: عنوان المقالة ← مسار الصورة
//   credits.html                 حقوق الصور (المصوّر والرخصة) — مطلوبة لرخص ويكيميديا
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const API = 'https://en.wikipedia.org/w/api.php';
const UA = 'ShowtimeGame/1.0 (https://github.com/ahmadalasady2002-del/-new-project; party game)';
const SIZE = 480;
// إذا sharp موجودة (بـ GitHub Actions) نضغط كل الصور لـ JPEG خفيف
let sharp = null;
try { sharp = (await import('sharp')).default; } catch (e) { console.warn('sharp not available: saving original files'); }
const outDir = path.join(root, 'assets/wiki');
fs.mkdirSync(outDir, { recursive: true });

// نقرا content.js بدون متصفح
const ctx = { window: { COUNTRIES: { flags: [], maps: [] }, LOGOS: { apps: [], cars: [] } } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(root, 'js/data/content.js'), 'utf8'), ctx);
const titles = [...new Set(ctx.window.CATEGORIES.filter(c => c.type === 'wiki').flatMap(c => c.items.map(i => i.t)))];
console.log('titles:', titles.length);

const sleep = ms => new Promise(r => setTimeout(r, ms));
async function api(params) {
  const u = API + '?' + new URLSearchParams({ format: 'json', formatversion: '2', ...params });
  for (let i = 0; i < 4; i++) {
    try {
      const r = await fetch(u, { headers: { 'User-Agent': UA } });
      if (r.ok) return await r.json();
      console.warn('api status', r.status);
    } catch (e) { console.warn('api error', e.message); }
    await sleep(1500 * (i + 1));
  }
  throw new Error('API failed');
}

// اسم ملف ثابت لكل عنوان
const fileBase = t => t.normalize('NFKD').replace(/[^\w]+/g, '_').replace(/^_|_$/g, '').slice(0, 50) + '_' +
  crypto.createHash('md5').update('v2:' + t).digest('hex').slice(0, 6);

// 1) صورة كل مقالة (pageimages ترجع بس الصور الحرة)
const info = {};   // title -> { thumb, file }
for (let i = 0; i < titles.length; i += 50) {
  const chunk = titles.slice(i, i + 50);
  const j = await api({ action: 'query', redirects: '1', prop: 'pageimages', piprop: 'thumbnail|name', pithumbsize: String(SIZE), titles: chunk.join('|') });
  const q = j.query || {};
  const final = t => {
    for (const n of q.normalized || []) if (n.from === t) t = n.to;
    for (const n of q.redirects || []) if (n.from === t) t = n.to;
    return t;
  };
  const byTitle = {};
  for (const p of q.pages || []) if (p.thumbnail) byTitle[p.title] = { thumb: p.thumbnail.source, file: p.pageimage };
  for (const t of chunk) if (byTitle[final(t)]) info[t] = byTitle[final(t)];
  await sleep(300);
}
console.log('with image:', Object.keys(info).length);

// 2) المصوّر والرخصة لكل صورة
const files = [...new Set(Object.values(info).map(v => v.file))];
const meta = {};
const strip = h => (h || '').replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();
for (let i = 0; i < files.length; i += 50) {
  const chunk = files.slice(i, i + 50);
  const j = await api({ action: 'query', prop: 'imageinfo', iiprop: 'extmetadata|url', iiextmetadatafilter: 'Artist|LicenseShortName|LicenseUrl', titles: chunk.map(f => 'File:' + f).join('|') });
  for (const p of (j.query && j.query.pages) || []) {
    const ii = p.imageinfo && p.imageinfo[0];
    if (!ii) continue;
    const m = ii.extmetadata || {};
    meta[p.title.replace(/^File:/, '').replace(/ /g, '_')] = {
      artist: strip(m.Artist && m.Artist.value) || 'غير معروف',
      license: strip(m.LicenseShortName && m.LicenseShortName.value) || '',
      licenseUrl: (m.LicenseUrl && m.LicenseUrl.value) || '',
      page: ii.descriptionurl || '',
    };
  }
  await sleep(300);
}

// 3) تنزيل الصور
const map = {};
const credits = [];
let n = 0;
for (const [t, v] of Object.entries(info)) {
  const ext = sharp ? 'jpg' : ((v.thumb.split('?')[0].match(/\.(\w+)$/) || [, 'jpg'])[1].toLowerCase()).replace('jpeg', 'jpg');
  const name = fileBase(t) + '.' + ext;
  const dest = path.join(outDir, name);
  if (!fs.existsSync(dest)) {
    let ok = false;
    for (let k = 0; k < 3 && !ok; k++) {
      try {
        const r = await fetch(v.thumb, { headers: { 'User-Agent': UA } });
        if (r.ok) {
          let buf = Buffer.from(await r.arrayBuffer());
          if (sharp) {
            buf = await sharp(buf).rotate().resize({ width: SIZE, height: SIZE, fit: 'inside', withoutEnlargement: true })
              .flatten({ background: '#ffffff' }).jpeg({ quality: 76, mozjpeg: true }).toBuffer();
          }
          fs.writeFileSync(dest, buf);
          ok = true;
        }
        else await sleep(1500);
      } catch (e) { await sleep(1500); }
    }
    if (!ok) { console.warn('download failed', t); continue; }
    await sleep(120);
  }
  map[t] = 'assets/wiki/' + name;
  const m = meta[(v.file || '').replace(/ /g, '_')] || {};
  credits.push({ title: t, file: v.file, ...m });
  n++;
}
console.log('downloaded/kept:', n);

// نشيل صور قديمة ما عادت مستخدمة
const used = new Set(Object.values(map).map(p => path.basename(p)));
for (const f of fs.readdirSync(outDir)) if (!used.has(f)) fs.unlinkSync(path.join(outDir, f));

const sorted = Object.fromEntries(Object.entries(map).sort());
fs.writeFileSync(path.join(root, 'js/data/wiki-images.js'),
  '// مولّد تلقائياً من tools/fetch-wiki-images.mjs — صور ويكيبيديا المحفوظة جوه اللعبة\nwindow.WIKI_IMAGES = ' + JSON.stringify(sorted, null, 0) + ';\n');

const esc = s => String(s || '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const rows = credits.sort((a, b) => a.title.localeCompare(b.title)).map(c =>
  `<tr><td>${esc(c.title)}</td><td><a href="${esc(c.page)}">${esc(c.file)}</a></td><td>${esc(c.artist)}</td><td>${c.licenseUrl ? `<a href="${esc(c.licenseUrl)}">${esc(c.license)}</a>` : esc(c.license)}</td></tr>`).join('\n');
fs.writeFileSync(path.join(root, 'credits.html'), `<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>حقوق الصور — شوتايم</title>
<style>body{font-family:system-ui,sans-serif;background:#0a0e1c;color:#eef1fb;margin:0;padding:16px}a{color:#67d3e0}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid #2a3354;padding:6px;text-align:right;vertical-align:top}
th{color:#a78bfa}h1{font-size:22px}</style></head><body>
<h1>حقوق الصور</h1>
<p>صور اللاعبين والمشاهير والأماكن والحيوانات والأكلات من <a href="https://commons.wikimedia.org">ويكيميديا كومنز</a> برخص حرة.
الأعلام من flag-icons (MIT)، والشعارات من simple-icons (CC0)، والخطوط Cairo وLalezar (SIL OFL).</p>
<table><thead><tr><th>السؤال</th><th>الملف</th><th>المصوّر / المصدر</th><th>الرخصة</th></tr></thead><tbody>
${rows}
</tbody></table></body></html>
`);
console.log('done');
