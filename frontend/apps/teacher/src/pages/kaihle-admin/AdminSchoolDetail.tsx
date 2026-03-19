import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { AdminLayout } from "@kaihle/ui";
import { Card, Badge, Button, Skeleton } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { useAdminSchool, useSchoolAnalytics } from "../../hooks/useKaihleAdmin";
import { AdminExtendTrialModal } from "./AdminExtendTrialModal";
import {
  ArrowLeft,
  Users,
  GraduationCap,
  ClipboardCheck,
  TrendingUp,
  Calendar,
} from "lucide-react";

function getDaysRemaining(trialEndDate: string | null): number | null {
  if (!trialEndDate) return null;
  const end = new Date(trialEndDate);
  const now = new Date();
  const diff = Math.ceil(
    (end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
  );
  return diff > 0 ? diff : 0;
}

function InfoSection({ school }: { school: any }) {
  const statusVariant =
    school.subscription_status === "ACTIVE"
      ? "success"
      : school.subscription_status === "TRIAL"
        ? "warning"
        : "danger";

  const planVariant =
    school.plan_tier === "GROWTH" || school.plan_tier === "SCALE"
      ? "success"
      : "neutral";

  return (
    <Card className="bg-white border border-role-admin-border">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-sm font-bold text-role-admin-ink">School info</h3>
        <Badge variant={statusVariant}>{school.subscription_status}</Badge>
      </div>
      <div className="grid grid-cols-2 gap-6">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-1">
            Name
          </p>
          <p className="text-sm font-semibold text-role-admin-ink">
            {school.name}
          </p>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-1">
            Slug
          </p>
          <p className="text-sm text-role-admin-subtle">{school.slug}</p>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-1">
            Country
          </p>
          <p className="text-sm text-role-admin-subtle">
            {school.country || "—"}
          </p>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-1">
            City
          </p>
          <p className="text-sm text-role-admin-subtle">{school.city || "—"}</p>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-1">
            Timezone
          </p>
          <p className="text-sm text-role-admin-subtle">{school.timezone}</p>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-1">
            Plan
          </p>
          <div className="flex items-center gap-2">
            <Badge variant={planVariant}>{school.plan_tier}</Badge>
          </div>
        </div>
      </div>
    </Card>
  );
}

function TrialSection({
  school,
  onExtend,
}: {
  school: any;
  onExtend: () => void;
}) {
  const daysRemaining = getDaysRemaining(school.trial_end_date);

  if (school.subscription_status !== "TRIAL" || !school.trial_end_date) {
    return null;
  }

  return (
    <Card className="bg-brand-amber-light border border-brand-gold-mid">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Calendar className="w-5 h-5 text-brand-amber" />
          <div>
            <p className="text-sm font-semibold text-brand-amber-dark">
              Trial expires:{" "}
              {new Date(school.trial_end_date).toLocaleDateString()}
            </p>
            <p className="text-xs text-brand-amber-dark">
              {daysRemaining} days remaining
            </p>
          </div>
        </div>
        <Button variant="secondary" size="sm" onClick={onExtend}>
          Extend trial
        </Button>
      </div>
    </Card>
  );
}

function StatsSection({
  analytics,
  loading,
}: {
  analytics: any;
  loading?: boolean;
}) {
  if (loading) {
    return (
      <Card className="bg-white border border-role-admin-border">
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="text-center">
              <Skeleton className="h-8 w-8 rounded-full mx-auto mb-2" />
              <Skeleton className="h-4 w-16 mx-auto" />
              <Skeleton className="h-3 w-12 mx-auto mt-1" />
            </div>
          ))}
        </div>
      </Card>
    );
  }

  return (
    <Card className="bg-white border border-role-admin-border">
      <h3 className="text-sm font-bold text-role-admin-ink mb-6">
        Summary stats
      </h3>
      <div className="grid grid-cols-4 gap-4">
        <div className="text-center">
          <div className="w-10 h-10 rounded-full bg-brand-light flex items-center justify-center mx-auto mb-2">
            <Users className="w-5 h-5 text-brand-primary" />
          </div>
          <p className="text-xl font-bold text-role-admin-ink">
            {analytics?.teacher_count ?? 0}
          </p>
          <p className="text-xs text-role-admin-muted">Teachers</p>
        </div>
        <div className="text-center">
          <div className="w-10 h-10 rounded-full bg-brand-light flex items-center justify-center mx-auto mb-2">
            <GraduationCap className="w-5 h-5 text-brand-primary" />
          </div>
          <p className="text-xl font-bold text-role-admin-ink">
            {analytics?.student_count ?? 0}
          </p>
          <p className="text-xs text-role-admin-muted">Students</p>
        </div>
        <div className="text-center">
          <div className="w-10 h-10 rounded-full bg-brand-light flex items-center justify-center mx-auto mb-2">
            <ClipboardCheck className="w-5 h-5 text-brand-primary" />
          </div>
          <p className="text-xl font-bold text-role-admin-ink">
            {analytics?.assessments_completed ?? 0}
          </p>
          <p className="text-xs text-role-admin-muted">Assessments</p>
        </div>
        <div className="text-center">
          <div className="w-10 h-10 rounded-full bg-brand-light flex items-center justify-center mx-auto mb-2">
            <TrendingUp className="w-5 h-5 text-brand-primary" />
          </div>
          <p className="text-xl font-bold text-role-admin-ink">
            {analytics?.avg_mastery != null
              ? Math.round(analytics.avg_mastery * 100)
              : 0}
            %
          </p>
          <p className="text-xs text-role-admin-muted">Avg mastery</p>
        </div>
      </div>
    </Card>
  );
}

export function AdminSchoolDetail() {
  const { logout } = useAuth();
  const { schoolId } = useParams<{ schoolId: string }>();
  const [showExtendModal, setShowExtendModal] = useState(false);

  const { data: school, isLoading: schoolLoading } = useAdminSchool(schoolId!);
  const { data: analytics, isLoading: analyticsLoading } = useSchoolAnalytics(
    schoolId!,
  );

  if (schoolLoading || !school) {
    return (
      <AdminLayout pageTitle="Loading..." onLogout={logout}>
        <div className="space-y-6">
          <Link
            to="/kaihle-admin/schools"
            className="inline-flex items-center gap-2 text-sm text-role-admin-subtle hover:text-role-admin-ink"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to schools
          </Link>
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout pageTitle={school.name} onLogout={logout}>
      <div className="space-y-6">
        <Link
          to="/kaihle-admin/schools"
          className="inline-flex items-center gap-2 text-sm text-role-admin-subtle hover:text-role-admin-ink"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to schools
        </Link>

        <InfoSection school={school} />

        {school.subscription_status === "TRIAL" && (
          <TrialSection
            school={school}
            onExtend={() => setShowExtendModal(true)}
          />
        )}

        <StatsSection analytics={analytics} loading={analyticsLoading} />
      </div>

      {showExtendModal && schoolId && (
        <AdminExtendTrialModal
          schoolId={schoolId}
          schoolName={school.name}
          currentTrialEnd={school.trial_end_date}
          onClose={() => setShowExtendModal(false)}
        />
      )}
    </AdminLayout>
  );
}
