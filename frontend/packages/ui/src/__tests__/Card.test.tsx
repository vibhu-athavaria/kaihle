import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Card } from "../components/Card";

describe("Card", () => {
  it("renders children", () => {
    render(<Card>Card content</Card>);
    expect(screen.getByText("Card content")).toBeInTheDocument();
  });

  it("renders default variant", () => {
    render(<Card>Content</Card>);
    const card = document.querySelector(".rounded-2xl");
    expect(card).toHaveClass("bg-white");
    expect(card).toHaveClass("border-brand-border");
    expect(card).toHaveClass("shadow-card");
  });

  it("renders interactive variant", () => {
    render(<Card variant="interactive">Click me</Card>);
    const card = document.querySelector(".rounded-2xl");
    expect(card).toHaveClass("cursor-pointer");
  });

  it("renders highlighted variant", () => {
    render(<Card variant="highlighted">Highlighted</Card>);
    const card = document.querySelector(".rounded-2xl");
    expect(card).toHaveClass("bg-brand-light");
    expect(card).toHaveClass("border-brand-mid");
  });

  it("renders ghost variant", () => {
    render(<Card variant="ghost">Ghost</Card>);
    const card = document.querySelector(".rounded-2xl");
    expect(card).toHaveClass("bg-transparent");
  });

  it("handles onClick", () => {
    const handleClick = vi.fn();
    render(<Card onClick={handleClick}>Clickable</Card>);
    const card = document.querySelector(".rounded-2xl");
    card?.click();
    expect(handleClick).toHaveBeenCalled();
  });
});
