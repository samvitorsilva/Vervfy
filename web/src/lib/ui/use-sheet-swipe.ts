"use client";

import { useEffect, useRef, type PointerEvent } from "react";

/** Drag from a sheet's header only; scrolling and form controls keep their gestures. */
export function useSheetSwipe(onDismiss: () => void, selector: string) {
  const drag = useRef<{ id: number; startX: number; startY: number; time: number; distance: number; element: HTMLElement } | null>(null);
  const animation = useRef<Animation | null>(null);
  useEffect(() => () => { animation.current?.cancel(); }, []);
  const settle = (cancelled: boolean) => {
    const current = drag.current;
    if (!current) return;
    drag.current = null;
    const velocity = current.distance / Math.max(1, performance.now() - current.time);
    const dismiss = !cancelled && (current.distance > 100 || (current.distance > 35 && velocity > .6));
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    animation.current?.cancel();
    if (dismiss) {
      if (reduced) {
        current.element.style.translate = "";
        onDismiss();
        return;
      }
      const exit = current.element.animate(
        [{ translate: `0 ${current.distance}px` }, { translate: `0 ${window.innerHeight}px` }],
        { duration: 120, easing: "cubic-bezier(.7,0,.84,0)", fill: "forwards" },
      );
      animation.current = exit;
      exit.onfinish = () => {
        current.element.style.translate = "";
        onDismiss();
        exit.cancel();
        animation.current = null;
      };
    } else {
      animation.current = current.element.animate([{ translate: `0 ${current.distance}px` }, { translate: "0 0" }], { duration: reduced ? 0 : 220, easing: "cubic-bezier(.2,.8,.2,1)" });
      current.element.style.translate = "";
    }
  };
  return {
    onPointerDown(event: PointerEvent<HTMLElement>) {
      if (event.pointerType === "mouse" || !event.isPrimary || !window.matchMedia("(max-width: 768px)").matches) return;
      if ((event.target as HTMLElement).closest("button, input, a, select, textarea")) return;
      const element = event.currentTarget.closest<HTMLElement>(selector);
      if (!element) return;
      const offset = Number.parseFloat(getComputedStyle(element).translate.split(" ")[1] ?? "0") || 0;
      animation.current?.cancel();
      element.style.translate = `0 ${offset}px`;
      const rawOffset = offset < 0 ? offset * 48 / (.55 * (48 + offset)) : offset;
      drag.current = { id: event.pointerId, startX: event.clientX, startY: event.clientY - rawOffset, time: performance.now(), distance: offset, element };
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    onPointerMove(event: PointerEvent<HTMLElement>) {
      const current = drag.current;
      if (!current || event.pointerId !== current.id) return;
      if (Math.abs(event.clientX - current.startX) > Math.abs(event.clientY - current.startY) + 20) { settle(true); return; }
      const distance = event.clientY - current.startY;
      // Upward motion resists at the top edge, with a maximum 48px stretch.
      current.distance = distance < 0 ? -(1 - 1 / (-distance * .55 / 48 + 1)) * 48 : distance;
      current.element.style.translate = `0 ${current.distance}px`;
    },
    onPointerUp() { settle(false); },
    onPointerCancel() { settle(true); },
    onLostPointerCapture() { settle(true); },
  };
}
