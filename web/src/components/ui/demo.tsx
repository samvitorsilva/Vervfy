"use client";

import { PasswordStrength } from "@/components/ui/password-strength";
import { PasswordInput } from "@/components/auth/password-input";
import { useId, useState } from "react";
import { useLanguage } from "@/lib/i18n";

export function PasswordStrengthDemo() {
  const { t } = useLanguage();
  const id = useId();
  const [value, setValue] = useState("");
  return (
    <div className="mx-auto w-full max-w-[320px]">
      <label htmlFor={id} className="block text-[13px] font-medium text-[var(--text-mid)]">{t("New password")}</label>
      <PasswordInput
        id={id}
        value={value}
        autoComplete="new-password"
        spellCheck={false}
        onChange={(e) => setValue(e.target.value)}
        placeholder={t("Type a password")}
        className="mt-1.5 h-10 w-full rounded-[10px] border-2 border-[var(--text-dim)] bg-[var(--bg-2)] px-3 text-[13px] text-[var(--text)] placeholder:text-[var(--text-dim)] focus:border-[var(--accent)] focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
      />
      <PasswordStrength value={value} className="mt-3" />
    </div>
  );
}
export default PasswordStrengthDemo;
