// يولّد js/data/logos.js من simple-icons (CC0).
// التشغيل: npm i simple-icons && node tools/build-logos.mjs <node_modules_dir>
// تجنّبنا الشعارات اللي بيها اسم الماركة مكتوب (يفضح الجواب).
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const nm = path.resolve(process.argv[2] || 'node_modules');
const require = createRequire(path.join(nm, 'x.js'));
const si = Object.values(require('simple-icons'));
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');

const APPS = {
  whatsapp: 'واتساب', instagram: 'إنستغرام', youtube: 'يوتيوب', netflix: 'نتفليكس', spotify: 'سبوتيفاي',
  tiktok: 'تيك توك', snapchat: 'سناب شات', facebook: 'فيسبوك', x: 'إكس (تويتر)', telegram: 'تيليغرام',
  discord: 'ديسكورد', twitch: 'تويتش', googlemaps: 'خرائط گوگل', gmail: 'جيميل', roblox: 'روبلوكس',
  fortnite: 'فورتنايت', pinterest: 'بنترست', reddit: 'ريديت', messenger: 'ماسنجر', viber: 'فايبر',
  shazam: 'شازام', googlechrome: 'گوگل كروم', firefox: 'فايرفوكس', safari: 'سفاري', duolingo: 'دولينجو',
  threads: 'ثريدز', wikipedia: 'ويكيبيديا', dropbox: 'دروب بوكس', airbnb: 'إير بي إن بي',
  playstation: 'بلايستيشن', android: 'أندرويد', apple: 'آبل', google: 'گوگل', steam: 'ستيم',
  paypal: 'باي بال', valorant: 'فالورانت', leagueoflegends: 'ليگ أوف ليجندز', ubisoft: 'يوبيسوفت',
  rockstargames: 'روكستار', wechat: 'وي تشات', signal: 'سيگنال', pubg: 'ببجي',
  mcdonalds: 'ماكدونالدز', starbucks: 'ستاربكس', nike: 'نايكي', adidas: 'أديداس', puma: 'بوما',
  huawei: 'هواوي', shell: 'شل', redbull: 'ريد بول', mastercard: 'ماستركارد', deliveroo: 'ديليفرو',
  nba: 'NBA (دوري السلة الأمريكي)', premierleague: 'الدوري الإنگليزي',
  bluetooth: 'بلوتوث', googledrive: 'گوگل درايف', googlephotos: 'صور گوگل', googleplay: 'گوگل بلاي',
  appstore: 'آب ستور', icloud: 'آي كلاود', tinder: 'تيندر', opera: 'متصفح أوبرا', tripadvisor: 'تريب أدفايزر',
  nvidia: 'إنفيديا', jordan: 'جوردن', underarmour: 'أندر آرمور', imessage: 'آي مسج', waze: 'ويز',
  googlemeet: 'گوگل ميت', googletranslate: 'ترجمة گوگل', linux: 'لينكس', ubuntu: 'أوبونتو',
  soundcloud: 'ساوند كلاود', bitcoin: 'بيتكوين', ethereum: 'إيثيريوم', binance: 'باينانس',
  tacobell: 'تاكو بيل', reebok: 'ريبوك', oneplus: 'ون بلس', motorola: 'موتورولا', bluesky: 'بلوسكاي',
  kick: 'كيك', battledotnet: 'باتل نت', googleassistant: 'مساعد گوگل',
};
const CARS = {
  toyota: 'تويوتا', audi: 'أودي', ferrari: 'فيراري', tesla: 'تيسلا', lamborghini: 'لامبورغيني',
  hyundai: 'هيونداي', honda: 'هوندا', volkswagen: 'فولكس واگن', chevrolet: 'شفروليه', mitsubishi: 'ميتسوبيشي',
  renault: 'رينو', mazda: 'مازدا', subaru: 'سوبارو', suzuki: 'سوزوكي', maserati: 'مازيراتي',
  bugatti: 'بوگاتي', rollsroyce: 'رولز رويس', citroen: 'ستروين', opel: 'أوبل', skoda: 'سكودا', seat: 'سيات',
  cadillac: 'كاديلاك', infiniti: 'إنفينيتي', acura: 'أكيورا', astonmartin: 'أستون مارتن', polestar: 'بولستار',
  dacia: 'داسيا', smart: 'سمارت', bentley: 'بنتلي', yamahacorporation: 'ياماها',
};

function build(map) {
  return Object.entries(map).map(([slug, a]) => {
    const ic = si.find(i => i.slug === slug);
    if (!ic) throw new Error('missing icon ' + slug);
    return { a, d: ic.path, h: ic.hex };
  });
}

const out = { apps: build(APPS), cars: build(CARS) };
fs.writeFileSync(path.join(root, 'js/data/logos.js'),
  '// مولّد تلقائياً من tools/build-logos.mjs — الشعارات من simple-icons (CC0)\nwindow.LOGOS = ' + JSON.stringify(out) + ';\n');
console.log('apps', out.apps.length, 'cars', out.cars.length);
