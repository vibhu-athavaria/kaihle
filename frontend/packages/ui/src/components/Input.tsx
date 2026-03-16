import React from "react";

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
  className = "",
  ...props
}: InputProps) {
  const inputId = id ?? label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className="w-full">
      <label
        htmlFor={inputId}
        className="block text-sm font-semibold text-brand-ink mb-1.5"
      >
        {label}
      </label>
      <input
        id={inputId}
        className={[
          "w-full bg-white border rounded-xl px-4 py-2.5",
          "text-brand-ink placeholder:text-brand-muted text-sm font-normal",
          "transition-colors",
          "focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          error ? "border-brand-red" : "border-brand-border",
          className,
        ].join(" ")}
        aria-describedby={
          error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined
        }
        aria-invalid={error ? "true" : undefined}
        {...props}
      />
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
