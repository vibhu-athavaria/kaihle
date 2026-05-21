import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff } from "lucide-react";
import { SlideOverPanel, toast } from "@kaihle/ui";
import { useUpdateUser } from "../hooks/useSchoolAdmin";

const schema = z.object({
  first_name: z.string().min(1, "Required"),
  last_name: z.string().min(1, "Required"),
  email: z.string().email("Enter a valid email"),
  is_active: z.boolean(),
  password: z.string().min(8, "Min 8 characters").or(z.literal("")).optional(),
});

type FormValues = z.infer<typeof schema>;

interface EditTeacherPanelProps {
  open: boolean;
  onClose: () => void;
  userId: string;
  initialValues: {
    first_name: string;
    last_name: string;
    email: string;
    is_active: boolean;
  };
}

export function EditTeacherPanel({
  open,
  onClose,
  userId,
  initialValues,
}: EditTeacherPanelProps) {
  const updateUser = useUpdateUser();
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { ...initialValues, password: "" },
  });

  useEffect(() => {
    if (open) reset({ ...initialValues, password: "" });
  }, [open, initialValues, reset]);

  const isActive = watch("is_active");
  const initiallyActive = initialValues.is_active;

  const onSubmit = async (values: FormValues) => {
    const updateData: Parameters<typeof updateUser.mutateAsync>[0] = {
      userId,
      first_name: values.first_name,
      last_name: values.last_name,
      email: values.email,
      is_active: values.is_active,
    };
    if (values.password) updateData.password = values.password;

    try {
      await updateUser.mutateAsync(updateData);
      toast.success("Teacher updated");
      onClose();
    } catch {
      toast.error("Failed to update teacher");
    }
  };

  return (
    <SlideOverPanel
      open={open}
      title="Edit teacher"
      onClose={onClose}
      footer={
        <div className="flex gap-2.5">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 border border-role-school-border rounded-full py-2.5 text-sm font-bold text-brand-body bg-white hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="edit-teacher-form"
            disabled={isSubmitting}
            className="flex-[2] bg-brand-primary text-white rounded-full py-2.5 text-sm font-bold hover:bg-brand-primary/90 disabled:opacity-60 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 transition-colors"
          >
            {isSubmitting ? "Saving…" : "Save changes"}
          </button>
        </div>
      }
    >
      <form id="edit-teacher-form" onSubmit={handleSubmit(onSubmit)} noValidate>
        <div className="grid grid-cols-2 gap-4 mb-5">
          <div>
            <label className="block text-sm font-semibold text-brand-ink mb-1.5">
              First name
            </label>
            <input
              {...register("first_name")}
              className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary outline-none"
            />
            {errors.first_name && (
              <p className="text-xs text-red-500 mt-1">
                {errors.first_name.message}
              </p>
            )}
          </div>
          <div>
            <label className="block text-sm font-semibold text-brand-ink mb-1.5">
              Last name
            </label>
            <input
              {...register("last_name")}
              className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary outline-none"
            />
            {errors.last_name && (
              <p className="text-xs text-red-500 mt-1">
                {errors.last_name.message}
              </p>
            )}
          </div>
        </div>

        <div className="mb-5">
          <label className="block text-sm font-semibold text-brand-ink mb-1.5">
            Email address
          </label>
          <input
            {...register("email")}
            type="email"
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary outline-none"
          />
          {errors.email && (
            <p className="text-xs text-red-500 mt-1">{errors.email.message}</p>
          )}
        </div>

        <div className="mb-5">
          <label className="block text-sm font-semibold text-brand-ink mb-1.5">
            Status
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setValue("is_active", true)}
              className={`flex-1 border rounded-xl py-2.5 text-sm font-semibold text-center transition-colors ${
                isActive
                  ? "border-brand-primary text-brand-primary bg-brand-light"
                  : "border-brand-border text-brand-muted bg-white"
              }`}
            >
              Active
            </button>
            <button
              type="button"
              onClick={() => setValue("is_active", false)}
              className={`flex-1 border rounded-xl py-2.5 text-sm font-semibold text-center transition-colors ${
                !isActive
                  ? "border-brand-primary text-brand-primary bg-brand-light"
                  : "border-brand-border text-brand-muted bg-white"
              }`}
            >
              Inactive
            </button>
          </div>
        </div>

        <div className="mb-5">
          <label className="block text-sm font-semibold text-brand-ink mb-1.5">
            Reset password
          </label>
          <div className="relative">
            <input
              {...register("password")}
              type={showPassword ? "text" : "password"}
              placeholder="Leave blank to keep current"
              className="w-full px-4 py-2.5 pr-10 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary outline-none"
            />
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
          </div>
          {errors.password ? (
            <p className="text-xs text-red-500 mt-1">
              {errors.password.message}
            </p>
          ) : (
            <p className="text-xs text-brand-muted mt-1">
              Teacher will use this password on next login.
            </p>
          )}
        </div>

        {initiallyActive ? (
          <>
            <hr className="border-t border-gray-100 my-6" />
            <p className="text-xs font-bold uppercase tracking-wide text-red-500 mb-2">
              Danger zone
            </p>
            <button
              type="button"
              onClick={() => {
                setValue("is_active", false);
                handleSubmit(onSubmit)();
              }}
              className="w-full border border-red-200 rounded-xl px-4 py-2.5 text-sm font-semibold text-red-500 bg-white text-left hover:bg-red-50 transition-colors focus-visible:ring-2 focus-visible:ring-red-400 focus-visible:ring-offset-1"
            >
              Deactivate teacher
            </button>
          </>
        ) : (
          <>
            <hr className="border-t border-gray-100 my-6" />
            <div className="bg-green-50 border border-green-100 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-green-700 mb-2">
                Account Deactivated
              </h3>
              <p className="text-xs text-green-600 mb-3">
                This teacher&apos;s account is currently deactivated. They
                cannot log in. Re-activate to restore their access.
              </p>
              <button
                type="button"
                onClick={() => {
                  setValue("is_active", true);
                  handleSubmit(onSubmit)();
                }}
                className="bg-green-600 hover:bg-green-700 text-white rounded-full px-4 py-2.5 text-sm font-semibold focus-visible:ring-2 focus-visible:ring-green-400 focus-visible:ring-offset-1 transition-colors"
              >
                Re-activate teacher
              </button>
            </div>
          </>
        )}
      </form>
    </SlideOverPanel>
  );
}
