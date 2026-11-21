"use client";

import { useState, type ComponentProps } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useLanguage } from "@/lib/i18n";

type PasswordInputProps = Omit<ComponentProps<"input">, "type"> & {
  allowReveal?: boolean;
  confirmation?: boolean;
};

export function PasswordInput({ allowReveal = true, confirmation = false, ...props }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  const { t } = useLanguage();
  if (!allowReveal) return <input {...props} type="password" />;

  const label = confirmation
    ? visible ? "Hide confirmation password" : "Show confirmation password"
    : visible ? "Hide password" : "Show password";
  const Icon = visible ? EyeOff : Eye;

  return (
    <div className="auth-password-input">
      <input {...props} type={visible ? "text" : "password"} spellCheck={false} autoCapitalize="none" autoCorrect="off" />
      <button
        type="button"
        className="auth-password-toggle"
        aria-label={t(label)}
        aria-controls={props.id}
        onClick={() => setVisible((current) => !current)}
      >
        <Icon size={18} aria-hidden="true" />
      </button>
    </div>
  );
}
