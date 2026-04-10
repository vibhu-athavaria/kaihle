/**
 * Unit tests for ScoreRing component.
 * Tests aria-label accuracy and mastery band color mapping.
 */
import "@testing-library/jest-dom";
import React from "react";
import { render, screen } from "@testing-library/react";
import { ScoreRing } from "../components/results/ScoreRing";

describe("ScoreRing", () => {
  test("test_score_ring_when_strong_score_then_has_correct_aria_label", () => {
    render(<ScoreRing score={0.85} />);
    const svg = screen.getByRole("img");
    expect(svg).toHaveAttribute("aria-label", "85% — Strong");
  });

  test("test_score_ring_when_developing_score_then_has_correct_aria_label", () => {
    render(<ScoreRing score={0.55} />);
    const svg = screen.getByRole("img");
    expect(svg).toHaveAttribute("aria-label", "55% — Developing");
  });

  test("test_score_ring_when_needs_work_score_then_has_correct_aria_label", () => {
    render(<ScoreRing score={0.25} />);
    const svg = screen.getByRole("img");
    expect(svg).toHaveAttribute("aria-label", "25% — Needs Work");
  });

  test("test_score_ring_when_null_score_then_aria_label_is_not_assessed", () => {
    render(<ScoreRing score={null} />);
    const svg = screen.getByRole("img");
    expect(svg).toHaveAttribute("aria-label", "Not assessed");
  });

  test("test_score_ring_when_strong_score_then_uses_green_stroke_color", () => {
    const { container } = render(<ScoreRing score={0.9} />);
    // The progress arc (second circle) should use Strong color #16a34a
    const circles = container.querySelectorAll("circle");
    // Second circle is the progress arc
    expect(circles[1]).toHaveAttribute("stroke", "#16a34a");
  });

  test("test_score_ring_when_developing_score_then_uses_amber_stroke_color", () => {
    const { container } = render(<ScoreRing score={0.5} />);
    const circles = container.querySelectorAll("circle");
    expect(circles[1]).toHaveAttribute("stroke", "#f59e0b");
  });

  test("test_score_ring_when_needs_work_score_then_uses_red_stroke_color", () => {
    const { container } = render(<ScoreRing score={0.2} />);
    const circles = container.querySelectorAll("circle");
    expect(circles[1]).toHaveAttribute("stroke", "#ef4444");
  });

  test("test_score_ring_when_null_score_then_uses_muted_stroke_color", () => {
    const { container } = render(<ScoreRing score={null} />);
    const circles = container.querySelectorAll("circle");
    expect(circles[1]).toHaveAttribute("stroke", "#9ca3af");
  });

  test("test_score_ring_when_rendered_then_contains_title_element", () => {
    const { container } = render(<ScoreRing score={0.72} />);
    const title = container.querySelector("title");
    expect(title).not.toBeNull();
    expect(title?.textContent).toBe("72% — Strong");
  });

  test("test_score_ring_when_score_is_boundary_0point4_then_label_is_developing", () => {
    render(<ScoreRing score={0.4} />);
    const svg = screen.getByRole("img");
    expect(svg).toHaveAttribute("aria-label", "40% — Developing");
  });

  test("test_score_ring_when_score_is_boundary_0point7_then_label_is_developing", () => {
    render(<ScoreRing score={0.7} />);
    const svg = screen.getByRole("img");
    expect(svg).toHaveAttribute("aria-label", "70% — Developing");
  });
});
