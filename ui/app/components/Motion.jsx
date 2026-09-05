"use client";

import { useEffect, useRef, useState } from "react";

/* Scroll-linked progress bar at the very top of the page. */
export function ScrollProgress() {
  const ref = useRef(null);

  useEffect(() => {
    let frame = 0;
    function onScroll() {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const doc = document.documentElement;
        const max = doc.scrollHeight - doc.clientHeight;
        const pct = max > 0 ? (doc.scrollTop / max) * 100 : 0;
        if (ref.current) ref.current.style.setProperty("--p", pct.toFixed(2) + "%");
      });
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div className="scroll-progress" aria-hidden="true">
      <i ref={ref} />
    </div>
  );
}

/* Adds .stuck to the nav once the page is scrolled. */
export function useStuck(threshold = 8) {
  const [stuck, setStuck] = useState(false);
  useEffect(() => {
    function onScroll() {
      setStuck(window.scrollY > threshold);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [threshold]);
  return stuck;
}

/* Reveals children on scroll via IntersectionObserver. Honors
   prefers-reduced-motion by revealing immediately. */
export function Reveal({ children, className = "", delay = 0, variant = "" }) {
  const ref = useRef(null);
  const [seen, setSeen] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setSeen(true);
      return;
    }
    if (!("IntersectionObserver" in window)) {
      setSeen(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            setSeen(true);
            io.unobserve(e.target);
          }
        });
      },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.12 }
    );
    io.observe(node);
    return () => io.disconnect();
  }, []);

  const cls = ["reveal", variant, seen ? "in" : "", className].filter(Boolean).join(" ");
  return (
    <div ref={ref} className={cls} style={{ "--rd": delay + "ms" }}>
      {children}
    </div>
  );
}
