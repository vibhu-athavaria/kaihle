/**
 * Unit tests for ScoreRing component.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { ScoreRing } from "../ScoreRing";

describe("ScoreRing", () => {
  it("renders with role='img' and aria-label", () => {
    render(<ScoreRing score={0.72} />);
    expect(screen.getByRole("img")).toHaveAttribute(
      "aria-label",
      "72% — Strong",
    );
  });

  it("renders '—' and 'Not assessed' label for null score", () => {
    render(<ScoreRing score={null} />);
    expect(screen.getByRole("img")).toHaveAttribute(
      "aria-label",
      "Not assessed",
    );
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders correctly for each size", () => {
    const { rerender } = render(<ScoreRing score={0.5} size="sm" />);
    expect(document.querySelector("svg")).toHaveAttribute("width", "48");
    rerender(<ScoreRing score={0.5} size="lg" />);
    expect(document.querySelector("svg")).toHaveAttribute("width", "100");
  });

  it("renders aria-label with correct percentage for score 0.85", () => {
    render(<ScoreRing score={0.85} />);
    expect(screen.getByRole("img")).toHaveAttribute(
      "aria-label",
      "85% — Strong",
    );
  });

  it("renders correct percentage text for score 0.55 (Developing)", () => {
    render(<ScoreRing score={0.55} />);
    expect(screen.getByRole("img")).toHaveAttribute(
      "aria-label",
      "55% — Developing",
    );
  });

  it("renders correct percentage text for score 0.30 (Needs Work)", () => {
    render(<ScoreRing score={0.3} />);
    expect(screen.getByRole("img")).toHaveAttribute(
      "aria-label",
      "30% — Needs Work",
    );
  });

  it("applies motion-safe transition classes for animation", () => {
    const { container } = render(<ScoreRing score={0.72} />);
    const progressArc = container.querySelectorAll("circle")[1];
    expect(progressArc).toHaveClass(
      "motion-safe:transition-all",
      "motion-safe:duration-600",
      "motion-safe:ease-out",
    );
  });

  it("renders with custom className", () => {
    const { container } = render(
      <ScoreRing score={0.72} className="custom-class" />,
    );
    expect(container.firstChild).toHaveClass("custom-class");
  });
});
