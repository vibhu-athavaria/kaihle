/**
 * Unit tests for LearningStyleTag component.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { LearningStyleTag } from "../LearningStyleTag";

describe("LearningStyleTag", () => {
  it("renders emoji and label for visual modality", () => {
    render(<LearningStyleTag modality="visual" />);
    expect(screen.getByText("Visual")).toBeInTheDocument();
    const emoji = screen.getByText("👁");
    expect(emoji).toHaveAttribute("aria-hidden", "true");
  });

  it("renders Reading & Writing label for reading_writing modality", () => {
    render(<LearningStyleTag modality="reading_writing" />);
    expect(screen.getByText("Reading & Writing")).toBeInTheDocument();
  });

  it("renders plain dash for null modality with no pill wrapper", () => {
    const { container } = render(<LearningStyleTag modality={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(container.querySelector(".rounded-full")).toBeNull();
  });

  it("applies teacher variant colour classes", () => {
    const { container } = render(
      <LearningStyleTag modality="visual" variant="teacher" />,
    );
    expect(container.firstChild).toHaveClass("bg-amber-50", "text-amber-700");
  });

  it("applies student variant colour classes", () => {
    const { container } = render(
      <LearningStyleTag modality="visual" variant="student" />,
    );
    expect(container.firstChild).toHaveClass(
      "bg-green-50",
      "text-brand-primary",
    );
  });

  it("applies neutral variant colour classes by default", () => {
    const { container } = render(<LearningStyleTag modality="visual" />);
    expect(container.firstChild).toHaveClass("bg-gray-100", "text-gray-700");
  });

  it("renders auditory modality with correct emoji and label", () => {
    render(<LearningStyleTag modality="auditory" />);
    expect(screen.getByText("Auditory")).toBeInTheDocument();
    expect(screen.getByText("👂")).toHaveAttribute("aria-hidden", "true");
  });

  it("renders kinesthetic modality with correct emoji and label", () => {
    render(<LearningStyleTag modality="kinesthetic" />);
    expect(screen.getByText("Hands-on")).toBeInTheDocument();
    expect(screen.getByText("🤲")).toHaveAttribute("aria-hidden", "true");
  });

  it("renders sm size by default", () => {
    const { container } = render(<LearningStyleTag modality="visual" />);
    expect(container.firstChild).toHaveClass("text-xs", "px-2.5", "py-1");
  });

  it("renders md size when specified", () => {
    const { container } = render(
      <LearningStyleTag modality="visual" size="md" />,
    );
    expect(container.firstChild).toHaveClass("text-sm", "px-3", "py-1.5");
  });
});
