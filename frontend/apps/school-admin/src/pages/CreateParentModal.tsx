import { useState, useMemo } from "react";
import { Modal, toast } from "@kaihle/ui";
import { Search } from "lucide-react";
import { useCreateUser, useSchoolStudents } from "../hooks/useSchoolAdmin";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface FormErrors {
  first_name?: string;
  last_name?: string;
  email?: string;
  password?: string;
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
        {label} · parent will be prompted to change this on first login
      </p>
    </div>
  );
}

export default function CreateParentModal({ open, onOpenChange }: Props) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [studentSearch, setStudentSearch] = useState("");
  const [selectedStudentIds, setSelectedStudentIds] = useState<string[]>([]);
  const [errors, setErrors] = useState<FormErrors>({});

  const { data: allStudents = [] } = useSchoolStudents();
  const { mutateAsync: createUser, isPending } = useCreateUser();

  const filteredStudents = useMemo(
    () =>
      allStudents.filter((s) =>
        `${s.first_name} ${s.last_name}`
          .toLowerCase()
          .includes(studentSearch.toLowerCase()),
      ),
    [allStudents, studentSearch],
  );

  function toggleStudent(id: string) {
    setSelectedStudentIds((prev) =>
      prev.includes(id) ? prev.filter((sid) => sid !== id) : [...prev, id],
    );
  }

  function validate(): FormErrors {
    const e: FormErrors = {};
    if (!firstName.trim()) e.first_name = "Required";
    if (!lastName.trim()) e.last_name = "Required";
    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      e.email = "Valid email required";
    if (password.length < 8) e.password = "At least 8 characters";
    return e;
  }

  function reset() {
    setFirstName("");
    setLastName("");
    setEmail("");
    setPassword("");
    setStudentSearch("");
    setSelectedStudentIds([]);
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
      await createUser({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim().toLowerCase(),
        password,
        role: "PARENT",
        student_ids:
          selectedStudentIds.length > 0 ? selectedStudentIds : undefined,
      });
      toast.success(`Parent ${firstName} ${lastName} created`);
      reset();
      onOpenChange(false);
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? "Failed to create parent";
      toast.error(msg);
    }
  }

  const selectedStudents = allStudents.filter((s) =>
    selectedStudentIds.includes(s.id),
  );

  return (
    <Modal
      open={open}
      onOpenChange={(v) => {
        if (!v) reset();
        onOpenChange(v);
      }}
      title="New Parent"
    >
      <form onSubmit={handleSubmit} className="space-y-4 p-6">
        <p className="text-sm text-brand-body -mt-2">
          Parent can log in immediately and will be prompted to change their
          password on first login.
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
              placeholder="James"
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

        {/* Email */}
        <div className="space-y-1">
          <label className="block text-[11px] font-bold uppercase tracking-wide text-brand-ink">
            Email address
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="james@gmail.com"
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
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Set a temporary password"
            className="w-full px-3 py-2.5 border border-brand-border rounded-lg text-sm focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 outline-none"
          />
          {password.length > 0 && <PasswordStrengthBar password={password} />}
          {errors.password && (
            <p className="text-red-500 text-xs">{errors.password}</p>
          )}
        </div>

        <hr className="border-brand-border" />

        {/* Student search — optional */}
        <div className="space-y-2">
          <label className="block text-[11px] font-bold uppercase tracking-wide text-brand-ink">
            Link to student(s){" "}
            <span className="normal-case font-normal text-brand-muted text-xs tracking-normal">
              — optional
            </span>
          </label>
          <div className="relative">
            <Search
              aria-hidden="true"
              className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-brand-muted"
            />
            <input
              value={studentSearch}
              onChange={(e) => setStudentSearch(e.target.value)}
              placeholder="Search by student name…"
              className="w-full pl-8 pr-3 py-2.5 border border-brand-border rounded-lg text-sm focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 outline-none"
            />
          </div>
          {filteredStudents.length > 0 && (
            <div className="border border-brand-border rounded-lg max-h-36 overflow-y-auto">
              {filteredStudents.map((s) => (
                <label
                  key={s.id}
                  className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer border-b border-brand-border last:border-b-0"
                >
                  <input
                    type="checkbox"
                    checked={selectedStudentIds.includes(s.id)}
                    onChange={() => toggleStudent(s.id)}
                    className="accent-brand-primary"
                  />
                  <div>
                    <p className="text-sm font-semibold text-brand-ink">
                      {s.first_name} {s.last_name}
                    </p>
                    {s.class_count > 0 && (
                      <p className="text-xs text-brand-muted">
                        {s.class_count} classes
                      </p>
                    )}
                  </div>
                </label>
              ))}
            </div>
          )}
          {selectedStudents.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-1">
              {selectedStudents.map((s) => (
                <span
                  key={s.id}
                  className="inline-flex items-center gap-1.5 bg-green-50 text-green-700 rounded-full text-xs font-semibold px-3 py-1"
                >
                  {s.first_name} {s.last_name}
                  <button
                    type="button"
                    onClick={() => toggleStudent(s.id)}
                    className="opacity-50 hover:opacity-100 text-sm leading-none"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
          <p className="text-xs text-brand-muted">
            You can link students later from the parent&apos;s profile
          </p>
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
                Create parent
              </>
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
}
