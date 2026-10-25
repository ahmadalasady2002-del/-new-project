import { forwardRef } from 'react';
import { Coins, Copy, Gem, Hammer, MessageCircle, RotateCcw, Scale } from 'lucide-react';
import { formatIQD } from '../lib/gold.js';
import { useAnimatedNumber } from '../hooks/useAnimatedNumber.js';

const ResultsPanel = forwardRef(function ResultsPanel({ result, karat, onCopy, shareUrl, onReset }, ref) {
  const animatedFinal = useAnimatedNumber(result.ready ? result.finalPrice : 0);
  const show = (v) => (result.ready ? formatIQD(v) : '—');

  const rows = [
    { icon: Scale, label: 'سعر الغرام بدون صياغة', value: show(result.gramPrice) },
    { icon: Hammer, label: 'أجور الصياغة الإجمالية', value: show(result.totalMaking) },
    { icon: Coins, label: 'قيمة الذهب بدون صياغة', value: show(result.goldValue) },
  ];

  return (
    <aside ref={ref} id="results" aria-live="polite" className="card overflow-hidden">
      {/* Hero total */}
      <div className="relative overflow-hidden bg-ink-900 px-6 pb-7 pt-6 text-ivory-100 dark:bg-black/40">
        <div
          aria-hidden
          className="pointer-events-none absolute -end-24 -top-28 size-72 rounded-full bg-[radial-gradient(circle,rgba(184,145,58,0.35),transparent_65%)]"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-28 -start-16 size-64 rounded-full bg-[radial-gradient(circle,rgba(226,196,122,0.14),transparent_65%)]"
        />
        <div className="relative flex items-center justify-between">
          <span className="text-sm text-ivory-300">السعر النهائي</span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-gold-400/40 bg-gold-400/10 px-3 py-1 text-xs font-semibold text-gold-200">
            <Gem className="size-3.5" />
            عيار <span className="num">{karat}</span>
          </span>
        </div>
        <div className="relative mt-4 flex items-baseline gap-2">
          <span
            className={`num font-display text-[2.6rem] font-extrabold leading-none tracking-tight sm:text-5xl ${
              result.ready ? 'gold-text' : 'text-ink-500'
            }`}
          >
            {result.ready ? formatIQD(animatedFinal) : '0'}
          </span>
          <span className="text-base font-medium text-gold-200/90">دينار عراقي</span>
        </div>
        <p className="relative mt-3 text-xs text-ivory-300/70">
          {result.ready ? 'شامل قيمة الذهب وأجور الصياغة' : 'أدخل سعر المثقال والوزن لعرض السعر'}
        </p>
      </div>

      {/* Breakdown */}
      <dl className="divide-y divide-ivory-200 px-6 dark:divide-ink-800">
        {rows.map(({ icon: Icon, label, value }) => (
          <div key={label} className="flex items-center justify-between gap-3 py-3.5">
            <dt className="flex items-center gap-2.5 text-sm text-ink-500 dark:text-ink-300">
              <span className="grid size-8 place-items-center rounded-xl bg-gold-100/70 text-gold-600 dark:bg-gold-700/15 dark:text-gold-300">
                <Icon className="size-4" strokeWidth={1.75} />
              </span>
              {label}
            </dt>
            <dd className="flex items-baseline gap-1">
              <span key={value} className="num animate-value-pop font-display text-base font-semibold text-ink-900 dark:text-ivory-50">
                {value}
              </span>
              {result.ready && <span className="text-[11px] text-ink-400">د.ع</span>}
            </dd>
          </div>
        ))}
        <div className="flex items-center justify-between gap-3 py-4">
          <dt className="text-sm font-semibold text-ink-800 dark:text-ivory-100">السعر النهائي</dt>
          <dd className="flex items-baseline gap-1">
            <span key={result.finalPrice} className="num animate-value-pop font-display text-lg font-bold text-gold-600 dark:text-gold-300">
              {show(result.finalPrice)}
            </span>
            {result.ready && <span className="text-[11px] text-ink-400">د.ع</span>}
          </dd>
        </div>
      </dl>

      {/* Actions */}
      <div className="grid grid-cols-2 gap-2 border-t border-ivory-200 p-4 dark:border-ink-800">
        <a
          href={result.ready ? shareUrl : undefined}
          target="_blank"
          rel="noopener noreferrer"
          aria-disabled={!result.ready}
          className={`btn col-span-2 bg-[#1f8f4e] text-white hover:bg-[#1a7a43] ${result.ready ? '' : 'pointer-events-none opacity-40'}`}
        >
          <MessageCircle className="size-4.5" />
          مشاركة عبر واتساب
        </a>
        <button
          type="button"
          onClick={onCopy}
          disabled={!result.ready}
          className="btn bg-ink-900 text-ivory-100 hover:bg-ink-800 dark:bg-ivory-100 dark:text-ink-900 dark:hover:bg-white"
        >
          <Copy className="size-4" />
          نسخ النتيجة
        </button>
        <button
          type="button"
          onClick={onReset}
          className="btn border border-ivory-300 bg-white text-ink-700 hover:border-gold-300 hover:text-gold-700 dark:border-ink-700 dark:bg-ink-900 dark:text-ivory-200 dark:hover:border-gold-600"
        >
          <RotateCcw className="size-4" />
          إعادة تعيين
        </button>
      </div>
    </aside>
  );
});

export default ResultsPanel;
