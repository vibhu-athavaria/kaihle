import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BottomNav } from "../components/nav/BottomNav";

describe("BottomNav", () => {
  it("applies text-brand-primary to active item label", () => {
    render(<BottomNav activeItem="progress" />);

    const progressLabel = screen.getByText("Progress");
    expect(progressLabel.className).toContain("text-brand-primary");
  });

  it("does not apply text-brand-primary to inactive items", () => {
    render(<BottomNav activeItem="progress" />);

    const homeLabel = screen.getByText("Home");
    expect(homeLabel.className).toContain("text-brand-muted");
  });

  it("applies aria-current to active item", () => {
    render(<BottomNav activeItem="study" />);

    const studyLink = screen.getByRole("link", { name: /study/i });
    expect(studyLink).toHaveAttribute("aria-current", "page");
  });

  it("has proper aria-label on nav", () => {
    render(<BottomNav />);

    expect(screen.getByLabelText(/student navigation/i)).toBeInTheDocument();
  });

  it("renders all four navigation items", () => {
    render(<BottomNav />);

    expect(screen.getByRole("link", { name: /home/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /progress/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /study/i })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /assessments/i }),
    ).toBeInTheDocument();
  });
});
