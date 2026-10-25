import { useId } from 'react';

/** Pill-style radio group. options: [{ value, label, sub? }] */
export default function Segmented({ label, options, value, onChange, columns = options.length }) {
  const name = useId();

  return (
    <fieldset className="min-w-0 space-y-2">
      {label && (
        <legend className="mb-2 block text-sm font-medium text-ink-700 dark:text-ivory-200">{label}</legend>
      )}
      <div
        className="grid gap-1.5 rounded-2xl border border-ivory-300 bg-ivory-200/60 p-1.5 dark:border-ink-700 dark:bg-ink-950/60"
        style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
      >
        {options.map((opt) => {
          const checked = opt.value === value;
          return (
            <label
              key={opt.value}
              className={`relative flex cursor-pointer flex-col items-center justify-center rounded-xl px-2 py-2.5 text-center transition-all duration-300 has-[:focus-visible]:ring-4 has-[:focus-visible]:ring-gold-300/50 ${
                checked
                  ? 'gold-fill text-ink-900 shadow-[0_6px_16px_-8px_rgba(122,92,34,0.7)]'
                  : 'text-ink-500 hover:bg-white/70 dark:text-ink-300 dark:hover:bg-ink-800'
              }`}
            >
              <input
                type="radio"
                name={name}
                value={opt.value}
                checked={checked}
                onChange={() => onChange(opt.value)}
                className="sr-only"
              />
              <span className="text-sm font-semibold">{opt.label}</span>
              {opt.sub && (
                <span className={`num mt-0.5 text-[11px] ${checked ? 'text-ink-800/80' : 'text-ink-400 dark:text-ink-500'}`}>
                  {opt.sub}
                </span>
              )}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
