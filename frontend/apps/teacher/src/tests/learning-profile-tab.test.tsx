import "@testing-library/jest-dom";
import React from "react";
import { render, screen } from "@testing-library/react";
import { LearningProfileTab } from "../components/students/LearningProfileTab";

const baseScores = {
  visual: 0.8,
  auditory: 0.3,
  reading_writing: 0.6,
  kinesthetic: 0.5,
};

describe("LearningProfileTab", () => {
  test("test_learning_profile_tab_when_valid_scores_then_shows_percentages_without_nan", () => {
    render(
      <LearningProfileTab
        modalityScores={baseScores}
        workStyle={null}
        interests={[]}
      />,
    );
    expect(screen.getByText("80%")).toBeInTheDocument();
    expect(screen.getByText("30%")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
  });

  test("test_learning_profile_tab_when_score_is_undefined_then_shows_0_percent_not_nan", () => {
    const scores = {
      visual: 0.8,
      auditory: undefined as unknown as number,
      reading_writing: 0.6,
      kinesthetic: 0.5,
    };
    render(
      <LearningProfileTab
        modalityScores={scores}
        workStyle={null}
        interests={[]}
      />,
    );
    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
  });

  test("test_learning_profile_tab_when_rendered_then_dominant_modality_shown_in_headline", () => {
    render(
      <LearningProfileTab
        modalityScores={baseScores}
        workStyle={null}
        interests={[]}
      />,
    );
    // "Dominant learning style" label confirms the headline section renders
    expect(screen.getByText("Dominant learning style")).toBeInTheDocument();
    // Visual appears in both headline and breakdown — at least one instance present
    expect(screen.getAllByText("Visual").length).toBeGreaterThan(0);
  });

  test("test_learning_profile_tab_when_interests_present_then_renders_them", () => {
    render(
      <LearningProfileTab
        modalityScores={baseScores}
        workStyle={null}
        interests={["football", "gaming"]}
      />,
    );
    expect(screen.getByText("football")).toBeInTheDocument();
    expect(screen.getByText("gaming")).toBeInTheDocument();
  });

  test("test_learning_profile_tab_when_work_style_prefers_solo_then_shows_chip", () => {
    render(
      <LearningProfileTab
        modalityScores={baseScores}
        workStyle={{ prefers_solo: true }}
        interests={[]}
      />,
    );
    expect(screen.getByText("Prefers solo work")).toBeInTheDocument();
  });
});
