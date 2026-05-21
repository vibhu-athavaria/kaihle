import { useEffect, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { SlideOverPanel, Button } from "@kaihle/ui";
import {
  useUpdateUser,
  useGrades,
  type StudentProfile,
} from "../hooks/useSchoolAdmin";

const editStudentSchema = z.object({
  first_name: z.string().min(1, "First name is required"),
  last_name: z.string().min(1, "Last name is required"),
  email: z.string().email("Invalid email address").optional().or(z.literal("")),
  grade_id: z.string().min(1, "Grade is required").optional().or(z.literal("")),
  is_active: z.boolean(),
  password: z
    .string()
    .min(8, "Password must be at least 8 characters")
    .optional()
    .or(z.literal("")),
});

type EditStudentFormValues = z.infer<typeof editStudentSchema>;

interface EditStudentPanelProps {
  open: boolean;
  onClose: () => void;
  student: StudentProfile | null;
}

export function EditStudentPanel({
  open,
  onClose,
  student,
}: EditStudentPanelProps) {
  const updateUser = useUpdateUser();
  const { data: grades, isLoading: gradesLoading } = useGrades();
  const [showDeactivateConfirm, setShowDeactivateConfirm] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<EditStudentFormValues>({
    resolver: zodResolver(editStudentSchema),
    defaultValues: {
      first_name: "",
      last_name: "",
      email: "",
      grade_id: "",
      is_active: true,
      password: "",
    },
  });

  // Reset form when student changes or panel opens
  useEffect(() => {
    if (student && open) {
      reset({
        first_name: student.first_name,
        last_name: student.last_name,
        email: student.email ?? "",
        grade_id: student.grade_id ?? "",
        is_active: student.is_active,
        password: "",
      });
    }
  }, [student, open, reset]);

  // Re-sync grade select after grades load asynchronously.
  // RHF's uncontrolled <select> only binds the value when options exist in the DOM;
  // if grades resolve after reset(), the select falls back to the first option.
  useEffect(() => {
    if (student && grades && open) {
      setValue("grade_id", student.grade_id ?? "");
    }
  }, [grades, student, open, setValue]);

  const onSubmit = async (values: EditStudentFormValues) => {
    if (!student) return;

    const payload: {
      userId: string;
      first_name?: string;
      last_name?: string;
      email?: string;
      grade_id?: string;
      is_active?: boolean;
      password?: string;
    } = {
      userId: student.id,
      first_name: values.first_name,
      last_name: values.last_name,
      is_active: values.is_active,
    };

    // Only include email if it changed (we don't have original email from student detail)
    if (values.email) {
      payload.email = values.email;
    }

    // Only include grade_id if it changed
    if (values.grade_id) {
      payload.grade_id = values.grade_id;
    }

    // Only include password if provided
    if (values.password) {
      payload.password = values.password;
    }

    await updateUser.mutateAsync(payload);

    onClose();
  };

  const handleDeactivate = async () => {
    if (!student) return;

    await updateUser.mutateAsync({
      userId: student.id,
      first_name: student.first_name,
      last_name: student.last_name,
      is_active: false,
    });

    setShowDeactivateConfirm(false);
    onClose();
  };

  const handleReactivate = async () => {
    if (!student) return;

    await updateUser.mutateAsync({
      userId: student.id,
      first_name: student.first_name,
      last_name: student.last_name,
      is_active: true,
    });

    setShowDeactivateConfirm(false);
    onClose();
  };

  const footer = (
    <div className="flex gap-3">
      <Button
        type="button"
        variant="secondary"
        onClick={onClose}
        disabled={isSubmitting}
        className="flex-1"
      >
        Cancel
      </Button>
      <Button
        type="submit"
        form="edit-student-form"
        variant="primary"
        loading={isSubmitting}
        disabled={isSubmitting || !isDirty}
        className="flex-1"
      >
        Save changes
      </Button>
    </div>
  );

  return (
    <SlideOverPanel
      open={open}
      title="Edit Student"
      onClose={onClose}
      footer={footer}
    >
      <form
        id="edit-student-form"
        onSubmit={handleSubmit(onSubmit)}
        className="space-y-5"
      >
        {/* First Name */}
        <div>
          <label
            htmlFor="first-name"
            className="block text-sm font-semibold text-brand-ink mb-1.5"
          >
            First name <span className="text-brand-red">*</span>
          </label>
          <input
            id="first-name"
            type="text"
            {...register("first_name")}
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
            placeholder="e.g. John"
          />
          {errors.first_name && (
            <p className="mt-1 text-xs text-brand-red">
              {errors.first_name.message}
            </p>
          )}
        </div>

        {/* Last Name */}
        <div>
          <label
            htmlFor="last-name"
            className="block text-sm font-semibold text-brand-ink mb-1.5"
          >
            Last name <span className="text-brand-red">*</span>
          </label>
          <input
            id="last-name"
            type="text"
            {...register("last_name")}
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
            placeholder="e.g. Smith"
          />
          {errors.last_name && (
            <p className="mt-1 text-xs text-brand-red">
              {errors.last_name.message}
            </p>
          )}
        </div>

        {/* Email */}
        <div>
          <label
            htmlFor="email"
            className="block text-sm font-semibold text-brand-ink mb-1.5"
          >
            Email
          </label>
          <input
            id="email"
            type="email"
            {...register("email")}
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
            placeholder="student@school.edu"
          />
          {errors.email && (
            <p className="mt-1 text-xs text-brand-red">
              {errors.email.message}
            </p>
          )}
          <p className="mt-1 text-xs text-brand-muted">
            Changing this will update the student&apos;s login email
          </p>
        </div>

        {/* Grade */}
        <div>
          <label
            htmlFor="grade"
            className="block text-sm font-semibold text-brand-ink mb-1.5"
          >
            Grade
          </label>
          <select
            id="grade"
            {...register("grade_id")}
            disabled={gradesLoading}
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary disabled:opacity-60"
          >
            <option value="">
              {gradesLoading ? "Loading…" : "Select grade"}
            </option>
            {grades?.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
          {errors.grade_id && (
            <p className="mt-1 text-xs text-brand-red">
              {errors.grade_id.message}
            </p>
          )}
        </div>

        {/* Active Status Toggle */}
        <div className="flex items-center justify-between pt-2">
          <div>
            <span className="block text-sm font-semibold text-brand-ink">
              Active Status
            </span>
            <span className="text-xs text-brand-muted">
              Inactive students cannot log in
            </span>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              {...register("is_active")}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-brand-primary/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-primary" />
          </label>
        </div>

        {/* Password Reset */}
        <div className="pt-4 border-t border-gray-100">
          <label
            htmlFor="password"
            className="block text-sm font-semibold text-brand-ink mb-1.5"
          >
            Reset Password
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              {...register("password")}
              className="w-full px-4 py-2.5 pr-10 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
              placeholder="Leave blank to keep current password"
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
          {errors.password && (
            <p className="mt-1 text-xs text-brand-red">
              {errors.password.message}
            </p>
          )}
          <p className="mt-1 text-xs text-brand-muted">
            If provided, the student will need to use this new password to log
            in
          </p>
        </div>

        {/* Danger Zone */}
        {student?.is_active ? (
          <div className="pt-6 border-t border-gray-100">
            <div className="bg-red-50 border border-red-100 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-red-700 mb-2">
                Danger Zone
              </h3>
              <p className="text-xs text-red-600 mb-3">
                Deactivating a student will prevent them from logging in. Their
                data will be preserved.
              </p>
              {showDeactivateConfirm ? (
                <div className="space-y-3">
                  <p className="text-xs text-red-700 font-semibold">
                    Are you sure? This will immediately prevent the student from
                    logging in.
                  </p>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() => setShowDeactivateConfirm(false)}
                      className="flex-1"
                    >
                      Cancel
                    </Button>
                    <Button
                      type="button"
                      variant="primary"
                      size="sm"
                      loading={updateUser.isPending}
                      onClick={handleDeactivate}
                      className="flex-1 bg-red-600 hover:bg-red-700"
                    >
                      Deactivate
                    </Button>
                  </div>
                </div>
              ) : (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setShowDeactivateConfirm(true)}
                  className="text-red-600 border-red-200 hover:bg-red-50"
                >
                  Deactivate student
                </Button>
              )}
            </div>
          </div>
        ) : (
          <div className="pt-6 border-t border-gray-100">
            <div className="bg-green-50 border border-green-100 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-green-700 mb-2">
                Account Deactivated
              </h3>
              <p className="text-xs text-green-600 mb-3">
                This student&apos;s account is currently deactivated. They
                cannot log in. Re-activate to restore their access.
              </p>
              <Button
                type="button"
                variant="primary"
                size="sm"
                loading={updateUser.isPending}
                onClick={handleReactivate}
                className="bg-green-600 hover:bg-green-700"
              >
                Re-activate student
              </Button>
            </div>
          </div>
        )}
      </form>
    </SlideOverPanel>
  );
}
