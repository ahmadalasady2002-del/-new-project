// يولّد js/data/countries.js (أسماء الدول + أشكالها على الخريطة) ويمسخ صور الأعلام.
// التشغيل: npm i flag-icons world-atlas@2 topojson-client d3-geo i18n-iso-countries
//          node tools/build-countries.mjs <node_modules_dir>
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const nm = path.resolve(process.argv[2] || 'node_modules');
const require = createRequire(path.join(nm, 'x.js'));
const countries = require('i18n-iso-countries');
countries.registerLocale(require('i18n-iso-countries/langs/ar.json'));
const topojson = require('topojson-client');
const d3 = require('d3-geo');
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');

// أسماء دارجة بدل الأسماء الرسمية الطويلة
const NAMES = {
  US: 'أمريكا', GB: 'بريطانيا', KR: 'كوريا الجنوبية', KP: 'كوريا الشمالية', RU: 'روسيا',
  AE: 'الإمارات', SA: 'السعودية', SY: 'سوريا', IR: 'إيران', CZ: 'التشيك', NL: 'هولندا',
  BO: 'بوليفيا', VE: 'فنزويلا', TZ: 'تنزانيا', CD: 'الكونغو الديمقراطية', CG: 'الكونغو',
  CI: 'ساحل العاج', LY: 'ليبيا', PS: 'فلسطين', VN: 'فيتنام', LA: 'لاوس', MD: 'مولدوفا',
  MK: 'مقدونيا الشمالية', BA: 'البوسنة والهرسك', TR: 'تركيا', CH: 'سويسرا', BH: 'البحرين',
  KW: 'الكويت', QA: 'قطر', OM: 'عُمان', YE: 'اليمن', JO: 'الأردن', LB: 'لبنان', EG: 'مصر',
  SD: 'السودان', MA: 'المغرب', DZ: 'الجزائر', TN: 'تونس', MR: 'موريتانيا', SO: 'الصومال',
  DJ: 'جيبوتي', KM: 'جزر القمر', IQ: 'العراق', CN: 'الصين', TW: 'تايوان', ZA: 'جنوب أفريقيا',
  NZ: 'نيوزيلندا', CV: 'الرأس الأخضر', SS: 'جنوب السودان', CF: 'أفريقيا الوسطى',
  DO: 'الدومينيكان', TT: 'ترينيداد وتوباغو', VA: 'الفاتيكان', MM: 'ميانمار', BN: 'بروناي',
};

// دول معروفة للأعلام (مرتبة تقريباً من الأسهل للأصعب)
const FLAGS = `IQ SA EG JO SY LB PS KW AE QA BH OM YE MA DZ TN LY SD MR SO DJ KM
TR IR PK AF IN CN JP KR KP ID MY TH VN PH SG BD LK NP MN KZ UZ AZ GE AM
US CA MX BR AR CL CO PE VE UY PY BO EC CU JM
GB FR DE IT ES PT NL BE CH AT SE NO DK FI IS IE PL CZ SK HU RO BG GR UA RU BY RS HR SI BA AL MK ME MT CY EE LV LT LU MC VA
NG GH SN CI CM KE ET TZ UG RW ZA ZW ZM AO MZ MG ML NE TD BF GN CD CG GA SS ER
AU NZ FJ PG`.split(/\s+/);

// دول شكلها على الخريطة واضح ومعروف
const MAPS = `IQ SA EG JO SY LB KW AE QA OM YE MA DZ TN LY SD SO
TR IR PK AF IN CN JP KR ID MY TH VN PH MN KZ LK
US CA MX BR AR CL CO PE VE CU
GB FR DE IT ES PT NL GR UA RU PL NO SE FI IS IE RO
NG ZA ET KE MG TZ ML NE TD SS
AU NZ PG`.split(/\s+/);

const name = c => NAMES[c] || countries.getName(c, 'ar');

// دول شكلها جزر متفرقة، نخليها كاملة
const KEEP_ALL = new Set('ID PH MY CA GR RU PG'.split(' '));
// نشيل الأراضي البعيدة (مثل غويانا الفرنسية، ألاسكا، سفالبارد) والجزر الصغيرة جداً
function mainland(code, f) {
  if (f.geometry.type !== 'MultiPolygon' || KEEP_ALL.has(code)) return f;
  const polys = f.geometry.coordinates.map(coords => {
    const g = { type: 'Polygon', coordinates: coords };
    return { coords, area: d3.geoArea(g), center: d3.geoCentroid(g) };
  });
  const big = polys.reduce((a, b) => (b.area > a.area ? b : a));
  const maxDist = 12 * Math.PI / 180;
  const kept = polys.filter(p => p.area >= big.area * 0.01 && d3.geoDistance(p.center, big.center) < maxDist);
  return { ...f, geometry: { type: 'MultiPolygon', coordinates: kept.map(p => p.coords) } };
}

// الأعلام
const flagDir = path.join(nm, 'flag-icons/flags/4x3');
for (const c of FLAGS) fs.copyFileSync(path.join(flagDir, c.toLowerCase() + '.svg'), path.join(root, 'assets/flags', c.toLowerCase() + '.svg'));

// أشكال الدول كـ SVG path جاهز
// 110m أخف بهواية؛ نرجع لـ 50m بس للدول الصغيرة اللي ما موجودة بيه
const load = f => { const t = JSON.parse(fs.readFileSync(path.join(nm, 'world-atlas', f))); return topojson.feature(t, t.objects.countries).features; };
const coarse = load('countries-110m.json'), fine = load('countries-50m.json');
const shapes = {};
for (const c of MAPS) {
  const num = countries.alpha2ToNumeric(c);
  let f = coarse.find(f => f.id === num);
  // الدول الصغيرة والمتوسطة تطلع مربعة بـ110m، فناخذها من 50m
  if (!f || d3.geoArea(f) < 0.012) f = fine.find(f => f.id === num);
  if (!f) throw new Error('no shape for ' + c);
  f = mainland(c, f);
  const [lon, lat] = d3.geoCentroid(f);
  const proj = d3.geoAzimuthalEqualArea().rotate([-lon, -lat]).fitExtent([[10, 10], [390, 390]], f);
  const p = d3.geoPath(proj).digits(0);
  shapes[c] = p(f);
}

const out = {
  flags: FLAGS.map(c => ({ c: c.toLowerCase(), a: name(c) })),
  maps: MAPS.map(c => ({ c, a: name(c), d: shapes[c] })),
};
fs.writeFileSync(path.join(root, 'js/data/countries.js'),
  '// مولّد تلقائياً من tools/build-countries.mjs — لا تعدله يدوياً\nwindow.COUNTRIES = ' + JSON.stringify(out) + ';\n');
console.log('flags', out.flags.length, 'maps', out.maps.length);
