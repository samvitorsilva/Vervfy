"use client";

import { useLayoutEffect, useRef, type ComponentProps } from "react";

/** Native modal containment, background inertness, Escape and focus restoration. */
export default function Modal({ open, onDismiss, children, ...props }: Omit<ComponentProps<"dialog">, "open"> & { open: boolean; onDismiss: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useLayoutEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open) return;
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialog.showModal();
    dialog.querySelector<HTMLElement>("[autofocus], input:not([disabled]), textarea:not([disabled])")?.focus();
    return () => {
      dialog.close();
      if (trigger?.isConnected) trigger.focus();
    };
  }, [open]);
  return <dialog {...props} ref={ref} onCancel={(event) => { event.preventDefault(); event.stopPropagation(); onDismiss(); }} onKeyDown={(event) => {
    props.onKeyDown?.(event);
    if (event.key === "Tab") {
      const dialog = ref.current;
      const focusable = dialog
        ? [
            ...dialog.querySelectorAll<HTMLElement>(
              'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
            ),
          ].filter(
            (element) =>
              element.getClientRects().length > 0 &&
              element.getAttribute("aria-hidden") !== "true",
          )
        : [];
      const first = focusable[0];
      const last = focusable.at(-1);
      const active = document.activeElement;
      if (!first) {
        event.preventDefault();
        dialog?.focus();
      } else if (event.shiftKey && (active === first || active === dialog)) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && (active === last || active === dialog)) {
        event.preventDefault();
        first.focus();
      }
    }
    event.stopPropagation();
  }}>{children}</dialog>;
}
