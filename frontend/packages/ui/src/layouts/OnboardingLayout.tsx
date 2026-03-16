import React from "react";

interface OnboardingLayoutProps {
  children: React.ReactNode;
  step: number;
  totalSteps: number;
  stepLabel: string;
}

export function OnboardingLayout({
  children,
  step,
  totalSteps,
  stepLabel,
}: OnboardingLayoutProps) {
  return (
    <div className="min-h-screen bg-brand-bg">
      <header className="bg-white border-b border-brand-border h-14 flex items-center px-6">
        <span className="font-display font-bold text-lg text-brand-ink">
          Kaihle
        </span>
        <div className="ml-auto text-sm text-brand-muted font-semibold">
          Step {step} of {totalSteps} — {stepLabel}
        </div>
      </header>
      <main className="p-4 md:p-8 max-w-2xl mx-auto">{children}</main>
    </div>
  );
}
