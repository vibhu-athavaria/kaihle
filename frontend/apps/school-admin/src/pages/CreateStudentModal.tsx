import { useState } from "react";
import { Modal, toast } from "@kaihle/ui";
import { Eye, EyeOff } from "lucide-react";
import { useCreateUser, useGrades } from "../hooks/useSchoolAdmin";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface FormErrors {
  first_name?: string;
  last_name?: string;
  email?: string;
  username?: string;
  password?: string;
  age?: string;
  grade_id?: string;
}

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

function PasswordStrengthBar({ password }: { password: string }) {
  const { score, label } = getPasswordStrength(password);
  const colors = ["bg-gray-200", "bg-red-500", "bg-amber-500", "bg-green-600"];
  const activeColor = colors[score];

  return (
    <div className="space-y-1">
      <div className="flex gap-1">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full transition-colors ${
              i <= score ? activeColor : "bg-gray-200"
            }`}
          />
        ))}
      </div>
      <p className="text-xs text-brand-muted">
        {label} · share this password with the student
      </p>
    </div>
  );
}

export default function CreateStudentModal({ open, onOpenChange }: Props) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [age, setAge] = useState("");
  const [gradeId, setGradeId] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});

  const { data: grades = [] } = useGrades();
  const { mutateAsync: createUser, isPending } = useCreateUser();

  function validate(): FormErrors {
    const e: FormErrors = {};
    if (!firstName.trim()) e.first_name = "Required";
    if (!lastName.trim()) e.last_name = "Required";
    // Either email or username is required
    const hasEmail = email.trim().length > 0;
    const hasUsername = username.trim().length > 0;
    if (!hasEmail && !hasUsername) {
      e.email = "Either email or username is required";
    }
    if (hasEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      e.email = "Valid email required";
    }
    if (password.length < 8) e.password = "At least 8 characters";
    if (!age || isNaN(Number(age)) || Number(age) < 5 || Number(age) > 25)
      e.age = "Age between 5 and 25";
    if (!gradeId) e.grade_id = "Select a grade";
    return e;
  }

  function reset() {
    setFirstName("");
    setLastName("");
    setEmail("");
    setUsername("");
    setPassword("");
    setAge("");
    setGradeId("");
    setErrors({});
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }
    try {
      const payload: {
        first_name: string;
        last_name: string;
        email?: string;
        username?: string;
        password: string;
        role: "STUDENT";
        age: number;
        grade_id: string;
      } = {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        password,
        role: "STUDENT",
        age: Number(age),
        grade_id: gradeId,
      };
      if (email.trim()) {
        payload.email = email.trim().toLowerCase();
      }
      if (username.trim()) {
        payload.username = username.trim();
      }
      await createUser(payload);
      toast.success(`Student ${firstName} ${lastName} created`);
      reset();
      onOpenChange(false);
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? "Failed to create student";
      toast.error(msg);
    }
  }

  return (
    <Modal
      open={open}
      onOpenChange={(v) => {
        if (!v) reset();
        onOpenChange(v);
      }}
      title="New Student"
    >
      <form onSubmit={handleSubmit} className="space-y-4 p-6">
        <p className="text-sm text-brand-body -mt-2">
          Student can log in immediately with the username/email and password
          below.
        </p>

        {/* Name row */}
        <div className="flex gap-3">
          <div className="flex-1 space-y-1">
            <label className="block text-[11px] font-bold uppercase tracking-wide text-brand-ink">
              First name
            </label>
            <input
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              placeholder="Aisha"
              className="w-full px-3 py-2.5 border border-brand-border rounded-lg text-sm focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 outline-none"
            />
            {errors.first_name && (
              <p className="text-red-500 text-xs">{errors.first_name}</p>
            )}
          </div>
          <div className="flex-1 space-y-1">
            <label className="block text-[11px] font-bold uppercase tracking-wide text-brand-ink">
              Last name
            </label>
            <input
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              placeholder="Al-Rashid"
              className="w-full px-3 py-2.5 border border-brand-border rounded-lg text-sm focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 outline-none"
            />
            {errors.last_name && (
              <p className="text-red-500 text-xs">{errors.last_name}</p>
            )}
          </div>
        </div>

        {/* Username */}
        <div className="space-y-1">
          <label className="block text-[11px] font-bold uppercase tracking-wide text-brand-ink">
            Username
          </label>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="aisha.rashid"
            className="w-full px-3 py-2.5 border border-brand-border rounded-lg text-sm focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 outline-none"
          />
          <p className="text-xs text-brand-muted">
            Either username or email is required
          </p>
        </div>

        {/* Email */}
        <div className="space-y-1">
          <label className="block text-[11px] font-bold uppercase tracking-wide text-brand-ink">
            Email address <span className="text-brand-muted">(optional)</span>
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="aisha@school.edu"
            className="w-full px-3 py-2.5 border border-brand-border rounded-lg text-sm focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 outline-none"
          />
          {errors.email && (
            <p className="text-red-500 text-xs">{errors.email}</p>
          )}
        </div>

        {/* Password */}
        <div className="space-y-1">
          <label className="block text-[11px] font-bold uppercase tracking-wide text-brand-ink">
            Password
          </label>
          <div className="relative">
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Set a temporary password"
              className="w-full px-3 py-2.5 pr-10 border border-brand-border rounded-lg text-sm focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 outline-none"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-brand-muted hover:text-brand-ink"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          {password.length > 0 && <PasswordStrengthBar password={password} />}
          {errors.password && (
            <p className="text-red-500 text-xs">{errors.password}</p>
          )}
        </div>

        <hr className="border-brand-border" />

        {/* Age + Grade row */}
        <div className="flex gap-3">
          <div className="flex-1 space-y-1">
            <label className="block text-[11px] font-bold uppercase tracking-wide text-brand-ink">
              Age
            </label>
            <input
              type="number"
              value={age}
              onChange={(e) => setAge(e.target.value)}
              placeholder="13"
              min={5}
              max={25}
              className="w-full px-3 py-2.5 border border-brand-border rounded-lg text-sm focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 outline-none"
            />
            {errors.age && <p className="text-red-500 text-xs">{errors.age}</p>}
          </div>
          <div className="flex-1 space-y-1">
            <label className="block text-[11px] font-bold uppercase tracking-wide text-brand-ink">
              Grade
            </label>
            <select
              value={gradeId}
              onChange={(e) => setGradeId(e.target.value)}
              className="w-full px-3 py-2.5 border border-brand-border rounded-lg text-sm bg-white focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 outline-none"
            >
              <option value="">Select grade</option>
              {grades.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
            {errors.grade_id && (
              <p className="text-red-500 text-xs">{errors.grade_id}</p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={() => {
              reset();
              onOpenChange(false);
            }}
            className="px-5 py-2 rounded-full text-xs font-bold border border-role-school-border text-brand-ink hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isPending}
            className="px-5 py-2 rounded-full text-xs font-bold bg-brand-primary text-white hover:bg-brand-dark disabled:opacity-60 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 flex items-center gap-1.5"
          >
            {isPending ? (
              "Creating…"
            ) : (
              <>
                <svg
                  className="w-3.5 h-3.5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={3}
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                Create student
              </>
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
}
