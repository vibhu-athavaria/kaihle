import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { DashboardLayout, GapMapCell } from "@kaihle/ui";
import { apiClient } from "@kaihle/auth";

interface GapMapData {
  class_name: string;
  subtopics: { id: string; name: string }[];
  students: { id: string; name: string }[];
  cells: {
    student_id: string;
    subtopic_id: string;
    mastery_score: number | null;
  }[];
}

export function AdminGapMapPage() {
  const { classId } = useParams<{ classId: string }>();
  const navigate = useNavigate();

  const { data, isLoading } = useQuery({
    queryKey: ["class-gap-map", classId],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/classes/${classId}/gap-map`);
      return res.data as GapMapData;
    },
    enabled: !!classId,
  });

  const getScore = (studentId: string, subtopicId: string) =>
    data?.cells.find(
      (c) => c.student_id === studentId && c.subtopic_id === subtopicId,
    )?.mastery_score ?? null;

  return (
    <DashboardLayout variant="school-admin" pageTitle="Gap Map">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2 text-sm">
          <button
            onClick={() => navigate("/school-admin/classes")}
            className="text-brand-muted font-semibold hover:text-brand-primary transition-colors"
          >
            Classes
          </button>
          <span className="text-brand-border">›</span>
          <span className="font-display font-bold text-brand-ink">
            {data?.class_name ?? "Loading…"}
          </span>
        </div>
        <span className="text-[10px] font-bold uppercase tracking-widest text-brand-muted bg-gray-100 px-3 py-1 rounded-full">
          Read only — contact teacher to update
        </span>
      </div>

      {isLoading ? (
        <div className="animate-pulse space-y-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-12 bg-role-school-border rounded" />
          ))}
        </div>
      ) : !data ? null : (
        <div className="overflow-auto">
          <table className="border-collapse">
            <thead>
              <tr>
                <th className="w-48 min-w-[12rem]" />
                {data.students.map((s) => (
                  <th
                    key={s.id}
                    className="px-1 pb-2 text-[10px] font-bold text-brand-muted text-center whitespace-nowrap max-w-[48px] overflow-hidden text-ellipsis"
                  >
                    {s.name.split(" ")[0]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.subtopics.map((sub) => (
                <tr
                  key={sub.id}
                  className="border-b border-role-school-border last:border-0"
                >
                  <td className="pr-3 py-1 text-xs text-brand-body font-semibold whitespace-nowrap">
                    {sub.name}
                  </td>
                  {data.students.map((stu) => (
                    <td key={stu.id} className="px-1 py-1 text-center">
                      <GapMapCell
                        masteryScore={getScore(stu.id, sub.id)}
                        studentName={stu.name}
                        subtopicName={sub.name}
                        display="label"
                        readOnly
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex gap-5 mt-4">
        {[
          { dotClass: "bg-brand-red", label: "Needs Work" },
          { dotClass: "bg-brand-amber", label: "Developing" },
          { dotClass: "bg-brand-green", label: "Strong" },
          { dotClass: "bg-brand-muted", label: "Not assessed" },
        ].map(({ dotClass, label }) => (
          <div
            key={label}
            className="flex items-center gap-1.5 text-[10px] text-brand-body font-semibold"
          >
            <span className={`w-2.5 h-2.5 rounded-full ${dotClass}`} />
            {label}
          </div>
        ))}
      </div>
    </DashboardLayout>
  );
}
