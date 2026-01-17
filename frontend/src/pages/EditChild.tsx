import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { http } from "@/lib/http";
import config from "../config";
import { GRADES } from "../lib/utils";

interface EditChildForm {
  full_name: string;
  age: number;
  grade: number;
  username: string;
  password?: string;
}

export const EditChild: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [loading, setLoading] = useState(false);
  const [child, setChild] = useState<any | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<EditChildForm>();

  // Load child data
  useEffect(() => {
    const storedChildren = JSON.parse(localStorage.getItem("children") || "[]");
    const foundChild = storedChildren.find(
      (c: any) => parseInt(c.id) === parseInt(id || "0")
    );

    if (foundChild) {
      setChild(foundChild);

      // Prefill form values
      setValue("full_name", foundChild.name);
      setValue("username", foundChild.username);
      setValue("age", Number(foundChild.age));
      setValue("grade", Number(foundChild.grade));
    }
  }, [id, setValue]);

  const onSubmit = async (data: EditChildForm) => {
    if (!id) return;

    setLoading(true);
    try {
      const response = await http.put(`/api/v1/students/${id}`, {
        full_name: data.full_name,
        age: data.age,
        grade_level: data.grade,
        username: data.username,
        ...(data.password ? { password: data.password } : {}),
      });

      const updatedChild = response.data;

      const children = JSON.parse(localStorage.getItem("children") || "[]");
      const updatedChildren = children.map((c: any) =>
        c.id === updatedChild.id ? updatedChild : c
      );

      localStorage.setItem("children", JSON.stringify(updatedChildren));
      localStorage.setItem("currentChild", JSON.stringify(updatedChild));

      navigate("/dashboard");
    } catch (err) {
      console.error("Failed to update child:", err);
      alert("Failed to update child profile. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (!child) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-600">Loading child data...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-blue-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-gray-900 mb-2">
              Edit Child Information
            </h2>
            <p className="text-gray-600">
              Update your child’s profile details below.
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            {/* Full Name */}
            <div>
              <label className="block mb-1 font-medium text-gray-700">
                Full Name
              </label>
              <input
                {...register("full_name", {
                  required: "Full name is required",
                })}
                type="text"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
              {errors.full_name && (
                <p className="mt-1 text-sm text-red-600">
                  {errors.full_name.message}
                </p>
              )}
            </div>

            {/* Username */}
            <div>
              <label className="block mb-1 font-medium text-gray-700">
                Username
              </label>
              <input
                {...register("username", { required: "Username is required" })}
                type="text"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
              {errors.username && (
                <p className="mt-1 text-sm text-red-600">
                  {errors.username.message}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <label className="block mb-1 font-medium text-gray-700">
                New Password
              </label>
              <input
                {...register("password")}
                type="password"
                placeholder="Leave blank to keep current password"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Age */}
            <div>
              <label className="block mb-1 font-medium text-gray-700">
                Age
              </label>
              <input
                {...register("age", {
                  required: "Age is required",
                  min: { value: 5, message: "Minimum age is 5" },
                  max: { value: 18, message: "Maximum age is 18" },
                })}
                type="number"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
              {errors.age && (
                <p className="mt-1 text-sm text-red-600">
                  {errors.age.message}
                </p>
              )}
            </div>

            {/* Grade */}
            <div>
              <label className="block mb-1 font-medium text-gray-700">
                Grade Level
              </label>
              <select
                id="grade"
                {...register("grade", {
                  required: "Grade selection is required",
                })}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg"
              >
                {GRADES.map((grade) => (
                  <option key={grade.value} value={grade.value}>
                    {grade.label}
                  </option>
                ))}
              </select>
              {errors.grade && (
                <p className="mt-1 text-sm text-red-600">
                  {errors.grade.message}
                </p>
              )}
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Updating..." : "Save Changes"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
