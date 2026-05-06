// M4 stub — lesson plan endpoint not yet implemented.
// Shows empty state UI. Never throws. Will be wired to real data in M4.
export function AllLessonPlansPage() {
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Lesson Plans
        </h1>
        <button
          type="button"
          disabled
          className="bg-brand-gold text-white text-xs font-bold px-4 py-2 rounded-full opacity-50 cursor-not-allowed"
          title="Coming soon"
        >
          + New Lesson Plan
        </button>
      </div>

      <div className="bg-white rounded-2xl border border-brand-border p-12 text-center">
        <div className="text-4xl mb-4" role="img" aria-label="lesson plans">
          📋
        </div>
        <h3 className="font-display font-semibold text-lg text-brand-ink mb-2">
          No lesson plans yet
        </h3>
        <p className="text-sm text-brand-muted max-w-sm mx-auto mb-4">
          Create a lesson plan for any topic your class is studying. Each plan
          gives you a structured teaching guide — and students automatically get
          a matching study plan.
        </p>
        <p className="text-sm text-brand-muted max-w-sm mx-auto">
          Lesson plan creation is coming soon.
        </p>
      </div>
    </div>
  );
}
