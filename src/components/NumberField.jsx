import { useId, useLayoutEffect, useRef } from 'react';
import { formatRawInput, sanitizeNumber } from '../lib/gold.js';

/**
 * Text input that only accepts positive numbers, shows thousands separators
 * as you type and reports the raw numeric string ("980000", "7.35").
 */
export default function NumberField({
  label,
  value,
  onChange,
  onFocus,
  onBlur,
  suffix,
  icon: Icon,
  decimals = 0,
  placeholder,
  hint,
  error,
  autoFocus,
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  const inputRef = useRef(null);
  // Number of digits/dots left of the caret, so it can be restored after commas are re-inserted.
  const caretRef = useRef(null);
  const display = formatRawInput(value);

  const handleChange = (e) => {
    const { value: typed, selectionStart } = e.target;
    caretRef.current = selectionStart == null ? null : countSignificant(typed.slice(0, selectionStart));
    onChange(sanitizeNumber(typed, { decimals }));
  };

  useLayoutEffect(() => {
    const el = inputRef.current;
    const wanted = caretRef.current;
    caretRef.current = null;
    if (wanted == null || !el || document.activeElement !== el) return;
    let pos = 0;
    for (let seen = 0; pos < display.length && seen < wanted; pos++) {
      if (/[\d.]/.test(display[pos])) seen++;
    }
    el.setSelectionRange(pos, pos);
  }, [display]);

  // Block keys that could never form a valid positive number.
  const handleKeyDown = (e) => {
    if (['-', '+', 'e', 'E'].includes(e.key)) e.preventDefault();
  };

  return (
    <div className="space-y-2">
      <label htmlFor={id} className="block text-sm font-medium text-ink-700 dark:text-ivory-200">
        {label}
      </label>
      <div className={`field ${error ? '!border-red-400 !ring-red-200/50 dark:!border-red-500/70' : ''}`}>
        {Icon && <Icon aria-hidden className="size-5 shrink-0 text-gold-500" strokeWidth={1.75} />}
        <input
          ref={inputRef}
          id={id}
          type="text"
          inputMode={decimals > 0 ? 'decimal' : 'numeric'}
          autoComplete="off"
          enterKeyHint="next"
          dir="ltr"
          value={display}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={onFocus}
          onBlur={onBlur}
          placeholder={placeholder}
          autoFocus={autoFocus}
          aria-invalid={Boolean(error)}
          aria-describedby={hint || error ? hintId : undefined}
          className="num min-w-0 flex-1 bg-transparent py-3.5 text-right text-lg font-semibold tracking-wide text-ink-900 outline-none placeholder:font-normal placeholder:text-ink-300 dark:text-ivory-50 dark:placeholder:text-ink-500"
        />
        {suffix && (
          <span className="shrink-0 rounded-lg bg-gold-100/70 px-2 py-1 text-xs font-semibold text-gold-700 dark:bg-gold-700/20 dark:text-gold-300">
            {suffix}
          </span>
        )}
      </div>
      {(error || hint) && (
        <p
          id={hintId}
          className={`text-xs leading-relaxed ${error ? 'text-red-600 dark:text-red-400' : 'text-ink-400 dark:text-ink-300'}`}
        >
          {error || hint}
        </p>
      )}
    </div>
  );
}

function countSignificant(text) {
  return (text.match(/[\d.٠-٩۰-۹٫]/g) || []).length;
}
