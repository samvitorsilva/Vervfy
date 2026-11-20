"use client";

import { useEffect, useRef, useState } from "react";
import Modal from "@/components/modal";
import { useLanguage } from "@/lib/i18n";

export interface MonthlyRecord {
  monthStart: number;
  playCount: number;
  previousRecordCount: number;
}

export default function MonthlyRecordPopup({ accountId, record, onViewRecap }: {
  accountId: string;
  record: MonthlyRecord;
  onViewRecap: () => void;
}) {
  const { t, language } = useLanguage();
  const [open, setOpen] = useState(false);
  const shown = useRef(false);
  const key = `vervfy:monthly-record:${accountId}:${record.monthStart}`;
  useEffect(() => {
    const showWhenReady = () => {
      if (shown.current || document.hidden) return;
      try { if (localStorage.getItem(key)) return; } catch { /* Session-only deduplication when storage is unavailable. */ }
      if ([...document.querySelectorAll('dialog[open], [role="dialog"][aria-modal="true"]')].some((element) => element.getClientRects().length > 0)) return;
      if (document.activeElement?.closest('input, textarea, select, [contenteditable="true"]')) return;
      shown.current = true;
      try { localStorage.setItem(key, "shown"); } catch { /* Keep the in-memory guard. */ }
      setOpen(true);
    };
    const initial = window.setTimeout(showWhenReady, 2000);
    const interval = window.setInterval(showWhenReady, 5000);
    return () => { window.clearTimeout(initial); window.clearInterval(interval); };
  }, [key]);
  const month = new Intl.DateTimeFormat(language, { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(record.monthStart * 1000));
  const number = new Intl.NumberFormat(language);
  return <Modal open={open} onDismiss={() => setOpen(false)} className={`queue-picker-overlay monthly-record-overlay${open ? " open" : ""}`} aria-labelledby="monthly-record-title" aria-describedby="monthly-record-copy">
    <section className="queue-picker-card monthly-record-card">
      <header className="queue-picker-head"><span className="monthly-record-eyebrow">{t("Your month in music")}</span><button className="icon-btn" type="button" aria-label={t("Close")} onClick={() => setOpen(false)}>×</button></header>
      <div className="monthly-record-content">
        <span className="monthly-record-symbol" aria-hidden="true">↗</span>
        <p className="monthly-record-month">{month}</p>
        <h2 id="monthly-record-title">{t("A new listening record")}</h2>
        <p className="monthly-record-count">{number.format(record.playCount)} <span>{t("plays")}</span></p>
        <p id="monthly-record-copy">{t("You beat your previous monthly best of {count} plays.").replace("{count}", number.format(record.previousRecordCount))}</p>
        <div className="monthly-record-actions"><button className="btn btn-primary" type="button" onClick={() => { setOpen(false); onViewRecap(); }}>{t("View recap")}</button><button className="btn" type="button" onClick={() => setOpen(false)}>{t("Keep listening")}</button></div>
      </div>
    </section>
  </Modal>;
}
