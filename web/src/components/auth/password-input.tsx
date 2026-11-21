"use client";

import { useId, useState, type ComponentProps } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useLanguage } from "@/lib/i18n";

type PasswordInputProps = Omit<ComponentProps<"input">, "type"> & {
  confirmation?: boolean;
};

export function PasswordInput({ confirmation = false, ...props }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  const generatedId = useId();
  const inputId = props.id ?? generatedId;
  const { t } = useLanguage();

  const label = confirmation
    ? visible ? "Hide confirmation password" : "Show confirmation password"
    : visible ? "Hide password" : "Show password";
  const Icon = visible ? EyeOff : Eye;

  return (
    <span className="auth-password-input">
      <input {...props} id={inputId} type={visible ? "text" : "password"} spellCheck={false} autoCapitalize="none" autoCorrect="off" />
      <button
        type="button"
        className="auth-password-toggle"
        aria-label={t(label)}
        aria-controls={inputId}
        disabled={props.disabled}
        onClick={() => setVisible((current) => !current)}
      >
        <Icon size={18} aria-hidden="true" />
      </button>
    </span>
  );
}
