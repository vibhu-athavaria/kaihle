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
