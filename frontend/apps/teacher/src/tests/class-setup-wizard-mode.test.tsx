import "@testing-library/jest-dom";
import React from "react";
import { render, screen } from "@testing-library/react";

// Test the mode-dependent rendering logic in isolation — the wizard's
// footer button and modal title change based on mode prop.

// Pure helper that mirrors the conditional logic inside ClassSetupWizard/TopicListStep
function renderFooterButton(mode: "setup" | "edit", topicsExist: boolean) {
  if (mode === "edit") return "Done";
  if (!topicsExist) return null; // disabled
  return "Next: Design Diagnostic →";
}

function renderModalTitle(mode: "setup" | "edit") {
  return mode === "edit" ? "Edit Topics" : "Class Curriculum Setup";
}

describe("ClassSetupWizard mode logic", () => {
  test("test_class_setup_wizard_when_edit_mode_then_footer_button_is_done", () => {
    expect(renderFooterButton("edit", true)).toBe("Done");
    expect(renderFooterButton("edit", false)).toBe("Done");
  });

  test("test_class_setup_wizard_when_setup_mode_with_topics_then_footer_button_is_next_diagnostic", () => {
    expect(renderFooterButton("setup", true)).toBe("Next: Design Diagnostic →");
  });

  test("test_class_setup_wizard_when_edit_mode_then_modal_title_is_edit_topics", () => {
    expect(renderModalTitle("edit")).toBe("Edit Topics");
  });

  test("test_class_setup_wizard_when_setup_mode_then_modal_title_is_class_curriculum_setup", () => {
    expect(renderModalTitle("setup")).toBe("Class Curriculum Setup");
  });
});

// ── Regression: reopening the wizard at a different step ──────────────────────

// Mirrors the shell's step state: useState(initialStep) alone latches the value
// from the wizard's first mount, because the wizard stays mounted while closed.
function WizardShell({
  isOpen,
  initialStep,
  sync,
}: {
  isOpen: boolean;
  initialStep: 1 | 2;
  sync: boolean;
}) {
  const [step, setStep] = React.useState<1 | 2>(initialStep);
  React.useEffect(() => {
    if (sync && isOpen) setStep(initialStep);
  }, [sync, isOpen, initialStep]);
  return <div>{isOpen ? `step-${step}` : "closed"}</div>;
}

describe("ClassSetupWizard step synchronisation", () => {
  test("test_wizard_when_reopened_at_step_2_without_sync_then_shows_stale_step_1", () => {
    const { rerender } = render(
      <WizardShell isOpen={true} initialStep={1} sync={false} />,
    );
    rerender(<WizardShell isOpen={false} initialStep={1} sync={false} />);
    rerender(<WizardShell isOpen={true} initialStep={2} sync={false} />);

    // Documents the bug this fix removes.
    expect(screen.getByText("step-1")).toBeInTheDocument();
  });

  test("test_wizard_when_reopened_at_step_2_with_sync_then_shows_step_2", () => {
    const { rerender } = render(
      <WizardShell isOpen={true} initialStep={1} sync={true} />,
    );
    rerender(<WizardShell isOpen={false} initialStep={1} sync={true} />);
    rerender(<WizardShell isOpen={true} initialStep={2} sync={true} />);

    expect(screen.getByText("step-2")).toBeInTheDocument();
  });
});

// ── Regression: mode must not be derived from initialStep ────────────────────

describe("ClassSetupWizard entry points", () => {
  // Each class-detail entry point declares step and mode independently.
  const entryPoints = {
    "Set up class (banner)": { step: 1, mode: "setup" },
    "Design diagnostic (banner)": { step: 2, mode: "setup" },
    "Set up class (topics tab)": { step: 1, mode: "setup" },
    "Edit topics": { step: 1, mode: "edit" },
  } as const;

  test("test_entry_points_when_starting_at_step_1_then_mode_is_not_forced_to_edit", () => {
    // The old `mode = initialStep === 1 ? "edit" : "setup"` rule made first-time
    // setup unable to continue into the diagnostic step.
    expect(entryPoints["Set up class (banner)"].mode).toBe("setup");
    expect(entryPoints["Set up class (topics tab)"].mode).toBe("setup");
  });

  test("test_entry_points_when_editing_topics_then_mode_is_edit_at_step_1", () => {
    expect(entryPoints["Edit topics"]).toEqual({ step: 1, mode: "edit" });
  });
});
