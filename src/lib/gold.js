// Core gold-price math and number helpers. Pure functions, no React.

/** Iraqi mithqal used by this calculator (grams). */
export const GRAMS_PER_MITHQAL = 5;

export const KARATS = [
  { value: 24, purity: 999, label: 'عيار 24' },
  { value: 22, purity: 916, label: 'عيار 22' },
  { value: 21, purity: 875, label: 'عيار 21' },
  { value: 18, purity: 750, label: 'عيار 18' },
];

export const MAKING_TYPES = {
  PER_GRAM: 'perGram',
  FIXED: 'fixed',
};

const ARABIC_DIGITS = '٠١٢٣٤٥٦٧٨٩';
const PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹';

/** Convert Arabic-Indic / Persian digits and separators to plain ASCII. */
export function normalizeDigits(input) {
  return String(input ?? '')
    .replace(/[٠-٩]/g, (d) => ARABIC_DIGITS.indexOf(d))
    .replace(/[۰-۹]/g, (d) => PERSIAN_DIGITS.indexOf(d))
    .replace(/[٫]/g, '.') // Arabic decimal separator
    .replace(/[٬،]/g, ','); // Arabic thousands separator / comma
}

/**
 * Clean whatever the user typed into a raw numeric string.
 * Strips everything except digits and one decimal point, so negative
 * numbers, letters and symbols can never get in.
 */
export function sanitizeNumber(input, { decimals = 0 } = {}) {
  let s = normalizeDigits(input).replace(/,/g, '').replace(/[^\d.]/g, '');

  if (decimals === 0) {
    // Whole dinars only: ignore anything after a decimal point.
    s = s.split('.')[0];
  } else {
    const firstDot = s.indexOf('.');
    if (firstDot !== -1) {
      const intPart = s.slice(0, firstDot);
      const fracPart = s.slice(firstDot + 1).replace(/\./g, '').slice(0, decimals);
      s = `${intPart || '0'}.${fracPart}`;
    }
  }

  // Drop leading zeros ("007" -> "7") but keep "0" and "0.x".
  s = s.replace(/^0+(?=\d)/, '');
  // Hard cap on length to keep values sane.
  const [i, f] = s.split('.');
  const capped = i.slice(0, 12);
  return f !== undefined ? `${capped}.${f}` : capped;
}

/** Format a raw numeric string for display while typing: "1528800.5" -> "1,528,800.5". */
export function formatRawInput(raw) {
  if (!raw) return '';
  const [i, f] = raw.split('.');
  const intFormatted = (i || '0').replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return f !== undefined ? `${intFormatted}.${f}` : intFormatted;
}

export function toNumber(raw) {
  if (raw === '' || raw == null) return 0;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

const intFmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const decFmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });

/** Whole-dinar formatting with thousands separators: 1528800 -> "1,528,800". */
export function formatIQD(value) {
  return intFmt.format(Math.round(value || 0));
}

/** Up to 2 decimals, used for weights and intermediate per-gram values. */
export function formatDecimal(value) {
  return decFmt.format(value || 0);
}

/**
 * The three-step calculation.
 *
 * 1. gramPrice      = mithqalPrice / 5
 * 2. finalGramPrice = gramPrice + making charge per gram
 *    (a fixed piece charge is spread over the weight: charge / weight)
 * 3. finalPrice     = finalGramPrice * weight
 */
export function calculateGold({ mithqalPrice, weight, making, makingType }) {
  const m = Math.max(0, Number(mithqalPrice) || 0);
  const w = Math.max(0, Number(weight) || 0);
  const c = Math.max(0, Number(making) || 0);
  const isFixed = makingType === MAKING_TYPES.FIXED;

  const gramPrice = m / GRAMS_PER_MITHQAL;
  const makingPerGram = isFixed ? (w > 0 ? c / w : 0) : c;
  const finalGramPrice = gramPrice + makingPerGram;

  const goldValue = gramPrice * w;
  const totalMaking = isFixed ? (w > 0 ? c : 0) : c * w;
  // Sum the parts (rather than finalGramPrice * w) to avoid float drift,
  // then round to whole dinars.
  const finalPrice = Math.round(goldValue + totalMaking);

  return {
    gramPrice,
    makingPerGram,
    finalGramPrice,
    goldValue,
    totalMaking,
    finalPrice,
    ready: m > 0 && w > 0,
  };
}
