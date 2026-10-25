import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Banknote,
  CheckCircle2,
  Gem,
  Info,
  Moon,
  Scale,
  Sparkles,
  Sun,
  Wand2,
  Weight,
  Zap,
} from 'lucide-react';

import NumberField from './components/NumberField.jsx';
import Segmented from './components/Segmented.jsx';
import StepCard from './components/StepCard.jsx';
import Equation from './components/Equation.jsx';
import ResultsPanel from './components/ResultsPanel.jsx';
import MobileTotalBar from './components/MobileTotalBar.jsx';
import { useLocalStorage } from './hooks/useLocalStorage.js';
import { useTheme } from './hooks/useTheme.js';
import {
  GRAMS_PER_MITHQAL,
  KARATS,
  MAKING_TYPES,
  calculateGold,
  formatDecimal,
  formatIQD,
  toNumber,
} from './lib/gold.js';

const DEFAULTS = {
  mithqal: '',
  weight: '',
  making: '',
  makingType: MAKING_TYPES.PER_GRAM,
  karat: 21,
};

const EXAMPLE = {
  mithqal: '980000',
  weight: '7.35',
  making: '12000',
  makingType: MAKING_TYPES.PER_GRAM,
  karat: 21,
};

export default function App() {
  const { theme, toggle } = useTheme();
  const [inputs, setInputs] = useLocalStorage('gold-calc:inputs', DEFAULTS, EXAMPLE);
  const [focusedStep, setFocusedStep] = useState(null);
  const [toast, setToast] = useState(null);
  const [resultsVisible, setResultsVisible] = useState(true);
  const resultsRef = useRef(null);

  const set = (key) => (value) => setInputs((s) => ({ ...s, [key]: value }));
  const isFixed = inputs.makingType === MAKING_TYPES.FIXED;

  const mithqal = toNumber(inputs.mithqal);
  const weight = toNumber(inputs.weight);
  const making = toNumber(inputs.making);

  const result = useMemo(
    () => calculateGold({ mithqalPrice: mithqal, weight, making, makingType: inputs.makingType }),
    [mithqal, weight, making, inputs.makingType],
  );

  // Step progress
  const step1Done = mithqal > 0;
  const step2Done = step1Done && inputs.making !== '';
  const step3Done = result.ready;
  const autoActive = !step1Done ? 1 : !step2Done ? 2 : !step3Done ? 3 : null;
  const activeStep = focusedStep ?? autoActive;

  // Validation messages (sanitizing already blocks negatives and letters)
  const mithqalError = inputs.mithqal !== '' && mithqal === 0 ? 'سعر المثقال يجب أن يكون أكبر من صفر' : null;
  const weightError = inputs.weight !== '' && weight === 0 ? 'الوزن يجب أن يكون أكبر من صفر' : null;

  const showToast = useCallback((message) => {
    setToast({ message, id: Date.now() });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2400);
    return () => clearTimeout(t);
  }, [toast]);

  // Show the floating total on mobile while the results card is out of view.
  useEffect(() => {
    const el = resultsRef.current;
    if (!el || !('IntersectionObserver' in window)) return;
    const io = new IntersectionObserver(([entry]) => setResultsVisible(entry.isIntersecting), { threshold: 0.15 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const summaryText = () => {
    const makingLine = isFixed
      ? `أجور الصياغة: ${formatIQD(making)} د.ع (مبلغ ثابت للقطعة)`
      : `أجور الصياغة: ${formatIQD(making)} د.ع لكل غرام`;
    return [
      '✨ حاسبة الذهب',
      `العيار: ${inputs.karat}`,
      `سعر المثقال: ${formatIQD(mithqal)} د.ع`,
      `الوزن: ${formatDecimal(weight)} غرام`,
      makingLine,
      '—————',
      `سعر الغرام بدون صياغة: ${formatIQD(result.gramPrice)} د.ع`,
      `أجور الصياغة الإجمالية: ${formatIQD(result.totalMaking)} د.ع`,
      `قيمة الذهب بدون صياغة: ${formatIQD(result.goldValue)} د.ع`,
      `السعر النهائي: ${formatIQD(result.finalPrice)} دينار عراقي`,
      '',
      `* المثقال = ${GRAMS_PER_MITHQAL} غرامات، والأسعار مُدخلة يدوياً.`,
    ].join('\n');
  };

  const handleCopy = async () => {
    const text = summaryText();
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
    }
    showToast('تم نسخ نتيجة الحساب');
  };

  const shareUrl = `https://wa.me/?text=${encodeURIComponent(summaryText())}`;

  const handleReset = () => {
    setInputs(DEFAULTS);
    setFocusedStep(null);
    showToast('تمت إعادة تعيين الحاسبة');
  };

  const handleExample = () => {
    setInputs(EXAMPLE);
    showToast('تم تعبئة مثال للتجربة');
  };

  const scrollToResults = () => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });

  const focusProps = (step) => ({
    onFocus: () => setFocusedStep(step),
    onBlur: () => setFocusedStep(null),
  });

  const isExample = Object.keys(EXAMPLE).every((k) => inputs[k] === EXAMPLE[k]);

  const fmt = (v, ok) => (ok ? formatIQD(v) : '—');
  const karatInfo = KARATS.find((k) => k.value === inputs.karat) ?? KARATS[2];

  return (
    <div className="relative min-h-dvh overflow-x-clip">
      <Backdrop />

      <div className="relative mx-auto max-w-6xl px-4 pb-32 sm:px-6 lg:pb-16">
        {/* Header */}
        <header className="flex items-center justify-between py-5">
          <div className="flex items-center gap-2.5">
            <span className="gold-fill grid size-10 place-items-center rounded-2xl text-ink-900 shadow-[0_8px_20px_-10px_rgba(122,92,34,0.9)]">
              <Gem className="size-5" strokeWidth={2} />
            </span>
            <div className="leading-tight">
              <p className="font-display text-sm font-bold text-ink-900 dark:text-ivory-50">ذهب العراق</p>
              <p className="text-[11px] text-ink-400 dark:text-ink-300">حاسبة الأسعار والمصنعية</p>
            </div>
          </div>
          <button
            type="button"
            onClick={toggle}
            aria-label={theme === 'dark' ? 'تفعيل الوضع النهاري' : 'تفعيل الوضع الليلي'}
            className="btn size-11 border border-gold-200/70 bg-white/70 p-0 text-gold-700 hover:bg-white dark:border-gold-700/40 dark:bg-ink-900/70 dark:text-gold-300"
          >
            {theme === 'dark' ? <Sun className="size-5" /> : <Moon className="size-5" />}
          </button>
        </header>

        {/* Hero */}
        <section className="animate-fade-up pb-8 pt-4 text-center sm:pb-12 sm:pt-8">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-gold-300/60 bg-white/70 px-3.5 py-1.5 text-xs font-semibold text-gold-700 dark:border-gold-700/40 dark:bg-ink-900/60 dark:text-gold-300">
            <Sparkles className="size-3.5" />
            بالدينار العراقي
          </span>
          <h1 className="gold-text mt-4 font-display text-5xl font-extrabold leading-tight sm:text-6xl">
            حاسبة الذهب
          </h1>
          <p className="mx-auto mt-3 max-w-md text-base leading-relaxed text-ink-500 dark:text-ink-300 sm:text-lg">
            احسب سعر الذهب وأجور الصياغة بثلاث خطوات بسيطة.
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2 text-xs">
            <Chip icon={Scale}>
              المثقال = <span className="num">{GRAMS_PER_MITHQAL}</span> غرامات
            </Chip>
            <Chip icon={Zap}>حساب تلقائي فوري</Chip>
            <Chip icon={Info}>أسعار تُدخلها أنت</Chip>
          </div>
          {isExample ? (
            <p className="mt-5 inline-flex items-center gap-1.5 rounded-full bg-gold-100/80 px-3.5 py-1.5 text-sm font-medium text-gold-800 dark:bg-gold-700/20 dark:text-gold-200">
              <Wand2 className="size-4" />
              هذه قيم تجريبية، غيّرها بأسعارك
            </p>
          ) : (
            <button
              type="button"
              onClick={handleExample}
              className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-gold-700 underline-offset-4 hover:underline dark:text-gold-300"
            >
              <Wand2 className="size-4" />
              جرّب مثالاً جاهزاً
            </button>
          )}
        </section>

        <main className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_400px] lg:items-start lg:gap-8">
          {/* The three steps */}
          <div className="space-y-5 sm:space-y-6">
            <StepCard
              index={1}
              title="سعر الغرام"
              subtitle="نقسم سعر المثقال على 5 لنحصل على سعر الغرام الواحد."
              done={step1Done}
              active={activeStep === 1}
              delay={80}
            >
              <Segmented
                label="العيار"
                value={inputs.karat}
                onChange={set('karat')}
                options={KARATS.map((k) => ({ value: k.value, label: k.label.replace('عيار ', ''), sub: k.purity }))}
              />
              <NumberField
                label={`سعر المثقال لعيار ${inputs.karat}`}
                value={inputs.mithqal}
                onChange={set('mithqal')}
                icon={Banknote}
                suffix="د.ع"
                placeholder="مثال: 980,000"
                hint={`أدخل سعر المثقال الخاص بعيار ${inputs.karat} (نقاوة ${karatInfo.purity}) كما هو في السوق اليوم.`}
                error={mithqalError}
                {...focusProps(1)}
              />
              <Equation
                muted={!step1Done}
                terms={[
                  { value: fmt(mithqal, step1Done), caption: 'سعر المثقال' },
                  { op: '÷', value: String(GRAMS_PER_MITHQAL), caption: 'غرامات' },
                  { op: '=', value: fmt(result.gramPrice, step1Done), caption: 'سعر الغرام', highlight: step1Done },
                ]}
              />
            </StepCard>

            <StepCard
              index={2}
              title="إضافة أجور الصياغة"
              subtitle="نضيف المصنعية إلى سعر الغرام لنحصل على سعر الغرام النهائي."
              done={step2Done}
              active={activeStep === 2}
              delay={160}
            >
              <Segmented
                label="نوع المصنعية"
                value={inputs.makingType}
                onChange={set('makingType')}
                options={[
                  { value: MAKING_TYPES.PER_GRAM, label: 'لكل غرام' },
                  { value: MAKING_TYPES.FIXED, label: 'مبلغ ثابت للقطعة' },
                ]}
              />
              <NumberField
                label={isFixed ? 'مبلغ المصنعية للقطعة كاملة' : 'أجور الصياغة لكل غرام'}
                value={inputs.making}
                onChange={set('making')}
                icon={Sparkles}
                suffix="د.ع"
                placeholder={isFixed ? 'مثال: 50,000' : 'مثال: 12,000'}
                hint={
                  isFixed
                    ? 'يُوزَّع المبلغ الثابت على وزن القطعة لمعرفة نصيب الغرام منه.'
                    : 'اترك الحقل صفراً إذا كانت القطعة بدون مصنعية.'
                }
                {...focusProps(2)}
              />
              <Equation
                muted={!step2Done}
                terms={[
                  { value: fmt(result.gramPrice, step1Done), caption: 'سعر الغرام' },
                  isFixed
                    ? {
                        op: '+',
                        value: fmt(result.makingPerGram, step2Done && weight > 0),
                        caption: weight > 0 ? `${formatIQD(making)} ÷ ${formatDecimal(weight)} غ` : 'المصنعية ÷ الوزن',
                      }
                    : { op: '+', value: fmt(making, step2Done), caption: 'مصنعية الغرام' },
                  {
                    op: '=',
                    value: fmt(result.finalGramPrice, step2Done && (!isFixed || weight > 0)),
                    caption: 'سعر الغرام النهائي',
                    highlight: step2Done && (!isFixed || weight > 0),
                  },
                ]}
              />
            </StepCard>

            <StepCard
              index={3}
              title="السعر النهائي"
              subtitle="نضرب سعر الغرام النهائي في وزن القطعة."
              done={step3Done}
              active={activeStep === 3}
              isLast
              delay={240}
            >
              <NumberField
                label="وزن القطعة"
                value={inputs.weight}
                onChange={set('weight')}
                icon={Weight}
                suffix="غرام"
                decimals={3}
                placeholder="مثال: 7.35"
                hint={
                  weight > 0
                    ? `تعادل ${formatDecimal(weight / GRAMS_PER_MITHQAL)} مثقال تقريباً. يدعم الأرقام العشرية.`
                    : 'يدعم الأرقام العشرية مثل 5.62'
                }
                error={weightError}
                {...focusProps(3)}
              />
              <Equation
                muted={!step3Done}
                terms={[
                  { value: fmt(result.finalGramPrice, step3Done), caption: 'سعر الغرام النهائي' },
                  { op: '×', value: weight > 0 ? formatDecimal(weight) : '—', caption: 'الوزن (غرام)' },
                  { op: '=', value: fmt(result.finalPrice, step3Done), caption: 'السعر النهائي (د.ع)', highlight: step3Done },
                ]}
              />
              {step3Done && (
                <p className="flex animate-fade-up items-center gap-2 text-sm font-medium text-emerald-700 dark:text-emerald-400">
                  <CheckCircle2 className="size-4.5" />
                  اكتمل الحساب — السعر النهائي{' '}
                  <span className="num font-display font-bold">{formatIQD(result.finalPrice)}</span> د.ع
                </p>
              )}
            </StepCard>
          </div>

          {/* Results */}
          <div className="space-y-5 lg:sticky lg:top-6">
            <ResultsPanel
              ref={resultsRef}
              result={result}
              karat={inputs.karat}
              onCopy={handleCopy}
              shareUrl={shareUrl}
              onReset={handleReset}
            />
            <Disclaimer />
          </div>
        </main>

        <footer className="mt-14 text-center text-xs text-ink-400 dark:text-ink-500">
          حاسبة الذهب — أداة حساب استرشادية. تُحفظ آخر القيم على جهازك فقط.
        </footer>
      </div>

      <MobileTotalBar visible={!resultsVisible} result={result} onClick={scrollToResults} />

      {toast && (
        <div
          key={toast.id}
          role="status"
          className="animate-toast fixed bottom-24 left-1/2 z-40 flex items-center gap-2 rounded-full bg-ink-900 px-5 py-3 text-sm font-medium text-ivory-100 shadow-xl dark:bg-ivory-100 dark:text-ink-900 lg:bottom-8"
        >
          <CheckCircle2 className="size-4.5 text-gold-400 dark:text-gold-600" />
          {toast.message}
        </div>
      )}
    </div>
  );
}

