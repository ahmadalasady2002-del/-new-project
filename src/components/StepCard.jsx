import { Check } from 'lucide-react';

/**
 * One of the three calculation steps. Shows its number on a vertical
 * "timeline" rail, its inputs, and the live formula.
 */
export default function StepCard({ index, title, subtitle, done, active, isLast, children, delay = 0 }) {
  return (
    <section
      className="relative animate-fade-up ps-0 sm:ps-16"
      style={{ animationDelay: `${delay}ms` }}
      aria-labelledby={`step-${index}-title`}
    >
      {/* Timeline rail (tablet and up) */}
      <div aria-hidden className="absolute inset-y-0 start-0 hidden w-12 flex-col items-center sm:flex">
        <StepBadge index={index} done={done} active={active} />
        {!isLast && (
          <div className="relative mt-2 w-px flex-1 overflow-hidden bg-ivory-300 dark:bg-ink-700">
            <div
              className={`absolute inset-x-0 top-0 gold-fill transition-all duration-700 ease-out ${done ? 'h-full' : 'h-0'}`}
            />
          </div>
        )}
      </div>

      <div
        className={`card p-5 transition-all duration-500 sm:p-6 ${
          active ? '!border-gold-400/80 ring-4 ring-gold-200/40 dark:!border-gold-500/60 dark:ring-gold-700/20' : ''
        }`}
      >
        <header className="mb-5 flex items-start gap-3">
          <div className="sm:hidden">
            <StepBadge index={index} done={done} active={active} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold tracking-wide text-gold-600 dark:text-gold-400">
              الخطوة {['الأولى', 'الثانية', 'الثالثة'][index - 1]}
            </p>
            <h2 id={`step-${index}-title`} className="mt-1 font-display text-lg font-bold text-ink-900 dark:text-ivory-50 sm:text-xl">
              {title}
            </h2>
            {subtitle && <p className="mt-1 text-sm leading-relaxed text-ink-400 dark:text-ink-300">{subtitle}</p>}
          </div>
        </header>
        <div className="space-y-5">{children}</div>
      </div>
    </section>
  );
}

function StepBadge({ index, done, active }) {
  return (
    <div
      className={`relative grid size-11 shrink-0 place-items-center rounded-full font-display text-base font-bold transition-all duration-500 ${
        done
          ? 'gold-fill text-ink-900 shadow-[0_8px_20px_-10px_rgba(122,92,34,0.9)]'
          : active
            ? 'border-2 border-gold-400 bg-white text-gold-600 dark:bg-ink-900 dark:text-gold-300'
            : 'border border-ivory-300 bg-white text-ink-400 dark:border-ink-700 dark:bg-ink-900 dark:text-ink-300'
      }`}
    >
      {done ? <Check className="size-5" strokeWidth={2.5} /> : <span className="num">{index}</span>}
      {active && !done && <span className="absolute inset-0 animate-ping rounded-full border border-gold-400/60" />}
    </div>
  );
}
