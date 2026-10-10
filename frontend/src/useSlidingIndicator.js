import { useLayoutEffect, useState } from "react";

export function useSlidingIndicator(activeKey, containerRef, activeSelector = ".on") {
  const [style, setStyle] = useState({
    transform: "translateX(0px)",
    width: 0,
    height: 0,
    top: 0,
    opacity: 0,
  });

  useLayoutEffect(() => {
    function update() {
      if (!containerRef.current) return;
      const activeEl = containerRef.current.querySelector(activeSelector);
      if (activeEl) {
        setStyle({
          transform: `translateX(${activeEl.offsetLeft}px)`,
          width: `${activeEl.offsetWidth}px`,
          height: `${activeEl.offsetHeight}px`,
          top: `${activeEl.offsetTop}px`,
          opacity: 1,
        });
      }
    }

    update();
    const raf = requestAnimationFrame(update);
    window.addEventListener("resize", update);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", update);
    };
  }, [activeKey, containerRef, activeSelector]);

  return style;
}
