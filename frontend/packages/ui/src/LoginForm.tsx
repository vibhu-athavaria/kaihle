import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

const magicSchema = z.object({
  email: z.string().email("Enter a valid email address"),
});

type LoginFields = z.infer<typeof loginSchema>;
type MagicFields = z.infer<typeof magicSchema>;

export interface LoginFormProps {
  onLogin: (email: string, password: string) => Promise<void>;
  onMagicLink: (email: string) => Promise<void>;
  logoLabel?: string; // e.g. "Teacher Portal"
  isLoading?: boolean;
}

export function LoginForm({
  onLogin,
  onMagicLink,
  logoLabel,
  isLoading,
}: LoginFormProps) {
  const [mode, setMode] = useState<"password" | "magic">("password");
  const [magicSent, setMagicSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const passwordForm = useForm<LoginFields>({
    resolver: zodResolver(loginSchema),
  });
  const magicForm = useForm<MagicFields>({
    resolver: zodResolver(magicSchema),
  });

  const handleLogin = async (data: LoginFields) => {
    setError(null);
    try {
      await onLogin(data.email, data.password);
    } catch {
      setError("Invalid email or password. Please try again.");
    }
  };

  const handleMagic = async (data: MagicFields) => {
    setError(null);
    try {
      await onMagicLink(data.email);
      setMagicSent(true);
    } catch {
      setError("Something went wrong. Please try again.");
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 w-full max-w-sm p-8">
        {/* Logo / Label */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-teal-600 rounded-xl mb-3">
            <span className="text-white font-bold text-xl">K</span>
          </div>
          <h1 className="text-xl font-semibold text-gray-900">Kaihle</h1>
          {logoLabel && (
            <p className="text-sm text-gray-500 mt-1">{logoLabel}</p>
          )}
        </div>

        {/* Mode toggle */}
        <div className="flex rounded-lg bg-gray-100 p-1 mb-6">
          <button
            type="button"
            onClick={() => {
              setMode("password");
              setError(null);
            }}
            className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors ${
              mode === "password"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500"
            }`}
          >
            Password
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("magic");
              setError(null);
            }}
            className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors ${
              mode === "magic"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500"
            }`}
          >
            Magic link
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 px-3 py-2 bg-red-50 border border-red-100 rounded-lg text-sm text-red-600">
            {error}
          </div>
        )}

        {/* Password form */}
        {mode === "password" && (
          <form onSubmit={passwordForm.handleSubmit(handleLogin)} noValidate>
            <div className="mb-4">
              <label
                htmlFor="email"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                {...passwordForm.register("email")}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                placeholder="you@school.edu"
              />
              {passwordForm.formState.errors.email && (
                <p className="mt-1 text-xs text-red-500">
                  {passwordForm.formState.errors.email.message}
                </p>
              )}
            </div>
            <div className="mb-6">
              <label
                htmlFor="password"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                {...passwordForm.register("password")}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
              />
              {passwordForm.formState.errors.password && (
                <p className="mt-1 text-xs text-red-500">
                  {passwordForm.formState.errors.password.message}
                </p>
              )}
            </div>
            <button
              type="submit"
              disabled={isLoading || passwordForm.formState.isSubmitting}
              className="w-full bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-colors"
            >
              {passwordForm.formState.isSubmitting ? "Signing in…" : "Sign in"}
            </button>
          </form>
        )}

        {/* Magic link form */}
        {mode === "magic" && !magicSent && (
          <form onSubmit={magicForm.handleSubmit(handleMagic)} noValidate>
            <div className="mb-6">
              <label
                htmlFor="magic-email"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Email
              </label>
              <input
                id="magic-email"
                type="email"
                autoComplete="email"
                {...magicForm.register("email")}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                placeholder="you@school.edu"
              />
              {magicForm.formState.errors.email && (
                <p className="mt-1 text-xs text-red-500">
                  {magicForm.formState.errors.email.message}
                </p>
              )}
            </div>
            <button
              type="submit"
              disabled={magicForm.formState.isSubmitting}
              className="w-full bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-colors"
            >
              {magicForm.formState.isSubmitting
                ? "Sending…"
                : "Send login link"}
            </button>
          </form>
        )}

        {/* Magic link sent confirmation */}
        {mode === "magic" && magicSent && (
          <div className="text-center">
            <div className="w-12 h-12 bg-teal-50 rounded-full flex items-center justify-center mx-auto mb-3">
              <span className="text-2xl">📧</span>
            </div>
            <p className="text-sm font-medium text-gray-900 mb-1">
              Check your inbox
            </p>
            <p className="text-sm text-gray-500">
              We sent a login link to your email. It expires in 10 minutes.
            </p>
            <button
              type="button"
              onClick={() => setMagicSent(false)}
              className="mt-4 text-sm text-teal-600 hover:underline"
            >
              Send again
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
