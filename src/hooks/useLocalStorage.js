import { useEffect, useState } from 'react';

/**
 * useState that persists to localStorage. Storage failures (private mode etc.) are ignored.
 * `firstVisitValue` is used instead of `initialValue` when nothing has been stored yet.
 */
export function useLocalStorage(key, initialValue, firstVisitValue = initialValue) {
  const [value, setValue] = useState(() => {
    try {
      const stored = localStorage.getItem(key);
      return stored != null ? { ...initialValue, ...JSON.parse(stored) } : firstVisitValue;
    } catch {
      return firstVisitValue;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* storage unavailable */
    }
  }, [key, value]);

  return [value, setValue];
}
