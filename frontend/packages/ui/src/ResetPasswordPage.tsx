import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff } from "lucide-react";

const schema = z
  .object({
    password: z.string().min(8, "At least 8 characters"),
    confirm_password: z.string(),
  })
  .refine((d) => d.password === d.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type Fields = z.infer<typeof schema>;

function getPasswordStrength(password: string): {
  score: number;
  label: string;
} {
  if (password.length < 8) return { score: 0, label: "Weak" };
  let types = 0;
  if (/[a-z]/.test(password)) types++;
  if (/[A-Z]/.test(password)) types++;
  if (/[0-9]/.test(password)) types++;
  if (/[^a-zA-Z0-9]/.test(password)) types++;
  if (types <= 1) return { score: 1, label: "Weak" };
  if (types === 2) return { score: 2, label: "Medium" };
  return { score: 3, label: "Strong" };
}

const strengthColors = [
  "bg-gray-200",
  "bg-red-500",
  "bg-amber-500",
  "bg-brand-primary",
];

export interface ResetPasswordPageProps {
  /** Raw token extracted from the URL query string by the host app. Empty string = show expired state. */
  token: string;
  onReset: (token: string, password: string) => Promise<void>;
  /** Called after a successful reset — host app should navigate to login. */
  onSuccess: () => void;
  appLoginPath: string;
  forgotPasswordPath?: string;
}

export function ResetPasswordPage({
  token,
  onReset,
  onSuccess,
  appLoginPath,
  forgotPasswordPath,
}: ResetPasswordPageProps) {
  const [expired, setExpired] = useState(!token);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const { register, handleSubmit, watch, formState } = useForm<Fields>({
    resolver: zodResolver(schema),
  });

  const passwordValue = watch("password", "");
  const { score, label } = getPasswordStrength(passwordValue);
  const activeColor = strengthColors[score];

  const handleFormSubmit = async (data: Fields) => {
    try {
      await onReset(token, data.password);
      onSuccess();
    } catch {
      setExpired(true);
    }
  };

  if (expired) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 w-full max-w-sm p-8 text-center">
          <div className="w-12 h-12 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl">⏱️</span>
          </div>
          <h1 className="text-xl font-semibold text-gray-900 mb-2">
            This link has expired
          </h1>
          <p className="text-sm text-gray-500 mb-6 leading-relaxed">
            Reset links are valid for 24 hours. Request a new one and try again.
          </p>
          {forgotPasswordPath && (
            <a
              href={forgotPasswordPath}
              className="block w-full bg-brand-primary hover:opacity-90 text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-opacity text-center mb-4"
            >
              Request a new link
            </a>
          )}
          <a
            href={appLoginPath}
            className="text-sm font-medium text-brand-primary hover:opacity-80 transition-opacity"
          >
            ← Back to login
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 w-full max-w-sm p-8">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-brand-primary rounded-xl mb-3">
            <span className="text-white font-bold text-xl">K</span>
          </div>
          <h1 className="text-xl font-semibold text-gray-900">
            Set a new password
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Must be at least 8 characters
          </p>
        </div>

        <form onSubmit={handleSubmit(handleFormSubmit)} noValidate>
          {/* New password */}
          <div className="mb-4">
            <label
              htmlFor="rp-password"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              New password
            </label>
            <div className="relative">
              <input
                id="rp-password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                {...register("password")}
                className="w-full px-3 py-2 pr-10 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <Eye size={16} /> : <EyeOff size={16} />}
              </button>
            </div>
            {passwordValue.length > 0 && (
              <div className="mt-2 space-y-1">
                <div className="flex gap-1">
                  {[0, 1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className={`h-1 flex-1 rounded-full transition-colors ${i <= score ? activeColor : "bg-gray-200"}`}
                    />
                  ))}
                </div>
                <p className="text-xs text-gray-400">{label}</p>
              </div>
            )}
            {formState.errors.password && (
              <p className="mt-1 text-xs text-red-500">
                {formState.errors.password.message}
              </p>
            )}
          </div>

          {/* Confirm password */}
          <div className="mb-6">
            <label
              htmlFor="rp-confirm"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Confirm password
            </label>
            <div className="relative">
              <input
                id="rp-confirm"
                type={showConfirm ? "text" : "password"}
                autoComplete="new-password"
                {...register("confirm_password")}
                className="w-full px-3 py-2 pr-10 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent"
              />
              <button
                type="button"
                onClick={() => setShowConfirm(!showConfirm)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
                aria-label={showConfirm ? "Hide password" : "Show password"}
              >
                {showConfirm ? <Eye size={16} /> : <EyeOff size={16} />}
              </button>
            </div>
            {formState.errors.confirm_password && (
              <p className="mt-1 text-xs text-red-500">
                {formState.errors.confirm_password.message}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={formState.isSubmitting}
            className="w-full bg-brand-primary hover:opacity-90 disabled:opacity-50 text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-opacity"
          >
            {formState.isSubmitting ? "Resetting…" : "Reset password"}
          </button>
        </form>
      </div>
    </div>
  );
}
