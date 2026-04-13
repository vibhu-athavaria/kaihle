import { Badge } from "@kaihle/ui";

export type AssessmentStatus = "DRAFT" | "ACTIVE" | "CLOSED";

export interface Assessment {
  id: string;
  title: string;
  assessment_type: string;
  status: AssessmentStatus;
  question_count: number;
  deadline: string | null;
  created_at: string;
}

export function statusBadge(status: AssessmentStatus) {
  switch (status) {
    case "DRAFT":
      return <Badge variant="neutral">Draft</Badge>;
    case "ACTIVE":
      return <Badge variant="success">Active</Badge>;
    case "CLOSED":
      return <Badge variant="info">Closed</Badge>;
  }
}

export function typeBadge(type: string) {
  const label = type
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return <Badge variant="gold">{label}</Badge>;
}
