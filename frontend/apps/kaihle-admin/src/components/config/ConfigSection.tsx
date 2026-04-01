import { ReactNode } from "react";

interface ConfigSectionProps {
  title: string;
  children: ReactNode;
}

export function ConfigSection({ title, children }: ConfigSectionProps) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 mb-4">
      <h3 className="font-['Inter'] text-sm font-semibold text-gray-700 px-6 pt-5 pb-3 border-b border-gray-100">
        {title}
      </h3>
      <div>{children}</div>
    </div>
  );
}
