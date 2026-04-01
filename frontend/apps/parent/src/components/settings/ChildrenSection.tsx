interface Child {
  id: string;
  first_name: string;
  last_name: string;
  grade: string;
  school_name: string;
}

interface ChildrenSectionProps {
  children: Child[];
}

export function ChildrenSection({ children }: ChildrenSectionProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100">
        <h2 className="font-lora text-base font-semibold text-gray-900">
          My children
        </h2>
      </div>

      {children.length === 0 ? (
        <div className="px-6 py-6 text-center">
          <p className="text-sm text-gray-400">
            No children linked to your account.
          </p>
          <p className="text-xs text-gray-400 mt-1">
            Contact your school admin to link your child's account.
          </p>
        </div>
      ) : (
        <>
          <div>
            {children.map((child, index) => (
              <div
                key={child.id}
                className={`flex items-center gap-4 px-6 py-4 border-gray-100 ${
                  index < children.length - 1 ? "border-b" : ""
                }`}
              >
                <div
                  className="w-9 h-9 rounded-full bg-amber-50 text-amber-700 font-semibold text-sm
                             flex items-center justify-center flex-shrink-0"
                  aria-hidden="true"
                >
                  {child.first_name.charAt(0).toUpperCase()}
                  {child.last_name.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900">
                    {child.first_name} {child.last_name}
                  </p>
                  <p className="text-xs text-gray-400 truncate">
                    {child.grade} · {child.school_name}
                  </p>
                </div>
              </div>
            ))}
          </div>
          <div className="px-6 py-3 bg-gray-50 border-t border-gray-100">
            <p className="text-xs text-gray-400">
              To add or remove linked children, contact your school admin.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
