import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, Check } from "lucide-react";
import { AuthLayout } from "../layouts/AuthLayout";

const passwordSchema = z
  .object({
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

type PasswordFields = z.infer<typeof passwordSchema>;

export interface PasswordSetupFormProps {
  onSubmit: (password: string) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  logoLabel?: string;
}

export function PasswordSetupForm({
  onSubmit,
  isLoading = false,
  error = null,
  logoLabel = "Kaihle",
}: PasswordSetupFormProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isValid },
  } = useForm<PasswordFields>({
    resolver: zodResolver(passwordSchema),
    mode: "onChange",
  });

  const password = watch("password", "");
  const confirmPassword = watch("confirmPassword", "");

  const hasMinLength = password.length >= 8;
  const hasMatch = password === confirmPassword && confirmPassword.length > 0;

  const onFormSubmit = async (data: PasswordFields) => {
    await onSubmit(data.password);
  };

  return (
    <AuthLayout>
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 w-full max-w-sm p-8">
        {/* Logo / Label */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-brand-primary rounded-xl mb-3">
            <span className="text-white font-bold text-xl">K</span>
          </div>
          <h1 className="text-xl font-semibold text-gray-900">Kaihle</h1>
          {logoLabel && (
            <p className="text-sm text-gray-500 mt-1">{logoLabel}</p>
          )}
        </div>

        {/* Heading */}
        <div className="text-center mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">
            Set your password
          </h2>
          <p className="text-sm text-gray-500">
            Create a password to secure your account
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 px-3 py-2 bg-red-50 border border-red-100 rounded-lg text-sm text-red-600">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit(onFormSubmit)} noValidate>
          {/* Password field */}
          <div className="mb-3">
            <label
              htmlFor="password"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Password
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                {...register("password")}
                className="w-full px-3 py-2 pr-10 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent"
                placeholder="Min. 8 characters"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
              >
                {showPassword ? <Eye size={18} /> : <EyeOff size={18} />}
              </button>
            </div>
          </div>

          {/* Confirm password field */}
          <div className="mb-4">
            <label
              htmlFor="confirmPassword"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Confirm password
            </label>
            <div className="relative">
              <input
                id="confirmPassword"
                type={showConfirm ? "text" : "password"}
                autoComplete="new-password"
                {...register("confirmPassword")}
                className="w-full px-3 py-2 pr-10 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent"
                placeholder="Re-enter your password"
              />
              <button
                type="button"
                onClick={() => setShowConfirm(!showConfirm)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
              >
                {showConfirm ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            {errors.confirmPassword && (
              <p className="mt-1 text-xs text-red-500">
                {errors.confirmPassword.message}
              </p>
            )}
          </div>

          {/* Validation indicators */}
          <div className="mb-6 space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <div
                className={`w-4 h-4 rounded-full flex items-center justify-center ${
                  hasMinLength ? "bg-brand-primary text-white" : "bg-gray-200"
                }`}
              >
                {hasMinLength && <Check size={12} />}
              </div>
              <span
                className={
                  hasMinLength ? "text-brand-primary" : "text-gray-500"
                }
              >
                Minimum 8 characters
              </span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <div
                className={`w-4 h-4 rounded-full flex items-center justify-center ${
                  hasMatch ? "bg-brand-primary text-white" : "bg-gray-200"
                }`}
              >
                {hasMatch && <Check size={12} />}
              </div>
              <span
                className={hasMatch ? "text-brand-primary" : "text-gray-500"}
              >
                Passwords match
              </span>
            </div>
          </div>

          {/* Submit button */}
          <button
            type="submit"
            disabled={!isValid || isLoading}
            className="w-full bg-brand-primary hover:bg-brand-dark disabled:opacity-50 text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-colors"
          >
            {isLoading ? "Setting password…" : "Set password & continue"}
          </button>
        </form>
      </div>
    </AuthLayout>
  );
}
