import React from "react";

interface AuthLayoutProps {
  children: React.ReactNode;
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="min-h-screen bg-brand-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <span className="font-display font-bold text-2xl text-brand-ink">
            Kaihle
          </span>
        </div>
        {children}
      </div>
    </div>
  );
}
