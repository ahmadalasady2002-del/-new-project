import { ChevronDown } from 'lucide-react';
import { formatIQD } from '../lib/gold.js';

/** Floating total shown on small screens while the results card is off-screen. */
export default function MobileTotalBar({ visible, result, onClick }) {
  return (
    <div
      className={`fixed inset-x-0 bottom-0 z-30 px-4 pb-[max(1rem,env(safe-area-inset-bottom))] transition-all duration-500 lg:hidden ${
        visible ? 'translate-y-0 opacity-100' : 'pointer-events-none translate-y-full opacity-0'
      }`}
    >
      <button
        type="button"
        onClick={onClick}
        className="flex w-full items-center justify-between gap-3 rounded-2xl border border-gold-500/30 bg-ink-900/95 px-5 py-3.5 text-start text-ivory-100 shadow-[0_20px_40px_-12px_rgba(0,0,0,0.5)] backdrop-blur"
      >
        <span className="flex flex-col">
          <span className="text-[11px] text-ivory-300">السعر النهائي</span>
          <span className="flex items-baseline gap-1.5">
            <span key={result.finalPrice} className="num gold-text animate-value-pop font-display text-xl font-bold">
              {result.ready ? formatIQD(result.finalPrice) : '—'}
            </span>
            {result.ready && <span className="text-xs text-gold-200/80">د.ع</span>}
          </span>
        </span>
        <span className="flex items-center gap-1 text-xs text-gold-200">
          التفاصيل
          <ChevronDown className="size-4" />
        </span>
      </button>
    </div>
  );
}
