"use client";

// Adapted from Password Strength by Özer (@ddoemonn) on 21st.dev:
// https://21st.dev/community/components/ddoemonn/password-strength/default
// Original component attribution and estimator notices: /third-party-notices.txt.

import { useEffect, useMemo, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { ZxcvbnFactory } from "@zxcvbn-ts/core";
import { adjacencyGraphs, dictionary } from "@zxcvbn-ts/language-common";
import { useLanguage } from "@/lib/i18n";

const CELL = { type: "spring", stiffness: 520, damping: 34, mass: 0.45 } as const;
const CROSSFADE = { type: "spring", stiffness: 260, damping: 34, mass: 0.8 } as const;
const INSTANT = { duration: 0 } as const;
// Local, bounded estimation only; no remote dictionaries or password telemetry.
// Common data keeps the bundle smaller than including per-language dictionaries.
// Attribution: /third-party-notices.txt.
const estimator = new ZxcvbnFactory({ dictionary, graphs: adjacencyGraphs, maxLength: 72 });
const SYMBOL = /[!-/:-@[-`{-~]/;

export type PasswordRule = { id: string; label: string; test: (value: string) => boolean };
export type EvaluatedRule = PasswordRule & { met: boolean };
export type UsePasswordStrengthOptions = {
  rules?: readonly PasswordRule[];
  labels?: readonly string[];
  announceDelay?: number;
};
export type PasswordStrengthState = {
  score: number;
  max: number;
  label: string;
  rules: EvaluatedRule[];
  guessable: boolean;
  announcement: string;
};
export const defaultPasswordRules: readonly PasswordRule[] = [
  { id: "length", label: "8 characters or more", test: (v) => Array.from(v).length >= 8 },
  { id: "case", label: "Upper and lower case", test: (v) => /[a-z]/.test(v) && /[A-Z]/.test(v) },
  { id: "digit", label: "A number", test: (v) => /\d/.test(v) },
  { id: "symbol", label: "A symbol", test: (v) => SYMBOL.test(v) },
];
const defaultLabels = ["Empty", "Weak", "Fair", "Good", "Strong"] as const;

export function usePasswordStrength(
  value: string,
  { rules = defaultPasswordRules, labels = defaultLabels, announceDelay = 700 }: UsePasswordStrengthOptions = {},
): PasswordStrengthState {
  const { t } = useLanguage();
  const estimate = useMemo(() => value === "" ? null : estimator.check(value).score, [value]);
  const state = useMemo(() => {
    const evaluated = rules.map((rule) => ({ ...rule, label: t(rule.label), met: rule.test(value) }));
    const guessable = estimate !== null && estimate <= 1;
    // Reserve zero/Empty for an empty input; requirements do not determine strength.
    const score = estimate === null ? 0 : Math.max(1, estimate);
    const label = t(labels[Math.min(score, labels.length - 1)] ?? "");
    const unmet = evaluated.filter((r) => !r.met);
    const announcement = value.length === 0 ? "" : [
      t("Password strength {label}.").replace("{label}", label.toLowerCase()),
      guessable ? t("This is a commonly guessed pattern.") : "",
      unmet.length === 0 ? t("All requirements met.") : t("Still needed: {rules}.").replace("{rules}", unmet.map((r) => r.label.toLowerCase()).join(", ")),
    ].filter(Boolean).join(" ");
    return { score, max: 4, label, rules: evaluated, guessable, announcement };
  }, [value, estimate, rules, labels, t]);
  const [settled, setSettled] = useState<typeof state | null>(null);
  useEffect(() => {
    const id = setTimeout(() => setSettled(state), announceDelay);
    return () => clearTimeout(id);
  }, [state, announceDelay]);
  // Invalidate immediately, including edits with identical feedback and language changes.
  return { ...state, announcement: settled === state ? state.announcement : "" };
}

export type PasswordStrengthProps = {
  value: string;
  rules?: readonly PasswordRule[];
  labels?: readonly string[];
  announceDelay?: number;
  showRules?: boolean;
  className?: string;
};
const TONES = {
  none: { bar: "bg-[var(--strength-empty-bar,var(--text-dim))]", text: "text-[var(--strength-empty-text,var(--text-dim))]" },
  danger: { bar: "bg-[var(--strength-danger-bar,var(--danger))]", text: "text-[var(--strength-danger-text,var(--danger))]" },
  caution: { bar: "bg-[var(--strength-caution-bar,var(--text-mid))]", text: "text-[var(--strength-caution-text,var(--text-mid))]" },
  safe: { bar: "bg-[var(--strength-safe-bar,var(--accent))]", text: "text-[var(--strength-safe-text,var(--accent))]" },
} as const;
function toneFor(score: number, max: number) {
  if (score === 0) return TONES.none;
  const ratio = score / max;
  if (ratio <= 0.34) return TONES.danger;
  if (ratio <= 0.67) return TONES.caution;
  return TONES.safe;
}
export function PasswordStrength({ value, rules = defaultPasswordRules, labels = defaultLabels, announceDelay = 700, showRules = true, className = "" }: PasswordStrengthProps) {
  const { score, max, label, rules: evaluated, guessable, announcement } = usePasswordStrength(value, { rules, labels, announceDelay });
  const { t } = useLanguage();
  const reduced = useReducedMotion();
  const tone = toneFor(score, max);
  return (
    <div className={`w-full ${className}`}>
      <div role="meter" aria-label={t("Password strength")} aria-valuemin={0} aria-valuemax={max} aria-valuenow={score} aria-valuetext={label} className="password-strength-meter" style={{ gridTemplateColumns: `repeat(${max}, minmax(0, 1fr))` }}>
        {Array.from({ length: max }, (_, i) => (
          <div key={i} className="relative h-1.5 overflow-hidden rounded-[2px] bg-[var(--strength-track,var(--surface-control))]">
            <motion.span className={`absolute inset-0 origin-left rounded-[2px] transition-colors duration-200 ${tone.bar}`} initial={false} animate={{ scaleX: i < score ? 1 : 0 }} transition={reduced ? INSTANT : { ...CELL, delay: i < score ? i * 0.03 : 0 }} />
          </div>
        ))}
      </div>
      <div className="mt-2 flex h-5 items-center justify-between gap-3">
        <span className="inline-grid text-[12.5px] font-medium leading-5">
          {labels.map((text, i) => (
            <motion.span key={text} aria-hidden className={`col-start-1 row-start-1 whitespace-nowrap transition-colors duration-200 ${tone.text}`} initial={false} animate={{ opacity: i === Math.min(score, labels.length - 1) ? 1 : 0 }} transition={reduced ? INSTANT : CROSSFADE}>{t(text)}</motion.span>
          ))}
        </span>
        <motion.span aria-hidden className="whitespace-nowrap text-[11.5px] leading-5 text-[var(--strength-caution-text,var(--text-mid))]" initial={false} animate={{ opacity: guessable ? 1 : 0 }} transition={reduced ? INSTANT : CROSSFADE}>{t("Commonly guessed")}</motion.span>
      </div>
      {showRules && (
        <ul className="password-strength-rules mt-3">
          {evaluated.map((rule) => (
            <li key={rule.id} className="flex items-center gap-2">
              <span className="password-strength-check relative size-[14px] shrink-0 rounded-[4px] border border-[var(--strength-check-border,var(--text-dim))] text-[var(--strength-check-ink,var(--ink))]">
                <motion.span className="absolute inset-0 rounded-[3px] bg-[var(--strength-safe-bar,var(--accent))]" initial={false} animate={{ opacity: rule.met ? 1 : 0 }} transition={reduced ? INSTANT : CROSSFADE} />
                <motion.svg viewBox="0 0 12 12" fill="none" aria-hidden className="relative size-[9px]" initial={false} animate={{ opacity: rule.met ? 1 : 0, scale: rule.met ? 1 : 0.6 }} transition={reduced ? INSTANT : CELL}>
                  <path d="M2 6.2 4.7 8.9 10 3.3" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" />
                </motion.svg>
              </span>
              <span className={`text-[12.5px] leading-5 transition-colors duration-200 ${rule.met ? "text-[var(--strength-met,var(--text-mid))]" : "text-[var(--strength-empty-text,var(--text-dim))]"}`}>{rule.label}</span>
              <span className="sr-only">{t(rule.met ? "met" : "not met")}</span>
            </li>
          ))}
        </ul>
      )}
      <p aria-live="polite" className="sr-only">{announcement}</p>
    </div>
  );
}
export default PasswordStrength;