function Chip({ icon: Icon, children }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-white/70 px-3 py-1.5 text-ink-500 ring-1 ring-ivory-300 dark:bg-ink-900/60 dark:text-ink-300 dark:ring-ink-700">
      <Icon className="size-3.5 text-gold-500" />
      {children}
    </span>
  );
}

function Disclaimer() {
  return (
    <div className="rounded-3xl border border-gold-200/60 bg-gold-100/30 p-5 text-sm leading-relaxed text-ink-500 dark:border-gold-700/25 dark:bg-gold-700/5 dark:text-ink-300">
      <p className="mb-2 flex items-center gap-2 font-semibold text-ink-800 dark:text-ivory-100">
        <Info className="size-4 text-gold-600 dark:text-gold-400" />
        ملاحظات مهمة
      </p>
      <ul className="list-disc space-y-1.5 ps-5 marker:text-gold-400">
        <li>الأسعار تُدخل يدوياً من قبلك، وليست أسعاراً مباشرة من السوق.</li>
        <li>
          تعتمد الحاسبة المثقال العراقي = <span className="num">{GRAMS_PER_MITHQAL}</span> غرامات.
        </li>
        <li>أدخل سعر المثقال الخاص بالعيار المختار؛ الحاسبة لا تحوّل بين العيارات.</li>
        <li>النتائج مقرّبة لأقرب دينار، وقد تختلف قليلاً عن فاتورة المحل.</li>
      </ul>
    </div>
  );
}

function Backdrop() {
  // Static, absolutely positioned (scrolls with the page) and filter-free so it stays cheap on phones.
  return (
    <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-[720px] overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_60%_at_50%_0%,rgba(226,196,122,0.35),transparent_70%)] dark:bg-[radial-gradient(ellipse_70%_60%_at_50%_0%,rgba(122,92,34,0.28),transparent_70%)]" />
      <div className="absolute inset-0 bg-[repeating-linear-gradient(45deg,rgba(209,171,88,0.12)_0_1px,transparent_1px_32px),repeating-linear-gradient(-45deg,rgba(209,171,88,0.12)_0_1px,transparent_1px_32px)] [mask-image:radial-gradient(ellipse_60%_70%_at_50%_0%,#000,transparent)] dark:opacity-50" />
    </div>
  );
}
