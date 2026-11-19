import { flushSync } from "react-dom";

let activeTransition: ViewTransition | null = null;

export function changeView(update: () => void) {
  if (typeof document === "undefined" || !document.startViewTransition || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    update();
    return;
  }
  activeTransition?.skipTransition();
  activeTransition = document.startViewTransition(() => { flushSync(update); });
  // Rapid navigation intentionally interrupts the previous animation.
  void activeTransition.ready.catch(() => undefined);
  void activeTransition.finished.catch(() => undefined);
}
