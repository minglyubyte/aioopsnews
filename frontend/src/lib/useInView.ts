import { useCallback, useRef, useState } from "react";

/**
 * Callback-ref hook that flips `inView` to `true` the first time the element
 * enters (or is already within) the viewport. Stays `true` forever (one-shot).
 *
 * Key behaviour:
 * - If the element is ALREADY visible when it mounts (e.g. above-the-fold
 *   content, or a list that renders after data loads), `inView` is set
 *   synchronously on mount — no waiting for the async IntersectionObserver.
 * - If the element is BELOW the fold, the IntersectionObserver watches for
 *   it and fires when it scrolls into view.
 *
 * Usage:  const [ref, inView] = useInView<HTMLDivElement>();
 *         <div ref={ref} data-inview={inView ? "true" : "false"} />
 */
export function useInView<T extends Element>(
  rootMargin = "0px 0px -40px 0px",
): [(node: T | null) => void, boolean] {
  const [inView, setInView] = useState(false);
  const observerRef = useRef<IntersectionObserver | null>(null);

  const refCallback = useCallback(
    (node: T | null) => {
      // Tear down previous observer whenever the ref changes
      if (observerRef.current) {
        observerRef.current.disconnect();
        observerRef.current = null;
      }

      if (!node) return;

      // ── Fast path: element already in viewport ────────────────────
      // getBoundingClientRect is synchronous; if any part of the element
      // is within the visible area right now, reveal it immediately instead
      // of waiting for the async IntersectionObserver callback.
      const rect = node.getBoundingClientRect();
      const alreadyVisible =
        rect.bottom > 0 &&
        rect.right > 0 &&
        rect.top < window.innerHeight &&
        rect.left < window.innerWidth;

      if (alreadyVisible) {
        setInView(true);
        return; // No observer needed
      }

      // ── Slow path: observe until scrolled into view ───────────────
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            setInView(true);
            observer.disconnect();
            observerRef.current = null;
          }
        },
        { threshold: 0, rootMargin },
      );

      observer.observe(node);
      observerRef.current = observer;
    },
    [rootMargin],
  );

  return [refCallback, inView];
}
