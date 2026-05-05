import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { SlideOverPanel, Button, toast } from "@kaihle/ui";
import { UserRole } from "@kaihle/types";
import {
  useUpdateClass,
  useSchoolUsers,
  type ClassDetail,
} from "../hooks/useSchoolAdmin";

const ACADEMIC_YEAR_REGEX = /^\d{4}\-\d{4}$/;

const editClassSchema = z.object({
  name: z.string().min(1, "Class name is required"),
  academic_year: z.string().regex(ACADEMIC_YEAR_REGEX, "Format: YYYY-YYYY"),
  teacher_id: z.string().min(1, "Teacher is required"),
  is_active: z.boolean(),
});

type EditClassFormValues = z.infer<typeof editClassSchema>;

interface EditClassPanelProps {
  open: boolean;
  onClose: () => void;
  classDetail: ClassDetail | undefined;
}

export function EditClassPanel({
  open,
  onClose,
  classDetail,
}: EditClassPanelProps) {
  const updateClass = useUpdateClass();
  const { data: teachers, isLoading: teachersLoading } = useSchoolUsers(
    UserRole.TEACHER,
  );

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<EditClassFormValues>({
    resolver: zodResolver(editClassSchema),
    defaultValues: {
      name: "",
      academic_year: "",
      teacher_id: "",
      is_active: true,
    },
  });

  // Reset form when classDetail changes or panel opens
  useEffect(() => {
    if (classDetail && open) {
      reset({
        name: classDetail.name,
        academic_year: classDetail.academic_year,
        teacher_id: classDetail.teacher_id ?? "",
        is_active: classDetail.is_active,
      });
    }
  }, [classDetail, open, reset]);

  // Re-sync teacher select after teachers load asynchronously.
  // RHF's uncontrolled <select> only binds the value when options exist in the DOM;
  // if teachers resolve after reset(), the select falls back to the first option.
  useEffect(() => {
    if (classDetail && teachers && open) {
      setValue("teacher_id", classDetail.teacher_id ?? "");
    }
  }, [teachers, classDetail, open, setValue]);

  const onSubmit = async (values: EditClassFormValues) => {
    if (!classDetail) return;

    try {
      await updateClass.mutateAsync({
        classId: classDetail.id,
        name: values.name,
        academic_year: values.academic_year,
        teacher_id: values.teacher_id,
        is_active: values.is_active,
      });
      toast.success("Class updated");
      onClose();
    } catch {
      toast.error("Failed to update class");
    }
  };

  const handleDeactivate = async () => {
    if (!classDetail) return;

    try {
      await updateClass.mutateAsync({
        classId: classDetail.id,
        name: classDetail.name,
        academic_year: classDetail.academic_year,
        teacher_id: classDetail.teacher_id,
        is_active: false,
      });
      toast.success("Class deactivated");
      onClose();
    } catch {
      toast.error("Failed to deactivate class");
    }
  };

  const handleReactivate = async () => {
    if (!classDetail) return;

    try {
      await updateClass.mutateAsync({
        classId: classDetail.id,
        name: classDetail.name,
        academic_year: classDetail.academic_year,
        teacher_id: classDetail.teacher_id,
        is_active: true,
      });
      toast.success("Class re-activated");
      onClose();
    } catch {
      toast.error("Failed to re-activate class");
    }
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
        form="edit-class-form"
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
      title="Edit Class"
      onClose={onClose}
      footer={footer}
    >
      <form
        id="edit-class-form"
        onSubmit={handleSubmit(onSubmit)}
        className="space-y-5"
      >
        {/* Class Name */}
        <div>
          <label
            htmlFor="class-name"
            className="block text-sm font-semibold text-brand-ink mb-1.5"
          >
            Class name <span className="text-brand-red">*</span>
          </label>
          <input
            id="class-name"
            type="text"
            {...register("name")}
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
            placeholder="e.g. Maths 9B"
          />
          {errors.name && (
            <p className="mt-1 text-xs text-brand-red">{errors.name.message}</p>
          )}
        </div>

        {/* Academic Year */}
        <div>
          <label
            htmlFor="academic-year"
            className="block text-sm font-semibold text-brand-ink mb-1.5"
          >
            Academic Year <span className="text-brand-red">*</span>
          </label>
          <input
            id="academic-year"
            type="text"
            {...register("academic_year")}
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
            placeholder="2025-2026"
          />
          {errors.academic_year && (
            <p className="mt-1 text-xs text-brand-red">
              {errors.academic_year.message}
            </p>
          )}
        </div>

        {/* Teacher */}
        <div>
          <label
            htmlFor="teacher"
            className="block text-sm font-semibold text-brand-ink mb-1.5"
          >
            Teacher <span className="text-brand-red">*</span>
          </label>
          <select
            id="teacher"
            {...register("teacher_id")}
            disabled={teachersLoading}
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary disabled:opacity-60"
          >
            <option value="">
              {teachersLoading ? "Loading…" : "Select teacher"}
            </option>
            {teachers?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.first_name} {t.last_name}
              </option>
            ))}
          </select>
          {errors.teacher_id && (
            <p className="mt-1 text-xs text-brand-red">
              {errors.teacher_id.message}
            </p>
          )}
        </div>

        {/* Active Status Toggle */}
        <div className="flex items-center justify-between pt-2">
          <div>
            <span className="block text-sm font-semibold text-brand-ink">
              Class Status
            </span>
            <span className="text-xs text-brand-muted">
              Inactive classes are hidden from students
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

        {/* Danger Zone */}
        {classDetail?.is_active ? (
          <div className="pt-6 border-t border-gray-100">
            <div className="bg-red-50 border border-red-100 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-red-700 mb-2">
                Danger Zone
              </h3>
              <p className="text-xs text-red-600 mb-3">
                Deactivating a class will hide it from students. Assessment and
                enrollment data will be preserved.
              </p>
              <Button
                type="button"
                variant="primary"
                size="sm"
                loading={updateClass.isPending}
                onClick={handleDeactivate}
                className="bg-red-600 hover:bg-red-700"
              >
                Deactivate class
              </Button>
            </div>
          </div>
        ) : (
          <div className="pt-6 border-t border-gray-100">
            <div className="bg-green-50 border border-green-100 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-green-700 mb-2">
                Class Deactivated
              </h3>
              <p className="text-xs text-green-600 mb-3">
                This class is currently deactivated. Students cannot see it.
                Re-activate to make it visible again.
              </p>
              <Button
                type="button"
                variant="primary"
                size="sm"
                loading={updateClass.isPending}
                onClick={handleReactivate}
                className="bg-green-600 hover:bg-green-700"
              >
                Re-activate class
              </Button>
            </div>
          </div>
        )}
      </form>
    </SlideOverPanel>
  );
}
