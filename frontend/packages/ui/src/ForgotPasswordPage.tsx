import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

const schema = z.object({
  email: z.string().email("Enter a valid email address"),
});

type Fields = z.infer<typeof schema>;

export interface ForgotPasswordPageProps {
  onSubmit: (email: string) => Promise<void>;
  appLoginPath: string;
}

export function ForgotPasswordPage({
  onSubmit,
  appLoginPath,
}: ForgotPasswordPageProps) {
  const [sent, setSent] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState("");

  const { register, handleSubmit, formState } = useForm<Fields>({
    resolver: zodResolver(schema),
  });

  const handleFormSubmit = async (data: Fields) => {
    await onSubmit(data.email);
    setSubmittedEmail(data.email);
    setSent(true);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 w-full max-w-sm p-8">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-teal-600 rounded-xl mb-3">
            <span className="text-white font-bold text-xl">K</span>
          </div>
          {!sent ? (
            <>
              <h1 className="text-xl font-semibold text-gray-900">
                Forgot your password?
              </h1>
              <p className="text-sm text-gray-500 mt-1 leading-relaxed">
                Enter your email and we'll send you a reset link. It expires in
                24 hours.
              </p>
            </>
          ) : (
            <h1 className="text-xl font-semibold text-gray-900">
              Check your inbox
            </h1>
          )}
        </div>

        {!sent ? (
          <form onSubmit={handleSubmit(handleFormSubmit)} noValidate>
            <div className="mb-4">
              <label
                htmlFor="fp-email"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Email address
              </label>
              <input
                id="fp-email"
                type="email"
                autoComplete="email"
                {...register("email")}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                placeholder="you@school.edu"
              />
              {formState.errors.email && (
                <p className="mt-1 text-xs text-red-500">
                  {formState.errors.email.message}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={formState.isSubmitting}
              className="w-full bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-colors mb-4"
            >
              {formState.isSubmitting ? "Sending…" : "Send reset link"}
            </button>

            <div className="text-center">
              <a
                href={appLoginPath}
                className="text-sm font-medium text-teal-600 hover:text-teal-700 transition-colors"
              >
                ← Back to login
              </a>
            </div>
          </form>
        ) : (
          <div className="text-center">
            <div className="w-12 h-12 bg-teal-50 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-2xl">📧</span>
            </div>
            <p className="text-sm text-gray-600 mb-1">
              We sent a reset link to
            </p>
            <p className="text-sm font-semibold text-gray-900 mb-5">
              {submittedEmail}
            </p>
            <p className="text-xs text-gray-400 mb-1">
              Didn't receive it? Check spam or
            </p>
            <button
              type="button"
              onClick={() => setSent(false)}
              className="text-sm font-semibold text-teal-600 hover:text-teal-700 transition-colors"
            >
              resend the email
            </button>
            <div className="mt-6 pt-5 border-t border-gray-100">
              <a
                href={appLoginPath}
                className="text-sm font-medium text-teal-600 hover:text-teal-700 transition-colors"
              >
                ← Back to login
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
