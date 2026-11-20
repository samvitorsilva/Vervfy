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
  return <dialog {...props} ref={ref} onCancel={(event) => { event.preventDefault(); event.stopPropagation(); onDismiss(); }} onKeyDown={(event) => { props.onKeyDown?.(event); event.stopPropagation(); }}>{children}</dialog>;
}
