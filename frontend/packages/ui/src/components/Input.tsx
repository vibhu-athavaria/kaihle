import React, { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

export function Input({
  label,
  error,
  hint,
  id,
  type,
  className = "",
  ...props
}: InputProps) {
  const inputId = id ?? label.toLowerCase().replace(/\s+/g, "-");
  const isPassword = type === "password";
  const [showPassword, setShowPassword] = useState(false);
  const resolvedType = isPassword ? (showPassword ? "text" : "password") : type;

  return (
    <div className="w-full">
      <label
        htmlFor={inputId}
        className="block text-sm font-semibold text-brand-ink mb-1.5"
      >
        {label}
      </label>
      <div className={isPassword ? "relative" : undefined}>
        <input
          id={inputId}
          type={resolvedType}
          className={[
            "w-full bg-white border rounded-xl px-4 py-2.5",
            "text-brand-ink placeholder:text-brand-muted text-sm font-normal",
            "transition-colors",
            "focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            error ? "border-brand-red" : "border-brand-border",
            isPassword ? "pr-10" : "",
            className,
          ].join(" ")}
          aria-describedby={
            error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined
          }
          aria-invalid={error ? "true" : undefined}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-brand-muted hover:text-brand-ink transition-colors"
            aria-label={showPassword ? "Hide password" : "Show password"}
          >
            {showPassword ? (
              <Eye size={18} aria-hidden="true" />
            ) : (
              <EyeOff size={18} aria-hidden="true" />
            )}
          </button>
        )}
      </div>
      {error && (
        <p
          id={`${inputId}-error`}
          className="text-xs text-brand-red mt-1.5 flex items-center gap-1"
          role="alert"
        >
          {error}
        </p>
      )}
      {hint && !error && (
        <p id={`${inputId}-hint`} className="text-xs text-brand-muted mt-1.5">
          {hint}
        </p>
      )}
    </div>
  );
}
