/**
 * Renders a live formula with real numbers, e.g.
 *   [سعر المثقال 980,000] ÷ [5] = [سعر الغرام 196,000]
 * terms: array of { value, caption?, op? , highlight? } where `op` is an
 * operator rendered before the term.
 */
export default function Equation({ terms, muted }) {
  return (
    <div
      className={`flex flex-wrap items-end gap-x-2 gap-y-3 rounded-2xl border border-dashed px-3 py-3.5 transition-colors sm:px-4 ${
        muted
          ? 'border-ivory-300 bg-ivory-50/60 dark:border-ink-700 dark:bg-ink-950/30'
          : 'border-gold-300/70 bg-gold-100/30 dark:border-gold-700/40 dark:bg-gold-700/10'
      }`}
    >
      {terms.map((t, i) => (
        <div key={i} className="flex items-end gap-2">
          {t.op && (
            <span aria-hidden className="pb-1 text-xl font-light text-gold-500">
              {t.op}
            </span>
          )}
          <div className="flex flex-col items-center">
            <span
              key={t.value}
              className={`num animate-value-pop rounded-xl px-2.5 py-1 font-display text-[15px] font-semibold sm:text-base ${
                t.highlight
                  ? 'gold-fill text-ink-900 shadow-[0_6px_14px_-8px_rgba(122,92,34,0.8)]'
                  : 'bg-white text-ink-800 ring-1 ring-ivory-300 dark:bg-ink-800 dark:text-ivory-100 dark:ring-ink-700'
              }`}
            >
              {t.value}
            </span>
            {t.caption && (
              <span className="mt-1 text-[10.5px] leading-none text-ink-400 dark:text-ink-300">{t.caption}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
