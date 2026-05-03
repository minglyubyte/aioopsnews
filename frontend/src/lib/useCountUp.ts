import { useEffect, useRef, useState } from "react";

/**
 * Animates a numeric string from 0 to `target` using requestAnimationFrame.
 * Returns the formatted display string. Non-numeric values (dates, text with
 * letters) are returned as-is without animation.
 *
 * @param target  The final value string (e.g. "42", "Nov 3, 2024")
 * @param active  When true, the animation starts. Tie this to `inView`.
 * @param duration Animation duration in ms (default 900)
 */
export function useCountUp(
  target: string,
  active: boolean,
  duration = 900,
): string {
  // Only animate purely numeric targets
  const numericValue = parseFloat(target.replace(/,/g, ""));
  const isNumeric = !isNaN(numericValue) && /^\d[\d,]*$/.test(target.trim());

  const [display, setDisplay] = useState(isNumeric ? "0" : target);
  const rafRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isNumeric || !active) return;

    // Reset if target changes while already animating
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
    }
    startTimeRef.current = null;

    function tick(timestamp: number) {
      if (startTimeRef.current === null) {
        startTimeRef.current = timestamp;
      }

      const elapsed = timestamp - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(eased * numericValue);

      setDisplay(String(current));

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    }

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [active, isNumeric, numericValue, duration, target]);

  // For non-numeric, just return the target once active
  if (!isNumeric) return target;
  return display;
}
